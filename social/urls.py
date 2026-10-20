from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("", views.CasoListView.as_view(), name="caso_list"),
    path("nuevo/", views.CasoCreateView.as_view(), name="caso_create"),
    path("estadisticas/", views.estadisticas, name="estadisticas"),
    path("<int:pk>/", views.CasoDetailView.as_view(), name="caso_detail"),
    path("<int:pk>/editar/", views.CasoUpdateView.as_view(), name="caso_update"),
    path("<int:pk>/estado/", views.CasoEstadoView.as_view(), name="caso_estado"),
    path("<int:pk>/gestiones/nueva/", views.GestionCreateView.as_view(), name="gestion_create"),
    path("gestiones/<int:pk>/editar/", views.GestionUpdateView.as_view(), name="gestion_update"),
]
