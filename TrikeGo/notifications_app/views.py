from typing import Any, Dict
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PushSubscription
from .serializers import PushSubscriptionSerializer
from .services import NotificationMessage, dispatch_notification


class PushSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        payload: Dict[str, Any] = request.data.copy()
        payload.setdefault('user_agent', request.META.get('HTTP_USER_AGENT', '')[:256])

        serializer = PushSubscriptionSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            subscription = serializer.save(user=request.user)

        return Response(
            {
                'id': subscription.id,
                'endpoint': subscription.endpoint,
                'topics': subscription.topics,
                'is_active': subscription.is_active,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, *args, **kwargs):
        endpoint = request.data.get('endpoint') or request.query_params.get('endpoint')
        if not endpoint:
            return Response({'detail': 'endpoint is required.'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        if deleted == 0:
            return Response({'detail': 'Subscription not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_vapid_key(request):
    """Return the VAPID public key from settings. This is publicly accessible by design."""
    public_key = getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '') or ''
    return Response({'public_key': public_key})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unsubscribe(request):
    endpoint = request.data.get('endpoint')
    if not endpoint:
        return Response({'detail': 'endpoint is required.'}, status=status.HTTP_400_BAD_REQUEST)

    deleted, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    if deleted == 0:
        return Response({'detail': 'Subscription not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)


# This endpoint is intended to be called from the ServiceWorker where CSRF headers
# may not be available. We accept the subscription POST from the SW and associate
# it to the currently authenticated user via session cookie. CSRF is skipped here
# because the SW cannot read the CSRF cookie; ensure HTTPS and session security.
@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sw_subscribe(request):
    payload: Dict[str, Any] = request.data.copy()
    payload.setdefault('user_agent', request.META.get('HTTP_USER_AGENT', '')[:256])

    serializer = PushSubscriptionSerializer(data=payload)
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        subscription = serializer.save(user=request.user)

    return Response({'id': subscription.id, 'endpoint': subscription.endpoint}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def send_test_notification(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'detail': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    title = request.data.get('title', 'Test notification')
    body = request.data.get('body', 'This is a test notification')
    data = request.data.get('data', {})

    message = NotificationMessage(title=title, body=body, data=data)
    queued = dispatch_notification([user_id], message, topics=request.data.get('topics'))

    return Response({'queued': queued})
