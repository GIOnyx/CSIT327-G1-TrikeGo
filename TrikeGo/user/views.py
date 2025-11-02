# In trikeGo/user/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views import View
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .forms import DriverRegistrationForm, RiderRegistrationForm, LoginForm, DriverVerificationForm, TricycleForm
from .models import Driver, Rider, CustomUser, Tricycle
from booking.forms import BookingForm
from datetime import date
from booking.models import Booking
import json
from django.http import JsonResponse
from django.core.cache import cache
import os
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from booking.services import RoutingService
from booking.models import DriverLocation
from datetime import timedelta
from django.conf import settings
from decimal import Decimal
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import logout as auth_logout
from django.views.decorators.csrf import csrf_protect
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
                # Check if driver is verified before allowing login
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
                    years_of_service=0
                )
                # Store pending driver id in session and redirect to tricycle registration (step 2)
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

class DriverDashboard(View):
    template_name = 'booking/driver_dashboard.html'
    def get(self, request):
        if not request.user.is_authenticated or request.user.trikego_user != 'D':
            return redirect('user:landing')
        profile = Driver.objects.filter(user=request.user).first()
        available_rides = Booking.objects.filter(status='pending', driver__isnull=True)
        active_booking = Booking.objects.filter(
            driver=request.user,
            status__in=['accepted', 'on_the_way', 'started']
        ).order_by('-booking_time').first()

        context = {
            'user': request.user,
            'driver_profile': profile,
            'settings': settings,
            'available_rides': available_rides,
            'active_booking': active_booking,
        }
        return render(request, self.template_name, context)


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
        if form.is_valid():
            trike = form.save(commit=False)
            try:
                driver = Driver.objects.get(id=pending_id)
            except Driver.DoesNotExist:
                messages.error(request, 'Driver profile missing. Please contact support.')
                return redirect('user:register')

            trike.driver = driver
            trike.save()

            # mark driver as not verified; approval is handled via admin verification
            driver.is_verified = False
            driver.save(update_fields=['is_verified'])

            # Notify admins via email if configured
            try:
                from django.core.mail import mail_admins
                subject = f'New tricycle registration for driver {driver.user.username}'
                message = f'Driver ID: {driver.id}\nTricycle: {trike.plate_number} ({trike.color})\nPlease review and approve.'
                mail_admins(subject, message)
            except Exception:
                # if mail not configured, still continue
                pass

            # Clear session and show confirmation
            request.session.pop('pending_driver_id', None)
            messages.success(request, 'Your application is under review.')
            return render(request, 'user/registration_complete.html')
        else:
            return render(request, self.template_name, {'form': form, 'step': 2})

