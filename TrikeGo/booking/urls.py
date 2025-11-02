from django.urls import path
from . import views, api_views

app_name = 'booking'
urlpatterns = [
    # Existing URLs
    path('create/', views.create_booking, name='create_booking'),
    path('<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    # Real-time tracking API endpoints
    path('api/location/update/', api_views.update_driver_location, name='update_driver_location'),
    path('api/location/<int:booking_id>/', api_views.get_driver_location, name='get_driver_location'),
    path('api/route/<int:booking_id>/', api_views.get_current_route, name='get_current_route'),
    path('api/reroute/<int:booking_id>/', api_views.manual_reroute, name='manual_reroute'),
    path('api/driver/itinerary/', api_views.driver_itinerary, name='driver_itinerary'),
    path('api/itinerary/complete_stop/', api_views.complete_itinerary_stop, name='complete_itinerary_stop'),
    
    # Payment PIN verification endpoints
    path('api/<int:booking_id>/payment/generate-pin/', api_views.generate_payment_pin_endpoint, name='generate_payment_pin'),
    path('api/<int:booking_id>/payment/verify-pin/', api_views.verify_payment_pin_endpoint, name='verify_payment_pin'),
    path('api/<int:booking_id>/payment/pin-status/', api_views.get_payment_pin_status, name='payment_pin_status'),
]