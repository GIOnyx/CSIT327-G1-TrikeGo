from django.urls import path
from . import views
from payments import api_views as payments_api
from tracking import api_views as tracking_api

app_name = 'booking'
urlpatterns = [
    # Existing URLs
    path('create/', views.create_booking, name='create_booking'),
    path('<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    # Real-time tracking API endpoints
    # Tracking endpoints moved to tracking app (wrappers)
    path('api/location/update/', tracking_api.update_driver_location, name='update_driver_location'),
    path('api/location/<int:booking_id>/', tracking_api.get_driver_location, name='get_driver_location'),
    path('api/route/<int:booking_id>/', tracking_api.get_current_route, name='get_current_route'),
    path('api/reroute/<int:booking_id>/', tracking_api.manual_reroute, name='manual_reroute'),
    path('api/driver/itinerary/', tracking_api.driver_itinerary, name='driver_itinerary'),
    path('api/itinerary/complete_stop/', tracking_api.complete_itinerary_stop, name='complete_itinerary_stop'),
    
    # Payment PIN verification endpoints
    # Payment PIN endpoints moved to payments app
    path('api/<int:booking_id>/payment/generate-pin/', payments_api.generate_payment_pin_endpoint, name='generate_payment_pin'),
    path('api/<int:booking_id>/payment/verify-pin/', payments_api.verify_payment_pin_endpoint, name='verify_payment_pin'),
    path('api/<int:booking_id>/payment/pin-status/', payments_api.get_payment_pin_status, name='payment_pin_status'),
]