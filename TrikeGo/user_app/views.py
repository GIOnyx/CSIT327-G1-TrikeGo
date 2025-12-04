from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views import View
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import (
    PassengerRegistrationForm,
    LoginForm,
)
from drivers_app.forms import (
    DriverRegistrationForm,
    DriverVerificationForm,
)
from .models import Driver, Passenger, CustomUser, Tricycle
from booking_app.forms import BookingForm
from ratings_app.forms import RatingForm
from datetime import date, timedelta
from booking_app.models import Booking, DriverLocation
from django.core.paginator import Paginator
from datetime import datetime
from django.db.models import Q
import json
from django.http import JsonResponse
from django.core.cache import cache
import os
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from booking_app.services import RoutingService
from django.conf import settings
from decimal import Decimal
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import logout as auth_logout
from django.utils.http import url_has_allowed_host_and_scheme
from discount_codes_app.models import DiscountCode
import logging

# Import notification services
try:
    from notifications_app.services import dispatch_notification, NotificationMessage
except ImportError:
    dispatch_notification = None
    NotificationMessage = None
from booking_app.utils import (
    seats_available,
    pickup_within_detour,
    ensure_booking_stops,
    build_driver_itinerary,
)

try:
    from booking_app.tasks import compute_and_cache_route
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
            # debug prints removed
            if user is not None:
                if user.trikego_user == 'D':
                    try:
                        driver_profile = Driver.objects.get(user=user)
                        if not driver_profile.is_verified:
                            messages.error(request, "Account not verified. Please wait for admin approval.")
                            # Render landing page with form and messages so the user sees the error
                            return render(request, self.template_name, {'form': form})
                    except Driver.DoesNotExist:
                        messages.error(request, "Driver profile not found. Please contact support.")
                        return render(request, self.template_name, {'form': form})

                login(request, user)
                # Refresh user from DB to pick up any recent changes and related profiles
                try:
                    user = CustomUser.objects.get(pk=user.pk)
                except Exception:
                    # fallback to the authenticated user object
                    pass

                # If a Passenger profile exists but the user's trikego_user flag is not 'P', fix it.
                try:
                    if Passenger.objects.filter(user=user).exists() and getattr(user, 'trikego_user', None) != 'P':
                        user.trikego_user = 'P'
                        user.save(update_fields=['trikego_user'])
                except Exception:
                    pass

                # Respect a safe `next` parameter if provided (from ?next= or form hidden input)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)

                # Ensure passenger profile exists (create if missing) so dashboard has required data
                if user.trikego_user == 'P':
                    try:
                        Passenger.objects.get_or_create(user=user)
                    except Exception:
                        pass
                    return redirect('user:passenger_dashboard')

                if user.trikego_user == 'D':
                    return redirect('user:driver_dashboard')
                if user.trikego_user == 'A':
                    return redirect('user:admin_dashboard')

                return redirect('user:passenger_dashboard')

        messages.error(request, "Invalid username or password.")
        # Re-render landing page so errors are visible and form values can be shown
        return render(request, self.template_name, {'form': form})

    def get(self, request):
        return redirect('user:landing')


class RegisterPage(View):
    template_name = 'user/register.html'

    def get(self, request):
        user_type = request.GET.get('type', 'passenger')
        form = DriverRegistrationForm() if user_type == 'driver' else PassengerRegistrationForm()
        return render(request, self.template_name, {'form': form, 'user_type': user_type})

    def post(self, request):
        user_type = request.POST.get('user_type', 'passenger')
        form = DriverRegistrationForm(request.POST) if user_type == 'driver' else PassengerRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.trikego_user = 'D' if user_type == 'driver' else 'P'
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
                Passenger.objects.create(user=user)

            messages.success(request, f"{user_type.capitalize()} registration successful!")
            return redirect('user:landing')

        return render(request, self.template_name, {'form': form, 'user_type': user_type})

