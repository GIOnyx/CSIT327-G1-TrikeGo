from datetime import timedelta
from decimal import Decimal

from django.http import JsonResponse
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import mail_admins
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from booking_app.models import Booking, DriverLocation
from booking_app.services import RoutingService
from booking_app.utils import ensure_booking_stops, pickup_within_detour, seats_available
from drivers_app.forms import TricycleForm
from user_app.models import Driver, Passenger
try:
    from notifications_app.services import dispatch_notification, NotificationMessage
except Exception:
    # Notifications are optional in some environments; degrade gracefully
    dispatch_notification = None
    NotificationMessage = None

try:  # Celery task is optional in some environments
    from booking_app.tasks import compute_and_cache_route
except Exception:  # pragma: no cover - background worker not always available
    compute_and_cache_route = None


ACTIVE_BOOKING_STATUSES = ('accepted', 'on_the_way', 'started')


def _driver_active_bookings_qs(user):
    """Return a queryset for a driver's active bookings."""
    return Booking.objects.filter(driver=user, status__in=ACTIVE_BOOKING_STATUSES)


def _driver_has_active_bookings(user) -> bool:
    """Convenience wrapper to check for active bookings."""
    return _driver_active_bookings_qs(user).exists()


def _ensure_driver(request):
    """Redirect non-driver users back to landing page."""
    if not request.user.is_authenticated or getattr(request.user, 'trikego_user', None) != 'D':
        return False
    return True


def _wants_json(request):
    accept = request.headers.get('Accept', '')
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in accept.lower()


@method_decorator(login_required, name='dispatch')
class DriverDashboard(View):
    template_name = 'booking/driver_dashboard.html'

    def get(self, request):
        if not _ensure_driver(request):
            return redirect('user:landing')

        profile = Driver.objects.filter(user=request.user).first()
        available_rides = Booking.objects.filter(status='pending', driver__isnull=True)
        active_booking = _driver_active_bookings_qs(request.user).order_by('-booking_time').first()

        if active_booking and profile and profile.status != 'In_trip':
            profile.status = 'In_trip'
            profile.save(update_fields=['status'])

        context = {
            'user': request.user,
            'driver_profile': profile,
            'settings': settings,
            'available_rides': available_rides,
            'active_booking': active_booking,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class DriverActiveBookings(View):
    template_name = 'booking/driver_active_books.html'

    def get(self, request):
        if not _ensure_driver(request):
            return redirect('user:landing')

        active_bookings = _driver_active_bookings_qs(request.user).order_by('-booking_time')

        pending_payment_bookings = Booking.objects.filter(
            driver=request.user,
            status='completed',
            payment_verified=False,
        ).order_by('-booking_time')

        bookings = list(active_bookings) + list(pending_payment_bookings)
        return render(request, self.template_name, {'active_bookings': bookings})


@method_decorator(login_required, name='dispatch')
class TricycleRegister(View):
    template_name = 'user/tricycle_register.html'

    def get(self, request):
        pending_id = request.session.get('pending_driver_id')
        if not pending_id:
            messages.error(request, 'No pending driver found. Please complete the first step.')
            return redirect('user:register')

        form = TricycleForm()
        return render(request, self.template_name, {'form': form, 'step': 2})

    def post(self, request):
        pending_id = request.session.get('pending_driver_id')
        if not pending_id:
            messages.error(request, 'Session expired or invalid. Please start registration again.')
            return redirect('user:register')

        form = TricycleForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'step': 2})

        try:
            driver = Driver.objects.get(id=pending_id)
        except Driver.DoesNotExist:
            messages.error(request, 'Driver profile missing. Please contact support.')
            return redirect('user:register')

        trike = form.save(commit=False)
        trike.driver = driver
        trike.save()

        driver.is_verified = False
        driver.save(update_fields=['is_verified'])

        try:
            subject = f'New tricycle registration for driver {driver.user.username}'
            message = (
                f'Driver ID: {driver.id}\nTricycle: {trike.plate_number} ({trike.color})\nPlease review and approve.'
            )
            mail_admins(subject, message)
        except Exception:
            pass

        request.session.pop('pending_driver_id', None)
        messages.success(request, 'Your application is under review.')
        return render(request, 'user/registration_complete.html')


