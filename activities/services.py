"""
Servicios de activities (equivalen a CRUDActividad, CRUDEvidencia y CRUDValidacion del diagrama
de clases). Flujo del PDF (4.1): ingreso -> código -> evidencia -> revisión -> resultado.

Resultado: solo una actividad en estado "Validada" aporta al avance (RN-009). Cada decisión del
verificador recalcula los indicadores mediante measurement.CalculoIndicadores.recalcular_para.
"""
import hashlib
import json
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_VALIDACION, ROL_CONSULTA, ROL_DELEGADO, ROL_VERIFICADOR,
    auditar, es_transversal, get_funcionario, tiene_rol,
)
from core.services import guardar, snapshot
from catalogs.models import Catalogo
from measurement.models import Periodo
from measurement.services import CalculoIndicadores

from .models import Actividad, Evidencia, Validacion

TIPOS_CATALOGO_ACTIVIDAD = (Catalogo.TIPO_ACTIVIDAD, Catalogo.TIPO_SERVICIO)

# Firmas ("magic numbers") para no confiar solo en la extensión del archivo (RNF-017)
FIRMAS_ARCHIVO = {
    "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",), "pdf": (b"%PDF-",),
}
CODIGO_RE = re.compile(r"^ACT-(\d+)(?:-E(\d+))?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Visibilidad (ámbito por rol y delegación, CA-07)
# ---------------------------------------------------------------------------
def actividades_visibles(user):
    """Funcionario: solo las suyas. Delegado/Verificador/Consulta: su delegación. Admin/Coord: todas."""
    qs = Actividad.objects.select_related("funcionario", "item", "catalogo", "periodo")
    funcionario = get_funcionario(user)
    if es_transversal(user):
        return qs
    if funcionario is None:
        return qs.none()
    if tiene_rol(user, ROL_DELEGADO, ROL_VERIFICADOR, ROL_CONSULTA):
        return qs.filter(funcionario__delegacion_id=funcionario.delegacion_id)
    return qs.filter(funcionario=funcionario)


def evidencias_visibles(user):
    return Evidencia.objects.select_related("actividad", "actividad__funcionario", "actividad__item") \
        .filter(actividad__in=actividades_visibles(user).values("pk"))


def _exigir_autor(actividad, actor):
    funcionario = get_funcionario(actor)
    if funcionario is None or funcionario.pk != actividad.funcionario_id:
        raise ReglaNegocioError("Solo el funcionario que registró la actividad puede realizar esta acción.")
    return funcionario


def _exigir_periodo_abierto(periodo_id, accion="modificar"):
    periodo = Periodo.objects.get(pk=periodo_id)
    if not periodo.abierto:
        raise ReglaNegocioError(f"El período {periodo} está cerrado: no se puede {accion}.")


def _recalcular_indicadores(*actividades):
    for a in {(x.funcionario_id, x.item_id, x.periodo_id) for x in actividades}:
        CalculoIndicadores.recalcular_para(*a)


def _recalcular_estado(actividad):
    """
    Estado de la actividad según sus evidencias: con alguna pendiente está 'En revisión';
    si todas están revisadas, manda la última decisión del verificador.
    """
    if actividad.estado == Actividad.ESTADO_ANULADA:
        return
    evidencias = list(actividad.evidencias.all())
    if not evidencias:
        nuevo = Actividad.ESTADO_REGISTRADA if actividad.estado == Actividad.ESTADO_EN_REVISION else actividad.estado
    elif any(e.estado_revision == Evidencia.ESTADO_PENDIENTE for e in evidencias):
        nuevo = Actividad.ESTADO_EN_REVISION
    else:
        ultima = Validacion.objects.filter(evidencia__actividad=actividad) \
            .order_by("-fecha", "-id_validacion").first()
        nuevo = {Validacion.DECISION_APROBADA: Actividad.ESTADO_VALIDADA,
                 Validacion.DECISION_RECHAZADA: Actividad.ESTADO_RECHAZADA,
                 Validacion.DECISION_CORRECCION: Actividad.ESTADO_CORRECCION}[ultima.decision]
    if nuevo != actividad.estado:
        actividad.estado = nuevo
        actividad.save(update_fields=["estado"])


# ---------------------------------------------------------------------------
# CRUDActividad (RF-009, RF-010, HU-01)
# ---------------------------------------------------------------------------
class CRUDActividad:
    @staticmethod
    def validar_campos_actividad(actividad, original=None):
        """Obligatoriedad, formatos y coherencia (RF-010). Asigna el período según la fecha."""
        if not actividad.fecha:
            raise ReglaNegocioError("La fecha es obligatoria.")
        if actividad.fecha > timezone.localdate():
            raise ReglaNegocioError("La fecha de la actividad no puede ser futura.")
        periodo = Periodo.objects.para_fecha(actividad.fecha)
        if periodo is None:
            raise ReglaNegocioError("No existe un período de medición para esa fecha.")
        if not periodo.abierto:
            raise ReglaNegocioError(f"El período {periodo} está cerrado: no se pueden registrar actividades.")
        funcionario = actividad.funcionario
        if not funcionario.activo:
            raise ReglaNegocioError("El funcionario está inactivo.")
        if actividad.item.cargo_id != funcionario.cargo_id:
            raise ReglaNegocioError("El ítem no corresponde al cargo del funcionario.")
        cambia_item = original is None or original.item_id != actividad.item_id
        cambia_catalogo = original is None or original.catalogo_id != actividad.catalogo_id
        if cambia_item and not actividad.item.vigencia:
            raise ReglaNegocioError("El ítem medible no está vigente.")
        if cambia_catalogo:
            if not actividad.catalogo.activo:
                raise ReglaNegocioError("El elemento de catálogo está desactivado.")
            if actividad.catalogo.tipo_catalogo not in TIPOS_CATALOGO_ACTIVIDAD:
                raise ReglaNegocioError("El catálogo debe ser de tipo Actividad o Servicio.")
        actividad.periodo = periodo
        return periodo

    @staticmethod
    def crear_actividad(actividad, actor=None):
        with transaction.atomic():
            actividad.estado = Actividad.ESTADO_REGISTRADA
            CRUDActividad.validar_campos_actividad(actividad)
            guardar(actividad, actor, "actividad")
        return actividad

    @staticmethod
    def mostrar_actividades_por_funcionario(funcionario, periodo=None):
        qs = Actividad.objects.filter(funcionario=funcionario).select_related("item", "catalogo", "periodo")
        return qs.filter(periodo=periodo) if periodo else qs

    @staticmethod
    def buscar_actividad_id(id_actividad):
        return Actividad.objects.filter(pk=id_actividad).first()

    @staticmethod
    def modificar_actividad(actividad, actor=None):
        original = Actividad.objects.get(pk=actividad.pk)
        _exigir_autor(original, actor)
        if not original.editable:
            raise ReglaNegocioError(f"Una actividad en estado «{original.estado}» no puede modificarse.")
        with transaction.atomic():
            CRUDActividad.validar_campos_actividad(actividad, original)
            guardar(actividad, actor, "actividad")
        return actividad

    @staticmethod
    def anular_actividad(actividad, motivo, actor=None):
        """Anula el registro: deja de aportar al avance (RF-022, RN-009). Conserva su historial."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la anulación.")
        with transaction.atomic():
            actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
            if actividad.estado == Actividad.ESTADO_ANULADA:
                raise ReglaNegocioError("La actividad ya está anulada.")
            _exigir_periodo_abierto(actividad.periodo_id, "anular actividades")
            anterior = snapshot(actividad)
            actividad.estado = Actividad.ESTADO_ANULADA
            actividad.save(update_fields=["estado"])
            auditar(actor, "ANULAR_ACTIVIDAD", "actividad", actividad.pk, anterior,
                    json.dumps({"motivo": motivo, "estado": actividad.estado}, ensure_ascii=False))
            _recalcular_indicadores(actividad)
        return actividad


# ---------------------------------------------------------------------------
# CRUDEvidencia (RF-011, RF-012, HU-09, HU-10)
# ---------------------------------------------------------------------------
class CRUDEvidencia:
    @staticmethod
    def generar_codigo_evidencia(actividad):
        """ACT-0000123-E01, -E02... (se debe llamar con la actividad bloqueada)."""
        return f"{actividad.codigo}-E{actividad.evidencias.count() + 1:02d}"

    @staticmethod
    def validar_formato_archivo(archivo):
        """Valida extensión, tamaño y firma real del archivo. Devuelve los metadatos (RNF-017)."""
        nombre = getattr(archivo, "name", "") or ""
        extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        permitidas = [e.lower() for e in settings.SGR_EVIDENCIA_EXTENSIONES]
        if extension not in permitidas:
            raise ReglaNegocioError(f"Formato no permitido. Use: {', '.join(permitidas)}.")
        maximo = settings.SGR_EVIDENCIA_MAX_MB * 1024 * 1024
        if archivo.size > maximo:
            raise ReglaNegocioError(f"El archivo supera el máximo de {settings.SGR_EVIDENCIA_MAX_MB} MB.")
        if archivo.size == 0:
            raise ReglaNegocioError("El archivo está vacío.")
        archivo.seek(0)
        cabecera = archivo.read(16)
        if not any(cabecera.startswith(f) for f in FIRMAS_ARCHIVO.get(extension, ())):
            raise ReglaNegocioError("El contenido del archivo no corresponde a su extensión.")
        sha = hashlib.sha256()
        archivo.seek(0)
        for bloque in iter(lambda: archivo.read(65536), b""):
            sha.update(bloque)
        archivo.seek(0)
        # Punto de extensión: aquí se conectaría un antivirus (p. ej. ClamAV) en producción.
        return {"nombre_original": nombre[:150], "extension": extension, "tamano_bytes": archivo.size,
                "content_type": getattr(archivo, "content_type", "") or "", "sha256": sha.hexdigest()}

    @staticmethod
    def adjuntar_evidencia(actividad, archivo, actor=None):
        """Vincula el archivo al código de la actividad; la actividad pasa a 'En revisión'."""
        funcionario = get_funcionario(actor)
        metadatos = CRUDEvidencia.validar_formato_archivo(archivo)
        evidencia = None
        try:
            with transaction.atomic():
                actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
                _exigir_autor(actividad, actor)
                if not actividad.admite_evidencia:
                    raise ReglaNegocioError(
                        f"Una actividad en estado «{actividad.estado}» no admite nuevas evidencias.")
                _exigir_periodo_abierto(actividad.periodo_id, "adjuntar evidencias")
                evidencia = Evidencia(
                    actividad=actividad, funcionario=funcionario, archivo_vinculo=archivo, metadatos=metadatos,
                    codigo_evidencia=CRUDEvidencia.generar_codigo_evidencia(actividad),
                    estado_revision=Evidencia.ESTADO_PENDIENTE)
                guardar(evidencia, actor, "evidencia")
                _recalcular_estado(actividad)
                _recalcular_indicadores(actividad)
        except Exception:
            if evidencia is not None and evidencia.archivo_vinculo and evidencia.archivo_vinculo.name:
                evidencia.archivo_vinculo.storage.delete(evidencia.archivo_vinculo.name)   # sin archivos huérfanos
            raise
        return evidencia

    @staticmethod
    def mostrar_evidencia_por_actividad(actividad):
        return actividad.evidencias.prefetch_related("validaciones")


# ---------------------------------------------------------------------------
# CRUDValidacion (RF-013, RF-014, HU-11)
# ---------------------------------------------------------------------------
class CRUDValidacion:
    @staticmethod
    def _decidir(evidencia, decision, observacion, actor):
        observacion = (observacion or "").strip()
        if not tiene_rol(actor, *ROLES_VALIDACION):
            raise ReglaNegocioError("No tiene el rol de verificador.")
        verificador = get_funcionario(actor)
        if verificador is None:
            raise ReglaNegocioError("Su usuario no tiene un funcionario asociado.")
        if decision != Validacion.DECISION_APROBADA and not observacion:
            raise ReglaNegocioError("Debe registrar una observación para rechazar o solicitar corrección.")

        with transaction.atomic():
            evidencia = Evidencia.objects.select_for_update().get(pk=evidencia.pk)
            if not evidencias_visibles(actor).filter(pk=evidencia.pk).exists():
                raise ReglaNegocioError("La evidencia está fuera de su ámbito.")
            actividad = Actividad.objects.select_for_update().get(pk=evidencia.actividad_id)
            if verificador.pk == actividad.funcionario_id:
                raise ReglaNegocioError("No puede validar sus propias actividades (segregación de funciones).")
            if actividad.estado == Actividad.ESTADO_ANULADA:
                raise ReglaNegocioError("La actividad está anulada.")
            _exigir_periodo_abierto(actividad.periodo_id, "validar evidencias")

            version = evidencia.validaciones.count() + 1
            anterior = evidencia.estado_revision
            Validacion.objects.create(evidencia=evidencia, funcionario=verificador, decision=decision,
                                      observacion=observacion, version=version)
            evidencia.estado_revision = decision
            evidencia.save(update_fields=["estado_revision"])
            estado_anterior_actividad = actividad.estado
            _recalcular_estado(actividad)
            auditar(actor, "VALIDAR_EVIDENCIA", "evidencia", evidencia.pk,
                    json.dumps({"estado_revision": anterior, "estado_actividad": estado_anterior_actividad}),
                    json.dumps({"decision": decision, "version": version, "observacion": observacion,
                                "estado_actividad": actividad.estado}, ensure_ascii=False))
            _recalcular_indicadores(actividad)
        return evidencia

    @staticmethod
    def aprobar_evidencia(evidencia, observacion="", actor=None):
        return CRUDValidacion._decidir(evidencia, Validacion.DECISION_APROBADA, observacion, actor)

    @staticmethod
    def rechazar_evidencia(evidencia, observacion, actor=None):
        return CRUDValidacion._decidir(evidencia, Validacion.DECISION_RECHAZADA, observacion, actor)

    @staticmethod
    def solicitar_correccion(evidencia, observacion, actor=None):
        return CRUDValidacion._decidir(evidencia, Validacion.DECISION_CORRECCION, observacion, actor)

    @staticmethod
    def mostrar_historial_validacion(codigo_evidencia):
        return Validacion.objects.filter(evidencia__codigo_evidencia=codigo_evidencia) \
            .select_related("funcionario").order_by("version")


# ---------------------------------------------------------------------------
# Búsqueda por código (HU-10)
# ---------------------------------------------------------------------------
def buscar_por_codigo(codigo, user):
    """Devuelve la actividad asociada a un código (de actividad o de evidencia) si el usuario puede verla."""
    coincidencia = CODIGO_RE.match((codigo or "").strip())
    if not coincidencia:
        return None
    return actividades_visibles(user).filter(pk=int(coincidencia.group(1))).first()
