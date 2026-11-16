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
from core.services import (
    guardar,
    snapshot,
    _notificar_crud,
)

from .models import AtencionSocial, UsuarioSocial
from core.mixins import (
    ROL_DELEGADO,
    ROLES_OPERATIVOS,
    ROLES_TRANSVERSALES,
    auditar,
    es_transversal,
    get_funcionario,
    get_delegaciones_autorizadas_ids,
    tiene_rol,
)

# Acceso al módulo: datos personales de usuarios atendidos => solo quienes los necesitan (RNF-009)
ROLES_SOCIAL = ROLES_OPERATIVOS + ROLES_TRANSVERSALES
TIPOS_CATALOGO_ATENCION = (Catalogo.TIPO_ATENCION, Catalogo.TIPO_SUBATENCION)


def maximo_gestiones():
    return settings.SGR_MAX_GESTIONES_SOCIAL


# ---------------------------------------------------------------------------
# Visibilidad y permisos
# ---------------------------------------------------------------------------
def casos_visibles(user):
    """
    Devuelve los casos correspondientes a las delegaciones autorizadas
    del usuario. Los usuarios transversales pueden consultar todas.
    """
    qs = UsuarioSocial.objects.select_related("delegacion")

    if not tiene_rol(user, *ROLES_SOCIAL):
        return qs.none()

    if es_transversal(user):
        return qs

    delegaciones_ids = get_delegaciones_autorizadas_ids(user)

    if not delegaciones_ids:
        return qs.none()

    return qs.filter(delegacion_id__in=delegaciones_ids)

def gestiones_visibles(user):
    return (
        AtencionSocial.objects.select_related(
            "usuario",
            "tipo_atencion",
            "subatencion",
            "funcionario",
            "delegacion",
        )
        .filter(
            usuario__in=casos_visibles(user).values("pk")
        )
    )

def puede_escribir(user, caso_delegacion_id):
    """
    Permite escribir a funcionarios y delegados dentro de sus
    delegaciones autorizadas.
    """
    if not tiene_rol(user, *ROLES_OPERATIVOS):
        return False

    delegaciones_ids = get_delegaciones_autorizadas_ids(user)

    return caso_delegacion_id in delegaciones_ids

def puede_reabrir(user, caso_delegacion_id):
    if es_transversal(user):
        return True
    f = get_funcionario(user)
    return tiene_rol(user, ROL_DELEGADO) and f is not None and f.delegacion_id == caso_delegacion_id


def _exigir_escritura(user, caso):
    if not puede_escribir(user, caso.delegacion_id):
        raise ReglaNegocioError("No tiene permiso para modificar casos de esta delegación.")



def _validar_catalogo(tipo_atencion, subatencion, original=None):
    if tipo_atencion is None or subatencion is None:
        raise ReglaNegocioError(
            "Debe seleccionar el Tipo de Atención y la Subatención."
        )

    if tipo_atencion.tipo_catalogo != Catalogo.TIPO_ATENCION:
        raise ReglaNegocioError(
            "El elemento seleccionado no es un Tipo de Atención."
        )

    if subatencion.tipo_catalogo != Catalogo.TIPO_SUBATENCION:
        raise ReglaNegocioError(
            "El elemento seleccionado no es una Subatención."
        )

    # En una edición, solo se tolera conservar elementos inactivos
    # cuando son exactamente los mismos que tenía el registro.
    conserva_tipo = (
        original is not None
        and original.tipo_atencion_id == tipo_atencion.pk
    )

    conserva_subatencion = (
        original is not None
        and original.subatencion_id == subatencion.pk
    )

    if not tipo_atencion.activo and not conserva_tipo:
        raise ReglaNegocioError(
            "No se pueden registrar atenciones con un Tipo de "
            "Atención inactivo."
        )

    if not subatencion.activo and not conserva_subatencion:
        raise ReglaNegocioError(
            "No se pueden registrar atenciones con una Subatención inactiva."
        )

    if not subatencion.tipo_atencion_padre_id:
        raise ReglaNegocioError(
            "La Subatención no tiene un Tipo de Atención asociado."
        )

    if subatencion.tipo_atencion_padre_id != tipo_atencion.pk:
        raise ReglaNegocioError(
            "La Subatención no corresponde al Tipo de Atención seleccionado."
        )

    padre = subatencion.tipo_atencion_padre

    padre_inactivo_conservado = (
        conserva_subatencion
        and conserva_tipo
        and padre.pk == tipo_atencion.pk
    )

    if not padre.activo and not padre_inactivo_conservado:
        raise ReglaNegocioError(
            "El Tipo de Atención asociado a la Subatención está inactivo."
        )

    if (
        padre.area != Catalogo.AREA_GENERAL
        and padre.area.casefold() != subatencion.area.casefold()
    ):
        raise ReglaNegocioError(
            "El Tipo de Atención y la Subatención no pertenecen "
            "a la misma área."
        )