@require_POST
def accept_ride(request, booking_id):
    if not request.user.is_authenticated or request.user.trikego_user != 'D':
        return redirect('user:landing')

    # Enforce capacity and proximity checks to allow multi-booking.
    # Fetch booking early so we can inspect requested passengers.
    booking = get_object_or_404(Booking, id=booking_id, status='pending', driver__isnull=True)

    try:
        requested = int(getattr(booking, 'passengers', 1) or 1)
    except Exception:
        requested = 1

    try:
        if not seats_available(request.user, additional_seats=requested):
            messages.error(request, "Cannot accept ride: vehicle capacity would be exceeded.")
            return redirect('user:driver_dashboard')
    except Exception:
        messages.error(request, "Could not verify vehicle capacity. Please try again or contact support.")
        return redirect('user:driver_dashboard')

    # Also prevent acceptance if rider already has an active trip
    rider_active = Booking.objects.filter(
        rider=booking.rider,
        status__in=['accepted', 'on_the_way', 'started']
    ).exists()
    if rider_active:
        messages.error(request, "Rider already has an active trip.")
        return redirect('user:driver_dashboard')

    # Proximity/detour check (Option A): require pickup to be within X km of any point on driver's route
    try:
        pickup_lat = booking.pickup_latitude
        pickup_lon = booking.pickup_longitude
        # If coordinates missing, conservatively block acceptance
        if pickup_lat is None or pickup_lon is None:
            messages.error(request, "Cannot verify pickup location for detour check.")
            return redirect('user:driver_dashboard')

        allowed = pickup_within_detour(request.user, pickup_lat, pickup_lon, max_km=5.0)
        if not allowed:
            messages.error(request, "Pickup is too far from your current route to accept this booking.")
            return redirect('user:driver_dashboard')
    except Exception:
        messages.warning(request, "Could not compute detour check; please ensure location sharing is enabled.")
        return redirect('user:driver_dashboard')

    booking.driver = request.user
    booking.status = 'accepted'
    booking.start_time = timezone.now()

    # Update statuses
    Driver.objects.filter(user=request.user).update(status='In_trip')
    Rider.objects.filter(user=booking.rider).update(status='In_trip')
    
    # Calculate initial route
    try:
        driver_location = DriverLocation.objects.get(driver=request.user)
        routing_service = RoutingService()
        
        # Calculate route from driver to pickup
        start_coords = (float(driver_location.longitude), float(driver_location.latitude))
        pickup_coords = (float(booking.pickup_longitude), float(booking.pickup_latitude))
        
        route_info = routing_service.calculate_route(start_coords, pickup_coords)
        
        if route_info:
            # Save route snapshot
            routing_service.save_route_snapshot(booking, route_info)
            
            # Update booking estimates
            booking.estimated_distance = Decimal(str(route_info['distance']))
            booking.estimated_duration = route_info['duration'] // 60  # minutes
            booking.estimated_arrival = timezone.now() + timedelta(seconds=route_info['duration'])
    except DriverLocation.DoesNotExist:
        messages.warning(request, "Please enable location sharing to see route information.")
    except Exception as e:
        messages.warning(request, f"Could not calculate route: {str(e)}")
    
    booking.save()
    ensure_booking_stops(booking)
    messages.success(request, f"You have accepted the ride from {booking.pickup_address} to {booking.destination_address}.")
    # Schedule an asynchronous task to compute and cache route information (non-blocking)
    try:
        if compute_and_cache_route:
            compute_and_cache_route.delay(booking.id)
    except Exception:
        pass
    return redirect('user:driver_dashboard')

class DriverActiveBookings(View):
    template_name = 'booking/driver_active_books.html'

    def get(self, request):
        if not request.user.is_authenticated or request.user.trikego_user != 'D':
            return redirect('user:landing')

        # Include 'completed' bookings that haven't been payment verified yet
        active_bookings = Booking.objects.filter(
            driver=request.user,
            status__in=['accepted', 'on_the_way', 'started']
        ).order_by('-booking_time')
        
        # Also get completed bookings awaiting payment verification
        pending_payment_bookings = Booking.objects.filter(
            driver=request.user,
            status='completed',
            payment_verified=False
        ).order_by('-booking_time')
        
        # Combine both querysets
        bookings = list(active_bookings) + list(pending_payment_bookings)

        return render(request, self.template_name, {'active_bookings': bookings})


@require_POST
def cancel_accepted_booking(request, booking_id):
    if not request.user.is_authenticated or request.user.trikego_user != 'D':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id, driver=request.user)

    if booking.status in ['accepted', 'on_the_way', 'started']:
        booking.status = 'pending'
        booking.driver = None
        booking.start_time = None
        booking.save()
        # Reset statuses
        Driver.objects.filter(user=request.user).update(status='Online')
        Rider.objects.filter(user=booking.rider).update(status='Available')

        messages.success(request, "You have cancelled your acceptance. The booking is now available again.")
    else:
        messages.error(request, "You cannot cancel this booking anymore.")

    return redirect('user:driver_active_books')