def logged_in_redirect(request):
    if request.user.is_authenticated:
        # Re-query the user to get fresh DB state
        try:
            u = CustomUser.objects.get(pk=request.user.pk)
        except Exception:
            u = request.user

        if getattr(u, 'trikego_user', None) == 'P':
            # ensure passenger profile exists
            try:
                Passenger.objects.get_or_create(user=u)
            except Exception:
                pass
            return redirect('user:passenger_dashboard')
        elif getattr(u, 'trikego_user', None) == 'D':
            return redirect('user:driver_dashboard')
        elif getattr(u, 'trikego_user', None) == 'A':
            return redirect('user:admin_dashboard')
    return redirect('user:landing')


@require_POST
def cancel_booking(request, booking_id):
    if not request.user.is_authenticated or request.user.trikego_user != 'P':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id)
    print(f"[cancel_booking] Booking {booking_id}, Status: {booking.status}, Driver: {booking.driver_id}")

    active_driver_statuses = {'accepted', 'on_the_way', 'started'}
    booking_is_active = booking.status in active_driver_statuses
    if booking.passenger != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('user:passenger_dashboard')

    if booking.status in ['pending', 'accepted', 'on_the_way']:
        old_status = booking.status
        old_driver_id = booking.driver_id
        old_driver = booking.driver  # Save driver reference before clearing

        if booking.status == 'pending' and booking.driver is None:
            print(f"[cancel_booking] Already pending with no driver, just clearing cache")
            booking.status = 'cancelled_by_passenger'
            booking.save()
        else:
            print(f"[cancel_booking] Reverting to pending from {old_status}")
            booking.status = 'pending'
            booking.driver = None
            booking.start_time = None
            booking.save()
            
            # Notify driver if booking was accepted
            if old_driver and old_status in ['accepted', 'on_the_way']:
                try:
                    if dispatch_notification and NotificationMessage:
                        msg = NotificationMessage(
                            title='Ride Cancelled by Passenger',
                            body=f"Passenger has cancelled booking #{booking.id}.",
                            data={'booking_id': booking.id, 'type': 'passenger_cancelled'},
                        )
                        dispatch_notification([old_driver.id], msg, topics=['driver'])
                        print(f'📢 Sent cancellation notification to driver {old_driver.username}')
                except Exception as e:
                    print(f'Failed to send cancellation notification: {e}')

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

    return redirect('user:passenger_dashboard')



