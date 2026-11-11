
"""
Servicios compartidos para guardar y eliminar registros del SGR.
Mantiene validación, transacciones, auditoría y notificaciones WebSocket.
"""
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.forms.models import model_to_dict

from .exceptions import ReglaNegocioError
from .mixins import auditar


# Campos que nunca deben quedar registrados en snapshots.
_EXCLUIDOS = [
    "password",
    "groups",
    "user_permissions",
    "roles",
]


# Entidad de auditoría -> módulo que recibirá el evento.
_MODULOS_CRUD = {
    "delegacion": "organizations",
    "cargo": "organizations",
    "item_medible": "organizations",
    "rol": "organizations",
    "funcionario": "organizations",
    "funcionario_rol": "organizations",
    "usuario": "organizations",
    "catalogo": "catalogs",
    "periodo": "measurement",
    "meta": "measurement",
    "ajuste": "measurement",
    "indicador": "measurement",
    "actividad": "activities",
    "evidencia": "activities",
    "validacion": "activities",
    "compromiso": "agenda",
    "usuario_social": "social",
    "caso": "social",
    "atencion_social": "social",
    "gestion": "social",
}


def snapshot(instancia):
    """Representación JSON segura del registro para auditoría."""
    return json.dumps(
        model_to_dict(instancia, exclude=_EXCLUIDOS),
        default=str,
        ensure_ascii=False,
    )


def mensaje_validacion(exc):
    if hasattr(exc, "error_dict"):
        return " ".join(
            mensaje
            for lista in exc.message_dict.values()
            for mensaje in lista
        )

    return " ".join(exc.messages)



def _notificar_crud(
    entidad,
    accion,
    actor,
    instancia,
    object_id=None,
    object_label=None,
    delegacion_id=None,
):
    """
    Programa la publicación después de confirmar la transacción.
    Conserva los datos del registro incluso cuando se elimina.
    """
    modulo = _MODULOS_CRUD.get(str(entidad).lower())

    if not modulo or instancia is None:
        return

    identificador = (
        object_id
        if object_id is not None
        else instancia.pk
    )

    etiqueta = (
        object_label
        if object_label
        else str(instancia)
    )

    def publicar():
        try:
            from websocket.services import publish_crud_event

            publish_crud_event(
                module=modulo,
                action=accion,
                actor=actor,
                objeto=instancia,
                object_id=identificador,
                object_label=etiqueta,
                delegacion_id=delegacion_id,
            )

        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "No se pudo publicar el evento CRUD de %s.",
                entidad,
            )

    transaction.on_commit(publicar)


def guardar(instancia, actor, entidad):
    """
    Crea o modifica un registro con validación, transacción,
    auditoría y notificación en tiempo real.
    """
    try:
        instancia.full_clean()
    except ValidationError as exc:
        raise ReglaNegocioError(mensaje_validacion(exc))

    with transaction.atomic():
        creado = instancia.pk is None

        anterior = (
            None
            if creado
            else snapshot(
                type(instancia).objects.select_for_update().get(
                    pk=instancia.pk
                )
            )
        )

        instancia.save()

        auditar(
            actor,
            "CREAR" if creado else "MODIFICAR",
            entidad,
            instancia.pk,
            anterior,
            snapshot(instancia),
        )

        _notificar_crud(
            entidad,
            "crear" if creado else "actualizar",
            actor,
            instancia,
        )

    return instancia



def eliminar(instancia, actor, entidad, mensaje_en_uso):
    """
    Elimina un registro respetando las relaciones protegidas.
    Conserva sus datos para notificar correctamente la eliminación.
    """
    pk = instancia.pk
    etiqueta = str(instancia)

    try:
        from websocket.services import obtener_delegacion_id

        delegacion_id = obtener_delegacion_id(instancia)

    except Exception:
        delegacion_id = None

    anterior = snapshot(instancia)

    try:
        with transaction.atomic():
            instancia.delete()

            auditar(
                actor,
                "ELIMINAR",
                entidad,
                pk,
                anterior,
                None,
            )

            _notificar_crud(
                entidad,
                "eliminar",
                actor,
                instancia,
                object_id=pk,
                object_label=etiqueta,
                delegacion_id=delegacion_id,
            )

    except (ProtectedError, IntegrityError):
        raise ReglaNegocioError(mensaje_en_uso)

    return True
