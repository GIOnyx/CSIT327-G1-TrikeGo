from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
import re

from user_app.models import CustomUser, Driver, Tricycle


class DriverRegistrationForm(UserCreationForm):
    """Registration form dedicated to driver onboarding."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'})
    )
    phone = forms.CharField(
        max_length=11,
        required=True,
        help_text="Format: 09XXXXXXXXX",
        widget=forms.TextInput(attrs={
            'pattern': r'^09\d{9}$',
            'inputmode': 'numeric',
            'maxlength': '11',
            'placeholder': 'Phone number (09XXXXXXXXX)'
        })
    )
    license_number = forms.CharField(
        max_length=11,
        required=True,
        widget=forms.TextInput(attrs={
            'pattern': r'^\d{11}$',
            'inputmode': 'numeric',
            'maxlength': '11',
            'placeholder': "Driver's License Number"
        })
    )
    license_image_url = forms.URLField(
        required=True,
        help_text="URL to your driver's license image",
        widget=forms.URLInput(attrs={'placeholder': 'License Image URL (must start with https://)'})
    )

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'password1',
            'password2',
            'email',
            'first_name',
            'last_name',
            'phone',
            'license_number',
            'license_image_url',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Choose a username'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Enter a password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm your password'})

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if not re.match(r'^09\d{9}$', phone):
            raise ValidationError('Phone must be in the format 09XXXXXXXXX')
        return phone

    def clean_license_number(self):
        license_number = self.cleaned_data.get('license_number', '')
        if not re.match(r'^\d{11}$', license_number):
            raise ValidationError('License number must be 11 digits')
        return license_number

    def clean_license_image_url(self):
        url = self.cleaned_data.get('license_image_url', '')
        if not url.startswith('https://'):
            raise ValidationError('License image URL must start with https://')
        return url


class DriverVerificationForm(forms.Form):
    """Admin action form to toggle a driver's verification flag."""

    driver_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.CharField(widget=forms.HiddenInput())

    def clean_action(self):
        action = self.cleaned_data.get('action')
        if action not in ['toggle_verify']:
            raise ValidationError('Invalid action.')
        return action

    def clean_driver_id(self):
        driver_id = self.cleaned_data.get('driver_id')
        try:
            Driver.objects.get(id=driver_id)
        except Driver.DoesNotExist as exc:
            raise ValidationError('Driver does not exist.') from exc
        return driver_id


class TricycleForm(forms.ModelForm):
    """Collect vehicle metadata during driver registration."""

    max_capacity = forms.IntegerField(
        min_value=1,
        max_value=20,
        required=True,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Max passengers (e.g. 8)',
            'required': True,
            'min': 1,
            'max': 20,
        })
    )

    class Meta:
        model = Tricycle
        fields = [
            'plate_number',
            'color',
            'max_capacity',
            'image_url',
            'or_image_url',
            'cr_image_url',
            'mtop_image_url',
        ]
        widgets = {
            'plate_number': forms.TextInput(attrs={'placeholder': 'Plate number', 'required': True}),
            'color': forms.TextInput(attrs={'placeholder': 'Tricycle color', 'required': True}),
            'image_url': forms.URLInput(attrs={'placeholder': 'Tricycle Image URL', 'required': True}),
            'or_image_url': forms.URLInput(attrs={'placeholder': 'Official Receipt (OR) Image URL', 'required': True}),
            'cr_image_url': forms.URLInput(attrs={'placeholder': 'Certificate of Registration (CR) Image URL', 'required': True}),
            'mtop_image_url': forms.URLInput(attrs={'placeholder': 'MTOP/Franchise Document Image URL', 'required': True}),
        }

    def clean_plate_number(self):
        plate = self.cleaned_data.get('plate_number', '').strip()
        if not plate:
            raise ValidationError('Plate number is required.')
        if Tricycle.objects.filter(plate_number__iexact=plate).exists():
            raise ValidationError('A tricycle with this plate number already exists.')
        return plate

    def clean_image_url(self):
        url = self.cleaned_data.get('image_url', '')
        if not url.startswith('https://'):
            raise ValidationError('Tricycle image URL must start with https://')
        return url

    def clean_or_image_url(self):
        url = self.cleaned_data.get('or_image_url', '')
        if not url.startswith('https://'):
            raise ValidationError('OR image URL must start with https://')
        return url

    def clean_cr_image_url(self):
        url = self.cleaned_data.get('cr_image_url', '')
        if not url.startswith('https://'):
            raise ValidationError('CR image URL must start with https://')
        return url

    def clean_mtop_image_url(self):
        url = self.cleaned_data.get('mtop_image_url', '')
        if not url.startswith('https://'):
            raise ValidationError('MTOP image URL must start with https://')
        return url

    def clean_max_capacity(self):
        cap = self.cleaned_data.get('max_capacity')
        try:
            cap = int(cap)
        except Exception as exc:
            raise ValidationError('Max capacity must be an integer') from exc
        if cap < 1:
            raise ValidationError('Max capacity must be at least 1')
        if cap > 20:
            raise ValidationError('Max capacity seems too large')
        return cap
