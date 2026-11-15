
"""
URLs principales del SGR.
Login, logout y dashboard viven en core.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("organizations/", include("organizations.urls")),
    path("catalogs/", include("catalogs.urls")),
    path("measurement/", include("measurement.urls")),
    path("activities/", include("activities.urls")),
    path("agenda/", include("agenda.urls")),
    path("social/", include("social.urls")),
    path("audit/", include("audit.urls")),
]
