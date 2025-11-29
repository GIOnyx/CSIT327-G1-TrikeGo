import base64
import io
from datetime import timedelta
from decimal import Decimal
from typing import List

import matplotlib

# Use Agg backend for headless environments
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from booking_app.models import Booking, RatingAndFeedback


def _format_currency(value: Decimal | None) -> str:
    if value is None:
        return "₱0.00"
    quantized = value.quantize(Decimal("0.01"))
    return f"₱{quantized:,.2f}"


def _generate_daily_trips_chart(labels: List[str], values: List[int]) -> str | None:
    if not labels or not values or len(labels) != len(values):
        return None

    try:
        sns.set_theme(style="whitegrid")
        figure, axis = plt.subplots(figsize=(8.6, 4.8))

        sns.lineplot(x=labels, y=values, marker="o", linewidth=2.5, color="#0b63d6", ax=axis)
        axis.set_xlabel("Date", fontsize=12)
        axis.set_ylabel("Trips Completed", fontsize=12)
        axis.set_title("Trips in the Last 7 Days", fontsize=14, pad=18)

        y_max = max(values) if values else 0
        padding = max(1, int(round(y_max * 0.25))) if y_max else 1
        axis.set_ylim(0, y_max + padding)
        axis.grid(axis="both", linestyle="--", alpha=0.25)
        axis.tick_params(axis="x", rotation=30, labelsize=10)
        axis.tick_params(axis="y", labelsize=10)

        for spine_name in ("top", "right"):
            axis.spines[spine_name].set_visible(False)

        plt.tight_layout(pad=1.4)

        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=160)
        plt.close(figure)
        buffer.seek(0)
        encoded = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        plt.close("all")
        return None


@login_required
@require_GET
def driver_statistics_summary(request):
    """Return aggregated performance metrics for the authenticated driver."""

    user = request.user
    if getattr(user, "trikego_user", "") != "D":
        return JsonResponse({"status": "error", "message": "Driver access required."}, status=403)

    now = timezone.now()
    today = timezone.localdate()
    seven_days_ago = now - timedelta(days=6)

    driver_bookings = Booking.objects.filter(driver=user)

    total_rides = driver_bookings.count()
    completed_rides = driver_bookings.filter(status="completed").count()
    cancelled_rides = driver_bookings.filter(status__in=["cancelled_by_driver", "cancelled_by_passenger"]).count()
    active_rides = driver_bookings.filter(status__in=["pending", "accepted", "on_the_way", "started"]).count()

    completion_rate = (completed_rides / total_rides * 100) if total_rides else 0
    cancellation_rate = (cancelled_rides / total_rides * 100) if total_rides else 0

    earnings_today = driver_bookings.filter(
        status="completed", end_time__date=today
    ).aggregate(total=Coalesce(Sum("fare"), Decimal("0")))
    earnings_today_value = earnings_today.get("total", Decimal("0"))

    recent_window = driver_bookings.filter(booking_time__date__gte=seven_days_ago.date())
    daily_counts = (
        recent_window.annotate(day=TruncDate("booking_time"))
        .values("day")
        .annotate(count=Count("id"))
    )
    day_lookup = {entry["day"]: entry["count"] for entry in daily_counts}

    labels, values = [], []
    for offset in range(7):
        day = seven_days_ago + timedelta(days=offset)
        date_key = day.date()
        labels.append(day.strftime("%b %d"))
        values.append(day_lookup.get(date_key, 0))

    chart_data_uri = _generate_daily_trips_chart(labels, values)

    ratings = RatingAndFeedback.objects.filter(rated_user=user).order_by("-created_at")
    recent_ratings = ratings[:50]
    average_rating = recent_ratings.aggregate(avg=Avg("rating_value"))
    average_rating_value = average_rating.get("avg") or 0
    ratings_sample_size = recent_ratings.count()

    response_payload = {
        "status": "success",
        "data": {
            "summary": {
                "total_rides": total_rides,
                "completed_rides": completed_rides,
                "active_rides": active_rides,
                "cancelled_rides": cancelled_rides,
                "completion_rate": round(completion_rate, 1),
                "cancellation_rate": round(cancellation_rate, 1),
                "average_rating": round(average_rating_value, 2),
                "earnings_today": {
                    "raw": float(earnings_today_value),
                    "display": _format_currency(earnings_today_value),
                },
                "ratings_sample_size": ratings_sample_size,
            },
            "trends": {
                "daily_trips": {
                    "labels": labels,
                    "values": values,
                    "chart_image": chart_data_uri,
                }
            },
        },
    }

    return JsonResponse(response_payload)
