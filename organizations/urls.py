
from django.urls import path

from . import views

app_name = "organizations"

urlpatterns = [
    # Delegaciones
    path(
        "delegaciones/",
        views.DelegacionListView.as_view(),
        name="delegacion_list",
    ),
    path(
        "delegaciones/nueva/",
        views.DelegacionCreateView.as_view(),
        name="delegacion_create",
    ),
    path(
        "delegaciones/<int:pk>/editar/",
        views.DelegacionUpdateView.as_view(),
        name="delegacion_update",
    ),
    path(
        "delegaciones/<int:pk>/estado/",
        views.DelegacionToggleView.as_view(),
        name="delegacion_toggle",
    ),

    # Cargos e ítems medibles
    path(
        "cargos/",
        views.CargoListView.as_view(),
        name="cargo_list",
    ),
    path(
        "cargos/nuevo/",
        views.CargoCreateView.as_view(),
        name="cargo_create",
    ),
    path(
        "cargos/<int:pk>/",
        views.CargoDetailView.as_view(),
        name="cargo_detail",
    ),
    path(
        "cargos/<int:pk>/editar/",
        views.CargoUpdateView.as_view(),
        name="cargo_update",
    ),
    path(
        "cargos/<int:pk>/eliminar/",
        views.CargoDeleteView.as_view(),
        name="cargo_delete",
    ),
    path(
        "cargos/<int:pk>/items/nuevo/",
        views.ItemCreateView.as_view(),
        name="item_create",
    ),
    path(
        "items/<int:pk>/vigencia/",
        views.ItemToggleView.as_view(),
        name="item_toggle",
    ),

    # Roles
    path(
        "roles/",
        views.RolListView.as_view(),
        name="rol_list",
    ),
    path(
        "roles/nuevo/",
        views.RolCreateView.as_view(),
        name="rol_create",
    ),
    path(
        "roles/<int:pk>/editar/",
        views.RolUpdateView.as_view(),
        name="rol_update",
    ),
    path(
        "roles/<int:pk>/eliminar/",
        views.RolDeleteView.as_view(),
        name="rol_delete",
    ),

    # Funcionarios
    path(
        "funcionarios/",
        views.FuncionarioListView.as_view(),
        name="funcionario_list",
    ),
    path(
        "funcionarios/nuevo/",
        views.FuncionarioCreateView.as_view(),
        name="funcionario_create",
    ),
    path(
        "funcionarios/<int:pk>/",
        views.FuncionarioDetailView.as_view(),
        name="funcionario_detail",
    ),
    path(
        "funcionarios/<int:pk>/editar/",
        views.FuncionarioUpdateView.as_view(),
        name="funcionario_update",
    ),
    path(
        "funcionarios/<int:pk>/estado/",
        views.FuncionarioToggleView.as_view(),
        name="funcionario_toggle",
    ),
    path(
        "funcionarios/<int:pk>/acceso/",
        views.FuncionarioAccesoView.as_view(),
        name="funcionario_acceso",
    ),

    # Usuarios
    path(
        "usuarios/",
        views.UsuarioListView.as_view(),
        name="usuario_list",
    ),
    path(
        "usuarios/nuevo/",
        views.UsuarioCreateView.as_view(),
        name="usuario_create",
    ),
    path(
        "usuarios/<int:pk>/editar/",
        views.UsuarioUpdateView.as_view(),
        name="usuario_update",
    ),
    path(
        "usuarios/<int:pk>/estado/",
        views.UsuarioToggleView.as_view(),
        name="usuario_toggle",
    ),
]
