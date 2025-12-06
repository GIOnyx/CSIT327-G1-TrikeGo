from django import forms
from .models import DiscountCode

class DiscountCodeForm(forms.ModelForm):
    class Meta:
        model = DiscountCode
        fields = [
            "code",
            "is_active",
            "discount_type",
            "value",
            "cost",
            "max_uses",
            "valid_from",
            "valid_to",
            "min_fare",
        ]

        widgets = {
            "valid_from": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            "valid_to": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }