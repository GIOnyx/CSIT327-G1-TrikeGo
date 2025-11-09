# discount/models.py

import uuid
from django.db import models
from django.utils import timezone
from decimal import Decimal

class DiscountCode(models.Model):
    """Model to store discount codes and their rules."""

    DISCOUNT_TYPE_CHOICES = [
        ('P', 'Percentage'), # e.g., 10% off
        ('F', 'Fixed Amount'), # e.g., $5.00 off
    ]

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="The actual code (e.g., 'SUMMER10')"
    )
    is_active = models.BooleanField(default=True)
    discount_type = models.CharField(
        max_length=1,
        choices=DISCOUNT_TYPE_CHOICES,
        default='P'
    )
    value = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="The value (e.g., 10.00 for 10% or $10.00 fixed)"
    )
    max_uses = models.PositiveIntegerField(
        default=0,
        help_text="Maximum total times the code can be used (0 for unlimited)"
    )
    uses_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    min_fare = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum fare required to use this code"
    )

    class Meta:
        verbose_name = "Discount Code"
        verbose_name_plural = "Discount Codes"

    def __str__(self):
        return self.code
    
    @property
    def is_valid_now(self):
        """Check if the code is currently active and not expired."""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_to and self.valid_to < now:
            return False
        if self.max_uses > 0 and self.uses_count >= self.max_uses:
            return False
        return True