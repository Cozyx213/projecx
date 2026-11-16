from django.urls import path

from .views import settings

app_name = "user_settings"
urlpatterns = [path("", settings, name="settings")]