@login_required
@require_POST
def accept_ride(request, booking_id):
    if not _ensure_driver(request):
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)
        return redirect('user:landing')

    driver_profile = Driver.objects.filter(user=request.user).first()
    if not driver_profile:
        msg = 'Driver profile not found. Please contact support.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect('drivers:driver_dashboard')

    if driver_profile.status == 'Offline':
        msg = 'Go online before accepting new rides.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect('drivers:driver_dashboard')

    booking = get_object_or_404(Booking, id=booking_id, status='pending', driver__isnull=True)

    try:
        requested = int(getattr(booking, 'passengers', 1) or 1)
    except Exception:
        requested = 1

    try:
        if not seats_available(request.user, additional_seats=requested):
            msg = 'Cannot accept ride: vehicle capacity would be exceeded.'
            messages.error(request, msg)
            if _wants_json(request):
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            return redirect('drivers:driver_dashboard')
    except Exception:
        msg = 'Could not verify vehicle capacity. Please try again or contact support.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=500)
        return redirect('drivers:driver_dashboard')

    passenger_active = Booking.objects.filter(
        passenger=booking.passenger,
        status__in=['accepted', 'on_the_way', 'started'],
    ).exists()
    if passenger_active:
        msg = 'Passenger already has an active trip.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect('drivers:driver_dashboard')

    try:
        pickup_lat = booking.pickup_latitude
        pickup_lon = booking.pickup_longitude
        if pickup_lat is None or pickup_lon is None:
            msg = 'Cannot verify pickup location for detour check.'
            messages.error(request, msg)
            if _wants_json(request):
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            return redirect('drivers:driver_dashboard')

        # Temporarily disable detour enforcement to allow all bookings during testing.
        # allowed = pickup_within_detour(request.user, pickup_lat, pickup_lon, max_km=5.0)
        # if not allowed:
        #     msg = 'Pickup is too far from your current route to accept this booking.'
        #     messages.error(request, msg)
        #     if _wants_json(request):
        #         return JsonResponse({'status': 'error', 'message': msg}, status=400)
        #     return redirect('drivers:driver_dashboard')
    except Exception:
        msg = 'Could not compute detour check; please ensure location sharing is enabled.'
        messages.warning(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=500)
        return redirect('drivers:driver_dashboard')

    booking.driver = request.user
    booking.status = 'accepted'
    booking.start_time = timezone.now()

    Driver.objects.filter(user=request.user).update(status='In_trip')
    Passenger.objects.filter(user=booking.passenger).update(status='In_trip')

    try:
        driver_location = DriverLocation.objects.get(driver=request.user)
        routing_service = RoutingService()

        start_coords = (float(driver_location.longitude), float(driver_location.latitude))
        pickup_coords = (float(booking.pickup_longitude), float(booking.pickup_latitude))

        route_info = routing_service.calculate_route(start_coords, pickup_coords)

        if route_info: 
            routing_service.save_route_snapshot(booking, route_info)
            booking.estimated_distance = Decimal(str(route_info['distance']))
            booking.estimated_duration = route_info['duration'] // 60
            booking.estimated_arrival = timezone.now() + timedelta(seconds=route_info['duration'])
    except DriverLocation.DoesNotExist:
        messages.warning(request, 'Please enable location sharing to see route information.')
    except Exception as exc:
        messages.warning(request, f'Could not calculate route: {exc}')

    booking.save()
    ensure_booking_stops(booking)
    messages.success(
        request,
        f"You have accepted the ride from {booking.pickup_address} to {booking.destination_address}.",
    )
    try:
        if compute_and_cache_route:
            compute_and_cache_route.delay(booking.id)
    except Exception:
        pass
    if _wants_json(request):
        return JsonResponse({
            'status': 'success',
            'booking': {
                'id': booking.id,
                'status': booking.status,
                'pickup': booking.pickup_address,
                'destination': booking.destination_address,
                'fare': float(booking.fare) if booking.fare is not None else None,
                'payment_verified': booking.payment_verified,
            },
        })
    # Push notification: inform the passenger that a driver accepted
    try:
        if dispatch_notification and NotificationMessage:
            msg = NotificationMessage(
                title='Ride Accepted',
                body=f"Your ride #{booking.id} was accepted by a driver. They'll arrive soon.",
                data={'booking_id': booking.id, 'type': 'ride_accepted'},
            )
            dispatch_notification([booking.passenger.id], msg, topics=['passenger'])
    except Exception:
        # Do not fail the request if notification sending has issues
        pass
    return redirect('drivers:driver_dashboard')


@login_required
@require_POST
def cancel_accepted_booking(request, booking_id):
    if not _ensure_driver(request):
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id, driver=request.user)

    if booking.status in ['accepted', 'on_the_way', 'started']:
        booking.status = 'pending'
        booking.driver = None
        booking.start_time = None
        booking.save(update_fields=['status', 'driver', 'start_time'])

        next_status = 'In_trip' if _driver_has_active_bookings(request.user) else 'Online'
        Driver.objects.filter(user=request.user).update(status=next_status)
        Passenger.objects.filter(user=booking.passenger).update(status='Available')
        msg = 'You have cancelled your acceptance. The booking is now available again.'
        messages.success(request, msg)
        # Notify passenger that driver cancelled acceptance
        try:
            if dispatch_notification and NotificationMessage:
                note = NotificationMessage(
                    title='Ride Cancelled by Driver',
                    body=f"Driver has cancelled acceptance for ride #{booking.id}. We're looking for another driver.",
                    data={'booking_id': booking.id, 'type': 'driver_cancelled'},
                )
                dispatch_notification([booking.passenger.id], note, topics=['passenger'])
        except Exception:
            pass
        if _wants_json(request):
            return JsonResponse({'status': 'success', 'booking': {'id': booking.id, 'status': booking.status}})
    else:
        msg = 'You cannot cancel this booking anymore.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)

    return redirect('drivers:driver_active_books')


