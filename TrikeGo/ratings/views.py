from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from booking.models import Booking
from ratings.forms import RatingForm
from user.models import Rider


@login_required
def rate_booking(request, booking_id):
    if request.user.trikego_user != 'R':
        return redirect('user:landing')

    booking = get_object_or_404(Booking, id=booking_id, rider=request.user)

    if booking.status != 'completed':
        messages.error(request, 'This trip is not yet complete or eligible for rating.')
        return redirect('user:rider_dashboard')

    if hasattr(booking, 'rating'):
        messages.info(request, 'You have already rated this trip.')
        return redirect('user:rider_dashboard')

    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.booking = booking
            rating.rater = request.user
            rating.rated_user = booking.driver
            rating.save()

            Rider.objects.filter(user=booking.rider).update(status='Available')

            messages.success(request, 'Thank you! Your rating has been saved.')
            return redirect('user:rider_dashboard')
    else:
        form = RatingForm()

    context = {
        'booking': booking,
        'driver': booking.driver,
        'form': form,
    }
    return render(request, 'ratings/rate_booking.html', context)


@login_required
@require_POST
def submit_rating_ajax(request, booking_id):
    if request.user.trikego_user != 'R':
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    booking = get_object_or_404(Booking, id=booking_id, rider=request.user, status='completed')

    if hasattr(booking, 'rating'):
        return JsonResponse({'status': 'info', 'message': 'Already rated.'}, status=200)

    form = RatingForm(request.POST)
    if form.is_valid():
        rating = form.save(commit=False)
        rating.booking = booking
        rating.rater = request.user
        rating.rated_user = booking.driver
        rating.save()

        Rider.objects.filter(user=booking.rider).update(status='Available')

        return JsonResponse({'status': 'success', 'message': 'Thank you! Rating saved.'})

    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)
