
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

    # Funcionarios.
    path(
        "funcionarios/",
        views.funcionario_list,
        name="api_funcionarios",
    ),
    path(
        "funcionarios/<int:pk>/",
        views.funcionario_detail,
        name="api_funcionario_detail",
    ),
    path(
        "funcionarios/<int:pk>/estado/",
        views.funcionario_estado,
        name="api_funcionario_estado",
    ),
]
