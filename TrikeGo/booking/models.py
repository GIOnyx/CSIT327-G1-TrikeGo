import uuid

from django.db import models
#from user.models import CustomUser 
from django.utils import timezone
from decimal import Decimal

class Booking(models.Model):
    rider = models.ForeignKey(
        'user.CustomUser',
        on_delete=models.CASCADE,
        related_name='rider_bookings',
        limit_choices_to={'trikego_user': 'R'}
    )
    driver = models.ForeignKey(
        'user.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='driver_bookings',
        limit_choices_to={'trikego_user': 'D'}
    )

    # Location fields
    pickup_address = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)

    destination_address = models.CharField(max_length=255)
    destination_latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    # Number of passengers for this booking. Default is 1.
    passengers = models.PositiveSmallIntegerField(default=1)

    STATUS_CHOICES = [
        ('pending', 'Pending Driver Assignment'),
        ('accepted', 'Driver Accepted'),
        ('on_the_way', 'Driver On The Way'),
        ('started', 'Trip Started'),
        ('completed', 'Completed'),
        ('cancelled_by_rider', 'Cancelled by Rider'),
        ('cancelled_by_driver', 'Cancelled by Driver'),
        ('no_driver_found', 'No Driver Found')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    booking_time = models.DateTimeField(default=timezone.now)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    fare = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Cash payment verification fields
    payment_pin_hash = models.CharField(max_length=128, null=True, blank=True, help_text="Hashed 4-digit PIN for cash payment verification")
    payment_pin_created_at = models.DateTimeField(null=True, blank=True, help_text="When the PIN was generated")
    payment_pin_expires_at = models.DateTimeField(null=True, blank=True, help_text="PIN expiry time (5 minutes)")
    payment_pin_attempts = models.PositiveSmallIntegerField(default=0, help_text="Number of failed PIN verification attempts")
    payment_pin_max_attempts = models.PositiveSmallIntegerField(default=3, help_text="Maximum allowed PIN attempts")
    payment_verified = models.BooleanField(default=False, help_text="Whether cash payment has been verified via PIN")
    payment_verified_at = models.DateTimeField(null=True, blank=True, help_text="When payment was verified")
    
    # Estimated values
    estimated_distance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # in km
    estimated_duration = models.IntegerField(null=True, blank=True)  # in minutes
    estimated_arrival = models.DateTimeField(null=True, blank=True)

    def calculate_fare(self):
        """
        Calculates the estimated fare based on distance and duration.
        estimated_distance should be in km (Decimal) and estimated_duration in minutes (int).
        """
        if self.estimated_distance is None or self.estimated_duration is None:
            # Cannot calculate without estimates
            self.fare = None
            return None 

        # --- FARE STRUCTURE (ADJUST THESE VALUES) ---
        BASE_FARE = Decimal('20.00') # Initial flat rate (PHP)
        PER_KM_RATE = Decimal('5.00') # Rate per kilometer (PHP/km)
        PER_MINUTE_RATE = Decimal('0.75') # Rate per minute (PHP/min)
        MINIMUM_FARE = Decimal('20.00') # Minimum total fare

        # 1. Distance Component
        # Ensure estimated_distance is treated as Decimal for multiplication
        distance_cost = self.estimated_distance * PER_KM_RATE

        # 2. Time Component
        # Convert duration (int minutes) to Decimal
        duration_decimal = Decimal(self.estimated_duration)
        time_cost = duration_decimal * PER_MINUTE_RATE

        # 3. Total Fare
        calculated_fare = BASE_FARE + distance_cost + time_cost
        
        # 4. Apply Minimum Fare and Round
        final_fare = max(calculated_fare, MINIMUM_FARE)
        
        # Set the fare field on the instance, rounded to 2 decimal places
        self.fare = final_fare.quantize(Decimal('0.01'))
        return self.fare

    def __str__(self):
        return f"Booking {self.id} - {self.rider.username} to {self.destination_address}"

    @property
    def is_active(self):
        return self.status in ['pending', 'accepted', 'on_the_way', 'started']
    
    @property
    def is_pin_valid(self):
        """Check if the payment PIN is still valid (not expired and attempts remaining)"""
        if not self.payment_pin_hash or not self.payment_pin_expires_at:
            return False
        if timezone.now() > self.payment_pin_expires_at:
            return False
        if self.payment_pin_attempts >= self.payment_pin_max_attempts:
            return False
        return True
    
    @property
    def pin_attempts_remaining(self):
        """Get remaining PIN verification attempts"""
        if not self.payment_pin_hash:
            return 0
        return max(0, self.payment_pin_max_attempts - self.payment_pin_attempts)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['driver']),
            models.Index(fields=['rider']),
            models.Index(fields=['booking_time']),
            models.Index(fields=['driver', 'status']),
        ]


