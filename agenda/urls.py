from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.CompromisoListView.as_view(), name="compromiso_list"),
    path("nuevo/", views.CompromisoCreateView.as_view(), name="compromiso_create"),
    path("resumen/", views.resumen_colectivo, name="resumen"),
    path("<int:pk>/", views.CompromisoDetailView.as_view(), name="compromiso_detail"),
    path("<int:pk>/editar/", views.CompromisoUpdateView.as_view(), name="compromiso_update"),
    path("<int:pk>/estado/", views.CompromisoEstadoView.as_view(), name="compromiso_estado"),
    path("<int:pk>/reasignar/", views.CompromisoReasignarView.as_view(), name="compromiso_reasignar"),
    path("<int:pk>/historial/", views.CompromisoHistorialView.as_view(), name="historial"),
]
