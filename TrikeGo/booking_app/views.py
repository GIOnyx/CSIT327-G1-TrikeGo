# In trikeGo/booking/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.core.cache import cache
from .forms import BookingForm
from .models import Booking
from user_app.models import CustomUser

@login_required
@require_POST # This view now only accepts POST requests from the form
def create_booking(request):
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

    form = BookingForm(request.POST)
    if form.is_valid():
        booking = form.save(commit=False)
        booking.rider = request.user  # Set the rider to the logged-in user
        booking.status = 'pending'    # Set the initial status
        booking.save()
        # Redirect to the new booking detail page to show status
        return redirect('booking:booking_detail', booking_id=booking.id)
    else:
        # If form is invalid, it's harder to show errors on the dashboard.
        # For now, we redirect back. A better solution would use AJAX.
        return redirect('user:rider_dashboard')

@login_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    # Security check: only the rider or driver of the booking can view it
    if request.user != booking.rider and request.user != booking.driver:
        return HttpResponseForbidden("You do not have permission to view this booking.")

    context = {
        'booking': booking
    }
    return render(request, 'booking/booking_detail.html', context)

@login_required
@require_POST
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    # Allow both riders and drivers to cancel
    if request.user != booking.rider and request.user != booking.driver:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    if booking.status in ['pending', 'accepted', 'on_the_way']:
        old_status = booking.status
        old_driver_id = booking.driver_id
        
        if request.user == booking.rider:
            # When rider cancels, just revert to pending and clear driver assignment
            booking.status = 'pending'
            booking.driver = None
        elif request.user == booking.driver:
            # When driver cancels, revert to pending so another driver can accept
            booking.status = 'pending'
            booking.driver = None
        booking.save()
        
        # Clear all possible cache entries for this booking
        cache_keys = [
            f'route_info_{booking_id}_{old_status}_{old_driver_id or "none"}',
            f'route_info_{booking_id}_pending_none',
            f'route_info_{booking_id}_accepted_{old_driver_id or "none"}',
            f'route_info_{booking_id}_on_the_way_{old_driver_id or "none"}',
        ]
        for key in cache_keys:
            try:
                cache.delete(key)
            except Exception:
                pass
        
        return JsonResponse({'status': 'success', 'message': 'Booking cancelled successfully.'})
    else:
        return JsonResponse({'status': 'error', 'message': 'This booking can no longer be cancelled.'}, status=400)
    
    
    