from django.urls import path

from .views import DriverWalletView, driver_wallet_summary

app_name = 'wallet'

urlpatterns = [
    path('driver/', DriverWalletView.as_view(), name='driver_wallet'),
    path('api/driver/summary/', driver_wallet_summary, name='driver_wallet_summary'),
]
