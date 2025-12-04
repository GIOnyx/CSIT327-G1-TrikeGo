"""
Unit tests for Payment PIN verification system.
Tests PIN generation, verification, expiry, and security features.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from rest_framework.test import APIClient
from decimal import Decimal

from booking_app.models import Booking
from booking_app.utils import (
    generate_payment_pin,
    hash_payment_pin,
    verify_payment_pin,
    get_pin_expiry_time
)
from user_app.models import CustomUser

User = get_user_model()


class PaymentPINUtilsTest(TestCase):
    """Test utility functions for PIN generation and verification"""
    
    def test_generate_payment_pin_format(self):
        """Test that generated PIN is 4 digits"""
        pin = generate_payment_pin()
        self.assertEqual(len(pin), 4)
        self.assertTrue(pin.isdigit())
    
    def test_generate_payment_pin_uniqueness(self):
        """Test that multiple PIN generations produce different results (most of the time)"""
        pins = [generate_payment_pin() for _ in range(100)]
        # At least 90% should be unique (allowing for rare collisions)
        unique_pins = set(pins)
        self.assertGreater(len(unique_pins), 90)
    
    def test_hash_payment_pin(self):
        """Test that PIN hashing works"""
        pin = "1234"
        pin_hash = hash_payment_pin(pin)
        self.assertIsNotNone(pin_hash)
        self.assertNotEqual(pin, pin_hash)
        self.assertGreater(len(pin_hash), 20)  # Hashes are long
    
    def test_verify_payment_pin_success(self):
        """Test successful PIN verification"""
        pin = "5678"
        pin_hash = hash_payment_pin(pin)
        self.assertTrue(verify_payment_pin(pin, pin_hash))
    
    def test_verify_payment_pin_failure(self):
        """Test failed PIN verification"""
        pin = "1234"
        pin_hash = hash_payment_pin(pin)
        self.assertFalse(verify_payment_pin("9999", pin_hash))
    
    def test_get_pin_expiry_time(self):
        """Test PIN expiry time calculation"""
        expiry = get_pin_expiry_time(5)
        now = timezone.now()
        diff = (expiry - now).total_seconds()
        # Should be approximately 5 minutes (300 seconds)
        self.assertGreater(diff, 299)
        self.assertLess(diff, 301)


class PaymentPINModelTest(TestCase):
    """Test Booking model properties related to PIN"""
    
    def setUp(self):
        self.rider = CustomUser.objects.create_user(
            username='rider1',
            email='rider1@test.com',
            password='testpass123',
            trikego_user='P'
        )
        self.driver = CustomUser.objects.create_user(
            username='driver1',
            email='driver1@test.com',
            password='testpass123',
            trikego_user='D'
        )
        self.booking = Booking.objects.create(
            rider=self.rider,
            driver=self.driver,
            pickup_address="Location A",
            destination_address="Location B",
            status='started',
            fare=Decimal('50.00')
        )
    
    def test_is_pin_valid_no_pin(self):
        """Test is_pin_valid when no PIN exists"""
        self.assertFalse(self.booking.is_pin_valid)
    
    def test_is_pin_valid_with_valid_pin(self):
        """Test is_pin_valid with a valid, non-expired PIN"""
        self.booking.payment_pin_hash = hash_payment_pin("1234")
        self.booking.payment_pin_expires_at = timezone.now() + timedelta(minutes=5)
        self.booking.payment_pin_attempts = 0
        self.booking.save()
        
        self.assertTrue(self.booking.is_pin_valid)
    
    def test_is_pin_valid_expired(self):
        """Test is_pin_valid with expired PIN"""
        self.booking.payment_pin_hash = hash_payment_pin("1234")
        self.booking.payment_pin_expires_at = timezone.now() - timedelta(minutes=1)
        self.booking.payment_pin_attempts = 0
        self.booking.save()
        
        self.assertFalse(self.booking.is_pin_valid)
    
    def test_is_pin_valid_max_attempts(self):
        """Test is_pin_valid when max attempts reached"""
        self.booking.payment_pin_hash = hash_payment_pin("1234")
        self.booking.payment_pin_expires_at = timezone.now() + timedelta(minutes=5)
        self.booking.payment_pin_attempts = 3
        self.booking.payment_pin_max_attempts = 3
        self.booking.save()
        
        self.assertFalse(self.booking.is_pin_valid)
    
    def test_pin_attempts_remaining(self):
        """Test pin_attempts_remaining property"""
        self.booking.payment_pin_hash = hash_payment_pin("1234")
        self.booking.payment_pin_attempts = 1
        self.booking.payment_pin_max_attempts = 3
        self.booking.save()
        
        self.assertEqual(self.booking.pin_attempts_remaining, 2)


class PaymentPINAPITest(TestCase):
    """Test API endpoints for PIN generation and verification"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create rider and driver users
        self.rider = CustomUser.objects.create_user(
            username='passenger1',
            email='passenger1@test.com',
            password='testpass123',
            trikego_user='P'
        )
        self.driver = CustomUser.objects.create_user(
            username='driver1',
            email='driver1@test.com',
            password='testpass123',
            trikego_user='D'
        )
        
        # Create a booking
        self.booking = Booking.objects.create(
            passenger=self.passenger,
            driver=self.driver,
            pickup_address="Location A",
            pickup_latitude=Decimal('10.123456'),
            pickup_longitude=Decimal('123.456789'),
            destination_address="Location B",
            destination_latitude=Decimal('10.987654'),
            destination_longitude=Decimal('123.987654'),
            status='started',
            fare=Decimal('50.00')
        )
    
    def test_generate_pin_as_driver_success(self):
        """Test successful PIN generation by driver"""
        self.client.force_authenticate(user=self.driver)
        url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('pin', response.data)
        self.assertEqual(len(response.data['pin']), 4)
        self.assertTrue(response.data['pin'].isdigit())
        
        # Check database
        self.booking.refresh_from_db()
        self.assertIsNotNone(self.booking.payment_pin_hash)
        self.assertIsNotNone(self.booking.payment_pin_expires_at)
    
    def test_generate_pin_as_passenger_forbidden(self):
        """Test that passengers cannot generate PIN"""
        self.client.force_authenticate(user=self.passenger)
        url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, 403)
    
    def test_generate_pin_wrong_driver_forbidden(self):
        """Test that only assigned driver can generate PIN"""
        other_driver = CustomUser.objects.create_user(
            username='driver2',
            email='driver2@test.com',
            password='testpass123',
            trikego_user='D'
        )
        self.client.force_authenticate(user=other_driver)
        url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, 403)
    
    def test_generate_pin_invalid_status(self):
        """Test PIN generation fails if booking is not in 'started' status"""
        self.booking.status = 'pending'
        self.booking.save()
        
        self.client.force_authenticate(user=self.driver)
        url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.data['message'].lower())
    
    def test_generate_pin_already_verified(self):
        """Test PIN generation fails if payment already verified"""
        self.booking.payment_verified = True
        self.booking.save()
        
        self.client.force_authenticate(user=self.driver)
        url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('already verified', response.data['message'].lower())
    
    def test_verify_pin_as_passenger_success(self):
        """Test successful PIN verification by rider"""
        # First generate PIN as driver
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        gen_response = self.client.post(gen_url, {})
        pin = gen_response.data['pin']
        
        # Now verify as passenger
        self.client.force_authenticate(user=self.rider)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        verify_response = self.client.post(verify_url, {'pin': pin})
        
        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.data['status'], 'success')
        
        # Check database
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.payment_verified)
        self.assertIsNotNone(self.booking.payment_verified_at)
        self.assertEqual(self.booking.status, 'completed')
    
    def test_verify_pin_incorrect_pin(self):
        """Test PIN verification with incorrect PIN"""
        # Generate PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        self.client.post(gen_url, {})
        
        # Verify with wrong PIN
        self.client.force_authenticate(user=self.rider)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        verify_response = self.client.post(verify_url, {'pin': '9999'})
        
        self.assertEqual(verify_response.status_code, 400)
        self.assertIn('incorrect', verify_response.data['message'].lower())
        
        # Check attempts incremented
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_pin_attempts, 1)
        self.assertFalse(self.booking.payment_verified)
    
    def test_verify_pin_max_attempts(self):
        """Test PIN verification fails after max attempts"""
        # Generate PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        self.client.post(gen_url, {})
        
        # Make 3 wrong attempts
        self.client.force_authenticate(user=self.rider)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        
        for i in range(3):
            response = self.client.post(verify_url, {'pin': '9999'})
            self.assertEqual(response.status_code, 400)
        
        # Fourth attempt should be blocked
        response = self.client.post(verify_url, {'pin': '9999'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('maximum', response.data['message'].lower())
        
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_pin_attempts, 3)
    
    def test_verify_pin_expired(self):
        """Test PIN verification fails with expired PIN"""
        # Manually set expired PIN
        self.booking.payment_pin_hash = hash_payment_pin("1234")
        self.booking.payment_pin_expires_at = timezone.now() - timedelta(minutes=1)
        self.booking.save()
        
        self.client.force_authenticate(user=self.rider)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        response = self.client.post(verify_url, {'pin': '1234'})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.data['message'].lower())
    
    def test_verify_pin_invalid_format(self):
        """Test PIN verification with invalid format"""
        # Generate PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        self.client.post(gen_url, {})
        
        # Test various invalid formats
        self.client.force_authenticate(user=self.rider)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        
        invalid_pins = ['123', '12345', 'abcd', '12a4', '']
        for invalid_pin in invalid_pins:
            response = self.client.post(verify_url, {'pin': invalid_pin})
            self.assertEqual(response.status_code, 400)
    
    def test_verify_pin_as_driver_forbidden(self):
        """Test that drivers cannot verify PIN"""
        # Generate PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        gen_response = self.client.post(gen_url, {})
        pin = gen_response.data['pin']
        
        # Try to verify as driver (should fail)
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        verify_response = self.client.post(verify_url, {'pin': pin})
        
        self.assertEqual(verify_response.status_code, 403)
    
    def test_get_payment_pin_status(self):
        """Test getting PIN status"""
        # Generate PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        self.client.post(gen_url, {})
        
        # Get status
        status_url = reverse('booking:payment_pin_status', kwargs={'booking_id': self.booking.id})
        response = self.client.get(status_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['pin_exists'])
        self.assertTrue(response.data['pin_valid'])
        self.assertFalse(response.data['payment_verified'])
        self.assertEqual(response.data['attempts_remaining'], 3)
    
    def test_get_payment_pin_status_unauthorized(self):
        """Test that unauthorized users cannot check PIN status"""
        other_user = CustomUser.objects.create_user(
            username='other_user',
            email='other@test.com',
            password='testpass123',
            trikego_user='P'
        )
        
        self.client.force_authenticate(user=other_user)
        status_url = reverse('booking:payment_pin_status', kwargs={'booking_id': self.booking.id})
        response = self.client.get(status_url)
        
        self.assertEqual(response.status_code, 403)


