"""
Servicios de agenda (equivalen a CRUDCompromiso y CRUDHistorialTransiciones del diagrama de clases).

Flujo del PDF (4.2): registrar compromiso -> definir solicitante, territorio, responsable, fecha
y área de apoyo -> actualizar estado -> registrar observaciones -> consolidar porcentajes.

Un compromiso "Realizado" asociado a un ítem medible alimenta el indicador individual una sola vez
(measurement.CalculoIndicadores.recalcular_para se llama al entrar o salir de ese estado).
"""
import json
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_SUPERVISION, auditar, es_transversal, get_funcionario, tiene_rol, filtrar_por_ambito,
)
from core.services import guardar, snapshot
from measurement.models import Periodo
from measurement.services import CalculoIndicadores
from organizations.models import Funcionario

from .models import Compromiso, HistorialTransiciones


# ---------------------------------------------------------------------------
# Visibilidad y permisos (CA-07)
# ---------------------------------------------------------------------------
def compromisos_visibles(user):
    """Agenda colectiva: todo el equipo de la delegación la ve; Administrador/Coordinador ven todas."""
    qs = Compromiso.objects.select_related("funcionario", "delegacion", "item_medible", "periodo")
    return filtrar_por_ambito(qs, user, "delegacion_id")


def _es_responsable(actor, compromiso):
    f = get_funcionario(actor)
    return f is not None and f.pk == compromiso.funcionario_id


def supervisa(actor, delegacion_id):
    """Rol de supervisión dentro del ámbito (Delegado de esa delegación, Administrador, Coordinador)."""
    if not tiene_rol(actor, *ROLES_SUPERVISION):
        return False
    if es_transversal(actor):
        return True
    f = get_funcionario(actor)
    return f is not None and f.delegacion_id == delegacion_id


def puede_gestionar(actor, compromiso):
    return _es_responsable(actor, compromiso) or supervisa(actor, compromiso.delegacion_id)


def funcionarios_asignables(actor):
    """Responsables que el usuario puede elegir: él mismo, o su equipo si supervisa."""
    activos = Funcionario.objects.filter(estado=Funcionario.ESTADO_ACTIVO).select_related("cargo", "delegacion")
    f = get_funcionario(actor)
    if f is None:
        return activos.none()
    if es_transversal(actor):
        return activos
    if tiene_rol(actor, *ROLES_SUPERVISION):
        return activos.filter(delegacion_id=f.delegacion_id)
    return activos.filter(pk=f.pk)


def _validar_item(compromiso):
    item = compromiso.item_medible
    if item is not None and item.cargo_id != compromiso.funcionario.cargo_id:
        raise ReglaNegocioError("El ítem medible no corresponde al cargo del responsable.")


def _periodo_cerrado_con_item(compromiso):
    """Un compromiso con ítem en un período cerrado no puede alterar resultados (RN-013)."""
    if compromiso.item_medible_id and compromiso.periodo_id:
        return not Periodo.objects.get(pk=compromiso.periodo_id).abierto
    return False


def _recalcular(compromiso):
    if compromiso.item_medible_id and compromiso.periodo_id:
        CalculoIndicadores.recalcular_para(compromiso.funcionario_id, compromiso.item_medible_id,
                                           compromiso.periodo_id)


# ---------------------------------------------------------------------------
# CRUDHistorialTransiciones (RF-018)
# ---------------------------------------------------------------------------
class CRUDHistorialTransiciones:
    @staticmethod
    def registrar_cambio_estado(compromiso, estado_anterior, estado_nuevo, observacion="", funcionario=None):
        return HistorialTransiciones.objects.create(
            compromiso=compromiso, estado_anterior=estado_anterior, estado_nuevo=estado_nuevo,
            observacion=(observacion or "").strip(), funcionario=funcionario)

    @staticmethod
    def mostrar_historial_por_compromiso(id_compromiso):
        return HistorialTransiciones.objects.filter(compromiso_id=id_compromiso).select_related("funcionario")


