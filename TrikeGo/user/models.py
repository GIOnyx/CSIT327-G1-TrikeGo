from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg, Count
from booking.models import RatingAndFeedback

class CustomUser(AbstractUser):
    USER_TYPES = (
        ('R', 'Rider'),
        ('A', 'Admin'),
        ('D', 'Driver'),
    )
    
    phone = models.CharField(max_length=20, blank=True, null=True)
    trikego_user = models.CharField(max_length=1, choices=USER_TYPES, default='R')


class Admin(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    position = models.CharField(max_length=100)
    date_hired = models.DateField()
    years_of_service = models.IntegerField()


class Driver(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    license_number = models.CharField(max_length=11)
    license_image_url = models.URLField(blank=True, null=True)
    license_expiry = models.DateField()
    date_hired = models.DateField()
    years_of_service = models.IntegerField()
    STATUS_CHOICES = (
        ('Offline', 'Offline'),
        ('Online', 'Online'),
        ('In_trip', 'In trip'),
    )
    @property
    def average_rating(self):
        """Calculates the average rating received by this driver."""
        
        # 1. Query the RatingAndFeedback model, filtering by the driver's user account (self.user)
        result = RatingAndFeedback.objects.filter(
            rated_user=self.user
        ).aggregate(
            average=Avg('rating_value'),
            count=Count('id')
        )
        
        avg = result['average']
        count = result['count']
        
        if avg is None:
            # Return 0.0 if no ratings exist yet
            return {'average': 0.0, 'count': 0}
        
        # 2. Round the average to one decimal place for clean display
        return {
            'average': round(float(avg), 1),
            'count': count
        }
    # status only represents availability/engagement. Pending approval is tracked with `is_verified`.
    # longest choice value is 'In_trip' (7 chars) so max_length can be small but keep 16 for safety.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='Offline')
    is_verified = models.BooleanField(default=False)
    current_latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)


class Tricycle(models.Model):
    plate_number = models.CharField(max_length=32, unique=True)
    color = models.CharField(max_length=32)
    # Maximum number of passengers this tricycle can carry. Default to 1 for single-rider trikes.
    max_capacity = models.PositiveSmallIntegerField(default=1)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='tricycles')
    image_url = models.URLField(blank=True, null=True)
    # Registration documents
    or_image_url = models.URLField(blank=True, null=True, verbose_name='Official Receipt (OR)')
    cr_image_url = models.URLField(blank=True, null=True, verbose_name='Certificate of Registration (CR)')
    mtop_image_url = models.URLField(blank=True, null=True, verbose_name='MTOP/Franchise Document')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tricycle'

    def __str__(self):
        return f"Trike {self.plate_number} ({self.color})"

class Rider(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    loyalty_points = models.IntegerField(default=0)
    # --- NEW FIELDS FOR RIDER TRACKING ---
    current_latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    # Rider availability status
    STATUS_CHOICES = (
        ('Available', 'Available'),
        ('In_trip', 'In trip'),
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='Available')

