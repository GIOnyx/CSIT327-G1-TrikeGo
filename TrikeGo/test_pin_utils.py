"""
Manual test script to verify PIN utility functions work correctly.
Run this script to test the core PIN functionality without Django ORM.

Usage:
    python test_pin_utils.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trikeGo.settings')
import django
django.setup()

from booking.utils import (
    generate_payment_pin,
    hash_payment_pin,
    verify_payment_pin,
    get_pin_expiry_time
)
from django.utils import timezone
from datetime import timedelta


def test_pin_generation():
    """Test that PINs are generated correctly"""
    print("\n=== Test 1: PIN Generation ===")
    
    # Generate 10 PINs
    pins = [generate_payment_pin() for _ in range(10)]
    
    print(f"Generated PINs: {pins}")
    
    # Check format (all should be 4 digits)
    for pin in pins:
        assert len(pin) == 4, f"PIN {pin} is not 4 digits!"
        assert pin.isdigit(), f"PIN {pin} contains non-digits!"
    
    print("✅ All PINs are 4 digits")
    
    # Check uniqueness (most should be unique)
    unique_pins = set(pins)
    print(f"✅ Generated {len(unique_pins)}/{len(pins)} unique PINs")


def test_pin_hashing():
    """Test that PIN hashing works"""
    print("\n=== Test 2: PIN Hashing ===")
    
    pin = "1234"
    pin_hash = hash_payment_pin(pin)
    
    print(f"Original PIN: {pin}")
    print(f"Hashed PIN: {pin_hash[:50]}...")
    
    assert pin != pin_hash, "Hash should be different from original!"
    assert len(pin_hash) > 20, "Hash should be long!"
    
    print("✅ PIN hashing works correctly")


def test_pin_verification():
    """Test PIN verification"""
    print("\n=== Test 3: PIN Verification ===")
    
    # Test correct PIN
    pin = "5678"
    pin_hash = hash_payment_pin(pin)
    
    result = verify_payment_pin(pin, pin_hash)
    assert result == True, "Correct PIN should verify!"
    print("✅ Correct PIN verification: PASS")
    
    # Test incorrect PIN
    result = verify_payment_pin("0000", pin_hash)
    assert result == False, "Incorrect PIN should fail!"
    print("✅ Incorrect PIN verification: FAIL (as expected)")
    
    # Test various incorrect PINs
    incorrect_pins = ["5679", "5677", "1234", "9999"]
    for wrong_pin in incorrect_pins:
        result = verify_payment_pin(wrong_pin, pin_hash)
        assert result == False, f"PIN {wrong_pin} should not match {pin}!"
    
    print("✅ All incorrect PINs properly rejected")


def test_pin_expiry():
    """Test PIN expiry time calculation"""
    print("\n=== Test 4: PIN Expiry Time ===")
    
    now = timezone.now()
    
    # Test 5 minute expiry
    expiry_5 = get_pin_expiry_time(5)
    diff = (expiry_5 - now).total_seconds()
    print(f"5-minute expiry: {diff:.0f} seconds from now")
    assert 299 <= diff <= 301, "Should be approximately 300 seconds (5 minutes)!"
    print("✅ 5-minute expiry correct")
    
    # Test 10 minute expiry
    expiry_10 = get_pin_expiry_time(10)
    diff = (expiry_10 - now).total_seconds()
    print(f"10-minute expiry: {diff:.0f} seconds from now")
    assert 599 <= diff <= 601, "Should be approximately 600 seconds (10 minutes)!"
    print("✅ 10-minute expiry correct")


def test_complete_flow():
    """Test a complete PIN generation and verification flow"""
    print("\n=== Test 5: Complete Flow Simulation ===")
    
    # Step 1: Generate PIN
    pin = generate_payment_pin()
    print(f"Step 1: Generated PIN: {pin}")
    
    # Step 2: Hash PIN (as if storing in database)
    pin_hash = hash_payment_pin(pin)
    created_at = timezone.now()
    expires_at = get_pin_expiry_time(5)
    attempts = 0
    max_attempts = 3
    
    print(f"Step 2: PIN hashed and stored")
    print(f"  - Created: {created_at}")
    print(f"  - Expires: {expires_at}")
    print(f"  - Max attempts: {max_attempts}")
    
    # Step 3: Simulate rider entering wrong PIN (attempt 1)
    print(f"\nStep 3: Rider enters wrong PIN: '0000'")
    is_valid = verify_payment_pin("0000", pin_hash)
    if not is_valid:
        attempts += 1
        print(f"  ❌ Incorrect! Attempts: {attempts}/{max_attempts}")
    
    # Step 4: Simulate rider entering wrong PIN again (attempt 2)
    print(f"\nStep 4: Rider enters wrong PIN: '9999'")
    is_valid = verify_payment_pin("9999", pin_hash)
    if not is_valid:
        attempts += 1
        print(f"  ❌ Incorrect! Attempts: {attempts}/{max_attempts}")
    
    # Step 5: Simulate rider entering correct PIN
    print(f"\nStep 5: Rider enters correct PIN: '{pin}'")
    is_valid = verify_payment_pin(pin, pin_hash)
    if is_valid:
        print(f"  ✅ Correct! Payment verified!")
        payment_verified = True
        payment_verified_at = timezone.now()
        print(f"  - Verified at: {payment_verified_at}")
    
    # Step 6: Check PIN is still valid (not expired, attempts remaining)
    print(f"\nStep 6: Checking PIN validity...")
    is_expired = timezone.now() > expires_at
    has_attempts = attempts < max_attempts
    
    print(f"  - Expired: {is_expired}")
    print(f"  - Attempts remaining: {has_attempts}")
    print(f"  - PIN was valid: {not is_expired and has_attempts}")
    
    assert payment_verified == True, "Payment should be verified!"
    print("\n✅ Complete flow successful!")


def main():
    """Run all tests"""
    print("=" * 60)
    print("PIN Payment Verification - Manual Test Suite")
    print("=" * 60)
    
    try:
        test_pin_generation()
        test_pin_hashing()
        test_pin_verification()
        test_pin_expiry()
        test_complete_flow()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
