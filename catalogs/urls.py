from django.urls import path

from . import views

app_name = "catalogs"

urlpatterns = [
    path("elementos/", views.CatalogoListView.as_view(), name="catalogo_list"),
    path("elementos/nuevo/", views.CatalogoCreateView.as_view(), name="catalogo_create"),
    path("elementos/<int:pk>/editar/", views.CatalogoUpdateView.as_view(), name="catalogo_update"),
    path("elementos/<int:pk>/estado/", views.CatalogoToggleView.as_view(), name="catalogo_toggle"),
    path("api/por-area/", views.catalogo_por_area, name="catalogo_por_area"),
]
