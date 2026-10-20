"""Decoradores equivalentes a los mixins, para vistas basadas en funciones."""
from functools import wraps

from django.contrib.auth.decorators import login_required

from .mixins import denegar_acceso, get_funcionario, tiene_rol


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
    """Exige que el usuario tenga un Funcionario (y por tanto delegación) asociado."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_funcionario(request.user) is None:
            return denegar_acceso(request, "Su usuario no tiene un funcionario asociado.")
        return view_func(request, *args, **kwargs)
    return wrapper
