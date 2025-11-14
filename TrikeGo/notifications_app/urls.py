from django.urls import path

from .views import PushSubscriptionView, send_test_notification
from .views import public_vapid_key, unsubscribe, sw_subscribe

app_name = 'notifications'

urlpatterns = [
    path('subscribe/', PushSubscriptionView.as_view(), name='subscribe'),
    path('public_key/', public_vapid_key, name='public_key'),
    path('unsubscribe/', unsubscribe, name='unsubscribe'),
    path('sw_subscribe/', sw_subscribe, name='sw_subscribe'),
    path('test/', send_test_notification, name='send_test'),
]