@require_POST
def cancel_booking(request, booking_id):
    """Allow riders to cancel their own bookings (pending or accepted)."""
    if not request.user.is_authenticated or request.user.trikego_user != 'R':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id)
    print(f"[cancel_booking] Booking {booking_id}, Status: {booking.status}, Driver: {booking.driver_id}")
    
    active_driver_statuses = {'accepted', 'on_the_way', 'started'}
    booking_is_active = booking.status in active_driver_statuses
    if booking.rider != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('user:rider_dashboard')

    # When rider cancels, revert booking to pending state so it stays in active bookings
    # but clears any driver assignment. This allows the rider to see the unaccepted booking card.
    if booking.status in ['pending', 'accepted', 'on_the_way']:
        old_status = booking.status
        old_driver_id = booking.driver_id
        
        # If already pending with no driver, this is effectively a "delete" request
        # But we keep it as pending to maintain the booking in the system
        if booking.status == 'pending' and booking.driver is None:
            print(f"[cancel_booking] Already pending with no driver, just clearing cache")
            booking.status = 'cancelled_by_rider'  # Mark as cancelled so it moves to history
            booking.save()
        else:
            print(f"[cancel_booking] Reverting to pending from {old_status}")
            booking.status = 'pending'
            booking.driver = None
            booking.start_time = None
            booking.save()
        
        # Clear route info cache entries
        from django.core.cache import cache
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


@require_POST
def complete_booking(request, booking_id):
    if not request.user.is_authenticated or request.user.trikego_user != 'D':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id, driver=request.user)

    if booking.status in ['accepted', 'on_the_way', 'started']:
        booking.status = 'completed'
        booking.end_time = timezone.now()
        booking.save()
        # Reset statuses
        Driver.objects.filter(user=request.user).update(status='Online')
        Rider.objects.filter(user=booking.rider).update(status='Available')
        messages.success(request, "Booking marked as completed!")
    else:
        messages.error(request, "Cannot complete this booking.")

    return redirect('user:driver_active_books')

