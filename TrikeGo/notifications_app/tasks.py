import logging
from typing import Optional
import requests

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)


def is_wns_endpoint(endpoint: str) -> bool:
    """Check if endpoint is Windows Notification Service"""
    return 'notify.windows.com' in endpoint.lower()


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def send_push_message_task(
    self,
    *,
    subscription_id: int,
    payload_json: str,
    ttl: int = 180,
    collapse_key: Optional[str] = None,
    urgency: str = 'normal',
) -> None:
    subscription = PushSubscription.objects.filter(id=subscription_id, is_active=True).first()
    if not subscription:
        logger.debug("Push subscription %s no longer active; skipping", subscription_id)
        return

    payload_bytes = payload_json.encode('utf-8')

    # WNS (Windows Notification Service) doesn't support VAPID, handle separately
    if is_wns_endpoint(subscription.endpoint):
        logger.warning(
            'WNS (Windows) endpoint detected for subscription %s. '
            'WNS requires Microsoft OAuth authentication which is not yet implemented. '
            'Skipping push notification. Use Android/Chrome for push notifications.',
            subscription_id
        )
        # Mark as inactive or don't retry WNS for now
        return

    # For FCM and other VAPID-supporting services
    try:
        logger.info('Sending webpush with VAPID to subscription id=%s endpoint=%s', subscription_id, subscription.endpoint[:80])
        if not settings.WEBPUSH_VAPID_PRIVATE_KEY:
            logger.warning('WEBPUSH_VAPID_PRIVATE_KEY appears empty. WebPush may fail. Check environment configuration.')
        vapid_claims = {}
        if settings.WEBPUSH_VAPID_CLAIM_EMAIL:
            vapid_claims['sub'] = f"mailto:{settings.WEBPUSH_VAPID_CLAIM_EMAIL}"

        headers = {'Urgency': urgency}
        if collapse_key:
            headers['Topic'] = collapse_key

        response = webpush(
            subscription_info={
                'endpoint': subscription.endpoint,
                'keys': {
                    'p256dh': subscription.p256dh,
                    'auth': subscription.auth,
                },
            },
            data=payload_bytes,
            vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            ttl=ttl,
            headers=headers,
        )
        if hasattr(response, 'status_code') and response.status_code in (404, 410):
            subscription.is_active = False
            subscription.save(update_fields=['is_active', 'updated_at'])
            logger.info("Marked subscription %s inactive due to %s", subscription_id, response.status_code)
            return

        subscription.last_success_at = timezone.now()
        subscription.is_active = True
        subscription.save(update_fields=['last_success_at', 'is_active', 'updated_at'])
    except WebPushException as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        resp = getattr(exc, 'response', None)
        resp_text = None
        try:
            resp_text = getattr(resp, 'text', None) or (resp.content.decode('utf-8') if getattr(resp, 'content', None) else None)
        except Exception:
            resp_text = None

        if status in (404, 410):
            subscription.is_active = False
            subscription.save(update_fields=['is_active', 'updated_at'])
            logger.info("Deactivated subscription %s after WebPush status %s", subscription_id, status)
            return
        # If the push service returned 401 (Unauthorized) it's usually a VAPID/signature issue
        # Log full response for debugging and avoid infinite retries for auth failures.
        if status == 401:
            logger.error("WebPush 401 for subscription %s. Response: %s", subscription_id, resp_text)
            # Do NOT retry since this is likely a configuration (VAPID key) problem.
            return

        logger.warning("WebPushException for subscription %s: %s; response=%s", subscription_id, exc, resp_text)
        raise self.retry(exc=exc)
    except Exception as exc:  # pragma: no cover - fallback for unexpected transport errors
        logger.exception("Unexpected push error for subscription %s", subscription_id)
        raise self.retry(exc=exc)