class BookingStop(models.Model):
    """Represents a single pickup or dropoff stop for a booking within a driver's itinerary."""

    STOP_TYPES = (
        ('PICKUP', 'Pickup'),
        ('DROPOFF', 'Dropoff'),
    )

    STATUS_CHOICES = (
        ('UPCOMING', 'Upcoming'),
        ('CURRENT', 'Current'),
        ('COMPLETED', 'Completed'),
    )

    stop_uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='stops')
    sequence = models.PositiveIntegerField(default=0, db_index=True)
    stop_type = models.CharField(max_length=8, choices=STOP_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UPCOMING')
    passenger_count = models.PositiveSmallIntegerField(default=1)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence', 'created_at']
        indexes = [
            models.Index(fields=['booking', 'sequence']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Stop {self.stop_type} for booking {self.booking_id} (seq {self.sequence})"


class DriverLocation(models.Model):
    """Track real-time driver locations"""
    driver = models.OneToOneField(
        'user.CustomUser',
        on_delete=models.CASCADE,
        related_name='current_location',
        limit_choices_to={'trikego_user': 'D'}
    )
    latitude = models.DecimalField(max_digits=18, decimal_places=15)
    longitude = models.DecimalField(max_digits=18, decimal_places=15)
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Direction in degrees
    speed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Speed in km/h
    accuracy = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # in meters
    timestamp = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Driver Location"
        verbose_name_plural = "Driver Locations"
    
    def __str__(self):
        return f"{self.driver.username} at ({self.latitude}, {self.longitude})"


class RouteSnapshot(models.Model):
    """Store route snapshots for rerouting and history"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='routes')
    route_data = models.JSONField()  # Store GeoJSON route data
    distance = models.DecimalField(max_digits=10, decimal_places=2)  # in km
    duration = models.IntegerField()  # in seconds
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Route for Booking {self.booking.id} at {self.created_at}"
    
class RatingAndFeedback(models.Model):
    """Stores the rider's rating and feedback for a specific booking."""
    
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)] # 1 to 5 stars

    # Links the rating to the completed trip
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='rating',
        verbose_name='Trip Booking'
    )
    
    # Store the user who submitted the rating (the rider)
    rater = models.ForeignKey(
        'user.CustomUser',
        on_delete=models.CASCADE,
        related_name='ratings_given',
        limit_choices_to={'trikego_user': 'R'},
        verbose_name='Rater (Rider)'
    )
    
    # Store the user who is being rated (the driver)
    rated_user = models.ForeignKey(
        'user.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ratings_received',
        limit_choices_to={'trikego_user': 'D'},
        verbose_name='Rated User (Driver)'
    )

    # Rating value (1-5 stars)
    rating_value = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        default=5,
        verbose_name='Star Rating'
    )
    
    # Optional text feedback
    feedback_text = models.TextField(
        blank=True,
        null=True,
        verbose_name='Feedback/Comment'
    )
    
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Rating and Feedback"
        verbose_name_plural = "Ratings and Feedback"
        # Constraint: Ensure a booking can only be rated once
        constraints = [
            models.UniqueConstraint(fields=['booking'], name='unique_booking_rating')
        ]
        
    def __str__(self):
        return f"Rating {self.rating_value} for Booking {self.booking_id}"