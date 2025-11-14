from django.test import TestCase
from booking_app.forms import BookingForm

class BookingFormTest(TestCase):
    def test_passengers_default_and_validation(self):
        data = {
            'pickup_address': 'A',
            'pickup_latitude': '14.5995',
            'pickup_longitude': '120.9842',
            'destination_address': 'B',
            'destination_latitude': '14.6030',
            'destination_longitude': '120.9842',
            'passengers': '2'
        }
        form = BookingForm(data=data)
        self.assertTrue(form.is_valid())
        cleaned = form.clean()
        self.assertEqual(int(form.cleaned_data.get('passengers')), 2)

    def test_passengers_invalid_values(self):
        data = {
            'pickup_address': 'A',
            'pickup_latitude': '14.5995',
            'pickup_longitude': '120.9842',
            'destination_address': 'B',
            'destination_latitude': '14.6030',
            'destination_longitude': '120.9842',
            'passengers': '0'
        }
        form = BookingForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('passengers', form.errors)
