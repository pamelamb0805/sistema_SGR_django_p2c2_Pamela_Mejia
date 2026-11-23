from django.urls import path

from . import views


urlpatterns = [
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
]