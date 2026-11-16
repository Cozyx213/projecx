from django.urls import path

from . import views

app_name = "similarity"

urlpatterns = [
    path("", views.check_list, name="list"),
    path("<int:pk>/", views.check_detail, name="detail"),
    path("run/<int:project_pk>/", views.run, name="run"),
]
