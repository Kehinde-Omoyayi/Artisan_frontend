from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.categories, name='categories'),
    path('services/', views.services, name='services'),
    path('artisans/', views.artisans, name='artisans'),
    path('artisans/<uuid:pk>/', views.artisan_detail, name='artisan-detail'),
    path('artisans/<uuid:pk>/request/', views.start_conversation, name='start-conversation'),
    path('artisans/<uuid:pk>/message/', views.start_direct_conversation, name='start-direct-conversation'),
    path('conversations/', views.conversation_inbox, name='conversation-inbox'),
    path('conversations/<uuid:conversation_id>/', views.conversation_detail, name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/messages/', views.conversation_messages, name='conversation-messages'),
    path('locations/', views.locations, name='locations'),
    path('locations/<uuid:pk>/', views.location_detail, name='location-detail'),
]
