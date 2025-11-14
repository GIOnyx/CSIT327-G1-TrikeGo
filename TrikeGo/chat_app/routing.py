from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/chat/<int:booking_id>/', consumers.ChatConsumer.as_asgi()),
]
