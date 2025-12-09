from django.urls import path

from drivers_app import views

app_name = 'drivers'

urlpatterns = [
    path('dashboard/', views.DriverDashboard.as_view(), name='driver_dashboard'),
    path('active/', views.DriverActiveBookings.as_view(), name='driver_active_books'),
    path('register/tricycle/', views.TricycleRegister.as_view(), name='tricycle_register'),
    path('booking/<int:booking_id>/accept/', views.accept_ride, name='accept_ride'),
    path('booking/<int:booking_id>/cancel/', views.cancel_accepted_booking, name='cancel_accepted_booking'),
    path('booking/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),
    path('api/active-booking/', views.get_driver_active_booking, name='get_driver_active_booking'),
    path('api/trip-history/', views.get_driver_trip_history, name='driver_trip_history'),
    path('api/available-rides/', views.available_rides_api, name='available_rides_api'),
    path('api/location/update/', views.update_driver_location, name='update_driver_location'),
    path('api/booking/<int:booking_id>/location/', views.get_driver_location, name='get_driver_location'),
    path('api/status/', views.driver_status, name='driver_status'),
    path('profile/', views.driver_profile_panel, name='driver_profile_panel'),
    path('profile/update-name/', views.update_driver_name, name='update_driver_name'),
    path('profile/toggle-status/', views.toggle_driver_status, name='toggle_driver_status'),
]
