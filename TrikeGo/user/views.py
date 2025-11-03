from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views import View
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import (
    RiderRegistrationForm,
    LoginForm,
)
from drivers.forms import (
    DriverRegistrationForm,
    DriverVerificationForm,
)
from .models import Driver, Rider, CustomUser, Tricycle
from booking.forms import BookingForm
from ratings.forms import RatingForm
from datetime import date, timedelta
from booking.models import Booking
import json
from django.http import JsonResponse
from django.core.cache import cache
import os
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from booking.services import RoutingService
from django.conf import settings
from decimal import Decimal
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import logout as auth_logout
from booking.utils import (
    seats_available,
    pickup_within_detour,
    ensure_booking_stops,
    build_driver_itinerary,
)

try:
    from booking.tasks import compute_and_cache_route
except Exception:
    compute_and_cache_route = None


class LandingPage(View):
    template_name = 'user/landingPage.html'

    def get(self, request):
        form = LoginForm()
        return render(request, self.template_name, {'form': form})


class Login(View):
    template_name = 'user/landingPage.html'

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.trikego_user == 'D':
                    try:
                        driver_profile = Driver.objects.get(user=user)
                        if not driver_profile.is_verified:
                            messages.error(request, "Account not verified. Please wait for admin approval.")
                            return redirect('/#login')
                    except Driver.DoesNotExist:
                        messages.error(request, "Driver profile not found. Please contact support.")
                        return redirect('/#login')

                login(request, user)
                if user.trikego_user == 'D':
                    return redirect('user:driver_dashboard')
                elif user.trikego_user == 'R':
                    return redirect('user:rider_dashboard')
                elif user.trikego_user == 'A':
                    return redirect('user:admin_dashboard')
                return redirect('user:logged_in')

        messages.error(request, "Invalid username or password.")
        return redirect('/#login')

    def get(self, request):
        return redirect('user:landing')


class RegisterPage(View):
    template_name = 'user/register.html'

    def get(self, request):
        user_type = request.GET.get('type', 'rider')
        form = DriverRegistrationForm() if user_type == 'driver' else RiderRegistrationForm()
        return render(request, self.template_name, {'form': form, 'user_type': user_type})

    def post(self, request):
        user_type = request.POST.get('user_type', 'rider')
        form = DriverRegistrationForm(request.POST) if user_type == 'driver' else RiderRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.trikego_user = 'D' if user_type == 'driver' else 'R'
            user.save()

            if user_type == 'driver':
                Driver.objects.create(
                    user=user,
                    license_number=form.cleaned_data.get('license_number', 'PENDING'),
                    license_image_url=form.cleaned_data.get('license_image_url', ''),
                    license_expiry=date.today(),
                    date_hired=date.today(),
                    years_of_service=0,
                )
                pending_driver = Driver.objects.filter(user=user).first()
                if pending_driver:
                    request.session['pending_driver_id'] = pending_driver.id
                    return redirect('user:tricycle_register')
            else:
                Rider.objects.create(user=user)

            messages.success(request, f"{user_type.capitalize()} registration successful!")
            return redirect('user:landing')

        return render(request, self.template_name, {'form': form, 'user_type': user_type})


class LoggedIn(View):
    template_name = 'user/tempLoggedIn.html'

    def get(self, request):
        return render(request, self.template_name) if request.user.is_authenticated else redirect('user:landing')


@require_POST
def cancel_booking(request, booking_id):
    if not request.user.is_authenticated or request.user.trikego_user != 'R':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id)
    print(f"[cancel_booking] Booking {booking_id}, Status: {booking.status}, Driver: {booking.driver_id}")

    active_driver_statuses = {'accepted', 'on_the_way', 'started'}
    booking_is_active = booking.status in active_driver_statuses
    if booking.rider != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('user:rider_dashboard')

    if booking.status in ['pending', 'accepted', 'on_the_way']:
        old_status = booking.status
        old_driver_id = booking.driver_id

        if booking.status == 'pending' and booking.driver is None:
            print(f"[cancel_booking] Already pending with no driver, just clearing cache")
            booking.status = 'cancelled_by_rider'
            booking.save()
        else:
            print(f"[cancel_booking] Reverting to pending from {old_status}")
            booking.status = 'pending'
            booking.driver = None
            booking.start_time = None
            booking.save()

        cache_keys = [
            f'route_info_{booking_id}_{old_status}_{old_driver_id or "none"}',
            f'route_info_{booking_id}_pending_none',
            f'route_info_{booking_id}_accepted_{old_driver_id or "none"}',
            f'route_info_{booking_id}_on_the_way_{old_driver_id or "none"}',
        ]
        for key in cache_keys:
            try:
                cache.delete(key)
                print(f"[cancel_booking] Cleared cache: {key}")
            except Exception as e:
                print(f"[cancel_booking] Cache delete failed for {key}: {e}")

        messages.success(request, 'Your booking has been cancelled.')
    else:
        messages.error(request, 'This booking cannot be cancelled at this stage.')

    return redirect('user:rider_dashboard')


