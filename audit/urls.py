from django.urls import path

from . import views

app_name = "audit"

urlpatterns = [
    path("", views.AuditoriaListView.as_view(), name="auditoria_list"),
    path("exportar/", views.AuditoriaExportarView.as_view(), name="auditoria_exportar"),
    path("evento/<int:pk>/", views.AuditoriaDetailView.as_view(), name="auditoria_detail"),
    path("historial/<str:entidad>/<int:pk>/", views.HistorialEntidadView.as_view(), name="entidad_historial"),
]
