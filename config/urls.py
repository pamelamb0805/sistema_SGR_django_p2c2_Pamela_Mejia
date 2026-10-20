"""
URLs principales del SGR.
Login, logout y dashboard viven en core (templates/registration/login.html
y templates/core/dashboard.html).
"""
from django.conf import settings
from django.conf.urls.static import static
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

# Las evidencias solo se sirven directamente en desarrollo.
# En producción deben entregarse mediante una vista con control de acceso.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
