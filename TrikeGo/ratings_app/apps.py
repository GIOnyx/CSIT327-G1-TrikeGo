from django.apps import AppConfig


class RatingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ratings_app'
    label = 'ratings'
    verbose_name = 'Ratings & Feedback'
