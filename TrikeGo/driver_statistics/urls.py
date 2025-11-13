from django.urls import path

from . import views

app_name = "driver_statistics"

urlpatterns = [
    path("api/driver/summary/", views.driver_statistics_summary, name="driver_statistics_summary"),
]
