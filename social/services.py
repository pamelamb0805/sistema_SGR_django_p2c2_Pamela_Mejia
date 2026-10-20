"""
Servicios de social (equivalen a CRUDUsuarioSocial y CRUDAtencionSocial del diagrama de clases).

Reglas: hasta 3 gestiones por persona (RN-012), con tipo diferenciado y fechas en orden
cronológico; no se duplica la identificación principal del usuario; las estadísticas cuentan
cada gestión realizada una sola vez (HU-03).
"""
import json

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROL_DELEGADO, ROLES_OPERATIVOS, ROLES_TRANSVERSALES, auditar, es_transversal, get_funcionario, tiene_rol,
)
from core.services import guardar, snapshot

from .models import AtencionSocial, UsuarioSocial

# Acceso al módulo: datos personales de usuarios atendidos => solo quienes los necesitan (RNF-009)
ROLES_SOCIAL = ROLES_OPERATIVOS + ROLES_TRANSVERSALES
TIPOS_CATALOGO_ATENCION = (Catalogo.TIPO_ATENCION, Catalogo.TIPO_SUBATENCION)


def maximo_gestiones():
    return settings.SGR_MAX_GESTIONES_SOCIAL


# ---------------------------------------------------------------------------
# Visibilidad y permisos
# ---------------------------------------------------------------------------
def casos_visibles(user):
    qs = UsuarioSocial.objects.select_related("delegacion")
    if not tiene_rol(user, *ROLES_SOCIAL):
        return qs.none()
    if es_transversal(user):
        return qs
    f = get_funcionario(user)
    return qs.filter(delegacion_id=f.delegacion_id) if f else qs.none()


def gestiones_visibles(user):
    return AtencionSocial.objects.select_related("usuario", "catalogo", "funcionario") \
        .filter(usuario__in=casos_visibles(user).values("pk"))


def puede_escribir(user, caso_delegacion_id):
    """Registrar y modificar: Funcionario o Delegado de la misma delegación."""
    if not tiene_rol(user, *ROLES_OPERATIVOS):
        return False
    f = get_funcionario(user)
    return f is not None and f.delegacion_id == caso_delegacion_id


def puede_reabrir(user, caso_delegacion_id):
    if es_transversal(user):
        return True
    f = get_funcionario(user)
    return tiene_rol(user, ROL_DELEGADO) and f is not None and f.delegacion_id == caso_delegacion_id


def _exigir_escritura(user, caso):
    if not puede_escribir(user, caso.delegacion_id):
        raise ReglaNegocioError("No tiene permiso para modificar casos de esta delegación.")


def _validar_catalogo(catalogo):
    if not catalogo.activo:
        raise ReglaNegocioError("El elemento de catálogo está desactivado.")
    if catalogo.tipo_catalogo not in TIPOS_CATALOGO_ATENCION:
        raise ReglaNegocioError("El catálogo debe ser de tipo Atención o Subatención.")


# ---------------------------------------------------------------------------
# CRUDAtencionSocial (RF-015, RN-012)
# ---------------------------------------------------------------------------
class CRUDAtencionSocial:
    @staticmethod
    def validar_maximo_tres_gestiones(id_usuario):
        """True si el caso aún admite otra gestión (el límite sale de settings, 3 por defecto)."""
        return AtencionSocial.objects.filter(usuario_id=id_usuario).count() < maximo_gestiones()

    @staticmethod
    def mostrar_gestiones_por_caso(id_usuario):
        return AtencionSocial.objects.filter(usuario_id=id_usuario).select_related("catalogo", "funcionario") \
            .order_by("numero_gestion")

    @staticmethod
    def _validar_fecha_y_estado(gestion, anterior=None, siguiente=None):
        hoy = timezone.localdate()
        if gestion.estado == AtencionSocial.ESTADO_REALIZADA and gestion.fecha > hoy:
            raise ReglaNegocioError("Una gestión realizada no puede tener fecha futura.")
        if gestion.estado == AtencionSocial.ESTADO_PROGRAMADA and gestion.pk is None and gestion.fecha < hoy:
            raise ReglaNegocioError("Una gestión programada debe tener fecha de hoy o futura.")
        if anterior is not None and gestion.fecha < anterior.fecha:
            raise ReglaNegocioError(
                f"La fecha no puede ser anterior a la de la gestión {anterior.numero_gestion} "
                f"({anterior.fecha:%d/%m/%Y}).")
        if siguiente is not None and gestion.fecha > siguiente.fecha:
            raise ReglaNegocioError(
                f"La fecha no puede ser posterior a la de la gestión {siguiente.numero_gestion} "
                f"({siguiente.fecha:%d/%m/%Y}).")

    @staticmethod
    def registrar_gestion(gestion, actor=None):
        """Agrega la siguiente gestión del caso (1, 2 o 3). Bloquea el caso para evitar duplicados."""
        autor = get_funcionario(actor)
        with transaction.atomic():
            caso = UsuarioSocial.objects.select_for_update().get(pk=gestion.usuario_id)
            _exigir_escritura(actor, caso)
            if caso.cerrado:
                raise ReglaNegocioError("El caso está cerrado: reábralo para registrar nuevas gestiones.")
            existentes = list(caso.gestiones.order_by("numero_gestion"))
            if len(existentes) >= maximo_gestiones():
                raise ReglaNegocioError(
                    f"El caso ya tiene las {maximo_gestiones()} gestiones permitidas (RN-012).")
            if any(g.tipo_atencion == gestion.tipo_atencion for g in existentes):
                raise ReglaNegocioError("Cada gestión del caso debe tener un tipo de atención diferente.")
            _validar_catalogo(gestion.catalogo)
            CRUDAtencionSocial._validar_fecha_y_estado(gestion, anterior=existentes[-1] if existentes else None)
            gestion.numero_gestion = len(existentes) + 1
            gestion.funcionario = autor
            guardar(gestion, actor, "atencion_social")
        return gestion

    @staticmethod
    def modificar_gestion(gestion, actor=None):
        """Corrige tipo, fecha, resultado, estado o catálogo de una gestión (queda auditado)."""
        with transaction.atomic():
            original = AtencionSocial.objects.select_for_update().get(pk=gestion.pk)
            caso = UsuarioSocial.objects.select_for_update().get(pk=original.usuario_id)
            _exigir_escritura(actor, caso)
            if caso.cerrado:
                raise ReglaNegocioError("El caso está cerrado: reábralo para modificar sus gestiones.")
            if gestion.usuario_id != original.usuario_id or gestion.numero_gestion != original.numero_gestion:
                raise ReglaNegocioError("No se puede cambiar el caso ni el número de la gestión.")
            otras = caso.gestiones.exclude(pk=gestion.pk)
            if otras.filter(tipo_atencion=gestion.tipo_atencion).exists():
                raise ReglaNegocioError("Cada gestión del caso debe tener un tipo de atención diferente.")
            if gestion.catalogo_id != original.catalogo_id:
                _validar_catalogo(gestion.catalogo)
            CRUDAtencionSocial._validar_fecha_y_estado(
                gestion,
                anterior=otras.filter(numero_gestion__lt=gestion.numero_gestion).order_by("-numero_gestion").first(),
                siguiente=otras.filter(numero_gestion__gt=gestion.numero_gestion).order_by("numero_gestion").first())
            guardar(gestion, actor, "atencion_social")
        return gestion