# ---------------------------------------------------------------------------
# CRUDAtencionSocial (RF-015, RN-012)
# ---------------------------------------------------------------------------

class CRUDAtencionSocial:
    @staticmethod
    def validar_maximo_tres_gestiones(id_usuario):
        return (
            AtencionSocial.objects.filter(usuario_id=id_usuario).count()
            < maximo_gestiones()
        )

    @staticmethod
    def mostrar_gestiones_por_caso(id_usuario):
        return (
            AtencionSocial.objects.filter(usuario_id=id_usuario)
            .select_related(
                "tipo_atencion",
                "subatencion",
                "funcionario",
                "delegacion",
            )
            .order_by("numero_gestion")
        )

    @staticmethod
    def _validar_fecha_y_estado(
        gestion,
        anterior=None,
        siguiente=None,
    ):
        hoy = timezone.localdate()

        if (
            gestion.estado == AtencionSocial.ESTADO_REALIZADA
            and gestion.fecha > hoy
        ):
            raise ReglaNegocioError(
                "Una gestión realizada no puede tener fecha futura."
            )

        if (
            gestion.estado == AtencionSocial.ESTADO_PROGRAMADA
            and gestion.pk is None
            and gestion.fecha < hoy
        ):
            raise ReglaNegocioError(
                "Una gestión programada debe tener fecha de hoy o futura."
            )

        if anterior is not None and gestion.fecha < anterior.fecha:
            raise ReglaNegocioError(
                f"La fecha no puede ser anterior a la de la gestión "
                f"{anterior.numero_gestion} ({anterior.fecha:%d/%m/%Y})."
            )

        if siguiente is not None and gestion.fecha > siguiente.fecha:
            raise ReglaNegocioError(
                f"La fecha no puede ser posterior a la de la gestión "
                f"{siguiente.numero_gestion} ({siguiente.fecha:%d/%m/%Y})."
            )

    @staticmethod
    def registrar_gestion(gestion, actor=None):
        autor = get_funcionario(actor)

        if autor is None:
            raise ReglaNegocioError(
                "El usuario autenticado no tiene un funcionario asociado."
            )

        with transaction.atomic():
            caso = UsuarioSocial.objects.select_for_update().get(
                pk=gestion.usuario_id
            )

            _exigir_escritura(actor, caso)

            if caso.cerrado:
                raise ReglaNegocioError(
                    "El caso está cerrado: reábralo para registrar nuevas gestiones."
                )

            existentes = list(
                caso.gestiones.order_by("numero_gestion")
            )

            if len(existentes) >= maximo_gestiones():
                raise ReglaNegocioError(
                    f"El caso ya tiene las {maximo_gestiones()} "
                    "gestiones permitidas."
                )

            if any(
                g.tipo_atencion_id == gestion.tipo_atencion_id
                for g in existentes
            ):
                raise ReglaNegocioError(
                    "Cada gestión del caso debe tener un Tipo de Atención diferente."
                )

            _validar_catalogo(
                gestion.tipo_atencion,
                gestion.subatencion,
            )

            CRUDAtencionSocial._validar_fecha_y_estado(
                gestion,
                anterior=existentes[-1] if existentes else None,
            )

            # La asignación se realiza en el servidor.
            gestion.numero_gestion = len(existentes) + 1
            gestion.funcionario = autor
            gestion.delegacion = caso.delegacion
            gestion.usuario = caso
            gestion.tipo_atencion_nombre = gestion.tipo_atencion.nombre
            gestion.subatencion_nombre = gestion.subatencion.nombre

            gestion.full_clean()
            guardar(gestion, actor, "atencion_social")

        return gestion

    @staticmethod
    def modificar_gestion(gestion, actor=None):
        with transaction.atomic():
            original = (
                AtencionSocial.objects
                .select_for_update()
                .select_related(
                    "usuario",
                    "delegacion",
                    "funcionario",
                    "tipo_atencion",
                    "subatencion",
                )
                .get(pk=gestion.pk)
            )

            caso = UsuarioSocial.objects.select_for_update().get(
                pk=original.usuario_id
            )

            _exigir_escritura(actor, caso)

            if caso.cerrado:
                raise ReglaNegocioError(
                    "El caso está cerrado: reábralo para modificar sus gestiones."
                )

            if (
                gestion.usuario_id != original.usuario_id
                or gestion.numero_gestion != original.numero_gestion
            ):
                raise ReglaNegocioError(
                    "No se puede cambiar el caso ni el número de la gestión."
                )

            otras = caso.gestiones.exclude(pk=gestion.pk)

            if otras.filter(
                tipo_atencion_id=gestion.tipo_atencion_id
            ).exists():
                raise ReglaNegocioError(
                    "Cada gestión del caso debe tener un Tipo de Atención diferente."
                )

            # Permite conservar la clasificación anterior aunque después
            # se haya desactivado, pero no permite cambiarla por una inactiva.
            _validar_catalogo(
                gestion.tipo_atencion,
                gestion.subatencion,
                original=original,
            )

            CRUDAtencionSocial._validar_fecha_y_estado(
                gestion,
                anterior=(
                    otras.filter(
                        numero_gestion__lt=gestion.numero_gestion
                    )
                    .order_by("-numero_gestion")
                    .first()
                ),
                siguiente=(
                    otras.filter(
                        numero_gestion__gt=gestion.numero_gestion
                    )
                    .order_by("numero_gestion")
                    .first()
                ),
            )

            # Asignaciones protegidas: no se cambian desde el formulario.
            gestion.usuario = caso
            gestion.delegacion = original.delegacion
            gestion.funcionario = original.funcionario
            gestion.fecha_registro = original.fecha_registro

            # Mantiene el nombre histórico si no cambió el catálogo.
            if gestion.tipo_atencion_id == original.tipo_atencion_id:
                gestion.tipo_atencion_nombre = (
                    original.tipo_atencion_nombre
                    or original.tipo_atencion.nombre
                )
            else:
                gestion.tipo_atencion_nombre = gestion.tipo_atencion.nombre

            if gestion.subatencion_id == original.subatencion_id:
                gestion.subatencion_nombre = (
                    original.subatencion_nombre
                    or original.subatencion.nombre
                )
            else:
                gestion.subatencion_nombre = gestion.subatencion.nombre

            gestion.full_clean()
            guardar(
                gestion,
                actor,
                "atencion_social",
            )

        return gestion
