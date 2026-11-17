
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
from .dashboard_details import dashboard_detalle

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("contexto/delegacion/", views.cambiar_delegacion_activa, name="cambiar_delegacion_activa"),

    path(
        "alertas/<int:pk>/atendida/",
        views.marcar_alerta_atendida,
        name="marcar_alerta_atendida",
    ),

    path("login/", views.SGRLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("registro/", views.registro, name="registro"),

    path(
        "recuperar-clave/",
        views.recuperar_clave,
        name="recuperar_clave",
    ),
    path(
        "validar-codigo/",
        views.validar_codigo,
        name="validar_codigo",
    ),
    path(
        "nueva-clave/",
        views.nueva_clave,
        name="nueva_clave",
    ),

    path("perfil/", views.perfil, name="perfil"),
    path(
        "perfil/editar/",
        views.perfil_editar,
        name="perfil_editar",
    ),

    path(
        "dashboard/detalle/",
        dashboard_detalle,
        name="dashboard_detalle",
    ),
]
