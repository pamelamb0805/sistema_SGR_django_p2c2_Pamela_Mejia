
"""
Servicio de publicación de eventos CRUD del SGR.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


logger = logging.getLogger(__name__)


def obtener_delegacion_id(objeto, profundidad=0):
    """
    Resuelve la delegación de un registro a través de sus relaciones.
    Evita depender de una estructura de organización ajena al SGR.
    """
    if objeto is None or profundidad > 5:
        return None

    modelo = objeto._meta.model_name

    if modelo == "delegacion":
        return objeto.pk

    delegacion_id = getattr(objeto, "delegacion_id", None)

    if delegacion_id:
        return delegacion_id

    relaciones = (
        "funcionario",
        "usuario",
        "actividad",
        "evidencia",
        "compromiso",
    )

    for relacion in relaciones:
        relacionado = getattr(objeto, relacion, None)

        if relacionado is not None:
            resultado = obtener_delegacion_id(
                relacionado,
                profundidad + 1,
            )

            if resultado:
                return resultado

    return None


def publish_crud_event(
    module,
    action,
    actor,
    objeto,
):
    """
    Publica un evento CRUD a la delegación correspondiente.

    Las entidades globales se notifican mediante sgr_global.
    Las entidades vinculadas a una delegación se notifican
    exclusivamente al grupo de esa delegación.
    """
    channel_layer = get_channel_layer()

    if channel_layer is None:
        logger.warning("No hay una capa de canales configurada.")
        return

    if objeto is None:
        return

    delegacion_id = obtener_delegacion_id(objeto)

    payload = {
        "type": "crud_update",
        "module": module,
        "action": action,
        "object_id": str(objeto.pk),
        "object_type": str(objeto._meta.verbose_name),
        "actor_id": getattr(actor, "pk", None),
        "delegacion_id": delegacion_id,
        "timestamp": timezone.localtime().isoformat(),
    }

    grupos = []

    if delegacion_id:
        grupos.append(f"sgr_delegacion_{delegacion_id}")

        # La creación/modificación de una delegación también
        # debe llegar al grupo de supervisión global.
        if objeto._meta.model_name == "delegacion":
            grupos.append("sgr_global")
    else:
        grupos.append("sgr_global")

    try:
        for grupo in set(grupos):
            async_to_sync(channel_layer.group_send)(
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