class RiderDashboard(View):
    template_name = 'booking/rider_dashboard.html'

    def get_context_data(self, request, form=None):
        if not request.user.is_authenticated or request.user.trikego_user != 'R':
            return None

        profile = Rider.objects.filter(user=request.user).first()
        booking_form = form or BookingForm()
        active_bookings = Booking.objects.filter(
            rider=request.user,
            status__in=['pending', 'accepted', 'on_the_way', 'started'],
        )
        try:
            for _bk in active_bookings:
                try:
                    if _bk.fare is None and _bk.estimated_distance is not None and _bk.estimated_duration is not None:
                        computed = _bk.calculate_fare()
                        if computed is not None:
                            _bk.save(update_fields=['fare'])
                except Exception as e:
                    print(f"RiderDashboard: could not compute fare for booking {_bk.id}: {e}")
        except Exception:
            pass
        ride_history = Booking.objects.filter(
            rider=request.user,
            status__in=['completed', 'cancelled_by_rider', 'cancelled_by_driver', 'no_driver_found'],
        ).order_by('-booking_time')

        latest_booking = (
            Booking.objects
            .filter(rider=request.user)
            .order_by('-booking_time', '-id')
            .first()
        )
        latest_unpaid_booking = None
        if latest_booking and latest_booking.status == 'completed' and not latest_booking.payment_verified:
            latest_unpaid_booking = latest_booking

        # This is the CORRECT code
        unrated_booking = Booking.objects.filter(
            rider=request.user,
            status='completed',
            payment_verified=True,
        ).filter(rating__isnull=True).order_by('-end_time').first()

        rating_form = RatingForm() if unrated_booking else None

        return {
            'user': request.user,
            'rider_profile': profile,
            'active_bookings': active_bookings,
            'ride_history': ride_history,
            'settings': settings,
            'booking_form': booking_form,
            'latest_unpaid_booking': latest_unpaid_booking,
            'unrated_booking': unrated_booking,
            'rating_form': rating_form,
        }

    def get(self, request):
        context = self.get_context_data(request)
        if context is None:
            return redirect('user:landing')
        return render(request, self.template_name, context)

    def post(self, request):
        if not request.user.is_authenticated or request.user.trikego_user != 'R':
            return redirect('user:landing')

        latest_booking = (
            Booking.objects
            .filter(rider=request.user)
            .order_by('-booking_time', '-id')
            .first()
        )
        if latest_booking and latest_booking.status == 'completed' and not latest_booking.payment_verified:
            messages.error(
                request,
                f'Please verify the cash payment for Trip #{latest_booking.id} before booking another ride.',
            )
            return redirect('user:rider_dashboard')

        active_qs = Booking.objects.filter(
            rider=request.user,
            status__in=['pending', 'accepted', 'on_the_way', 'started'],
        )
        active_count = active_qs.count()
        print(f'RiderDashboard.post: existing active bookings for user {request.user.username}: {active_count}')
        if active_count > 0:
            messages.error(request, 'You already have an active ride. Please complete or cancel it first.')
            return redirect('user:rider_dashboard')

        form = BookingForm(request.POST)
        try:
            print('RiderDashboard.post: POST keys:', list(request.POST.keys()))
        except Exception:
            pass

        valid = form.is_valid()
        print(f'RiderDashboard.post: BookingForm.is_valid() => {valid}')
        if not valid:
            try:
                non_field = form.non_field_errors()
                if non_field:
                    for err in non_field:
                        messages.error(request, err)
                for field, errs in form.errors.items():
                    for err in errs:
                        messages.error(request, f"{field}: {err}")
                print('BookingForm invalid:', form.errors.as_json())
            except Exception as e:
                print('Error reporting booking form errors:', e)

            context = self.get_context_data(request, form=form)
            return render(request, self.template_name, context)

        try:
            print('BookingForm cleaned_data:', form.cleaned_data)
            booking = form.save(commit=False)
            booking.rider = request.user

            pickup_lon = form.cleaned_data['pickup_longitude']
            pickup_lat = form.cleaned_data['pickup_latitude']
            dest_lon = form.cleaned_data['destination_longitude']
            dest_lat = form.cleaned_data['destination_latitude']

            start_coords = (float(pickup_lon), float(pickup_lat))
            end_coords = (float(dest_lon), float(dest_lat))

            try:
                routing_service = RoutingService()
                route_info = routing_service.calculate_route(start_coords, end_coords)

                if route_info and not route_info.get('too_close'):
                    booking.estimated_distance = Decimal(str(route_info['distance']))
                    booking.estimated_duration = route_info['duration'] // 60
                    booking.calculate_fare()
                else:
                    messages.warning(request, "Could not determine route estimates for fare calculation or points are too close.")
            except Exception as e:
                print(f"Routing/Fare calculation failed: {e}")
                messages.warning(request, "An issue occurred with fare estimation. Booking pending approval.")

            booking.save()
            print(f'Booking saved with id={booking.id} for rider={request.user.username}')

            from django.db import connection
            connection.cursor().execute("COMMIT")

            try:
                saved_booking = Booking.objects.get(id=booking.id)
                print(f'✅ Verified booking {booking.id} exists in database after save')
            except Booking.DoesNotExist:
                print(f'❌ ERROR: Booking {booking.id} NOT found in database after save!')
                raise Exception(f'Booking {booking.id} was not saved to database')

            messages.success(request, 'Your booking has been created successfully!')
            return redirect('user:rider_dashboard')
        except Exception as e:
            print('Exception saving booking:', e)
            messages.error(request, 'An error occurred while saving your booking. Please try again.')
            context = self.get_context_data(request, form=form)
            return render(request, self.template_name, context)


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect('user:landing')


