from django.urls import path
from . import views

app_name = 'user'

urlpatterns = [
    path('', views.LandingPage.as_view(), name='landing'),

    # Authentication
    path('login/', views.Login.as_view(), name='login'),
    path('register/', views.RegisterPage.as_view(), name='register'),
    path('logged_in/', views.LoggedIn.as_view(), name='logged_in'),

    # Dashboards
    path('rider_dashboard/', views.RiderDashboard.as_view(), name='rider_dashboard'),
    path('driver_dashboard/', views.DriverDashboard.as_view(), name='driver_dashboard'),
    path('trike-admin/dashboard/', views.AdminDashboard.as_view(), name='admin_dashboard'),
    path('register/tricycle/', views.TricycleRegister.as_view(), name='tricycle_register'),

    # Ride actions
    path('accept_ride/<int:booking_id>/', views.accept_ride, name='accept_ride'),
    path('driver_active_books', views.DriverActiveBookings.as_view(), name='driver_active_books'),
    path('driver/active/<int:booking_id>/cancel/', views.cancel_accepted_booking, name='cancel_accepted_booking'),
    path('driver/active/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),
    path('rider/booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('<int:booking_id>/rate/', views.rate_booking, name='rate_booking'),
    path('api/booking/<int:booking_id>/submit_rating/', views.submit_rating_ajax, name='submit_rating_ajax'),

    # --- ADDED: REAL-TIME TRACKING API URLS ---
    path('api/driver/update_location/', views.update_driver_location, name='update_driver_location'),
    path('api/booking/<int:booking_id>/driver_location/', views.get_driver_location, name='get_driver_location'),
    path('api/rider/update_location/', views.update_rider_location, name='update_rider_location'),
    path('api/booking/<int:booking_id>/route_info/', views.get_route_info, name='get_route_info'),
    path('api/driver/active-booking/', views.get_driver_active_booking, name='get_driver_active_booking'),
    
    # --- TRIP HISTORY API URLS ---
    path('api/rider/trip-history/', views.get_rider_trip_history, name='rider_trip_history'),
    path('api/driver/trip-history/', views.get_driver_trip_history, name='driver_trip_history'),
    
    # Custom logout that redirects to landing (accepts POST)
    path('logout/', views.logout_view, name='logout'),
]

