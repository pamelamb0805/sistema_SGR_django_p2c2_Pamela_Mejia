from django.urls import path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # API REST
    path("api/", include("sgr_api.urls")),

    # Aplicaciones del SGR
    path("", include("core.urls")),
    path("organizations/", include("organizations.urls")),
    path("catalogs/", include("catalogs.urls")),
    path("measurement/", include("measurement.urls")),
    path("activities/", include("activities.urls")),
    path("agenda/", include("agenda.urls")),
    path("solicitudes/", include("agenda.solicitudes_urls")),
    path("social/", include("social.urls")),
    path("audit/", include("audit.urls")),
]
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