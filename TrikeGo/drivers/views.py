from datetime import timedelta
from decimal import Decimal

from django.http import JsonResponse
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import mail_admins
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from booking.models import Booking, DriverLocation
from booking.services import RoutingService
from booking.utils import ensure_booking_stops, pickup_within_detour, seats_available
from drivers.forms import TricycleForm
from user.models import Driver, Rider
try:
    from notifications.services import dispatch_notification, NotificationMessage
except Exception:
    # Notifications are optional in some environments; degrade gracefully
    dispatch_notification = None
    NotificationMessage = None

try:  # Celery task is optional in some environments
    from booking.tasks import compute_and_cache_route
except Exception:  # pragma: no cover - background worker not always available
    compute_and_cache_route = None


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
        active_booking = (
            Booking.objects.filter(
                driver=request.user,
                status__in=['accepted', 'on_the_way', 'started'],
            ).order_by('-booking_time').first()
        )

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

        active_bookings = Booking.objects.filter(
            driver=request.user,
            status__in=['accepted', 'on_the_way', 'started'],
        ).order_by('-booking_time')

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

    rider_active = Booking.objects.filter(
        rider=booking.rider,
        status__in=['accepted', 'on_the_way', 'started'],
    ).exists()
    if rider_active:
        msg = 'Rider already has an active trip.'
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

        allowed = pickup_within_detour(request.user, pickup_lat, pickup_lon, max_km=5.0)
        if not allowed:
            msg = 'Pickup is too far from your current route to accept this booking.'
            messages.error(request, msg)
            if _wants_json(request):
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            return redirect('drivers:driver_dashboard')
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
    Rider.objects.filter(user=booking.rider).update(status='In_trip')

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
    # Push notification: inform the rider that a driver accepted
    try:
        if dispatch_notification and NotificationMessage:
            msg = NotificationMessage(
                title='Ride Accepted',
                body=f"Your ride #{booking.id} was accepted by a driver. They'll arrive soon.",
                data={'booking_id': booking.id, 'type': 'ride_accepted'},
            )
            dispatch_notification([booking.rider.id], msg, topics=['rider'])
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
        Driver.objects.filter(user=request.user).update(status='Online')
        Rider.objects.filter(user=booking.rider).update(status='Available')
        msg = 'You have cancelled your acceptance. The booking is now available again.'
        messages.success(request, msg)
        # Notify rider that driver cancelled acceptance
        try:
            if dispatch_notification and NotificationMessage:
                note = NotificationMessage(
                    title='Ride Cancelled by Driver',
                    body=f"Driver has cancelled acceptance for ride #{booking.id}. We're looking for another driver.",
                    data={'booking_id': booking.id, 'type': 'driver_cancelled'},
                )
                dispatch_notification([booking.rider.id], note, topics=['rider'])
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
        Driver.objects.filter(user=request.user).update(status='Online')
        Rider.objects.filter(user=booking.rider).update(status='Available')
        msg = 'Booking marked as completed!'
        messages.success(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'success', 'booking': {'id': booking.id, 'status': booking.status}})
    else:
        msg = 'Cannot complete this booking.'
        messages.error(request, msg)
        if _wants_json(request):
            return JsonResponse({'status': 'error', 'message': msg}, status=400)

    # Notify rider that trip is completed
    try:
        if dispatch_notification and NotificationMessage:
            note = NotificationMessage(
                title='Trip Completed',
                body=f"Your trip #{booking.id} is completed. Thank you for riding with us.",
                data={'booking_id': booking.id, 'type': 'trip_completed'},
            )
            dispatch_notification([booking.rider.id], note, topics=['rider'])
    except Exception:
        pass

    return redirect('drivers:driver_active_books')


@login_required
def get_driver_active_booking(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Only drivers can access this endpoint.'}, status=403)

    active_booking = (
        Booking.objects.filter(
            driver=request.user,
            status__in=['accepted', 'on_the_way', 'started'],
        ).order_by('-booking_time').first()
    )

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

    bookings = (
        Booking.objects.filter(driver=request.user)
        .select_related('rider')
        .order_by('-booking_time')[:50]
    )

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
            'riderName': booking.rider.get_full_name() if booking.rider else 'Unknown',
            'distanceKm': float(booking.estimated_distance) if booking.estimated_distance is not None else None,
        })

    return JsonResponse({'status': 'success', 'trips': trips})


@login_required
@require_GET
def available_rides_api(request):
    if not _ensure_driver(request):
        return JsonResponse({'status': 'error', 'message': 'Driver only'}, status=403)

    rides = []
    pending_bookings = (
        Booking.objects.filter(status='pending', driver__isnull=True)
        .select_related('rider')
        .order_by('booking_time')[:30]
    )

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'Available rides API called by {request.user.username}, found {pending_bookings.count()} pending bookings')

    for booking in pending_bookings:
        try:
            rider_name = booking.rider.get_full_name().strip() or booking.rider.username
        except Exception:
            rider_name = 'Passenger'

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
            'rider_name': rider_name,
        }
        rides.append(ride_data)

    return JsonResponse({'status': 'success', 'rides': rides})


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
    if not _ensure_driver(request) and request.user.trikego_user != 'R':
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    booking = get_object_or_404(Booking, id=booking_id)
    if request.user != booking.rider and request.user != booking.driver:
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
