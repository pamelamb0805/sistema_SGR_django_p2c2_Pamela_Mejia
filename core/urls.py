from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

# Sin app_name: settings.py usa los nombres 'login' y 'dashboard' directamente.
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.SGRLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),  # solo acepta POST
]