# ---------------------------------------------------------------------------
# CRUDCompromiso (RF-016 a RF-021, HU-02, HU-12 a HU-15)
# ---------------------------------------------------------------------------
class CRUDCompromiso:
    @staticmethod
    def crear_compromiso(compromiso, actor=None):
        creador = get_funcionario(actor)
        if creador is None:
            raise ReglaNegocioError("Su usuario no tiene un funcionario asociado.")
        responsable = compromiso.funcionario
        if not funcionarios_asignables(actor).filter(pk=responsable.pk).exists():
            raise ReglaNegocioError("No puede asignar compromisos a ese funcionario.")
        if compromiso.fecha_comprometida < timezone.localdate():
            raise ReglaNegocioError("La fecha comprometida no puede estar en el pasado.")
        _validar_item(compromiso)
        with transaction.atomic():
            compromiso.estado = Compromiso.ESTADO_INGRESADO
            compromiso.delegacion_id = responsable.delegacion_id
            compromiso.periodo = Periodo.objects.para_fecha(compromiso.fecha_comprometida)
            guardar(compromiso, actor, "compromiso")
            CRUDHistorialTransiciones.registrar_cambio_estado(
                compromiso, "", Compromiso.ESTADO_INGRESADO, "Compromiso registrado.", creador)
        return compromiso

    @staticmethod
    def mostrar_compromisos_por_delegacion(delegacion):
        return Compromiso.objects.filter(delegacion=delegacion).select_related("funcionario", "item_medible")

    @staticmethod
    def modificar_compromiso(compromiso, actor=None):
        original = Compromiso.objects.get(pk=compromiso.pk)
        if not puede_gestionar(actor, original):
            raise ReglaNegocioError("No tiene permiso para modificar este compromiso.")
        if original.realizado:
            raise ReglaNegocioError("Un compromiso realizado no puede modificarse.")
        if compromiso.funcionario_id != original.funcionario_id:
            raise ReglaNegocioError("Para cambiar el responsable use la opción «Reasignar».")
        _validar_item(compromiso)
        cambia_fecha = compromiso.fecha_comprometida != original.fecha_comprometida
        if cambia_fecha:
            if compromiso.fecha_comprometida < timezone.localdate():
                raise ReglaNegocioError("La nueva fecha comprometida no puede estar en el pasado.")
            if not (compromiso.observacion or "").strip() or compromiso.observacion == original.observacion:
                raise ReglaNegocioError("Indique en la observación el motivo del cambio de fecha.")
        with transaction.atomic():
            compromiso.periodo = Periodo.objects.para_fecha(compromiso.fecha_comprometida)
            guardar(compromiso, actor, "compromiso")
            if cambia_fecha:
                CRUDHistorialTransiciones.registrar_cambio_estado(
                    compromiso, original.estado, original.estado,
                    f"Fecha reprogramada del {original.fecha_comprometida:%d/%m/%Y} al "
                    f"{compromiso.fecha_comprometida:%d/%m/%Y}. {compromiso.observacion}".strip(),
                    get_funcionario(actor))
        return compromiso

    @staticmethod
    def actualizar_estado(compromiso, nuevo_estado, observacion="", actor=None):
        """Transición controlada (RF-018). Conserva estado anterior, nuevo, autor, fecha y observación."""
        observacion = (observacion or "").strip()
        autor = get_funcionario(actor)
        with transaction.atomic():
            c = Compromiso.objects.select_for_update().get(pk=compromiso.pk)
            if not puede_gestionar(actor, c):
                raise ReglaNegocioError("No tiene permiso para cambiar el estado de este compromiso.")
            anterior = c.estado
            if nuevo_estado == anterior:
                raise ReglaNegocioError(f"El compromiso ya está en estado «{anterior}».")
            if nuevo_estado not in Compromiso.TRANSICIONES.get(anterior, ()):
                raise ReglaNegocioError(f"Transición no permitida: de «{anterior}» a «{nuevo_estado}».")
            if nuevo_estado == Compromiso.ESTADO_PENDIENTE and not observacion:
                raise ReglaNegocioError("Indique en la observación por qué queda pendiente.")
            if anterior == Compromiso.ESTADO_REALIZADO:
                if not supervisa(actor, c.delegacion_id):
                    raise ReglaNegocioError("Solo la supervisión puede reabrir un compromiso realizado.")
                if not observacion:
                    raise ReglaNegocioError("Indique el motivo de la reapertura.")
            if nuevo_estado == Compromiso.ESTADO_REALIZADO and c.periodo_id is None:
                c.periodo = Periodo.objects.para_fecha(c.fecha_comprometida)
            toca_resultados = Compromiso.ESTADO_REALIZADO in (anterior, nuevo_estado)
            if toca_resultados and _periodo_cerrado_con_item(c):
                raise ReglaNegocioError("El período está cerrado: el compromiso no puede alterar sus resultados.")

            c.estado = nuevo_estado
            if observacion:
                c.observacion = observacion
            c.save(update_fields=["estado", "observacion", "periodo"])
            CRUDHistorialTransiciones.registrar_cambio_estado(c, anterior, nuevo_estado, observacion, autor)
            auditar(actor, "CAMBIO_ESTADO_COMPROMISO", "compromiso", c.pk, anterior,
                    json.dumps({"estado": nuevo_estado, "observacion": observacion}, ensure_ascii=False))
            if toca_resultados:
                _recalcular(c)
        return c

    @staticmethod
    def reasignar_responsable(compromiso, nuevo_responsable, motivo, actor=None):
        """Continuidad operativa (HU-15): conserva responsable anterior, nuevo, autor, fecha y motivo."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la reasignación.")
        with transaction.atomic():
            c = Compromiso.objects.select_for_update().get(pk=compromiso.pk)
            if not supervisa(actor, c.delegacion_id):
                raise ReglaNegocioError("Solo la supervisión puede reasignar compromisos.")
            if c.realizado:
                raise ReglaNegocioError("No se puede reasignar un compromiso realizado.")
            if nuevo_responsable.pk == c.funcionario_id:
                raise ReglaNegocioError("El compromiso ya está asignado a ese funcionario.")
            if not funcionarios_asignables(actor).filter(pk=nuevo_responsable.pk).exists():
                raise ReglaNegocioError("No puede reasignar a ese funcionario.")
            anterior = c.funcionario
            anterior_snapshot = snapshot(c)
            c.funcionario = nuevo_responsable
            c.delegacion_id = nuevo_responsable.delegacion_id
            _validar_item(c)
            c.save(update_fields=["funcionario", "delegacion"])
            CRUDHistorialTransiciones.registrar_cambio_estado(
                c, c.estado, c.estado,
                f"Reasignado de {anterior.nombre} a {nuevo_responsable.nombre}. Motivo: {motivo}",
                get_funcionario(actor))
            auditar(actor, "REASIGNAR_COMPROMISO", "compromiso", c.pk, anterior_snapshot, snapshot(c))
        return c

    @staticmethod
    def controlar_plazos(delegacion=None, queryset=None, hoy=None):
        """Próximos a vencer, vencidos y realizados fuera de plazo (RF-019)."""
        hoy = hoy or timezone.localdate()
        qs = Compromiso.objects.all() if queryset is None else queryset
        if delegacion is not None:
            qs = qs.filter(delegacion=delegacion)
        dias = settings.SGR_DIAS_ALERTA_VENCIMIENTO
        realizados = qs.filter(estado=Compromiso.ESTADO_REALIZADO).prefetch_related("historial")
        return {
            "vencidos": qs.vencidos(hoy),
            "por_vencer": qs.por_vencer(hoy, dias),
            "realizados_fuera_de_plazo": [c for c in realizados if c.plazo == Compromiso.PLAZO_REALIZADO_FUERA],
            "dias_alerta": dias,
        }

    @staticmethod
    def resumen_colectivo(queryset):
        """
        Totales por funcionario y estado, con % realizado y % pendiente (RF-021).
        Sale del mismo queryset del detalle, por lo que los totales siempre coinciden (CA-06).
        """
        estados = [e for e, _ in Compromiso.ESTADOS]
        filas = defaultdict(lambda: dict.fromkeys(estados, 0))
        nombres = {}
        for c in queryset.values("funcionario_id", "funcionario__nombre", "estado"):
            filas[c["funcionario_id"]][c["estado"]] += 1
            nombres[c["funcionario_id"]] = c["funcionario__nombre"]

        def armar(nombre, conteo):
            total = sum(conteo.values())
            realizados = conteo[Compromiso.ESTADO_REALIZADO]
            pct = lambda n: (Decimal(n) / Decimal(total) * 100).quantize(Decimal("0.01")) if total else Decimal("0.00")
            return {"nombre": nombre, "por_estado": conteo, "total": total, "realizados": realizados,
                    "pct_realizado": pct(realizados), "pct_pendiente": pct(total - realizados) if total else Decimal("0.00")}

        resumen = [armar(nombres[pk], conteo) for pk, conteo in sorted(filas.items(), key=lambda x: nombres[x[0]])]
        total_estados = {e: sum(f["por_estado"][e] for f in resumen) for e in estados}
        return {"filas": resumen, "estados": estados, "total": armar("Total", total_estados)}
