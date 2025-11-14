from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """Web push subscription metadata stored per user and device."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=512)
    auth = models.CharField(max_length=128)
    p256dh = models.CharField(max_length=128)
    user_agent = models.CharField(max_length=256, blank=True)
    topics = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'endpoint')
        indexes = [
            models.Index(fields=('user', 'is_active')),
            models.Index(fields=('is_active',)),
        ]

    def mark_failed(self) -> None:
        if self.is_active:
            self.is_active = False
            self.save(update_fields=['is_active', 'updated_at'])

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Subscription<{self.user_id}:{self.endpoint[:32]}>"