# ---------------------------------------------------------------------------
# CRUDUsuarioSocial (RF-015, HU-03)
# ---------------------------------------------------------------------------
class CRUDUsuarioSocial:
    @staticmethod
    def crear_caso(caso, primera_gestion, actor=None):
        """Crea el caso y su primera gestión en una sola transacción."""
        autor = get_funcionario(actor)

        if autor is None or not tiene_rol(actor, *ROLES_OPERATIVOS):
            raise ReglaNegocioError(
                "No tiene permiso para registrar casos sociales."
            )

        with transaction.atomic():
            caso.delegacion_id = autor.delegacion_id
            caso.estado_caso = UsuarioSocial.ESTADO_ABIERTO
            guardar(caso, actor, "usuario_social")

            primera_gestion.usuario = caso
            primera_gestion.delegacion = caso.delegacion
            primera_gestion.funcionario = autor

            CRUDAtencionSocial.registrar_gestion(
                primera_gestion,
                actor,
            )

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
    def cambiar_estado_caso(
        caso,
        nuevo_estado,
        actor=None,
    ):
        """
        Cambia el estado del caso social, conserva la auditoría
        y publica el cambio para los usuarios autorizados.
        """
        with transaction.atomic():
            caso = UsuarioSocial.objects.select_for_update().get(
                pk=caso.pk
            )

            if not (
                puede_escribir(actor, caso.delegacion_id)
                or es_transversal(actor)
            ):
                raise ReglaNegocioError(
                    "No tiene permiso para modificar casos "
                    "de esta delegación."
                )

            if nuevo_estado not in dict(UsuarioSocial.ESTADOS):
                raise ReglaNegocioError(
                    "Estado de caso no válido."
                )

            if nuevo_estado == caso.estado_caso:
                raise ReglaNegocioError(
                    f"El caso ya está «{caso.estado_caso}»."
                )

            if (
                caso.cerrado
                and not puede_reabrir(
                    actor,
                    caso.delegacion_id,
                )
            ):
                raise ReglaNegocioError(
                    "Solo el delegado o la coordinación "
                    "pueden reabrir un caso cerrado."
                )

            anterior = snapshot(caso)

            caso.estado_caso = nuevo_estado
            caso.save(update_fields=["estado_caso"])

            auditar(
                actor,
                "CAMBIO_ESTADO_CASO",
                "usuario_social",
                caso.pk,
                anterior,
                json.dumps(
                    {"estado_caso": nuevo_estado},
                    ensure_ascii=False,
                ),
            )

            _notificar_crud(
                "usuario_social",
                "actualizar",
                actor,
                caso,
            )

        return caso

