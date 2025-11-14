from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from booking_app.models import Booking


def _build_driver_wallet_context(user):
    base_qs = (
        Booking.objects.filter(
            driver=user,
            status='completed',
            fare__isnull=False,
        )
        .select_related('rider')
        .annotate(
            completed_at=Coalesce(
                'end_time',
                'booking_time',
                output_field=models.DateTimeField(),
            )
        )
    )

    today = timezone.localdate()
    today_totals = base_qs.filter(completed_at__date=today).aggregate(
        total=Sum('fare'),
        trip_count=Count('id'),
    )

    lifetime_total = base_qs.aggregate(total=Sum('fare'))['total'] or Decimal('0')

    recent_trips = list(base_qs.order_by('-completed_at')[:20])

    daily_breakdown_qs = (
        base_qs.annotate(day=TruncDate('completed_at'))
        .values('day')
        .annotate(total=Sum('fare'), trip_count=Count('id'))
        .order_by('-day')[:14]
    )
    daily_breakdown = [
        {
            'date': entry['day'],
            'total': entry['total'] or Decimal('0'),
            'trip_count': entry['trip_count'] or 0,
        }
        for entry in daily_breakdown_qs
    ]

    return {
        'today_summary': {
            'total': today_totals.get('total') or Decimal('0'),
            'trip_count': today_totals.get('trip_count') or 0,
        },
        'lifetime_total': lifetime_total,
        'recent_trips': recent_trips,
        'daily_breakdown': daily_breakdown,
    }


class DriverWalletView(LoginRequiredMixin, TemplateView):
    """Display earnings summary for drivers."""

    template_name = 'wallet/driver_wallet.html'

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'trikego_user', None) != 'D':
            return redirect('user:landing')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_build_driver_wallet_context(self.request.user))
        return context


@login_required
def driver_wallet_summary(request):
    user = request.user
    if getattr(user, 'trikego_user', None) != 'D':
        return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)

    data = _build_driver_wallet_context(user)

    def currency(value):
        value = value or Decimal('0')
        return float(value)

    def format_date(date_value):
        return date_value.strftime('%b %d, %Y') if date_value else ''

    recent_trips = []
    for trip in data['recent_trips']:
        completed_at = getattr(trip, 'completed_at', None)
        if completed_at:
            completed_display = timezone.localtime(completed_at).strftime('%b %d, %Y %I:%M %p')
            completed_iso = timezone.localtime(completed_at).isoformat()
        else:
            completed_display = ''
            completed_iso = ''

        rider_name = ''
        if trip.rider:
            rider_name = trip.rider.get_full_name() or trip.rider.username or ''

        recent_trips.append(
            {
                'id': trip.id,
                'completed_iso': completed_iso,
                'completed_display': completed_display,
                'fare': currency(trip.fare),
                'rider_name': rider_name,
                'pickup': trip.pickup_address or '',
                'destination': trip.destination_address or '',
                'distance': float(trip.estimated_distance) if trip.estimated_distance is not None else None,
            }
        )

    payload = {
        'today': {
            'total': currency(data['today_summary']['total']),
            'trip_count': data['today_summary']['trip_count'] or 0,
        },
        'lifetime_total': currency(data['lifetime_total']),
        'daily_breakdown': [
            {
                'date_iso': entry['date'].isoformat() if entry['date'] else '',
                'date_display': format_date(entry['date']),
                'total': currency(entry['total']),
                'trip_count': entry['trip_count'],
            }
            for entry in data['daily_breakdown']
        ],
        'recent_trips': recent_trips,
    }

    return JsonResponse({'status': 'success', 'data': payload})
