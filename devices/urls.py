#	Ruta de la lista de dispositivos
#correccion eva2-n3
from django.urls import path

from . import views

app_name = "devices"

urlpatterns = [
    path("", views.device_list, name="device_list"),

    
]