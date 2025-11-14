from django.urls import path
from . import api_views

app_name = 'chat'

urlpatterns = [
    # Get all messages for a booking
    path('api/booking/<int:booking_id>/messages/', api_views.get_messages, name='get_messages'),
    # Send a message for a booking
    path('api/booking/<int:booking_id>/messages/send/', api_views.post_message, name='post_message'),
]
