from django import forms
from .models import Booking
import math
from .models import RatingAndFeedback

class BookingForm(forms.ModelForm):
    passengers = forms.IntegerField(
        min_value=1,
        max_value=20,
        initial=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'max': 20,
            'value': 1,
            'placeholder': 'Number of passengers',
            'id': 'id_passengers'
        })
    )
    class Meta:
        model = Booking
        fields = [
            'pickup_address',
            'pickup_latitude',
            'pickup_longitude',
            'destination_address',
            'destination_latitude',
            'destination_longitude',
            'passengers',
        ]
        widgets = {
            'pickup_address': forms.TextInput(attrs={
                'placeholder': 'Enter pickup location',
                'id': 'pickup_location_input',
                'class': 'autocomplete-input',
                'autocomplete': 'off'
            }),
            'destination_address': forms.TextInput(attrs={
                'placeholder': 'Enter destination',
                'id': 'destination_location_input',
                'class': 'autocomplete-input',
                'autocomplete': 'off'
            }),
            'pickup_latitude': forms.HiddenInput(),
            'pickup_longitude': forms.HiddenInput(),
            'destination_latitude': forms.HiddenInput(),
            'destination_longitude': forms.HiddenInput(),
            'passengers': forms.NumberInput(attrs={
                'min': 1,
                'max': 20,
                'value': 1,
                'placeholder': 'Number of passengers',
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        pickup = cleaned_data.get('pickup_address')
        destination = cleaned_data.get('destination_address')
        pickup_lat = cleaned_data.get('pickup_latitude')
        pickup_lon = cleaned_data.get('pickup_longitude')
        dest_lat = cleaned_data.get('destination_latitude')
        dest_lon = cleaned_data.get('destination_longitude')
        
        # Prefer coordinate-based comparison: if coordinates are provided, use distance to decide.
        if all([pickup_lat, pickup_lon, dest_lat, dest_lon]):
            distance = self._calculate_distance(
                float(pickup_lat), float(pickup_lon),
                float(dest_lat), float(dest_lon)
            )

            # If coordinates are very close, reject. Otherwise allow even if textual addresses look identical
            if distance < 20:  # Less than 20 meters (reduced threshold for tricycle-scale trips)
                raise forms.ValidationError(
                    f'Pickup and destination are too close ({distance:.0f}m apart). '
                    'Please select locations at least 50 meters apart.'
                )
        else:
            # Fallback: if coordinates aren't available, fall back to textual equality check
            if pickup and destination and pickup.strip() and destination.strip() and pickup.strip() == destination.strip():
                raise forms.ValidationError('Pickup and destination must be different locations.')
        
        return cleaned_data
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def clean_passengers(self):
        val = self.cleaned_data.get('passengers')
        try:
            v = int(val)
        except Exception:
            raise forms.ValidationError('Passengers must be an integer')
        if v < 1:
            raise forms.ValidationError('There must be at least 1 passenger')
        if v > 20:
            raise forms.ValidationError('Passengers exceeds allowed maximum')
        return v

class RatingForm(forms.ModelForm):
    """Form for rider to submit star rating and text feedback after a trip."""

    # Explicitly define rating_value as a field to use the choices from the model
    rating_value = forms.ChoiceField(
        choices=RatingAndFeedback.RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'rating-star-radio'}),
        initial=5,
        label='How would you rate your driver?'
    )

    class Meta:
        model = RatingAndFeedback
        fields = ['rating_value', 'feedback_text']
        widgets = {
            'feedback_text': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional: Tell us about your experience...',
                'class': 'form-control'
            }),
        }