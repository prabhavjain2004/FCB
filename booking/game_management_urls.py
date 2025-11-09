from django.urls import path
from . import game_management_views

app_name = 'game_management'

urlpatterns = [
    # Game Management Dashboard
    path('', game_management_views.game_management_dashboard, name='dashboard'),
    
    # Game CRUD Operations
    path('create/', game_management_views.game_create, name='game_create'),
    path('<uuid:game_id>/', game_management_views.game_detail, name='game_detail'),
    path('<uuid:game_id>/update/', game_management_views.game_update, name='game_update'),
    path('<uuid:game_id>/toggle-status/', game_management_views.game_toggle_status, name='game_toggle_status'),
    path('<uuid:game_id>/analytics/', game_management_views.game_analytics, name='game_analytics'),
    
    # Schedule Management
    path('schedule/', game_management_views.schedule_management, name='schedule_management'),
    path('schedule/individual/<uuid:game_id>/', game_management_views.individual_schedule_management, name='individual_schedule_management'),
    path('schedule/bulk-update/', game_management_views.bulk_schedule_update, name='bulk_schedule_update'),
    
    # Custom Slots
    path('custom-slots/create/', game_management_views.custom_slot_create, name='custom_slot_create'),
    path('custom-slots/<uuid:slot_id>/delete/', game_management_views.custom_slot_delete, name='custom_slot_delete'),
    
    # Advanced Schedule Management
    path('schedule/advanced/<uuid:game_id>/', game_management_views.advanced_schedule_management, name='advanced_schedule_management'),
    
    # AJAX Endpoints
    path('api/slot-preview/', game_management_views.slot_preview, name='slot_preview'),
    path('api/schedule-preview/', game_management_views.schedule_preview, name='schedule_preview'),
    path('api/schedule-optimization/<uuid:game_id>/', game_management_views.schedule_optimization_suggestions, name='schedule_optimization_suggestions'),
    path('api/generate-slots/<uuid:game_id>/', game_management_views.generate_slots_with_progress, name='generate_slots_with_progress'),
    path('<uuid:game_id>/delete-with-slots/', game_management_views.delete_game_with_slots, name='delete_game_with_slots'),
]