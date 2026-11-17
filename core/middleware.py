"""Middleware de contexto territorial activo.

El identificador almacenado en sesión nunca concede permisos: se valida contra
las delegaciones activas que el usuario ya tiene autorizadas.
"""

from .mixins import get_delegaciones_autorizadas_ids, get_delegacion_id


class DelegacionActivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            autorizadas = set(get_delegaciones_autorizadas_ids(user))
            seleccion = request.session.get("sgr_delegacion_activa")
            try:
                seleccion = int(seleccion) if seleccion is not None else None
            except (TypeError, ValueError):
                seleccion = None

            if seleccion not in autorizadas:
                seleccion = get_delegacion_id(user)
                if seleccion not in autorizadas:
                    seleccion = next(iter(sorted(autorizadas)), None)
                if seleccion is None:
                    request.session.pop("sgr_delegacion_activa", None)
                else:
                    request.session["sgr_delegacion_activa"] = seleccion

            user._sgr_delegacion_activa_id = seleccion
        return self.get_response(request)