class PaymentPINIntegrationTest(TestCase):
    """Integration tests for complete payment flow"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.rider = CustomUser.objects.create_user(
            username='rider1',
            email='rider1@test.com',
            password='testpass123',
            trikego_user='P'
        )
        self.driver = CustomUser.objects.create_user(
            username='driver1',
            email='driver1@test.com',
            password='testpass123',
            trikego_user='D'
        )
        
        self.booking = Booking.objects.create(
            rider=self.rider,
            driver=self.driver,
            pickup_address="Location A",
            destination_address="Location B",
            status='started',
            fare=Decimal('50.00')
        )
    
    def test_complete_payment_flow(self):
        """Test the complete payment verification flow"""
        # 1. Driver generates PIN
        self.client.force_authenticate(user=self.driver)
        gen_url = reverse('booking:generate_payment_pin', kwargs={'booking_id': self.booking.id})
        gen_response = self.client.post(gen_url, {})
        
        self.assertEqual(gen_response.status_code, 200)
        pin = gen_response.data['pin']
        
        # 2. Rider checks status (should show PIN exists)
        self.client.force_authenticate(user=self.rider)
        status_url = reverse('booking:payment_pin_status', kwargs={'booking_id': self.booking.id})
        status_response = self.client.get(status_url)
        
        self.assertTrue(status_response.data['pin_exists'])
        self.assertTrue(status_response.data['pin_valid'])
        
        # 3. Rider enters correct PIN
        verify_url = reverse('booking:verify_payment_pin', kwargs={'booking_id': self.booking.id})
        verify_response = self.client.post(verify_url, {'pin': pin})
        
        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.data['status'], 'success')
        
        # 4. Verify booking is completed
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.payment_verified)
        self.assertEqual(self.booking.status, 'completed')
        self.assertIsNotNone(self.booking.payment_verified_at)
        self.assertIsNotNone(self.booking.end_time)
        
        # 5. Verify cannot generate new PIN after payment verified
        self.client.force_authenticate(user=self.driver)
        gen_response2 = self.client.post(gen_url, {})
        self.assertEqual(gen_response2.status_code, 400)
        
        # 6. Verify cannot verify again
        self.client.force_authenticate(user=self.rider)
        verify_response2 = self.client.post(verify_url, {'pin': pin})
        self.assertEqual(verify_response2.status_code, 400)
