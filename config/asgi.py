
"""
Configuración ASGI del Sistema de Gestión de Resultados.
Soporta HTTP y WebSockets autenticados mediante sesión Django.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

# Inicializar Django antes de importar las rutas WebSocket.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

import websocket.routing


application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket.routing.websocket_urlpatterns
            )
        )
    ),
})
