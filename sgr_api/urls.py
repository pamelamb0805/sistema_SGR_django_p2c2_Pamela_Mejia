
from django.urls import path

from . import views


urlpatterns = [
    # Delegaciones.
    path(
        "delegaciones/",
        views.delegacion_list,
        name="api_delegaciones",
    ),
    path(
        "delegaciones/<int:pk>/",
        views.delegacion_detail,
        name="api_delegacion_detail",
    ),
    path(
        "delegaciones/<int:pk>/estado/",
        views.delegacion_estado,
        name="api_delegacion_estado",
    ),

    # Roles.
    path(
        "roles/",
        views.rol_list,
        name="api_roles",
    ),
    path(
        "roles/<int:pk>/",
        views.rol_detail,
        name="api_rol_detail",
    ),
]
