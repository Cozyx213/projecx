from django.urls import path

from .views import explore_detail, explore_list

app_name = "explore"
urlpatterns = [
    path("", explore_list, name="list"),
    path("<int:pk>/", explore_detail, name="detail"),
]
