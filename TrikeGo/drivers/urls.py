from django.urls import path

from drivers import views

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
    path('api/location/update/', views.update_driver_location, name='update_driver_location'),
    path('api/booking/<int:booking_id>/location/', views.get_driver_location, name='get_driver_location'),
]
