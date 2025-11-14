import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from django.conf import settings
from django.utils import timezone

from .models import PushSubscription


def _get_send_push_task():
    from .tasks import send_push_message_task  # Local import to avoid circular dependency

    return send_push_message_task


@dataclass(slots=True)
class NotificationMessage:
    """Normalized payload for web push messages."""

    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    icon: Optional[str] = None
    badge: Optional[str] = None
    tag: Optional[str] = None
    require_interaction: bool = False
    silent: bool = False

    def as_payload(self) -> Dict[str, Any]:
        payload = {
            'title': self.title,
            'options': {
                'body': self.body,
                'data': self.data,
                'requireInteraction': self.require_interaction,
                'silent': self.silent,
            },
        }
        icon = self.icon or getattr(settings, 'PUSH_NOTIFICATION_DEFAULT_ICON', None)
        if icon:
            payload['options']['icon'] = icon
        if self.badge:
            payload['options']['badge'] = self.badge
        if self.tag:
            payload['options']['tag'] = self.tag
        return payload


def _filter_subscriptions(
    user_ids: Sequence[int],
    topics: Optional[Sequence[str]] = None,
    include_global: bool = True,
) -> List[PushSubscription]:
    if not user_ids:
        return []

    topic_set: Set[str] = set(topics or [])
    subscriptions = list(
        PushSubscription.objects.filter(
            user_id__in=user_ids,
            is_active=True,
        )
    )

    if topic_set:
        filtered: List[PushSubscription] = []
        for sub in subscriptions:
            topics_list = sub.topics or []
            if not topics_list and include_global:
                filtered.append(sub)
                continue
            if 'all' in topics_list:
                filtered.append(sub)
                continue
            if any(topic in topic_set for topic in topics_list):
                filtered.append(sub)
        return filtered

    return subscriptions


def dispatch_notification(
    user_ids: Sequence[int],
    message: NotificationMessage,
    *,
    topics: Optional[Sequence[str]] = None,
    ttl: int = 180,
    collapse_key: Optional[str] = None,
    urgency: str = 'normal',
) -> int:
    """Queue push notifications for all matching subscriptions.

    Returns the number of queued messages.
    """

    if not getattr(settings, 'PUSH_NOTIFICATIONS_ENABLED', False):
        return 0

    subscriptions = _filter_subscriptions(user_ids, topics)
    if not subscriptions:
        return 0

    payload = message.as_payload()
    payload_json = json.dumps(payload)

    queued = 0
    send_task = _get_send_push_task()
    for subscription in subscriptions:
        send_task.delay(
            subscription_id=subscription.id,
            payload_json=payload_json,
            ttl=ttl,
            collapse_key=collapse_key,
            urgency=urgency,
        )
        queued += 1
    return queued


def touch_subscription_success(subscription_id: int) -> None:
    PushSubscription.objects.filter(id=subscription_id).update(
        last_success_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True,
    )


def deactivate_subscription(subscription_id: int) -> None:
    PushSubscription.objects.filter(id=subscription_id).update(
        is_active=False,
        updated_at=timezone.now(),
    )