class RiderDashboard(View):
    template_name = 'booking/rider_dashboard.html'

    def get_context_data(self, request, form=None):
        if not request.user.is_authenticated or request.user.trikego_user != 'R':
            return None

        profile = Rider.objects.filter(user=request.user).first()
        booking_form = form or BookingForm()
        active_bookings = Booking.objects.filter(
            rider=request.user,
            status__in=['pending', 'accepted', 'on_the_way', 'started']
        )
        # Ensure fare is available for active bookings when estimates exist.
        # Some bookings may have been created before fare logic existed, or
        # without estimates; compute and persist fare when we can so templates
        # can render it directly as `booking.fare`.
        try:
            for _bk in active_bookings:
                try:
                    if _bk.fare is None and _bk.estimated_distance is not None and _bk.estimated_duration is not None:
                        computed = _bk.calculate_fare()
                        if computed is not None:
                            # Persist only the fare field to avoid touching other columns
                            _bk.save(update_fields=['fare'])
                except Exception as e:
                    # Non-fatal: do not block dashboard rendering for logging/calculation issues
                    print(f"RiderDashboard: could not compute fare for booking {_bk.id}: {e}")
        except Exception:
            # If iterating the queryset fails for any reason, continue without fares
            pass
        ride_history = Booking.objects.filter(
            rider=request.user,
            status__in=['completed', 'cancelled_by_rider', 'cancelled_by_driver', 'no_driver_found']
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

        return {
            'user': request.user,
            'rider_profile': profile,
            'active_bookings': active_bookings,
            'ride_history': ride_history,
            'settings': settings,
            'booking_form': booking_form,
            'latest_unpaid_booking': latest_unpaid_booking,
        }

    def get(self, request):
        context = self.get_context_data(request)
        if context is None:
            return redirect('user:landing')
        return render(request, self.template_name, context)

    def post(self, request):
        if not request.user.is_authenticated or request.user.trikego_user != 'R':
            return redirect('user:landing')
        
        # Restrict: rider must settle the most recent completed trip before creating a new one
        latest_booking = (
            Booking.objects
            .filter(rider=request.user)
            .order_by('-booking_time', '-id')
            .first()
        )
        if latest_booking and latest_booking.status == 'completed' and not latest_booking.payment_verified:
            messages.error(
                request,
                f'Please verify the cash payment for Trip #{latest_booking.id} before booking another ride.'
            )
            return redirect('user:rider_dashboard')

        # Restrict: rider can only have one active booking
        active_qs = Booking.objects.filter(
            rider=request.user,
            status__in=['pending', 'accepted', 'on_the_way', 'started']
        )
        active_count = active_qs.count()
        print(f'RiderDashboard.post: existing active bookings for user {request.user.username}: {active_count}')
        if active_count > 0:
            messages.error(request, 'You already have an active ride. Please complete or cancel it first.')
            return redirect('user:rider_dashboard')

        form = BookingForm(request.POST)
        # Debug: print validity and incoming POST keys
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
                # Print raw errors to console for deeper inspection
                print('BookingForm invalid:', form.errors.as_json())
            except Exception as e:
                print('Error reporting booking form errors:', e)

            context = self.get_context_data(request, form=form)
            return render(request, self.template_name, context)

        # If valid, show cleaned data and save within try/except
        try:
            print('BookingForm cleaned_data:', form.cleaned_data)
            booking = form.save(commit=False)
            booking.rider = request.user

            pickup_lon = form.cleaned_data['pickup_longitude']
            pickup_lat = form.cleaned_data['pickup_latitude']
            dest_lon = form.cleaned_data['destination_longitude']
            dest_lat = form.cleaned_data['destination_latitude']
            
            # 1. Prepare coordinates (RoutingService expects lon, lat)
            start_coords = (float(pickup_lon), float(pickup_lat))
            end_coords = (float(dest_lon), float(dest_lat))

            try:
                # 2. Get route estimates
                routing_service = RoutingService()
                # We use 'driving-car', which is the default in your RoutingService
                route_info = routing_service.calculate_route(start_coords, end_coords) 
                
                if route_info and not route_info.get('too_close'):
                    # 3. Store estimated values (distance in km, duration in minutes)
                    booking.estimated_distance = Decimal(str(route_info['distance']))
                    booking.estimated_duration = route_info['duration'] // 60 # Convert seconds to minutes
                    
                    # 4. Calculate and set the fare
                    booking.calculate_fare() 
                    
                else:
                    messages.warning(request, "Could not determine route estimates for fare calculation or points are too close.")

            except Exception as e:
                # Log the error but proceed with booking (without fare) if possible
                print(f"Routing/Fare calculation failed: {e}")
                messages.warning(request, "An issue occurred with fare estimation. Booking pending approval.")

            booking.save()
            print(f'Booking saved with id={booking.id} for rider={request.user.username}')
            
            # Verify the booking was actually saved to database
            from django.db import connection
            connection.cursor().execute("COMMIT")  # Force commit
            
            # Verify it exists in DB
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
    """Log the user out and redirect to the landing page.

    This endpoint accepts POST only (the logout icon submits a POST form).
    """
    # Use Django's logout helper
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

# --- REAL-TIME TRACKING VIEWS ---

@csrf_exempt
@login_required
@require_POST
def update_driver_location(request):
    if request.user.trikego_user != 'D':
        return JsonResponse({'status': 'error', 'message': 'Only drivers can update location.'}, status=403)
    
    try:
        data = json.loads(request.body)
        lat, lon = data.get('lat'), data.get('lon')
        if lat is None or lon is None:
            return JsonResponse({'status': 'error', 'message': 'Missing lat/lon.'}, status=400)
        Driver.objects.filter(user=request.user).update(current_latitude=lat, current_longitude=lon)
        # Invalidate cached route info for any active booking assigned to this driver
        try:
            from booking.models import Booking as _Booking
            active_bookings = _Booking.objects.filter(
                driver=request.user,
                status__in=['accepted', 'on_the_way', 'started']
            ).values('id', 'status', 'driver_id')
            for entry in active_bookings:
                bid = entry.get('id')
                try:
                    cache.delete(f'route_info_{bid}')
                    cache.delete(f"route_info_{bid}_{entry.get('status')}_{entry.get('driver_id') or 'none'}")
                except Exception:
                    pass
        except Exception:
            # If booking model unavailable or cache deletion fails, continue silently
            pass
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_driver_location(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.user != booking.rider:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
    if not booking.driver:
        return JsonResponse({'status': 'error', 'message': 'No driver assigned yet.'}, status=404)
    try:
        driver_profile = Driver.objects.get(user=booking.driver)
        return JsonResponse({'status': 'success', 'lat': driver_profile.current_latitude, 'lon': driver_profile.current_longitude})
    except Driver.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Driver profile not found.'}, status=404)

# --- NEW: VIEWS FOR RIDER LOCATION AND DRIVER MAP ---
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
    # Handle unauthenticated requests gracefully for API callers (fetch/ajax)
    if not request.user.is_authenticated:
        # Determine if the caller expects JSON (fetch/XHR)
        accept = request.META.get('HTTP_ACCEPT', '')
        xrw = request.META.get('HTTP_X_REQUESTED_WITH', '') or request.headers.get('x-requested-with', '') if hasattr(request, 'headers') else ''
        if xrw == 'XMLHttpRequest' or 'application/json' in accept:
            return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
        # otherwise redirect to login page (preserve next)
        return redirect_to_login(request.get_full_path())
    booking = get_object_or_404(Booking, id=booking_id)

    # Try to serve a cached route_info payload to reduce repeated ORS calls
    cache_key = f'route_info_{booking_id}_{booking.status}_{booking.driver_id or "none"}'
    try:
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse(cached)
    except Exception:
        # If cache is unavailable, continue and compute normally
        cached = None
    
    # Allow: drivers to preview using their own current location; riders to view for their own booking
    
    # Define booking_is_active first to determine if driver info should be exposed
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
        # Allow riders to preview the route (pickup -> destination) even when no driver has
        # been assigned yet. In that case, we will compute a pickup->destination route
        # and return it with driver coordinates set to null so the frontend draws only
        # the preview route. If a driver exists, return driver info as before.
        try:
            rider_profile = Rider.objects.get(user=request.user)
        except Rider.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Rider profile not found.'}, status=404)

        driver_profile = None
        if booking_is_active and booking.driver:
            try:
                driver_profile = Driver.objects.get(user=booking.driver)
            except Driver.DoesNotExist:
                # If driver record is missing, continue without driver info
                driver_profile = None
    else:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized.'}, status=403)
    # Try to include tricycle details if available. The Tricycle model or relation
    # may not exist yet in the codebase, so handle gracefully.
    tricycle_data = None
    try:
        # Prefer explicit Tricycle model if available
        from user.models import Tricycle
        try:
            # Some implementations may link Tricycle to Driver (model instance) or to the CustomUser.
            trike = Tricycle.objects.filter(driver=driver_profile).first()
            if not trike:
                # Try linking by user if different FK was used
                trike = Tricycle.objects.filter(driver__user=driver_profile.user).first()
        except Exception:
            trike = None
        if trike:
            tricycle_data = {
                'plate_number': getattr(trike, 'plate_number', None),
                'color': getattr(trike, 'color', None),
                'image_url': getattr(trike, 'image_url', None),
            }
    except Exception:
        # No Tricycle model present — try to access a related attribute on the driver_profile
        try:
            trike = getattr(driver_profile, 'tricycle', None)
            if trike:
                tricycle_data = {
                    'plate_number': getattr(trike, 'plate_number', None),
                    'color': getattr(trike, 'color', None),
                    'image_url': getattr(trike, 'image_url', None),
                }
        except Exception:
            tricycle_data = None

    # If there's no driver assigned (rider preview), compute pickup->destination route
    route_payload = None
    try:
        if not booking_is_active or not booking.driver:
            routing_service = RoutingService()
            # Calculate route from pickup to destination (coords expected as lon,lat)
            start = (float(booking.pickup_longitude), float(booking.pickup_latitude))
            end = (float(booking.destination_longitude), float(booking.destination_latitude))
            route_info = routing_service.calculate_route(start, end)
            if route_info:
                route_payload = {
                    'route_data': route_info.get('route_data'),
                    'distance': route_info.get('distance'),
                    'duration': route_info.get('duration'),
                    'too_close': route_info.get('too_close', False)
                }
        else:
            # If a driver exists, the frontend will fetch driver/pickup and pickup/destination as needed
            route_payload = None
    except Exception as e:
        route_payload = None
    # Compute distances for convenience to display in the UI
    pickup_to_dest_km = None
    driver_to_pickup_km = None
    if route_payload:
        try:
            pickup_to_dest_km = route_payload.get('distance')
        except Exception:
            pickup_to_dest_km = None
    else:
        # If driver exists and routing can compute, try to compute distances
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

    # Driver/tricycle frontend-friendly details
    driver_info = None
    if driver_profile:
        # If the Driver model doesn't have current coords, try to read the real-time
        # DriverLocation (apps.booking.models.DriverLocation) as a fallback source.
        try:
            from booking.models import DriverLocation as _DriverLocation
            dl = _DriverLocation.objects.filter(driver=driver_profile.user).first()
            if dl:
                # Only set if missing on the driver_profile
                if not driver_profile.current_latitude and getattr(dl, 'latitude', None) is not None:
                    driver_profile.current_latitude = dl.latitude
                if not driver_profile.current_longitude and getattr(dl, 'longitude', None) is not None:
                    driver_profile.current_longitude = dl.longitude
        except Exception:
            # Booking app or DriverLocation may not be present; ignore and continue
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
        # Try to attach tricycle info if not yet included
        if tricycle_data:
            driver_info['plate'] = tricycle_data.get('plate_number')
            driver_info['color'] = tricycle_data.get('color')

    # Build stop payload (pickup/dropoff and any subsequent itinerary points) so the
    # rider map can render numbered markers matching the driver's itinerary.
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

    # Cache the response briefly to reduce repeated ORS calls from many clients.
    try:
        cache.set(cache_key, response_data, timeout=int(os.environ.get('ROUTE_CACHE_TTL', 15)))
    except Exception:
        pass

    return JsonResponse(response_data)

@login_required
def get_driver_active_booking(request):
    """Get the active booking for the current driver"""
    if request.user.trikego_user != 'D':
        return JsonResponse({'status': 'error', 'message': 'Only drivers can access this endpoint.'}, status=403)
    
    active_booking = Booking.objects.filter(
        driver=request.user,
        status__in=['accepted', 'on_the_way', 'started']
    ).order_by('-booking_time').first()
    
    if active_booking:
        return JsonResponse({
            'status': 'success',
            'booking_id': active_booking.id,
            'booking_status': active_booking.status
        })
    else:
        return JsonResponse({
            'status': 'success',
            'booking_id': None
        })


@login_required
def get_rider_trip_history(request):
    """
    Get all bookings made by the rider (all statuses).
    Returns trip history with payment status.
    """
    if request.user.trikego_user != 'R':
        return JsonResponse({'status': 'error', 'message': 'Rider only'}, status=403)
    
    bookings = Booking.objects.filter(
        rider=request.user
    ).select_related('driver').order_by('-booking_time')[:50]  # Last 50 trips
    
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
        })
    
    return JsonResponse({'status': 'success', 'trips': trips})


@login_required
def get_driver_trip_history(request):
    """
    Get all accepted bookings by the driver (not declined ones).
    Returns trip history with payment status.
    """
    if request.user.trikego_user != 'D':
        return JsonResponse({'status': 'error', 'message': 'Driver only'}, status=403)
    
    bookings = Booking.objects.filter(
        driver=request.user
    ).select_related('rider').order_by('-booking_time')[:50]  # Last 50 trips
    
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
        })
    
    return JsonResponse({'status': 'success', 'trips': trips})
