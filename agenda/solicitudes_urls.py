from django.urls import path
from . import solicitudes_views as views

app_name = "solicitudes"
urlpatterns = [
    path("nueva/", views.solicitud_publica, name="publica"),
    path("verificar-tutor/", views.verificar_tutor, name="verificar_tutor"),
    path("verificar-menor/", views.verificar_menor, name="verificar_menor"),
    path("", views.lista_solicitudes, name="lista"),
    path("exportar-excel/", views.exportar_solicitudes, name="exportar_excel"),
    path("<int:pk>/", views.detalle_solicitud, name="detalle"),
    path("<int:pk>/actualizar/", views.actualizar_solicitud, name="actualizar"),
    path("<int:pk>/eventos/", views.agregar_evento_solicitud, name="evento"),
]
