from django.apps import AppConfig


class TrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracking_app'
    label = 'tracking'
    verbose_name = 'Tracking & Routing'
