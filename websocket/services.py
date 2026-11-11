
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone


logger = logging.getLogger(__name__)


MODULOS_DISPLAY = {
    "organizations": "Organización municipal",
    "catalogs": "Catálogos",
    "measurement": "Medición y metas",
    "activities": "Actividades",
    "agenda": "Agenda colectiva",
    "social": "Atención social",
}

ACCIONES_DISPLAY = {
    "crear": "Creación",
    "creado": "Creación",
    "actualizar": "Modificación",
    "actualizado": "Modificación",
    "modificar": "Modificación",
    "eliminar": "Eliminación",
    "eliminado": "Eliminación",
}


def obtener_delegacion_id(objeto, profundidad=0):
    if objeto is None or profundidad > 5:
        return None

    modelo = objeto._meta.model_name

    if modelo == "delegacion":
        return objeto.pk

    delegacion_id = getattr(
        objeto,
        "delegacion_id",
        None,
    )

    if delegacion_id:
        return delegacion_id

    relaciones = (
        "funcionario",
        "usuario",
        "actividad",
        "evidencia",
        "compromiso",
        "meta",
    )

    for relacion in relaciones:
        try:
            relacionado = getattr(
                objeto,
                relacion,
                None,
            )
        except Exception:
            relacionado = None

        if relacionado is not None:
            resultado = obtener_delegacion_id(
                relacionado,
                profundidad + 1,
            )

            if resultado:
                return resultado

    return None


def modelo_es_delegacion(objeto):
    return objeto._meta.model_name == "delegacion"


def obtener_nombre_actor(actor):
    if actor is None:
        return "Sistema"

    try:
        funcionario = actor.funcionario

        if funcionario:
            return funcionario.nombre

    except Exception:
        pass

    return (
        actor.get_full_name()
        or getattr(actor, "username", "")
        or "Usuario no disponible"
    )


def obtener_nombre_delegacion(delegacion_id):
    if not delegacion_id:
        return "General"

    try:
        Delegacion = apps.get_model(
            "organizations",
            "Delegacion",
        )

        delegacion = Delegacion.objects.filter(
            pk=delegacion_id
        ).first()

        return (
            delegacion.nombre
            if delegacion
            else "Delegación no disponible"
        )

    except Exception:
        logger.exception(
            "No se pudo obtener el nombre de la delegación."
        )
        return "Delegación no disponible"


def publish_crud_event(
    module,
    action,
    actor,
    objeto,
    object_id=None,
    object_label=None,
    delegacion_id=None,
):
    channel_layer = get_channel_layer()

    if channel_layer is None:
        logger.warning(
            "No hay una capa de canales configurada."
        )
        return

    if objeto is None:
        return

    if delegacion_id is None:
        delegacion_id = obtener_delegacion_id(
            objeto
        )

    identificador = (
        object_id
        if object_id is not None
        else objeto.pk
    )

    etiqueta = (
        object_label
        if object_label
        else str(objeto)
    )

    tipo_objeto = str(
        objeto._meta.verbose_name
    )

    actor_nombre = obtener_nombre_actor(actor)

    delegacion_nombre = obtener_nombre_delegacion(
        delegacion_id
    )

    fecha = timezone.localtime()

    payload = {
        "type": "crud_update",

        "module": module,
        "module_display": MODULOS_DISPLAY.get(
            module,
            module.replace("_", " ").capitalize(),
        ),

        "action": action,
        "action_display": ACCIONES_DISPLAY.get(
            action,
            action.capitalize(),
        ),

        "object_id": str(identificador or ""),
        "object_pk": str(identificador or ""),
        "object_type": tipo_objeto,
        "object_label": etiqueta,

        "actor_id": getattr(actor, "pk", None),
        "actor_name": actor_nombre,

        "delegacion_id": delegacion_id,
        "delegacion_name": delegacion_nombre,
        "organization_name": delegacion_nombre,

        "timestamp": fecha.isoformat(),
        "created_at": fecha.isoformat(),
    }

    grupos = []

    if delegacion_id:
        grupos.append(
            f"sgr_delegacion_{delegacion_id}"
        )

        if modelo_es_delegacion(objeto):
            grupos.append("sgr_global")

    else:
        grupos.append("sgr_usuarios_activos")

    try:
        for grupo in set(grupos):
            async_to_sync(
                channel_layer.group_send
            )(
                grupo,
                {
                    "type": "crud_event",
                    "module": module,
                    "payload": payload,
                },
            )

    except Exception:
        logger.exception(
            "No se pudo publicar el evento CRUD del módulo %s.",
            module,
        )
