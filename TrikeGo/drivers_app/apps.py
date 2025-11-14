from django.apps import AppConfig


class DriversConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'drivers_app'
    label = 'drivers'
    verbose_name = 'Driver Profiles & Vehicles'
