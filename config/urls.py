
"""
URLs principales del SGR.
Login, logout y dashboard viven en core.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # Aplicación principal.
    path("", include("core.urls")),

    # Aplicaciones del SGR.
    path(
        "organizations/",
        include("organizations.urls"),
    ),
    path(
        "catalogs/",
        include("catalogs.urls"),
    ),
    path(
        "measurement/",
        include("measurement.urls"),
    ),
    path(
        "activities/",
        include("activities.urls"),
    ),
    path(
        "agenda/",
        include("agenda.urls"),
    ),
    path(
        "solicitudes/",
        include("agenda.solicitudes_urls"),
    ),
    path(
        "social/",
        include("social.urls"),
    ),
    path(
        "audit/",
        include("audit.urls"),
    ),

    # API REST.
    path(
        "api/",
        include("sgr_api.urls"),
    ),
]


# Archivos multimedia durante desarrollo.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
