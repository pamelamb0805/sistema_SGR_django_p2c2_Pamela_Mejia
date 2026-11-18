
"""Decoradores de autenticación y autorización para vistas basadas en funciones."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .mixins import (
    denegar_acceso,
    get_funcionario,
    tiene_permiso,
    tiene_rol,
)


def rol_requerido(*roles):
    """Exige sesión iniciada y al menos uno de los roles indicados."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not tiene_rol(request.user, *roles):
                return denegar_acceso(request)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def funcionario_requerido(view_func):
    """Exige que el usuario tenga un funcionario asociado."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_funcionario(request.user) is None:
            return denegar_acceso(
                request,
                "Su usuario no tiene un funcionario asociado.",
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def permiso_requerido(*permisos, respuesta_json=False):
    """
    Exige todos los permisos indicados en Rol.permisos.

    Uso normal:
        @permiso_requerido("reportes.ver")

    Para endpoints AJAX/API:
        @permiso_requerido("reportes.ver", respuesta_json=True)
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            if not tiene_permiso(request.user, *permisos):

                if respuesta_json:
                    return JsonResponse(
                        {
                            "ok": False,
                            "error": "No tiene autorización para realizar esta operación.",
                        },
                        status=403,
                    )

                return denegar_acceso(
                    request,
                    "Su rol no tiene autorización para realizar esta operación.",
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
