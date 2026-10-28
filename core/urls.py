from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
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
]