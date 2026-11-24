
from django.urls import path

from . import views


urlpatterns = [
    # Listado y creación.
    path(
        "delegaciones/",
        views.delegacion_list,
        name="api_delegaciones",
    ),

    # Consulta y modificación.
    path(
        "delegaciones/<int:pk>/",
        views.delegacion_detail,
        name="api_delegacion_detail",
    ),

    # Consulta y cambio de estado.
    path(
        "delegaciones/<int:pk>/estado/",
        views.delegacion_estado,
        name="api_delegacion_estado",
    ),
]
