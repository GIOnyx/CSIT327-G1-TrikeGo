from django.contrib import admin
from .models import Booking, DriverLocation, RouteSnapshot

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'rider', 'driver', 'status', 'pickup_address', 'destination_address', 'booking_time', 'estimated_arrival']
    list_filter = ['status', 'booking_time']
    search_fields = ['rider__username', 'driver__username', 'pickup_address', 'destination_address']
    readonly_fields = ['booking_time', 'estimated_distance', 'estimated_duration']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('rider', 'driver', 'status', 'booking_time')
        }),
        ('Pickup Location', {
            'fields': ('pickup_address', 'pickup_latitude', 'pickup_longitude')
        }),
        ('Destination', {
            'fields': ('destination_address', 'destination_latitude', 'destination_longitude')
        }),
        ('Trip Details', {
            'fields': ('start_time', 'end_time', 'fare')
        }),
        ('Estimates', {
            'fields': ('estimated_distance', 'estimated_duration', 'estimated_arrival')
        }),
    )

@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ['driver', 'latitude', 'longitude', 'speed', 'heading', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['driver__username']
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        return False

@admin.register(RouteSnapshot)
class RouteSnapshotAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking', 'distance', 'duration', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['booking__id']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False