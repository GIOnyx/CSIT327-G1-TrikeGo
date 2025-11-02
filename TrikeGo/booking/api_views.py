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

from .models import DriverLocation, Booking, RouteSnapshot, BookingStop
from .services import RoutingService
from .utils import (
    build_driver_itinerary, 
    ensure_booking_stops, 
    plan_driver_stops, 
    calculate_distance,
    generate_payment_pin,
    hash_payment_pin,
    verify_payment_pin,
    get_pin_expiry_time
)
from user.models import Driver, Rider

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_driver_location(request):
    """Update driver's current location"""
    if request.user.trikego_user != 'D':
        return Response({'error': 'Only drivers can update location'}, status=status.HTTP_403_FORBIDDEN)
    
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')
    heading = request.data.get('heading')
    speed = request.data.get('speed')
    accuracy = request.data.get('accuracy')
    
    if not latitude or not longitude:
        return Response({'error': 'Latitude and longitude required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update or create driver location
    location, created = DriverLocation.objects.update_or_create(
        driver=request.user,
        defaults={
            'latitude': Decimal(str(latitude)),
            'longitude': Decimal(str(longitude)),
            'heading': Decimal(str(heading)) if heading else None,
            'speed': Decimal(str(speed)) if speed else None,
            'accuracy': Decimal(str(accuracy)) if accuracy else None,
        }
    )
    
    # Check for active bookings and reroute if needed
    active_bookings = Booking.objects.filter(
        driver=request.user,
        status__in=['accepted', 'on_the_way', 'started']
    )

    for active_booking in active_bookings:
        check_and_reroute(active_booking, location)
    
    return Response({
        'status': 'success',
        'location': {
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'timestamp': location.timestamp.isoformat()
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_driver_location(request, booking_id):
    """Get driver's current location for a booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permissions
    if request.user not in [booking.rider, booking.driver]:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    if not booking.driver:
        return Response({'error': 'No driver assigned'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        location = DriverLocation.objects.get(driver=booking.driver)
        
        # Calculate ETA if rider is requesting
        eta_seconds = None
        if request.user == booking.rider:
            routing_service = RoutingService()
            
            if booking.status == 'accepted' or booking.status == 'on_the_way':
                # ETA to pickup
                destination = (float(booking.pickup_longitude), float(booking.pickup_latitude))
            else:
                # ETA to destination
                destination = (float(booking.destination_longitude), float(booking.destination_latitude))
            
            eta_seconds = routing_service.get_eta(location, destination)
        
        return Response({
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'heading': float(location.heading) if location.heading else None,
            'speed': float(location.speed) if location.speed else None,
            'timestamp': location.timestamp.isoformat(),
            'eta_seconds': eta_seconds
        })
    except DriverLocation.DoesNotExist:
        return Response({'error': 'Driver location not available'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_route(request, booking_id):
    """Get current active route for a booking"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permissions
    if request.user not in [booking.rider, booking.driver]:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    route = RouteSnapshot.objects.filter(booking=booking, is_active=True).first()
    
    if not route:
        return Response({'error': 'No active route found'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'route_data': route.route_data,
        'distance': float(route.distance),
        'duration': route.duration,
        'created_at': route.created_at.isoformat()
    })


def check_and_reroute(booking, driver_location):
    """Check if rerouting is needed and perform reroute"""
    routing_service = RoutingService()
    
    # Get current active route
    current_route = RouteSnapshot.objects.filter(booking=booking, is_active=True).first()
    
    # Check if rerouting is needed
    if routing_service.should_reroute(driver_location, current_route):
        print(f"Rerouting needed for booking {booking.id}")
        
        # Determine destination based on status
        if booking.status in ['accepted', 'on_the_way']:
            destination = (float(booking.pickup_longitude), float(booking.pickup_latitude))
        else:
            destination = (float(booking.destination_longitude), float(booking.destination_latitude))
        
        # Calculate new route
        start = (float(driver_location.longitude), float(driver_location.latitude))
        new_route = routing_service.calculate_route(start, destination)
        
        if new_route:
            # Save new route
            routing_service.save_route_snapshot(booking, new_route)
            
            # Update booking estimates
            booking.estimated_distance = Decimal(str(new_route['distance']))
            booking.estimated_duration = new_route['duration'] // 60  # Convert to minutes
            booking.estimated_arrival = timezone.now() + timedelta(seconds=new_route['duration'])
            booking.save()
            
            print(f"New route saved. Distance: {new_route['distance']}km, Duration: {new_route['duration']}s")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_reroute(request, booking_id):
    """Manually trigger a reroute"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.user != booking.driver:
        return Response({'error': 'Only the assigned driver can reroute'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        location = DriverLocation.objects.get(driver=request.user)
        check_and_reroute(booking, location)
        
        return Response({'status': 'success', 'message': 'Route recalculated'})
    except DriverLocation.DoesNotExist:
        return Response({'error': 'Driver location not available'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def driver_itinerary(request):
    """Return the consolidated itinerary for the authenticated driver."""
    if request.user.trikego_user != 'D':
        return Response({'error': 'Only drivers can access the itinerary.'}, status=status.HTTP_403_FORBIDDEN)

    active_bookings = Booking.objects.filter(
        driver=request.user,
        status__in=['accepted', 'on_the_way', 'started']
    )

    for booking in active_bookings:
        ensure_booking_stops(booking)

    payload = build_driver_itinerary(request.user)
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_itinerary_stop(request):
    """Mark a specific itinerary stop as completed and refresh the driver's itinerary."""
    if request.user.trikego_user != 'D':
        return Response({'error': 'Only drivers can update itinerary stops.'}, status=status.HTTP_403_FORBIDDEN)

    stop_id = request.data.get('stopId') or request.data.get('stop_id')
    if not stop_id:
        return Response({'error': 'stopId is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        stop = BookingStop.objects.select_related('booking', 'booking__rider').get(
            stop_uid=stop_id,
            booking__driver=request.user,
            booking__status__in=['accepted', 'on_the_way', 'started']
        )
    except BookingStop.DoesNotExist:
        return Response({'error': 'Stop not found or already completed.'}, status=status.HTTP_404_NOT_FOUND)

    if stop.status == 'COMPLETED':
        return Response({'status': 'success', 'message': 'Stop already completed.', 'itinerary': build_driver_itinerary(request.user)['itinerary']})

    # TEMPORARILY DISABLED FOR TESTING - Check if driver is within 10 meters of the stop location
    # TODO: Re-enable this proximity check after testing PIN feature
    # try:
    #     driver_profile = Driver.objects.get(user=request.user)
    #     driver_lat = driver_profile.current_latitude
    #     driver_lon = driver_profile.current_longitude
    #     stop_lat = stop.latitude
    #     stop_lon = stop.longitude
    #     
    #     if driver_lat and driver_lon and stop_lat and stop_lon:
    #         distance_km = calculate_distance(
    #             float(driver_lat), float(driver_lon),
    #             float(stop_lat), float(stop_lon)
    #         )
    #         distance_meters = distance_km * 1000
    #         
    #         if distance_meters > 10:
    #             return Response({
    #                 'error': f'You must be within 10 meters of the {stop.stop_type.lower()} location. You are currently {distance_meters:.1f}m away.',
    #                 'distance': distance_meters,
    #                 'required': 10
    #             }, status=status.HTTP_400_BAD_REQUEST)
    # except Driver.DoesNotExist:
    #     pass  # If driver profile doesn't exist, skip proximity check
    # except Exception as e:
    #     print(f"Proximity check error: {e}")
    #     pass  # Don't block on proximity check errors

    stop.status = 'COMPLETED'
    stop.completed_at = timezone.now()
    stop.save(update_fields=['status', 'completed_at', 'updated_at'])

    booking = stop.booking

    if stop.stop_type == 'PICKUP':
        if booking.status != 'started':
            booking.status = 'started'
            booking.start_time = booking.start_time or timezone.now()
            booking.save(update_fields=['status', 'start_time'])
    else:  # dropoff
        booking.status = 'completed'
        booking.end_time = timezone.now()
        booking.save(update_fields=['status', 'end_time'])

        # Reset rider availability
        Rider.objects.filter(user=booking.rider).update(status='Available')

    # If all bookings completed, set driver status to online
    remaining_stops = BookingStop.objects.filter(
        booking__driver=request.user,
        status__in=['UPCOMING', 'CURRENT'],
        booking__status__in=['accepted', 'on_the_way', 'started']
    )

    if remaining_stops.exists():
        Driver.objects.filter(user=request.user).update(status='In_trip')
    else:
        Driver.objects.filter(user=request.user).update(status='Online')

    # Ensure pick/drop pair consistency – if dropoff completed, mark booking rider status handled above
    plan_driver_stops(request.user)

    payload = build_driver_itinerary(request.user)
    
    # Check if this was a dropoff completion and add completed booking info for payment modal
    if stop.stop_type == 'DROPOFF':
        # Get all recently completed bookings that need payment verification
        completed_bookings_qs = (
            Booking.objects
            .filter(
                driver=request.user,
                status='completed',
                payment_verified=False
            )
            .order_by('-end_time', '-id')
            .values('id', 'fare')
        )

        completed_bookings = list(completed_bookings_qs)

        if completed_bookings:
            payload['completedBookings'] = completed_bookings
            payload['showPaymentModal'] = True
            payload['paymentModalBookingId'] = stop.booking_id
    
    return Response(payload)


# ============================================================================
# Payment PIN Verification Endpoints
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_payment_pin_endpoint(request, booking_id):
    """
    Generate a payment verification PIN for a completed trip.
    Only the assigned driver can generate the PIN.
    
    Expected request body: {} (no parameters needed)
    
    Returns:
        200: {
            'status': 'success',
            'pin': '1234',
            'expires_at': '2025-11-01T12:30:00Z',
            'max_attempts': 3
        }
        
        400: PIN already exists and is still valid
        403: Not the assigned driver
        404: Booking not found
    """
    logger.info(f"=== PIN GENERATION REQUEST for booking {booking_id} by user {request.user.username} ===")
    
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only the assigned driver can generate PIN
    if request.user.trikego_user != 'D':
        return Response({
            'status': 'error',
            'message': 'Only drivers can generate payment PINs.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if booking.driver != request.user:
        return Response({
            'status': 'error',
            'message': 'You are not the assigned driver for this booking.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if booking is in a completable state (either started or completed)
    logger.info(f"PIN generation request for booking {booking_id}: status={booking.status}, driver={booking.driver}, payment_verified={booking.payment_verified}")
    
    if booking.status not in ['started', 'completed']:
        logger.warning(f"PIN generation rejected for booking {booking_id}: invalid status {booking.status}")
        return Response({
            'status': 'error',
            'message': f'Cannot generate PIN. Booking must be started or completed, current status: {booking.status}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if already verified
    if booking.payment_verified:
        return Response({
            'status': 'error',
            'message': 'Payment already verified for this booking.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if valid PIN already exists
    # Since PINs are hashed, we can't retrieve the original PIN
    # So if one exists and is still valid, we need to inform the user
    # But for auto-generation after dropoff, we should allow regeneration
    # by clearing the old PIN first
    if booking.is_pin_valid:
        # Check if this is a recent PIN (less than 30 seconds old)
        # If so, likely a duplicate request - return error
        if booking.payment_pin_created_at:
            time_since_creation = (timezone.now() - booking.payment_pin_created_at).total_seconds()
            if time_since_creation < 30:
                return Response({
                    'status': 'error',
                    'message': 'A valid PIN was just generated. Please wait or use the existing PIN.',
                    'expires_at': booking.payment_pin_expires_at.isoformat(),
                    'attempts_remaining': booking.pin_attempts_remaining
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Old PIN exists, clear it and generate new one
        logger.info(f"Clearing old PIN for booking {booking_id} to generate new one")
        booking.payment_pin_hash = None
        booking.payment_pin_created_at = None
        booking.payment_pin_expires_at = None
        booking.payment_pin_attempts = 0
        booking.save(update_fields=[
            'payment_pin_hash',
            'payment_pin_created_at',
            'payment_pin_expires_at',
            'payment_pin_attempts'
        ])
    
    # Generate new PIN
    pin = generate_payment_pin()
    pin_hash = hash_payment_pin(pin)
    expiry_time = get_pin_expiry_time(minutes=5)
    
    logger.info(f"Generating PIN for booking {booking_id}: PIN={pin}, hash={pin_hash[:20]}...")
    
    # Save PIN with transaction to ensure atomicity
    try:
        with transaction.atomic():
            booking_locked = Booking.objects.select_for_update().get(id=booking_id)
            
            logger.info(f"Before save - booking_locked {booking_id}: old hash={'EXISTS' if booking_locked.payment_pin_hash else 'NONE'}")
            
            booking_locked.payment_pin_hash = pin_hash
            booking_locked.payment_pin_created_at = timezone.now()
            booking_locked.payment_pin_expires_at = expiry_time
            booking_locked.payment_pin_attempts = 0
            booking_locked.save(update_fields=[
                'payment_pin_hash',
                'payment_pin_created_at', 
                'payment_pin_expires_at',
                'payment_pin_attempts'
            ])
            logger.info(f"Saved PIN for booking {booking_id} inside transaction - new hash={pin_hash[:20]}...")
    except Exception as e:
        logger.error(f"Exception during PIN save for booking {booking_id}: {str(e)}")
        raise
    
    # After transaction commits, verify the save worked
    logger.info(f"Transaction committed for booking {booking_id}, verifying...")
    booking.refresh_from_db()
    
    logger.info(f"After refresh - booking {booking_id}: payment_pin_hash={'EXISTS ('+str(len(booking.payment_pin_hash))+' chars)' if booking.payment_pin_hash else 'NONE'}, expires_at={booking.payment_pin_expires_at}")
    
    if not booking.payment_pin_hash:
        logger.error(f"PIN verification failed for booking {booking_id}: payment_pin_hash is None after save!")
        logger.error(f"booking_locked had: {booking_locked.payment_pin_hash[:20] if booking_locked.payment_pin_hash else 'NONE'}")

        # Fallback: try performing an atomic raw update (use update() to issue direct SQL)
        try:
            logger.info(f"Attempting raw update fallback for booking {booking_id}")
            with transaction.atomic():
                Booking.objects.select_for_update().filter(id=booking_id).update(
                    payment_pin_hash=pin_hash,
                    payment_pin_created_at=timezone.now(),
                    payment_pin_expires_at=expiry_time,
                    payment_pin_attempts=0
                )
            # Re-read from DB
            booking.refresh_from_db()
            logger.info(f"After fallback refresh - booking {booking_id}: payment_pin_hash={'EXISTS' if booking.payment_pin_hash else 'NONE'}")
        except Exception as e:
            logger.error(f"Fallback raw update failed for booking {booking_id}: {e}")
            return Response({
                'status': 'error',
                'message': 'Failed to save PIN to database. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Force-close the DB connection and re-open to ensure we read the committed state
    try:
        from django.db import connection
        connection.close()
        fresh = Booking.objects.get(id=booking_id)
        logger.info(f"DB direct check for booking {booking_id}: payment_pin_hash={'EXISTS' if fresh.payment_pin_hash else 'NONE'}, expires_at={fresh.payment_pin_expires_at}")
    except Exception as e:
        logger.warning(f"DB direct re-read failed for booking {booking_id}: {e}")

    logger.info(f"✅ PIN SUCCESSFULLY SAVED for booking {booking_id}: PIN={pin}, expires at {expiry_time}")
    
    return Response({
        'status': 'success',
        'pin': pin,  # Only show PIN in this response
        'expires_at': expiry_time.isoformat(),
        'max_attempts': booking.payment_pin_max_attempts,
        'message': 'PIN generated successfully. Please share this PIN with the rider to confirm payment.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment_pin_endpoint(request, booking_id):
    """
    Verify the payment PIN entered by the rider.
    Only the assigned rider can verify the PIN.
    
    Expected request body:
        {
            "pin": "1234"
        }
    
    Returns:
        200: Payment verified successfully
        400: Invalid PIN, expired, or max attempts reached
        403: Not the assigned rider
        404: Booking not found
    """
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only the assigned rider can verify PIN
    if request.user.trikego_user != 'R':
        return Response({
            'status': 'error',
            'message': 'Only riders can verify payment PINs.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if booking.rider != request.user:
        return Response({
            'status': 'error',
            'message': 'You are not the assigned rider for this booking.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Refresh from database to ensure we have the latest PIN data
    booking.refresh_from_db()
    
    # Check if already verified
    if booking.payment_verified:
        return Response({
            'status': 'error',
            'message': 'Payment already verified for this booking.',
            'verified_at': booking.payment_verified_at.isoformat()
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if PIN exists
    if not booking.payment_pin_hash:
        return Response({
            'status': 'error',
            'message': 'No payment PIN has been generated yet. Please wait for the driver to provide the PIN.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if PIN is expired
    if booking.payment_pin_expires_at and timezone.now() > booking.payment_pin_expires_at:
        return Response({
            'status': 'error',
            'message': 'Payment PIN has expired. Please ask the driver to generate a new PIN.',
            'expired_at': booking.payment_pin_expires_at.isoformat()
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if max attempts reached
    if booking.payment_pin_attempts >= booking.payment_pin_max_attempts:
        return Response({
            'status': 'error',
            'message': 'Maximum PIN verification attempts reached. Please ask the driver to generate a new PIN.',
            'max_attempts': booking.payment_pin_max_attempts
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get PIN from request
    pin = request.data.get('pin', '').strip()
    
    if not pin:
        return Response({
            'status': 'error',
            'message': 'PIN is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate PIN format (4 digits)
    if not pin.isdigit() or len(pin) != 4:
        return Response({
            'status': 'error',
            'message': 'PIN must be exactly 4 digits.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify PIN with atomic transaction
    with transaction.atomic():
        booking_locked = Booking.objects.select_for_update().get(id=booking_id)
        
        # Double-check conditions again inside transaction
        if booking_locked.payment_verified:
            return Response({
                'status': 'error',
                'message': 'Payment already verified.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the PIN
        is_valid = verify_payment_pin(pin, booking_locked.payment_pin_hash)
        
        if is_valid:
            # PIN is correct - mark as verified and complete the booking
            booking_locked.payment_verified = True
            booking_locked.payment_verified_at = timezone.now()
            booking_locked.status = 'completed'
            booking_locked.end_time = timezone.now()
            booking_locked.save(update_fields=[
                'payment_verified',
                'payment_verified_at',
                'status',
                'end_time'
            ])
            
            return Response({
                'status': 'success',
                'message': 'Payment verified successfully! Trip completed.',
                'booking_id': booking_locked.id,
                'verified_at': booking_locked.payment_verified_at.isoformat(),
                'fare': str(booking_locked.fare) if booking_locked.fare else None
            }, status=status.HTTP_200_OK)
        else:
            # PIN is incorrect - increment attempts
            booking_locked.payment_pin_attempts += 1
            attempts_remaining = booking_locked.payment_pin_max_attempts - booking_locked.payment_pin_attempts
            booking_locked.save(update_fields=['payment_pin_attempts'])
            
            if attempts_remaining > 0:
                return Response({
                    'status': 'error',
                    'message': f'Incorrect PIN. {attempts_remaining} attempt(s) remaining.',
                    'attempts_remaining': attempts_remaining
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'status': 'error',
                    'message': 'Incorrect PIN. Maximum attempts reached. Please ask the driver to generate a new PIN.',
                    'attempts_remaining': 0
                }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_pin_status(request, booking_id):
    """
    Get the current status of payment PIN verification.
    Both driver and rider can check the status.
    
    Returns:
        200: {
            'pin_exists': true/false,
            'pin_valid': true/false,
            'payment_verified': true/false,
            'expires_at': '...',
            'attempts_remaining': 3
        }
    """
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security check: only rider or driver can check status
    if request.user not in [booking.rider, booking.driver]:
        return Response({
            'status': 'error',
            'message': 'Permission denied.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Refresh from database to ensure we have the latest data
    booking.refresh_from_db()
    
    logger.info(f"PIN status check for booking {booking_id}: pin_hash={'EXISTS' if booking.payment_pin_hash else 'NONE'}, is_valid={booking.is_pin_valid}, verified={booking.payment_verified}")
    
    return Response({
        'status': 'success',
        'pin_exists': bool(booking.payment_pin_hash),
        'pin_valid': booking.is_pin_valid,
        'payment_verified': booking.payment_verified,
        'expires_at': booking.payment_pin_expires_at.isoformat() if booking.payment_pin_expires_at else None,
        'attempts_remaining': booking.pin_attempts_remaining,
        'max_attempts': booking.payment_pin_max_attempts,
        'booking_status': booking.status,
        'fare': str(booking.fare) if booking.fare else None
    }, status=status.HTTP_200_OK)

    
