from django.urls import path

from . import views

app_name = "measurement"

urlpatterns = [
    # Períodos
    path("periodos/", views.PeriodoListView.as_view(), name="periodo_list"),
    path("periodos/nuevo/", views.PeriodoCreateView.as_view(), name="periodo_create"),
    path("periodos/<int:pk>/", views.PeriodoDetailView.as_view(), name="periodo_detail"),
    path("periodos/<int:pk>/editar/", views.PeriodoUpdateView.as_view(), name="periodo_update"),
    path("periodos/<int:pk>/cerrar/", views.PeriodoCerrarView.as_view(), name="periodo_cerrar"),
    path("periodos/<int:pk>/reabrir/", views.PeriodoReabrirView.as_view(), name="periodo_reabrir"),
    path("periodos/<int:pk>/recalcular/", views.PeriodoRecalcularView.as_view(), name="periodo_recalcular"),

    # Metas
    path("metas/", views.MetaListView.as_view(), name="meta_list"),
    path("metas/nueva/", views.MetaCreateView.as_view(), name="meta_create"),
    path("metas/<int:pk>/editar/", views.MetaUpdateView.as_view(), name="meta_update"),
    path("metas/<int:pk>/eliminar/", views.MetaDeleteView.as_view(), name="meta_delete"),

    # Ajustes
    path("ajustes/", views.AjusteListView.as_view(), name="ajuste_list"),
    path("ajustes/nuevo/", views.AjusteCreateView.as_view(), name="ajuste_create"),
    path("ajustes/<int:pk>/eliminar/", views.AjusteDeleteView.as_view(), name="ajuste_delete"),

    # Desempeño y semáforo
    path("mi-desempeno/", views.mi_desempeno, name="mi_desempeno"),
    path("desempeno/<int:pk>/", views.desempeno_funcionario, name="desempeno_funcionario"),
    path("semaforo/", views.semaforo, name="semaforo"),
]
