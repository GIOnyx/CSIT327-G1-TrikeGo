from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import ChatMessage
from booking.models import Booking

# Import notification dispatcher
try:
    from notifications.services import dispatch_notification, NotificationMessage
except ImportError:
    dispatch_notification = None
    NotificationMessage = None


CHAT_ACTIVE_STATUSES = {'accepted', 'on_the_way', 'started'}
CHAT_READ_STATUSES = CHAT_ACTIVE_STATUSES | {'pending', 'completed'}


def _chat_can_read(booking):
    if booking.status not in CHAT_READ_STATUSES:
        return False
    if booking.status == 'pending' and booking.driver is None:
        return False
    return True


def _chat_can_post(booking):
    if booking.status in CHAT_ACTIVE_STATUSES:
        return True
    if booking.status == 'pending' and booking.driver is not None:
        return True
    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_messages(request, booking_id):
    """Return messages visible to everyone in the driver's active trip."""
    booking = get_object_or_404(Booking, id=booking_id)

    # Permission: only the rider tied to the booking, or the driver handling it.
    if request.user not in [booking.rider, booking.driver]:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    if not _chat_can_read(booking):
        return Response({'error': 'Chat not available for this booking status'}, status=status.HTTP_403_FORBIDDEN)

    # Determine the current trip scope: all active bookings with the same driver.
    if booking.driver:
        linked_ids = list(
            Booking.objects.filter(driver=booking.driver, status__in=CHAT_ACTIVE_STATUSES)
            .values_list('id', flat=True)
        )
        if booking.id not in linked_ids:
            linked_ids.append(booking.id)
        linked_bookings = Booking.objects.filter(id__in=linked_ids)
    else:
        linked_bookings = Booking.objects.filter(id=booking.id)

    messages = (
        ChatMessage.objects.filter(booking__in=linked_bookings)
        .select_related('booking', 'booking__rider', 'booking__driver', 'sender')
        .order_by('timestamp')
    )

    data = []
    for msg in messages:
        sender_display = msg.sender.get_full_name() or msg.sender.username
        trip_driver = msg.booking.driver
        sender_role = 'Driver' if trip_driver and msg.sender_id == trip_driver.id else 'Passenger'
        rider_name = msg.booking.rider.get_full_name() or msg.booking.rider.username if msg.booking.rider else 'Passenger'
        data.append({
            'id': msg.id,
            'message': msg.message,
            'timestamp': msg.timestamp.isoformat(),
            'sender_id': msg.sender.id,
            'sender_username': msg.sender.username,
            'sender_display_name': sender_display,
            'sender_role': sender_role,
            'booking_id': msg.booking_id,
            'booking_label': rider_name,
        })

    return Response({'messages': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_message(request, booking_id):
    """Create a message for a booking (only rider or driver may post)."""
    booking = get_object_or_404(Booking, id=booking_id)

    if request.user not in [booking.rider, booking.driver]:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    allowed_statuses = ['accepted', 'on_the_way', 'started']
    if not _chat_can_post(booking):
        return Response({'error': 'Chat not available for this booking status'}, status=status.HTTP_403_FORBIDDEN)

    message_text = (request.data.get('message') or '').strip()
    if not message_text:
        return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)

    msg = ChatMessage.objects.create(
        message=message_text,
        booking=booking,
        sender=request.user
    )

    # Send push notification to the other participant
    try:
        if dispatch_notification and NotificationMessage:
            recipients = set()
            if booking.rider and booking.rider.id != request.user.id:
                recipients.add(booking.rider.id)
            if booking.driver and booking.driver.id != request.user.id:
                recipients.add(booking.driver.id)
            
            if recipients:
                sender_name = request.user.get_full_name() or request.user.username
                notification_msg = NotificationMessage(
                    title=f'💬 {sender_name}',
                    body=message_text if len(message_text) < 240 else message_text[:236] + '...',
                    data={'booking_id': booking.id, 'type': 'chat_message', 'chat_id': msg.id},
                )
                dispatch_notification(list(recipients), notification_msg, topics=['rider', 'driver'])
    except Exception:
        pass  # Don't fail message creation if notification fails

    sender_display = msg.sender.get_full_name() or msg.sender.username
    sender_role = 'Driver' if booking.driver and msg.sender_id == booking.driver.id else 'Passenger'
    rider_name = booking.rider.get_full_name() or booking.rider.username if booking.rider else 'Passenger'

    return Response({
        'id': msg.id,
        'message': msg.message,
        'timestamp': msg.timestamp.isoformat(),
        'sender_id': msg.sender.id,
        'sender_username': msg.sender.username,
        'sender_display_name': sender_display,
        'sender_role': sender_role,
        'booking_id': msg.booking_id,
        'booking_label': rider_name,
    }, status=status.HTTP_201_CREATED)
