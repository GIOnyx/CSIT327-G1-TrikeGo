from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications_app'
    label = 'notifications'
    verbose_name = 'Web Push Notifications'

    def ready(self) -> None:
        # Import signal handlers when app is ready (lazy import to avoid circular deps)
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Signals are optional; ignore import errors to keep startup resilient.
            pass