class PassengerDashboard(View):
    template_name = 'booking/passenger_dashboard.html'

    def get_context_data(self, request, form=None):
        if not request.user.is_authenticated:
            return None

        # If the user flag isn't 'P' but a Passenger profile exists, fix the flag so dashboard can load.
        try:
            if getattr(request.user, 'trikego_user', None) != 'P':
                if Passenger.objects.filter(user=request.user).exists():
                    request.user.trikego_user = 'P'
                    request.user.save(update_fields=['trikego_user'])
                else:
                    return None
        except Exception:
            pass

        profile = Passenger.objects.filter(user=request.user).first()
        booking_form = form or BookingForm()
        active_bookings = Booking.objects.filter(
            passenger=request.user,
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
                    print(f"PassengerDashboard: could not compute fare for booking {_bk.id}: {e}")
        except Exception:
            pass
        ride_history = Booking.objects.filter(
            passenger=request.user,
            status__in=['completed', 'cancelled_by_passenger', 'cancelled_by_driver', 'no_driver_found'],
        ).order_by('-booking_time')

        latest_booking = (
            Booking.objects
            .filter(passenger=request.user)
            .order_by('-booking_time', '-id')
            .first()
        )
        latest_unpaid_booking = None
        if latest_booking and latest_booking.status == 'completed' and not latest_booking.payment_verified:
            latest_unpaid_booking = latest_booking

        # This is the CORRECT code
        unrated_booking = Booking.objects.filter(
            passenger=request.user,
            status='completed',
            payment_verified=True,
        ).filter(rating__isnull=True).order_by('-end_time').first()

        rating_form = RatingForm() if unrated_booking else None

        return {
            'user': request.user,
            'passenger_profile': profile,
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
        if not request.user.is_authenticated:
            return redirect('user:landing')
        try:
            if getattr(request.user, 'trikego_user', None) != 'P':
                if Passenger.objects.filter(user=request.user).exists():
                    request.user.trikego_user = 'P'
                    request.user.save(update_fields=['trikego_user'])
                else:
                    return redirect('user:landing')
        except Exception:
            pass

        latest_booking = (
            Booking.objects
            .filter(passenger=request.user)
            .order_by('-booking_time', '-id')
            .first()
        )
        if latest_booking and latest_booking.status == 'completed' and not latest_booking.payment_verified:
            messages.error(
                request,
                f'Please verify the cash payment for Trip #{latest_booking.id} before booking another ride.',
            )
            return redirect('user:passenger_dashboard')

        active_qs = Booking.objects.filter(
            passenger=request.user,
            status__in=['pending', 'accepted', 'on_the_way', 'started'],
        )
        active_count = active_qs.count()
        print(f'PassengerDashboard.post: existing active bookings for user {request.user.username}: {active_count}')
        if active_count > 0:
            messages.error(request, 'You already have an active ride. Please complete or cancel it first.')
            return redirect('user:passenger_dashboard')

        form = BookingForm(request.POST)
        try:
            print('PassengerDashboard.post: POST keys:', list(request.POST.keys()))
        except Exception:
            pass

        valid = form.is_valid()
        print(f'PassengerDashboard.post: BookingForm.is_valid() => {valid}')
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
            booking.passenger = request.user

            discount_code_str = request.POST.get('discount_code_input', '').strip() or None

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
                    booking.calculate_fare(discount_code_str=discount_code_str)
                else:
                    messages.warning(request, "Could not determine route estimates for fare calculation or points are too close.")
            except Exception as e:
                print(f"Routing/Fare calculation failed: {e}")
                messages.warning(request, "An issue occurred with fare estimation. Booking pending approval.")

            booking.save()

            if booking.discount_code:
            # Re-fetch the code to ensure we get the latest usage count before saving
            # This helps prevent race conditions, though a transaction is better
                try:
                # We need to lock the row for atomic update in a production environment
                # For simplicity here, we'll just increment and save.
                # NOTE: You should ensure this is done in a transaction/atomic block 
                # for true concurrency safety.
                    applied_code = DiscountCode.objects.get(pk=booking.discount_code.pk)
                    applied_code.uses_count += 1
                    applied_code.save(update_fields=['uses_count'])
                    messages.success(request, f'Discount code {applied_code.code} applied! Your final fare is ₱{booking.final_fare}.')
                except DiscountCode.DoesNotExist:
                    print(f"Warning: Discount code {booking.discount_code.code} disappeared after booking creation.")
                except Exception as e:
                    print(f"Error updating discount code usage: {e}")

            print(f'Booking saved with id={booking.id} for passenger={request.user.username}')

            from django.db import connection
            connection.cursor().execute("COMMIT")

            try:
                saved_booking = Booking.objects.get(id=booking.id)
                print(f'✅ Verified booking {booking.id} exists in database after save')
            except Booking.DoesNotExist:
                print(f'❌ ERROR: Booking {booking.id} NOT found in database after save!')
                raise Exception(f'Booking {booking.id} was not saved to database')

            # Notify all available drivers about new ride
            try:
                if dispatch_notification and NotificationMessage:
                    # Get all online/available drivers
                    available_drivers = Driver.objects.filter(
                        status__in=['Online', 'Available'],
                        user__is_active=True
                    ).values_list('user_id', flat=True)
                    
                    if available_drivers:
                        fare_display = f"₱{booking.fare:.2f}" if booking.fare else "TBD"
                        msg = NotificationMessage(
                            title='🚖 New Ride Available',
                            body=f"New booking #{booking.id} • {booking.pickup_address[:50]} → {booking.destination_address[:50]} • Fare: {fare_display}",
                            data={
                                'booking_id': booking.id,
                                'type': 'new_ride_available',
                                'fare': str(booking.fare) if booking.fare else None,
                                'pickup': booking.pickup_address,
                                'destination': booking.destination_address,
                            },
                        )
                        dispatch_notification(list(available_drivers), msg, topics=['driver'])
                        print(f'📢 Sent new ride notification to {len(available_drivers)} drivers')
            except Exception as e:
                print(f'Failed to send new ride notifications: {e}')

            messages.success(request, 'Your booking has been created successfully!')
            return redirect('user:passenger_dashboard')
        except Exception as e:
            print('Exception saving booking:', e)
            messages.error(request, 'An error occurred while saving your booking. Please try again.')
            context = self.get_context_data(request, form=form)
            return render(request, self.template_name, context)


@require_POST
def logout_view(request):
    try:
        if request.user.is_authenticated:
            request.session['driver_desired_status'] = 'Offline'
            if getattr(request.user, 'trikego_user', None) == 'D':
                try:
                    driver_profile = Driver.objects.filter(user=request.user).first()
                    if driver_profile:
                        driver_profile.status = 'Offline'
                        driver_profile.current_latitude = None
                        driver_profile.current_longitude = None
                        driver_profile.save(update_fields=['status', 'current_latitude', 'current_longitude'])
                    DriverLocation.objects.filter(driver=request.user).delete()
                except Exception:
                    pass
    except Exception:
        pass
    auth_logout(request)
    return redirect('user:landing')

from django.views import View
from django.shortcuts import render


class AdminDashboard(View):
    template_name = 'user/admin_dashboard.html'

    def get(self, request):
        if not request.user.is_authenticated or getattr(request.user, 'trikego_user', None) != 'A':
            return redirect('user:landing')

        # Include trips (bookings) for admin overview. Order by most recent bookings.
        trips_qs = Booking.objects.select_related('driver', 'passenger').order_by('-booking_time')

        # Apply simple filters from query params (status, driver username, date range)
        status_filter = request.GET.get('status')
        driver_filter = request.GET.get('driver')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if status_filter:
            trips_qs = trips_qs.filter(status=status_filter)

        if driver_filter:
            trips_qs = trips_qs.filter(driver__username__icontains=driver_filter)

        # Parse dates in YYYY-MM-DD format (simple best-effort)
        try:
            if date_from:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                trips_qs = trips_qs.filter(booking_time__date__gte=df)
            if date_to:
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                trips_qs = trips_qs.filter(booking_time__date__lte=dt)
        except Exception:
            # ignore parse errors and show unfiltered range
            pass

        # Pagination
        per_page = 25
        page_number = request.GET.get('page', 1)
        paginator = Paginator(trips_qs, per_page)
        page_obj = paginator.get_page(page_number)

        # Drivers list with filters, sorting and pagination
        drivers_qs = Driver.objects.select_related('user').all()
        d_search = request.GET.get('d_search')
        d_status = request.GET.get('d_status')
        d_verified = request.GET.get('d_verified')
        d_sort = request.GET.get('d_sort')
        d_order = request.GET.get('d_order', 'desc')

        if d_search:
            drivers_qs = drivers_qs.filter(
                Q(user__first_name__icontains=d_search) |
                Q(user__last_name__icontains=d_search) |
                Q(user__username__icontains=d_search)
            )
        if d_status:
            drivers_qs = drivers_qs.filter(status=d_status)
        if d_verified in ('true', 'false'):
            drivers_qs = drivers_qs.filter(is_verified=(d_verified == 'true'))

        # sorting
        if d_sort:
            order_field = {
                'name': 'user__first_name',
                'username': 'user__username',
                'date_hired': 'date_hired',
                'status': 'status',
            }.get(d_sort, 'user__username')
            if d_order == 'desc':
                order_field = '-' + order_field
            drivers_qs = drivers_qs.order_by(order_field)
        else:
            drivers_qs = drivers_qs.order_by('-date_hired')

        drivers_paginator = Paginator(drivers_qs, per_page)
        drivers_page = drivers_paginator.get_page(request.GET.get('page_drivers', 1))

        # Passengers list with filters, sorting and pagination
        passengers_qs = Passenger.objects.select_related('user').all()
        p_search = request.GET.get('p_search')
        p_status = request.GET.get('p_status')
        p_sort = request.GET.get('p_sort')
        p_order = request.GET.get('p_order', 'desc')

        if p_search:
            passengers_qs = passengers_qs.filter(
                Q(user__first_name__icontains=p_search) |
                Q(user__last_name__icontains=p_search) |
                Q(user__username__icontains=p_search) |
                Q(user__email__icontains=p_search)
            )
        if p_status:
            passengers_qs = passengers_qs.filter(status=p_status)

        if p_sort:
            r_order_field = {
                'name': 'user__first_name',
                'username': 'user__username',
                'loyalty': 'loyalty_points',
                'status': 'status',
            }.get(p_sort, 'user__username')
            if p_order == 'desc':
                r_order_field = '-' + r_order_field
            passengers_qs = passengers_qs.order_by(r_order_field)
        else:
            passengers_qs = passengers_qs.order_by('-user__date_joined')

        passengers_paginator = Paginator(passengers_qs, per_page)
        passengers_page = passengers_paginator.get_page(request.GET.get('page_passengers', 1))

        context = {
            "drivers_page": drivers_page,
            "passengers_page": passengers_page,
            "users": CustomUser.objects.all(),
            "verification_form": DriverVerificationForm(),
            "trips_page": page_obj,
            # expose current filters so template can keep form values
            'filter_status': status_filter or '',
            'filter_driver': driver_filter or '',
            'filter_date_from': date_from or '',
            'filter_date_to': date_to or '',
            'active_tab': request.GET.get('tab', 'drivers'),
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
def update_passenger_location(request):
    if request.user.trikego_user != 'P':
        return JsonResponse({'status': 'error', 'message': 'Only passengers can update location.'}, status=403)

    try:
        data = json.loads(request.body)
        lat, lon = data.get('lat'), data.get('lon')
        if lat is None or lon is None:
            return JsonResponse({'status': 'error', 'message': 'Missing lat/lon.'}, status=400)
        Passenger.objects.filter(user=request.user).update(current_latitude=lat, current_longitude=lon)
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
            passenger_profile = Passenger.objects.get(user=booking.passenger)
        except (Driver.DoesNotExist, Passenger.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Profile not found for driver or passenger.'}, status=404)
    elif request.user.trikego_user == 'P':
        if request.user != booking.passenger:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        try:
            passenger_profile = Passenger.objects.get(user=request.user)
        except Passenger.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Passenger profile not found.'}, status=404)

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
            from booking_app.models import DriverLocation as _DriverLocation
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
        'passenger_lat': passenger_profile.current_latitude if passenger_profile else None,
        'passenger_lon': passenger_profile.current_longitude if passenger_profile else None,
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
        'payment_verified': booking.payment_verified,
    }

    try:
        cache.set(cache_key, response_data, timeout=int(os.environ.get('ROUTE_CACHE_TTL', 15)))
    except Exception:
        pass

    return JsonResponse(response_data)
@login_required
def get_passenger_trip_history(request):
    if request.user.trikego_user != 'P':
        return JsonResponse({'status': 'error', 'message': 'Passenger only'}, status=403)

    bookings = Booking.objects.filter(
        passenger=request.user
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
