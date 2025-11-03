from django.urls import path
from . import views
from drivers import views as driver_views
from ratings import views as rating_views

app_name = 'user'

urlpatterns = [
    path('', views.LandingPage.as_view(), name='landing'),

    # Authentication
    path('login/', views.Login.as_view(), name='login'),
    path('register/', views.RegisterPage.as_view(), name='register'),
    path('logged_in/', views.LoggedIn.as_view(), name='logged_in'),

    # Dashboards
    path('rider_dashboard/', views.RiderDashboard.as_view(), name='rider_dashboard'),
    path('driver_dashboard/', driver_views.DriverDashboard.as_view(), name='driver_dashboard'),
    path('trike-admin/dashboard/', views.AdminDashboard.as_view(), name='admin_dashboard'),
    path('register/tricycle/', driver_views.TricycleRegister.as_view(), name='tricycle_register'),

    # Ride actions
    path('accept_ride/<int:booking_id>/', driver_views.accept_ride, name='accept_ride'),
    path('driver_active_books', driver_views.DriverActiveBookings.as_view(), name='driver_active_books'),
    path('driver/active/<int:booking_id>/cancel/', driver_views.cancel_accepted_booking, name='cancel_accepted_booking'),
    path('driver/active/<int:booking_id>/complete/', driver_views.complete_booking, name='complete_booking'),
    path('rider/booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('<int:booking_id>/rate/', rating_views.rate_booking, name='rate_booking'),
    path('api/booking/<int:booking_id>/submit_rating/', rating_views.submit_rating_ajax, name='submit_rating_ajax'),

    # --- ADDED: REAL-TIME TRACKING API URLS ---
    path('api/driver/update_location/', driver_views.update_driver_location, name='update_driver_location'),
    path('api/booking/<int:booking_id>/driver_location/', driver_views.get_driver_location, name='get_driver_location'),
    path('api/rider/update_location/', views.update_rider_location, name='update_rider_location'),
    path('api/booking/<int:booking_id>/route_info/', views.get_route_info, name='get_route_info'),
    path('api/driver/active-booking/', driver_views.get_driver_active_booking, name='get_driver_active_booking'),
    
    # --- TRIP HISTORY API URLS ---
    path('api/rider/trip-history/', views.get_rider_trip_history, name='rider_trip_history'),
    path('api/driver/trip-history/', driver_views.get_driver_trip_history, name='driver_trip_history'),
    
    # Custom logout that redirects to landing (accepts POST)
    path('logout/', views.logout_view, name='logout'),
]

