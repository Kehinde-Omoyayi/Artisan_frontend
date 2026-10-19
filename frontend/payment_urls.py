from django.urls import path
from . import views

urlpatterns = [
    path('booking/<uuid:booking_id>/initialize/', views.payment_initialize, name='payment-initialize'),
    path('<uuid:payment_id>/', views.payment_detail, name='payment-detail'),
    path('payout-account/', views.payout_account, name='payout-account'),
    path('payout-account/<uuid:pk>/verify/', views.payout_verify, name='payout-verify'),
]
