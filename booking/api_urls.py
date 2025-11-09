"""
API URL Configuration for Booking System
All API endpoints are prefixed with /api/
"""
from django.urls import path
from .api_views import (
    GameDetailAPI,
    GameSlotsAPI,
    GameSlotsWeekAPI,
    AvailableDatesAPI
)

app_name = 'booking_api'

urlpatterns = [
    # Game detail
    path('games/<uuid:game_id>/', GameDetailAPI.as_view(), name='game_detail'),
    
    # Slots for specific date
    path('games/<uuid:game_id>/slots/', GameSlotsAPI.as_view(), name='game_slots'),
    
    # Slots for week view
    path('games/<uuid:game_id>/slots/week/', GameSlotsWeekAPI.as_view(), name='game_slots_week'),
    
    # Available dates
    path('games/<uuid:game_id>/available-dates/', AvailableDatesAPI.as_view(), name='available_dates'),
]
