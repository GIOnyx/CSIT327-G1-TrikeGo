from django.test import TestCase
from django.contrib.auth import get_user_model
from booking_app.utils import seats_available, pickup_within_detour
from booking_app.models import Booking
from user_app.models import Driver, Tricycle

User = get_user_model()

class UtilsTestCase(TestCase):
    def setUp(self):
        # create a driver user and profile
        self.user = User.objects.create_user(username='drv1', password='pass', trikego_user='D')
        self.driver_profile = Driver.objects.create(user=self.user, license_number='12345678901', license_expiry='2099-01-01', date_hired='2020-01-01', years_of_service=1)
        # create a tricycle with capacity 3
        self.trike = Tricycle.objects.create(plate_number='ABC123', color='Red', driver=self.driver_profile, max_capacity=3)

    def test_seats_available_counts_passengers(self):
        # no active bookings => seats_available for 1 should be True
        self.assertTrue(seats_available(self.user, additional_seats=1))
        # create an active booking with 2 passengers
        Booking.objects.create(rider=self._create_rider(), driver=self.user, pickup_address='A', destination_address='B', status='accepted', passengers=2)
        # now active seats = 2, capacity = 3 -> can accept 1 more
        self.assertTrue(seats_available(self.user, additional_seats=1))
        # cannot accept 2 more
        self.assertFalse(seats_available(self.user, additional_seats=2))

    def test_pickup_within_detour(self):
        # Set driver current location
        self.driver_profile.current_latitude = 14.5995
        self.driver_profile.current_longitude = 120.9842
        self.driver_profile.save()
        # pickup within ~300m
        ok = pickup_within_detour(self.user, 14.6020, 120.9842, max_km=0.5)
        self.assertTrue(ok)
        # pickup far > 0.5km
        far = pickup_within_detour(self.user, 14.6200, 120.9842, max_km=0.5)
        self.assertFalse(far)

    def _create_rider(self):
        r = User.objects.create_user(username='r1'+self._rand(), password='p', trikego_user='R')
        return r
    def _rand(self):
        import random
        return str(random.randint(1000,9999))
