from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core.mixins import (
    es_transversal,
    get_delegaciones_autorizadas_ids,
    tiene_permiso,
)

from .models import ComentarioRegistro


MODELOS_COMENTABLES = {
    ("activities", "actividad"),
    ("activities", "evidencia"),
    ("agenda", "compromiso"),
    ("social", "usuariosocial"),
    ("social", "atencionsocial"),
    ("organizations", "funcionario"),
}


def obtener_registro_comentable(usuario, app_label, model_name, pk):
    """
    Recupera un registro permitido y comprueba permiso funcional
    y ámbito territorial antes de mostrar la conversación.
    """
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied(
            "Debe iniciar sesión con una cuenta activa."
        )

    if not tiene_permiso(usuario, "comentarios.ver"):
        raise PermissionDenied(
            "No tiene permiso para consultar comentarios."
        )

    clave = (
        str(app_label).lower(),
        str(model_name).lower(),
    )

    if clave not in MODELOS_COMENTABLES:
        raise PermissionDenied(
            "Este tipo de registro no admite conversaciones."
        )

    modelo = apps.get_model(app_label, model_name)

    if modelo is None:
        raise PermissionDenied(
            "El tipo de registro solicitado no existe."
        )

    registro = modelo._default_manager.filter(pk=pk).first()

    if registro is None:
        raise PermissionDenied(
            "El registro solicitado no existe o no está disponible."
        )

    from websocket.services import obtener_delegacion_id

    delegacion_id = obtener_delegacion_id(registro)

    if not delegacion_id:
        raise PermissionDenied(
            "El registro no tiene una delegación asociada."
        )

    if not es_transversal(usuario):
        delegaciones = set(
            get_delegaciones_autorizadas_ids(usuario)
        )

        if delegacion_id not in delegaciones:
            raise PermissionDenied(
                "No tiene autorización para consultar "
                "la conversación de este registro."
            )

    return registro, delegacion_id


def obtener_conversacion(registro, delegacion_id):
    """
    Obtiene los mensajes del registro en orden cronológico.
    La autorización de lectura se comprueba antes de llamar
    a esta función mediante obtener_registro_comentable.
    """
    tipo = ContentType.objects.get_for_model(
        registro,
        for_concrete_model=False,
    )

    return (
        ComentarioRegistro.objects
        .filter(
            content_type=tipo,
            object_id=registro.pk,
            delegacion_id=delegacion_id,
        )
        .select_related(
            "autor",
            "funcionario",
            "respuesta_a",
        )
        .order_by(
            "fecha_creacion",
            "id_comentario",
        )
    )


def crear_comentario(
    registro,
    delegacion_id,
    usuario,
    mensaje,
    respuesta_a=None,
):
    """
    Registra un comentario o respuesta únicamente si el usuario
    posee permiso de escritura y el registro pertenece a su ámbito.
    """
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied(
            "Debe iniciar sesión con una cuenta activa."
        )

    if not tiene_permiso(usuario, "comentarios.crear"):
        raise PermissionDenied(
            "No tiene permiso para publicar comentarios."
        )

    if not es_transversal(usuario):
        delegaciones = set(
            get_delegaciones_autorizadas_ids(usuario)
        )

        if delegacion_id not in delegaciones:
            raise PermissionDenied(
                "No tiene autorización para comentar en esta delegación."
            )

    mensaje = (mensaje or "").strip()

    if not mensaje:
        raise PermissionDenied(
            "El comentario no puede estar vacío."
        )

    from .services import registrar_evento

    tipo = ContentType.objects.get_for_model(
        registro,
        for_concrete_model=False,
    )

    with transaction.atomic():
        if respuesta_a is not None:
            respuesta_valida = ComentarioRegistro.objects.filter(
                pk=respuesta_a.pk,
                content_type=tipo,
                object_id=registro.pk,
                delegacion_id=delegacion_id,
            ).exists()

            if not respuesta_valida:
                raise PermissionDenied(
                    "La respuesta seleccionada no pertenece "
                    "a esta conversación."
                )

        comentario = ComentarioRegistro(
            content_type=tipo,
            object_id=registro.pk,
            autor=usuario,
            funcionario=getattr(
                usuario,
                "funcionario",
                None,
            ),
            delegacion_id=delegacion_id,
            respuesta_a=respuesta_a,
            mensaje=mensaje,
        )

        comentario.save()

        registrar_evento(
            usuario=usuario,
            evento="COMENTAR",
            entidad=registro._meta.model_name,
            id_entidad=registro.pk,
            valor_nuevo={
                "comentario_id": comentario.pk,
                "respuesta_a": (
                    respuesta_a.pk
                    if respuesta_a
                    else None
                ),
                "mensaje": comentario.mensaje,
            },
        )

    return comentario