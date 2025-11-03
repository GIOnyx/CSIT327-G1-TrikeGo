from django import forms

from booking.models import RatingAndFeedback


class RatingForm(forms.ModelForm):
    """Collect rider feedback for a completed booking."""

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
                'class': 'form-control',
            }),
        }
