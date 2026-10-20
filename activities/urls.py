from django.urls import path

from . import views

app_name = "activities"

urlpatterns = [
    # Actividades
    path("", views.ActividadListView.as_view(), name="actividad_list"),
    path("nueva/", views.ActividadCreateView.as_view(), name="actividad_create"),
    path("codigo/", views.buscar_codigo, name="buscar_codigo"),
    path("<int:pk>/", views.ActividadDetailView.as_view(), name="actividad_detail"),
    path("<int:pk>/editar/", views.ActividadUpdateView.as_view(), name="actividad_update"),
    path("<int:pk>/anular/", views.ActividadAnularView.as_view(), name="actividad_anular"),

    # Evidencias
    path("<int:pk>/evidencias/nueva/", views.EvidenciaCreateView.as_view(), name="evidencia_create"),
    path("evidencias/<int:pk>/archivo/", views.evidencia_archivo, name="evidencia_archivo"),

    # Validación
    path("validaciones/", views.ValidacionBandejaView.as_view(), name="validacion_bandeja"),
    path("evidencias/<int:pk>/validar/", views.ValidacionCreateView.as_view(), name="validacion_create"),
]
