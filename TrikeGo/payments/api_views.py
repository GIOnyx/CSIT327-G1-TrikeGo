from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
import logging

from booking.models import Booking
from payments.utils import (
    generate_payment_pin,
    hash_payment_pin,
    verify_payment_pin,
    get_pin_expiry_time
)

logger = logging.getLogger(__name__)
try:
    from notifications.services import dispatch_notification, NotificationMessage
except Exception:
    dispatch_notification = None
    NotificationMessage = None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_payment_pin_endpoint(request, booking_id):
    """Generate a payment PIN for a completed trip (driver-only)."""
    booking = get_object_or_404(Booking, id=booking_id)

    if request.user.trikego_user != 'D' or booking.driver != request.user:
        return Response({'status': 'error', 'message': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if booking.status not in ['started', 'completed']:
        return Response({'status': 'error', 'message': 'Invalid booking status.'}, status=status.HTTP_400_BAD_REQUEST)

    if booking.payment_verified:
        return Response({'status': 'error', 'message': 'Payment already verified.'}, status=status.HTTP_400_BAD_REQUEST)

    if booking.is_pin_valid:
        # clear old pin and continue
        booking.payment_pin_hash = None
        booking.payment_pin_created_at = None
        booking.payment_pin_expires_at = None
        booking.payment_pin_attempts = 0
        booking.save(update_fields=['payment_pin_hash', 'payment_pin_created_at', 'payment_pin_expires_at', 'payment_pin_attempts'])

    pin = generate_payment_pin()
    pin_hash = hash_payment_pin(pin)
    expiry_time = get_pin_expiry_time(minutes=5)

    try:
        with transaction.atomic():
            booking_locked = Booking.objects.select_for_update().get(id=booking_id)
            booking_locked.payment_pin_hash = pin_hash
            booking_locked.payment_pin_created_at = timezone.now()
            booking_locked.payment_pin_expires_at = expiry_time
            booking_locked.payment_pin_attempts = 0
            booking_locked.save(update_fields=['payment_pin_hash', 'payment_pin_created_at', 'payment_pin_expires_at', 'payment_pin_attempts'])
    except Exception as e:
        logger.exception('Failed to save payment PIN')
        return Response({'status': 'error', 'message': 'Failed to save PIN.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Notify rider that a payment PIN was generated
    try:
        if dispatch_notification and NotificationMessage:
            note = NotificationMessage(
                title='Payment PIN Generated',
                body=f"A payment PIN has been generated for your trip #{booking.id}. Please enter it to verify payment.",
                data={'booking_id': booking.id, 'type': 'payment_pin_generated'},
            )
            dispatch_notification([booking.rider.id], note, topics=['rider'])
    except Exception:
        pass

    return Response({'status': 'success', 'pin': pin, 'expires_at': expiry_time.isoformat(), 'max_attempts': booking.payment_pin_max_attempts})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment_pin_endpoint(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.user.trikego_user != 'R' or booking.rider != request.user:
        return Response({'status': 'error', 'message': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    booking.refresh_from_db()
    if booking.payment_verified:
        return Response({'status': 'error', 'message': 'Already verified.'}, status=status.HTTP_400_BAD_REQUEST)

    if not booking.payment_pin_hash:
        return Response({'status': 'error', 'message': 'No PIN generated yet.'}, status=status.HTTP_400_BAD_REQUEST)

    if booking.payment_pin_expires_at and timezone.now() > booking.payment_pin_expires_at:
        return Response({'status': 'error', 'message': 'PIN expired.'}, status=status.HTTP_400_BAD_REQUEST)

    if booking.payment_pin_attempts >= booking.payment_pin_max_attempts:
        return Response({'status': 'error', 'message': 'Max attempts reached.'}, status=status.HTTP_400_BAD_REQUEST)

    pin = str(request.data.get('pin', '')).strip()
    if not pin.isdigit() or len(pin) != 4:
        return Response({'status': 'error', 'message': 'Invalid PIN format.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        booking_locked = Booking.objects.select_for_update().get(id=booking_id)
        if verify_payment_pin(pin, booking_locked.payment_pin_hash):
            booking_locked.payment_verified = True
            booking_locked.payment_verified_at = timezone.now()
            booking_locked.status = 'completed'
            booking_locked.end_time = timezone.now()
            booking_locked.save(update_fields=['payment_verified', 'payment_verified_at', 'status', 'end_time'])
            # Notify driver and rider that payment was verified
            try:
                if dispatch_notification and NotificationMessage:
                    rider_msg = NotificationMessage(
                        title='Payment Verified',
                        body=f"Payment for trip #{booking_locked.id} has been verified. Thank you!",
                        data={'booking_id': booking_locked.id, 'type': 'payment_verified'},
                    )
                    dispatch_notification([booking_locked.rider.id], rider_msg, topics=['rider'])

                    if booking_locked.driver:
                        driver_msg = NotificationMessage(
                            title='Payment Verified',
                            body=f"Payment for trip #{booking_locked.id} has been verified by the rider.",
                            data={'booking_id': booking_locked.id, 'type': 'payment_verified'},
                        )
                        dispatch_notification([booking_locked.driver.id], driver_msg, topics=['driver'])
            except Exception:
                pass

            return Response({'status': 'success', 'message': 'Payment verified.'})
        else:
            booking_locked.payment_pin_attempts += 1
            attempts_left = booking_locked.payment_pin_max_attempts - booking_locked.payment_pin_attempts
            booking_locked.save(update_fields=['payment_pin_attempts'])
            return Response({'status': 'error', 'message': 'Incorrect PIN.', 'attempts_remaining': attempts_left}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_pin_status(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.user not in [booking.rider, booking.driver]:
        return Response({'status': 'error', 'message': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    booking.refresh_from_db()
    return Response({
        'status': 'success',
        'pin_exists': bool(booking.payment_pin_hash),
        'pin_valid': booking.is_pin_valid,
        'payment_verified': booking.payment_verified,
        'expires_at': booking.payment_pin_expires_at.isoformat() if booking.payment_pin_expires_at else None,
        'attempts_remaining': booking.pin_attempts_remaining,
        'max_attempts': booking.payment_pin_max_attempts,
    })
