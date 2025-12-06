import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import DiscountCode, LoyaltyRedemption
from user_app.models import Passenger
from django.utils import timezone

@login_required
@require_GET
def available_discount_codes(request):
    """
    Returns all active discount codes with cost that the passenger can redeem.
    """
    codes = DiscountCode.objects.filter(is_active=True, valid_from__lte=timezone.now())
    code_list = [
        {"id": code.id, "code": code.code, "cost": code.cost}
        for code in codes if code.is_valid_now
    ]
    return JsonResponse({"status": "success", "codes": code_list})


@login_required
@require_POST
def redeem_discount_code(request, code_id):  # code_id comes from URL
    user = request.user

    # Get passenger profile
    try:
        passenger = user.passenger
    except Passenger.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Passenger profile not found"}, status=404)

    # Fetch discount code
    try:
        discount_code = DiscountCode.objects.get(id=code_id)
    except DiscountCode.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Discount code not found"}, status=404)

    # Validate code status
    if not discount_code.is_valid_now:
        return JsonResponse({"status": "error", "message": "This discount code is no longer valid"}, status=400)

    # Check points
    if passenger.loyalty_points < discount_code.cost:
        return JsonResponse({"status": "error", "message": "Not enough loyalty points"}, status=400)

    # Prevent double redemption
    if LoyaltyRedemption.objects.filter(passenger=passenger, discount_code=discount_code).exists():
        return JsonResponse({"status": "error", "message": "You have already redeemed this code"}, status=400)

    # Redeem!
    passenger.loyalty_points -= discount_code.cost
    passenger.save()

    discount_code.uses_count += 1
    discount_code.save()

    LoyaltyRedemption.objects.create(
        passenger=passenger,
        discount_code=discount_code,
        points_used=discount_code.cost
    )

    return JsonResponse({
        "status": "success",
        "message": f"You have successfully redeemed {discount_code.code}",
        "remaining_points": passenger.loyalty_points
    })