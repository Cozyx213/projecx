from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_form, name="new"),
    path("<int:pk>/edit/", views.project_form, name="edit"),
]