# ---------------------------------------------------------------------------
# CRUDUsuarioSocial (RF-015, HU-03)
# ---------------------------------------------------------------------------
class CRUDUsuarioSocial:
    @staticmethod
    def crear_caso(caso, primera_gestion, actor=None):
        """Crea el caso y su primera gestión en una sola transacción: nunca queda un caso vacío."""
        autor = get_funcionario(actor)
        if autor is None or not tiene_rol(actor, *ROLES_OPERATIVOS):
            raise ReglaNegocioError("No tiene permiso para registrar casos sociales.")
        with transaction.atomic():
            caso.delegacion_id = autor.delegacion_id
            caso.estado_caso = UsuarioSocial.ESTADO_ABIERTO
            guardar(caso, actor, "usuario_social")
            primera_gestion.usuario = caso
            CRUDAtencionSocial.registrar_gestion(primera_gestion, actor)
        return caso

    @staticmethod
    def mostrar_caso_por_id(id_usuario, user):
        return casos_visibles(user).filter(pk=id_usuario).first()

    @staticmethod
    def mostrar_historial_gestiones(id_usuario):
        """Secuencia completa del caso, sin repetir la identificación principal (CA-04)."""
        return CRUDAtencionSocial.mostrar_gestiones_por_caso(id_usuario)

    @staticmethod
    def modificar_caso(caso, actor=None):
        _exigir_escritura(actor, caso)
        original = UsuarioSocial.objects.get(pk=caso.pk)
        if original.delegacion_id != caso.delegacion_id:
            raise ReglaNegocioError("No se puede cambiar la delegación del caso.")
        return guardar(caso, actor, "usuario_social")

    @staticmethod
    def cambiar_estado_caso(caso, nuevo_estado, actor=None):
        with transaction.atomic():
            caso = UsuarioSocial.objects.select_for_update().get(pk=caso.pk)
            if not (puede_escribir(actor, caso.delegacion_id) or es_transversal(actor)):
                raise ReglaNegocioError("No tiene permiso para modificar casos de esta delegación.")
            if nuevo_estado not in dict(UsuarioSocial.ESTADOS):
                raise ReglaNegocioError("Estado de caso no válido.")
            if nuevo_estado == caso.estado_caso:
                raise ReglaNegocioError(f"El caso ya está «{caso.estado_caso}».")
            if caso.cerrado and not puede_reabrir(actor, caso.delegacion_id):
                raise ReglaNegocioError("Solo el delegado o la coordinación pueden reabrir un caso cerrado.")
            anterior = snapshot(caso)
            caso.estado_caso = nuevo_estado
            caso.save(update_fields=["estado_caso"])
            auditar(actor, "CAMBIO_ESTADO_CASO", "usuario_social", caso.pk, anterior,
                    json.dumps({"estado_caso": nuevo_estado}, ensure_ascii=False))
        return caso


# ---------------------------------------------------------------------------
# Estadísticas (HU-03: cada atención válida se cuenta una sola vez)
# ---------------------------------------------------------------------------
def estadisticas_atenciones(queryset):
    """Resumen de gestiones REALIZADAS. Cada gestión es una fila, por lo que nunca se cuenta dos veces."""
    realizadas = queryset.filter(estado=AtencionSocial.ESTADO_REALIZADA)
    return {
        "total_gestiones": realizadas.count(),
        "total_personas": realizadas.values("usuario_id").distinct().count(),
        "por_tipo": list(realizadas.values("tipo_atencion").annotate(total=Count("pk")).order_by("-total")),
        "por_catalogo": list(realizadas.values("catalogo__nombre", "catalogo__tipo_catalogo")
                             .annotate(total=Count("pk")).order_by("-total")),
        "por_delegacion": list(realizadas.values("usuario__delegacion__nombre")
                               .annotate(total=Count("pk")).order_by("-total")),
        "por_mes": list(realizadas.annotate(mes=TruncMonth("fecha")).values("mes")
                        .annotate(total=Count("pk")).order_by("mes")),
    }
