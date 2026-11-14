
"""
Servicios compartidos para guardar y eliminar registros del SGR.
Mantiene validación, transacciones, auditoría, notificaciones
persistentes y publicación WebSocket.
"""
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.forms.models import model_to_dict

from .exceptions import ReglaNegocioError


_EXCLUIDOS = [
    "password",
    "groups",
    "user_permissions",
    "roles",
]


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
    Publica el evento WebSocket solamente después
    de confirmar la transacción.
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


def _registrar_operacion(
    actor,
    evento,
    entidad,
    id_entidad,
    valor_anterior,
    valor_nuevo,
    delegacion_id,
):
    """
    Registra la auditoría y crea las notificaciones
    dentro de la transacción de la operación.
    """
    from audit.services import (
        registrar_evento,
        crear_notificaciones,
    )

    auditoria = registrar_evento(
        usuario=actor,
        evento=evento,
        entidad=entidad,
        id_entidad=id_entidad,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
    )

    crear_notificaciones(
        auditoria,
        delegacion_id=delegacion_id,
    )

    return auditoria


def guardar(instancia, actor, entidad):
    """
    Crea o modifica un registro con validación, auditoría,
    notificaciones persistentes y publicación en tiempo real.
    """
    try:
        instancia.full_clean()
    except ValidationError as exc:
        raise ReglaNegocioError(mensaje_validacion(exc))

    try:
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

            from websocket.services import obtener_delegacion_id

            delegacion_id = obtener_delegacion_id(instancia)

            _registrar_operacion(
                actor=actor,
                evento="CREAR" if creado else "MODIFICAR",
                entidad=entidad,
                id_entidad=instancia.pk,
                valor_anterior=anterior,
                valor_nuevo=snapshot(instancia),
                delegacion_id=delegacion_id,
            )

            _notificar_crud(
                entidad,
                "crear" if creado else "actualizar",
                actor,
                instancia,
                delegacion_id=delegacion_id,
            )

    except (ProtectedError, IntegrityError):
        raise ReglaNegocioError(
            "No se pudo guardar el registro porque existe una relación "
            "o restricción que impide la operación."
        )

    return instancia


def eliminar(instancia, actor, entidad, mensaje_en_uso):
    """
    Elimina un registro conservando su auditoría,
    notificaciones y publicación WebSocket.
    """
    pk = instancia.pk
    etiqueta = str(instancia)
    anterior = snapshot(instancia)

    try:
        from websocket.services import obtener_delegacion_id

        delegacion_id = obtener_delegacion_id(instancia)

    except Exception:
        delegacion_id = None

    try:
        with transaction.atomic():
            instancia.delete()

            _registrar_operacion(
                actor=actor,
                evento="ELIMINAR",
                entidad=entidad,
                id_entidad=pk,
                valor_anterior=anterior,
                valor_nuevo=None,
                delegacion_id=delegacion_id,
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
