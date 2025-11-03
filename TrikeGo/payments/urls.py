from django.urls import path
from . import api_views

app_name = 'payments'
urlpatterns = [
    path('<int:booking_id>/payment/generate-pin/', api_views.generate_payment_pin_endpoint, name='generate_payment_pin'),
    path('<int:booking_id>/payment/verify-pin/', api_views.verify_payment_pin_endpoint, name='verify_payment_pin'),
    path('<int:booking_id>/payment/pin-status/', api_views.get_payment_pin_status, name='payment_pin_status'),
]
