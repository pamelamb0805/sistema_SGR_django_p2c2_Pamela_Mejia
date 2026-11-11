
from django.urls import path

from .consumers import SGRCrudConsumer


websocket_urlpatterns = [
    path(
        "ws/crud/",
        SGRCrudConsumer.as_asgi(),
        name="sgr_crud_websocket",
    ),
]
