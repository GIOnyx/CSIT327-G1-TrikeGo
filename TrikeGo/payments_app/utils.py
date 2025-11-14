from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta
import random


def generate_payment_pin() -> str:
    """
    Generate a random 4-digit PIN for payment verification.
    Returns the PIN as a string (e.g., "1234").
    """
    return f"{random.randint(0, 9999):04d}"


def hash_payment_pin(pin: str) -> str:
    """
    Hash the payment PIN using Django's password hasher.
    """
    return make_password(pin)


def verify_payment_pin(pin: str, pin_hash: str) -> bool:
    """
    Verify a payment PIN against its hash.
    """
    return check_password(pin, pin_hash)


def get_pin_expiry_time(minutes: int = 5) -> timezone.datetime:
    """
    Get the expiry time for a payment PIN.
    """
    return timezone.now() + timedelta(minutes=minutes)
