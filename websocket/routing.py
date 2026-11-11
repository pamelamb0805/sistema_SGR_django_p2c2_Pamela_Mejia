
from django.urls import path

from .consumers import SGRConsumer


websocket_urlpatterns = [
    path("ws/sgr/", SGRConsumer.as_asgi()),
]
