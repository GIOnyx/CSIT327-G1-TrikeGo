from django.urls import path

from ratings import views

app_name = 'ratings'

urlpatterns = [
    path('booking/<int:booking_id>/rate/', views.rate_booking, name='rate_booking'),
    path('api/booking/<int:booking_id>/submit/', views.submit_rating_ajax, name='submit_rating_ajax'),
]