# ---------------------------------------------------------------------------
# Estadísticas (HU-03: cada atención válida se cuenta una sola vez)
# ---------------------------------------------------------------------------
def estadisticas_atenciones(queryset):
    """
    Estadísticas utilizando las fotografías históricas
    de los catálogos registradas en cada gestión.
    """
    realizadas = queryset.filter(
        estado=AtencionSocial.ESTADO_REALIZADA
    ).select_related(
        "tipo_atencion",
        "subatencion",
        "delegacion",
    )

    gestiones = list(realizadas)

    por_tipo = {}
    por_subatencion = {}
    por_delegacion = {}
    por_mes = {}

    for gestion in gestiones:
        tipo = (
            gestion.tipo_atencion_nombre
            or gestion.tipo_atencion.nombre
        )

        subatencion = (
            gestion.subatencion_nombre
            or gestion.subatencion.nombre
        )

        delegacion = gestion.delegacion.nombre

        mes = gestion.fecha.strftime("%m/%Y")

        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        por_subatencion[subatencion] = (
            por_subatencion.get(subatencion, 0) + 1
        )
        por_delegacion[delegacion] = (
            por_delegacion.get(delegacion, 0) + 1
        )
        por_mes[mes] = por_mes.get(mes, 0) + 1

    return {
        "total_gestiones": len(gestiones),

        "total_personas": len({
            gestion.usuario_id
            for gestion in gestiones
        }),

        "por_tipo": [
            {
                "tipo_atencion__nombre": nombre,
                "total": total,
            }
            for nombre, total in sorted(
                por_tipo.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ],

        "por_subatencion": [
            {
                "subatencion__nombre": nombre,
                "total": total,
            }
            for nombre, total in sorted(
                por_subatencion.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ],

        "por_delegacion": [
            {
                "delegacion__nombre": nombre,
                "total": total,
            }
            for nombre, total in sorted(
                por_delegacion.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ],

        "por_mes": [
            {
                "mes": mes,
                "total": total,
            }
            for mes, total in sorted(por_mes.items())
        ],
    }