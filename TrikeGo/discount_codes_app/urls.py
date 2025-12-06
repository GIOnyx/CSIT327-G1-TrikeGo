from django.urls import path
from . import views

app_name = "discount_codes"

urlpatterns = [
    path('api/discount_codes/available/', views.available_discount_codes, name='available_discount_codes'),
    path('api/discount_codes/redeem/<int:code_id>/', views.redeem_discount_code, name='redeem_discount_code'),
]