
"""Decoradores de autenticación y autorización del SGR."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .mixins import (
    denegar_acceso,
    get_funcionario,
    registrar_auditoria,
    tiene_permiso,
    tiene_rol,
)


def permiso_requerido(*permisos, respuesta_json=False):
    """
    Exige que el usuario tenga al menos uno de los permisos indicados
    en alguno de sus roles asignados.

    La validación se ejecuta en el servidor, antes de ejecutar la vista.

    respuesta_json:
        False: registra la denegación y redirige al dashboard.
        True: registra la denegación y devuelve HTTP 403 en JSON.
    """

    if not permisos:
        raise ValueError(
            "Debe indicar al menos un permiso para proteger la vista."
        )

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            # El superusuario técnico conserva acceso total.
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            funcionario = get_funcionario(request.user)

            funcionario_activo = bool(
                funcionario is not None
                and funcionario.activo
            )

            autorizado = (
                funcionario_activo
                and tiene_permiso(
                    request.user,
                    *permisos,
                )
            )

            if not autorizado:

                detalle = (
                    "No tiene un funcionario activo asociado "
                    "o no posee el permiso necesario para realizar "
                    "esta operación."
                )

                if respuesta_json:
                    registrar_auditoria(
                        request,
                        evento="ACCESO_DENEGADO",
                        entidad="ruta",
                        id_entidad=0,
                        valor_nuevo=request.path,
                    )

                    return JsonResponse(
                        {
                            "ok": False,
                            "error": detalle,
                        },
                        status=403,
                    )

                return denegar_acceso(
                    request,
                    detalle,
                )

            return view_func(
                request,
                *args,
                **kwargs,
            )

        wrapper.permisos_requeridos = tuple(permisos)

        return wrapper

    return decorator


def rol_requerido(*roles):
    """
    Compatibilidad con vistas antiguas que todavía requieren
    comprobar nombres de roles.
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            if not tiene_rol(request.user, *roles):
                return denegar_acceso(request)

            return view_func(
                request,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


def funcionario_requerido(view_func):
    """
    Exige un funcionario asociado y activo.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        funcionario = get_funcionario(request.user)

        if funcionario is None or not funcionario.activo:
            return denegar_acceso(
                request,
                "Su usuario no tiene un funcionario activo asociado.",
            )

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper
