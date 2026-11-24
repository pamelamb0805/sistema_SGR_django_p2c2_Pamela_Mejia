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

    # Usuarios y accesos.
    path(
        "usuarios/",
        views.usuario_list,
        name="api_usuarios",
    ),
    path(
        "usuarios/<int:pk>/",
        views.usuario_detail,
        name="api_usuario_detail",
    ),
    path(
        "usuarios/<int:pk>/estado/",
        views.usuario_estado,
        name="api_usuario_estado",
    ),
    path(
        "usuarios/<int:pk>/contrasenia/",
        views.usuario_contrasenia,
        name="api_usuario_contrasenia",
    ),

        # Ítems medibles.
    path(
        "items/",
        views.item_list,
        name="api_items",
    ),
    path(
        "items/<int:pk>/",
        views.item_detail,
        name="api_item_detail",
    ),
    path(
        "items/<int:pk>/vigencia/",
        views.item_vigencia,
        name="api_item_vigencia",
    ),


    # Metas.
    path(
        "metas/",
        views.meta_list,
        name="api_metas",
    ),
    path(
        "metas/<int:pk>/",
        views.meta_detail,
        name="api_meta_detail",
    ),

]