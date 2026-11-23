from django.urls import path

from .views import settings, toggle_theme

app_name = "user_settings"
urlpatterns = [
    path("", settings, name="settings"),
    path("toggle-theme/", toggle_theme, name="toggle_theme"),
]
