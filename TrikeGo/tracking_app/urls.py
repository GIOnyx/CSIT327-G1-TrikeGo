from django.urls import path
from . import api_views

app_name = 'tracking'
urlpatterns = [
    path('location/update/', api_views.update_driver_location, name='update_driver_location'),
    path('location/<int:booking_id>/', api_views.get_driver_location, name='get_driver_location'),
    path('route/<int:booking_id>/', api_views.get_current_route, name='get_current_route'),
    path('reroute/<int:booking_id>/', api_views.manual_reroute, name='manual_reroute'),
    path('driver/itinerary/', api_views.driver_itinerary, name='driver_itinerary'),
    path('itinerary/complete_stop/', api_views.complete_itinerary_stop, name='complete_itinerary_stop'),
]