class AdminDashboard(View):
    template_name = 'user/admin_dashboard.html'

    def get(self, request):
        if not request.user.is_authenticated or getattr(request.user, 'trikego_user', None) != 'A':
            return redirect('user:landing')

        context = {
            "drivers": Driver.objects.select_related("user").all(),
            "riders": Rider.objects.select_related("user").all(),
            "users": CustomUser.objects.all(),
            "verification_form": DriverVerificationForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        if not request.user.is_authenticated or getattr(request.user, 'trikego_user', None) != 'A':
            return redirect('user:landing')

        form = DriverVerificationForm(request.POST)

        if form.is_valid():
            driver_id = form.cleaned_data['driver_id']
            driver = Driver.objects.get(id=driver_id)
            driver.is_verified = not driver.is_verified
            driver.save(update_fields=["is_verified"])
            messages.success(request, f"Driver {driver.user.username}'s verification status has been updated.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

        return redirect('user:admin_dashboard')


@csrf_exempt
@login_required
@require_POST
def update_rider_location(request):
    if request.user.trikego_user != 'R':
        return JsonResponse({'status': 'error', 'message': 'Only riders can update location.'}, status=403)

    try:
        data = json.loads(request.body)
        lat, lon = data.get('lat'), data.get('lon')
        if lat is None or lon is None:
            return JsonResponse({'status': 'error', 'message': 'Missing lat/lon.'}, status=400)
        Rider.objects.filter(user=request.user).update(current_latitude=lat, current_longitude=lon)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_route_info(request, booking_id):
    if not request.user.is_authenticated:
        accept = request.META.get('HTTP_ACCEPT', '')
        xrw = request.META.get('HTTP_X_REQUESTED_WITH', '') or (
            request.headers.get('x-requested-with', '') if hasattr(request, 'headers') else ''
        )
        if xrw == 'XMLHttpRequest' or 'application/json' in accept:
            return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
        return redirect_to_login(request.get_full_path())
    booking = get_object_or_404(Booking, id=booking_id)

    cache_key = f'route_info_{booking_id}_{booking.status}_{booking.driver_id or "none"}'
    try:
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse(cached)
    except Exception:
        cached = None

    accepted_statuses = {'accepted', 'on_the_way', 'started'}
    booking_is_active = booking.status in accepted_statuses

    if request.user.trikego_user == 'D':
        try:
            driver_profile = Driver.objects.get(user=request.user)
            rider_profile = Rider.objects.get(user=booking.rider)
        except (Driver.DoesNotExist, Rider.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Profile not found for driver or rider.'}, status=404)
    elif request.user.trikego_user == 'R':
        if request.user != booking.rider:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        try:
            rider_profile = Rider.objects.get(user=request.user)
        except Rider.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Rider profile not found.'}, status=404)

        driver_profile = None
        if booking_is_active and booking.driver:
            try:
                driver_profile = Driver.objects.get(user=booking.driver)
            except Driver.DoesNotExist:
                driver_profile = None
    else:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized.'}, status=403)

    tricycle_data = None
    try:
        trike = Tricycle.objects.filter(driver=driver_profile).first() if driver_profile else None
        if not trike and driver_profile:
            trike = Tricycle.objects.filter(driver__user=driver_profile.user).first()
        if trike:
            tricycle_data = {
                'plate_number': getattr(trike, 'plate_number', None),
                'color': getattr(trike, 'color', None),
                'image_url': getattr(trike, 'image_url', None),
            }
    except Exception:
        try:
            trike = getattr(driver_profile, 'tricycle', None) if driver_profile else None
            if trike:
                tricycle_data = {
                    'plate_number': getattr(trike, 'plate_number', None),
                    'color': getattr(trike, 'color', None),
                    'image_url': getattr(trike, 'image_url', None),
                }
        except Exception:
            tricycle_data = None

    route_payload = None
    try:
        if not booking_is_active or not booking.driver:
            routing_service = RoutingService()
            start = (float(booking.pickup_longitude), float(booking.pickup_latitude))
            end = (float(booking.destination_longitude), float(booking.destination_latitude))
            route_info = routing_service.calculate_route(start, end)
            if route_info:
                route_payload = {
                    'route_data': route_info.get('route_data'),
                    'distance': route_info.get('distance'),
                    'duration': route_info.get('duration'),
                    'too_close': route_info.get('too_close', False),
                }
        else:
            route_payload = None
    except Exception:
        route_payload = None

    pickup_to_dest_km = None
    driver_to_pickup_km = None
    if route_payload:
        try:
            pickup_to_dest_km = route_payload.get('distance')
        except Exception:
            pickup_to_dest_km = None
    else:
        try:
            routing_service = RoutingService()
            if booking.pickup_latitude and booking.pickup_longitude and booking.destination_latitude and booking.destination_longitude:
                pd_start = (float(booking.pickup_longitude), float(booking.pickup_latitude))
                pd_end = (float(booking.destination_longitude), float(booking.destination_latitude))
                pd_info = routing_service.calculate_route(pd_start, pd_end)
                if pd_info:
                    pickup_to_dest_km = pd_info.get('distance')
            if booking.driver and driver_profile and driver_profile.current_latitude and driver_profile.current_longitude and booking.pickup_latitude and booking.pickup_longitude:
                dp_start = (float(driver_profile.current_longitude), float(driver_profile.current_latitude))
                dp_end = (float(booking.pickup_longitude), float(booking.pickup_latitude))
                dp_info = routing_service.calculate_route(dp_start, dp_end)
                if dp_info:
                    driver_to_pickup_km = dp_info.get('distance')
        except Exception:
            pass

    driver_info = None
    if driver_profile:
        try:
            from booking.models import DriverLocation as _DriverLocation
            dl = _DriverLocation.objects.filter(driver=driver_profile.user).first()
            if dl:
                if not driver_profile.current_latitude and getattr(dl, 'latitude', None) is not None:
                    driver_profile.current_latitude = dl.latitude
                if not driver_profile.current_longitude and getattr(dl, 'longitude', None) is not None:
                    driver_profile.current_longitude = dl.longitude
        except Exception:
            pass
        try:
            driver_name = f"{driver_profile.user.first_name} {driver_profile.user.last_name}".strip() or driver_profile.user.username
        except Exception:
            driver_name = getattr(driver_profile.user, 'username', 'Driver')
        driver_info = {
            'id': getattr(driver_profile, 'id', None),
            'name': driver_name,
            'lat': driver_profile.current_latitude,
            'lon': driver_profile.current_longitude,
        }
        if tricycle_data:
            driver_info['plate'] = tricycle_data.get('plate_number')
            driver_info['color'] = tricycle_data.get('color')

    stops_payload = []
    try:
        ensure_booking_stops(booking)
        booking_stops = booking.stops.order_by('sequence', 'created_at')
        for idx, stop in enumerate(booking_stops, start=1):
            lat_val = None
            lon_val = None
            try:
                if stop.latitude is not None and stop.longitude is not None:
                    lat_val = float(stop.latitude)
                    lon_val = float(stop.longitude)
            except Exception:
                lat_val = None
                lon_val = None

            stops_payload.append({
                'sequence': idx,
                'type': stop.stop_type,
                'status': stop.status,
                'address': stop.address,
                'lat': lat_val,
                'lon': lon_val,
                'passenger_count': stop.passenger_count,
                'label': 'Pickup' if stop.stop_type == 'PICKUP' else 'Drop-off',
                'booking_id': stop.booking_id,
            })
    except Exception:
        stops_payload = []

    shared_itinerary = None
    if booking_is_active and booking.driver and driver_profile:
        try:
            itinerary_result = build_driver_itinerary(booking.driver)
            if isinstance(itinerary_result, dict):
                shared_itinerary = itinerary_result.get('itinerary')
        except Exception:
            shared_itinerary = None

    fare_amount = None
    fare_display = None
    if booking.fare is not None:
        try:
            fare_amount = float(booking.fare)
        except (TypeError, ValueError, OverflowError):
            try:
                fare_amount = float(Decimal(str(booking.fare)))
            except Exception:
                fare_amount = None
        if fare_amount is not None:
            fare_display = f"₱{booking.fare}"

    estimated_distance_val = None
    if booking.estimated_distance is not None:
        try:
            estimated_distance_val = float(booking.estimated_distance)
        except (TypeError, ValueError, OverflowError):
            estimated_distance_val = None

    estimated_duration_val = booking.estimated_duration if booking.estimated_duration is not None else None

    estimated_arrival_iso = None
    if booking.estimated_arrival is not None:
        try:
            estimated_arrival_iso = booking.estimated_arrival.isoformat()
        except Exception:
            estimated_arrival_iso = None

    response_data = {
        'status': 'success',
        'booking_status': booking.status,
        'driver': driver_info if booking_is_active else None,
        'driver_lat': driver_profile.current_latitude if (booking_is_active and driver_profile) else None,
        'driver_lon': driver_profile.current_longitude if (booking_is_active and driver_profile) else None,
        'driver_name': driver_info.get('name') if (booking_is_active and driver_info) else None,
        'rider_lat': rider_profile.current_latitude if rider_profile else None,
        'rider_lon': rider_profile.current_longitude if rider_profile else None,
        'pickup_address': booking.pickup_address,
        'pickup_lat': booking.pickup_latitude,
        'pickup_lon': booking.pickup_longitude,
        'destination_address': booking.destination_address,
        'destination_lat': booking.destination_latitude,
        'destination_lon': booking.destination_longitude,
        'estimated_arrival': estimated_arrival_iso,
        'estimated_distance_km': estimated_distance_val,
        'estimated_duration_min': estimated_duration_val,
        'fare': fare_amount,
        'fare_display': fare_display,
        'tricycle': tricycle_data,
        'route_payload': route_payload,
        'pickup_to_destination_km': pickup_to_dest_km,
        'driver_to_pickup_km': driver_to_pickup_km,
        'stops': stops_payload,
        'itinerary': shared_itinerary,
    }

    try:
        cache.set(cache_key, response_data, timeout=int(os.environ.get('ROUTE_CACHE_TTL', 15)))
    except Exception:
        pass

    return JsonResponse(response_data)
@login_required
def get_rider_trip_history(request):
    if request.user.trikego_user != 'R':
        return JsonResponse({'status': 'error', 'message': 'Rider only'}, status=403)

    bookings = Booking.objects.filter(
        rider=request.user
    ).select_related('driver').order_by('-booking_time')[:50]

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
            'driverName': booking.driver.get_full_name() if booking.driver else 'N/A',
            'distanceKm': float(booking.estimated_distance) if booking.estimated_distance is not None else None,
        })

    return JsonResponse({'status': 'success', 'trips': trips})
