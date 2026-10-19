from django.urls import path
from . import views

urlpatterns = [path('new/', views.review_create, name='review-create')]