@login_required
@require_POST
def complete_booking(request, booking_id):
    if not _ensure_driver(request):
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id, driver=request.user)

    if booking.status in ['accepted', 'on_the_way', 'started']:
        booking.status = 'completed'
        booking.end_time = timezone.now()
        booking.save(update_fields=['status', 'end_time'])

        next_status = 'In_trip' if _driver_has_active_bookings(request.user) else 'Online'
        Driver.objects.filter(user=request.user).update(status=next_status)
        Passenger.objects.filter(user=booking.passenger).update(status='Available')
        msg = 'Booking marked as completed!'
        messages.success(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'success', 'booking': {'id': booking.id, 'status': booking.status}})
    else:
        msg = 'Cannot complete this booking.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)

    # Notify passenger that trip is completed
    try:
        if dispatch_notification and NotificationMessage:
            note = NotificationMessage(
                title='Trip Completed',
                body=f"Your trip #{booking.id} is completed. Thank you for riding with us.",
                data={'booking_id': booking.id, 'type': 'trip_completed'},
            )
            dispatch_notification([booking.passenger.id], note, topics=['passenger'])
    except Exception:
        pass

    return redirect('drivers:driver_active_books')


@login_required
def get_driver_active_booking(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Only drivers can access this endpoint.'}, status=403)

    active_booking = _driver_active_bookings_qs(request.user).order_by('-booking_time').first()

    if active_booking:
        return JsonResponse({
            'status': 'success',
            'booking_id': active_booking.id,
            'booking_status': active_booking.status,
        })
    return JsonResponse({'status': 'success', 'booking_id': None})


@login_required
def get_driver_trip_history(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Driver only'}, status=403)

    try:
        offset = int(request.GET.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(request.GET.get('limit', 20))
    except (TypeError, ValueError):
        limit = 20

    offset = max(offset, 0)
    limit = max(1, min(limit, 50))

    queryset = (
        Booking.objects.filter(driver=request.user)
        .select_related('passenger')
        .order_by('-booking_time')
    )

    bookings = list(queryset[offset:offset + limit + 1])
    has_more = len(bookings) > limit
    if has_more:
        bookings = bookings[:limit]

    trips = []
    for booking in bookings:
        trips.append({
            'id': booking.id,
            'pickup': booking.pickup_address,
            'destination': booking.destination_address,
            'fare': float(booking.fare) if booking.fare else 0,
            'status': booking.status,
            'date': booking.booking_time.strftime('%b %d, %Y %I:%M %p'),
            'paymentVerified': booking.payment_verified,
            'passengerName': booking.passenger.get_full_name() if booking.passenger else 'Unknown',
            'distanceKm': float(booking.estimated_distance) if booking.estimated_distance is not None else None,
        })

    next_offset = offset + len(bookings)

    return JsonResponse({
        'status': 'success',
        'trips': trips,
        'hasMore': has_more,
        'nextOffset': next_offset,
    })


@login_required
@require_GET
def available_rides_api(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Driver only'}, status=403)

    rides = []
    pending_bookings = (
        Booking.objects.filter(status='pending', driver__isnull=True)
        .select_related('passenger')
        .order_by('booking_time')[:30]
    )

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'Available rides API called by {request.user.username}, found {pending_bookings.count()} pending bookings')

    for booking in pending_bookings:
        try:
            passenger_name = booking.passenger.get_full_name().strip() or booking.passenger.username
        except Exception:
            passenger_name = 'Passenger'

        ride_data = {
            'id': booking.id,
            'status': booking.status,
            'booking_time': booking.booking_time.isoformat() if booking.booking_time else None,
            'updated_at': booking.booking_time.isoformat() if booking.booking_time else None,
            'pickup_address': booking.pickup_address,
            'destination_address': booking.destination_address,
            'passengers': booking.passengers or 1,
            'fare': float(booking.fare) if booking.fare is not None else None,
            'fare_display': f"₱{booking.fare:.2f}" if booking.fare is not None else None,
            'estimated_distance_km': float(booking.estimated_distance) if booking.estimated_distance is not None else None,
            'estimated_duration_min': booking.estimated_duration,
            'passenger_name': passenger_name,
        }
        rides.append(ride_data)

    return JsonResponse({'status': 'success', 'rides': rides})


@login_required
@require_http_methods(['GET', 'POST'])
def driver_status(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Driver only'}, status=403)

    driver_profile = Driver.objects.filter(user=request.user).first()
    if not driver_profile:
        return JsonResponse({'status': 'error', 'message': 'Driver profile not found.'}, status=404)

    active_trip_exists = _driver_has_active_bookings(request.user)

    if active_trip_exists and driver_profile.status != 'In_trip':
        driver_profile.status = 'In_trip'
        driver_profile.save(update_fields=['status'])


    if request.method == 'GET':
        desired_status = request.session.get('driver_desired_status')
        if desired_status not in {'Online', 'Offline'}:
            desired_status = driver_profile.status
            if not active_trip_exists:
                request.session['driver_desired_status'] = desired_status
        payload = {
            'status': 'success',
            'driverStatus': driver_profile.status,
            'hasActiveTrip': active_trip_exists,
            'desiredStatus': desired_status,
        }
        try:
            if driver_profile.current_latitude is not None and driver_profile.current_longitude is not None:
                payload['currentLocation'] = {
                    'lat': float(driver_profile.current_latitude),
                    'lon': float(driver_profile.current_longitude),
                }
        except (TypeError, ValueError):
            payload['currentLocation'] = None
        return JsonResponse(payload)

    if request.content_type and 'application/json' in request.content_type.lower():
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, TypeError):
            data = {}
    else:
        data = request.POST

    requested_status = (data.get('status') or data.get('driverStatus') or '').strip()
    if requested_status:
        requested_status = requested_status.capitalize()
    if requested_status not in {'Online', 'Offline'}:
        return JsonResponse({'status': 'error', 'message': 'Status must be Online or Offline.'}, status=400)

    if requested_status == 'Offline':
        if active_trip_exists:
            return JsonResponse({'status': 'error', 'message': 'Finish or cancel your current trip before going offline.'}, status=400)
        driver_profile.status = 'Offline'
        driver_profile.current_latitude = None
        driver_profile.current_longitude = None
        driver_profile.save(update_fields=['status', 'current_latitude', 'current_longitude'])
        try:
            DriverLocation.objects.filter(driver=request.user).delete()
        except Exception:
            pass
        request.session['driver_desired_status'] = 'Offline'
        return JsonResponse({'status': 'success', 'driverStatus': 'Offline', 'hasActiveTrip': False})

    if requested_status == 'Online' and not active_trip_exists:
        request.session['driver_desired_status'] = 'Online'

    new_status = 'In_trip' if active_trip_exists else 'Online'
    if driver_profile.status != new_status:
        driver_profile.status = new_status
        driver_profile.save(update_fields=['status'])

    if not active_trip_exists:
        request.session['driver_desired_status'] = 'Online'

    response_payload = {
        'status': 'success',
        'driverStatus': new_status,
        'hasActiveTrip': active_trip_exists,
    }
    try:
        if driver_profile.current_latitude is not None and driver_profile.current_longitude is not None:
            response_payload['currentLocation'] = {
                'lat': float(driver_profile.current_latitude),
                'lon': float(driver_profile.current_longitude),
            }
    except (TypeError, ValueError):
        pass
    return JsonResponse(response_payload)


@csrf_exempt
@login_required
@require_POST
def update_driver_location(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Only drivers can update location.'}, status=403)

    try:
        data = json.loads(request.body)
        lat, lon = data.get('lat'), data.get('lon')
        if lat is None or lon is None:
            return JsonResponse({'status': 'error', 'message': 'Missing lat/lon.'}, status=400)
        Driver.objects.filter(user=request.user).update(current_latitude=lat, current_longitude=lon)
        try:
            active_bookings = Booking.objects.filter(
                driver=request.user,
                status__in=['accepted', 'on_the_way', 'started'],
            ).values('id', 'status', 'driver_id')
            for entry in active_bookings:
                bid = entry.get('id')
                try:
                    cache.delete(f'route_info_{bid}')
                    cache.delete(f"route_info_{bid}_{entry.get('status')}_{entry.get('driver_id') or 'none'}")
                except Exception:
                    pass
        except Exception:
            pass
        return JsonResponse({'status': 'success'})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)


@login_required
def get_driver_location(request, booking_id):
    if not _ensure_driver(request) and request.user.trikego_user != 'P':
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    booking = get_object_or_404(Booking, id=booking_id)
    if request.user != booking.passenger and request.user != booking.driver:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
    if not booking.driver:
        return JsonResponse({'status': 'error', 'message': 'No driver assigned yet.'}, status=404)
    try:
        driver_profile = Driver.objects.get(user=booking.driver)
        return JsonResponse({
            'status': 'success',
            'lat': driver_profile.current_latitude,
            'lon': driver_profile.current_longitude,
        })
    except Driver.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Driver profile not found.'}, status=404)
