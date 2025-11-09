from django.urls import path
from . import views
from . import dashboard_views
from . import tapnex_views
from . import superuser_views

app_name = 'authentication'

urlpatterns = [
    # Customer authentication (Google OAuth handled by allauth)
    path('login/', views.customer_login_view, name='customer_login'),
    path('login/email/', views.customer_email_login_view, name='customer_email_login'),
    
    # Cafe owner authentication
    path('cafe-owner/login/', superuser_views.SuperuserLoginView.as_view(), name='cafe_owner_login'),  # Now handles superuser login
    path('cafe-owner/register/', views.CafeOwnerRegistrationView.as_view(), name='cafe_owner_register'),
    
    # Common authentication
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.profile_redirect_view, name='profile_redirect'),
    path('update-phone/', views.update_phone_number, name='update_phone'),
    
    # Dashboards
    path('customer/dashboard/', dashboard_views.customer_dashboard, name='customer_dashboard'),
    path('owner/dashboard/', dashboard_views.cafe_owner_dashboard, name='cafe_owner_dashboard'),
    
    # Owner Dashboard Sections
    path('owner/overview/', dashboard_views.owner_overview, name='owner_overview'),
    path('owner/bookings/', dashboard_views.owner_bookings, name='owner_bookings'),
    path('owner/games/', dashboard_views.owner_games, name='owner_games'),
    path('owner/customers/', dashboard_views.owner_customers, name='owner_customers'),
    path('owner/revenue/', dashboard_views.owner_revenue, name='owner_revenue'),
    path('owner/reports/', dashboard_views.owner_reports, name='owner_reports'),
    
    # TapNex Superuser Dashboard (Main Custom Admin)
    path('tapnex/dashboard/', superuser_views.superuser_dashboard, name='tapnex_dashboard'),
    
    # User Management
    path('tapnex/users/', superuser_views.manage_users, name='manage_users'),
    path('tapnex/users/<int:user_id>/', superuser_views.user_detail, name='user_detail'),
    path('tapnex/users/<int:user_id>/action/', superuser_views.user_action, name='user_action'),
    
    # Booking Management
    path('tapnex/bookings/', superuser_views.manage_bookings, name='manage_bookings'),
    path('tapnex/bookings/<uuid:booking_id>/', superuser_views.booking_detail, name='booking_detail'),
    path('tapnex/bookings/<uuid:booking_id>/action/', superuser_views.booking_action, name='booking_action'),
    
    # Game Management
    path('tapnex/games/', superuser_views.manage_games, name='manage_games'),
    path('tapnex/games/<uuid:game_id>/', superuser_views.game_detail, name='game_detail'),
    path('tapnex/games/<uuid:game_id>/action/', superuser_views.game_action, name='game_action'),
    
    # Commission & Revenue
    path('tapnex/commission-settings/', tapnex_views.commission_settings, name='commission_settings'),
    path('tapnex/revenue-reports/', tapnex_views.revenue_reports, name='revenue_reports'),
    path('tapnex/ajax/revenue-data/', tapnex_views.ajax_revenue_data, name='ajax_revenue_data'),
    
    # Cafe Owner Management
    path('tapnex/cafe-owner/create/', tapnex_views.create_cafe_owner, name='create_cafe_owner'),
    path('tapnex/cafe-owner-management/', tapnex_views.cafe_owner_management, name='cafe_owner_management'),
    path('tapnex/reset-cafe-owner-password/', tapnex_views.reset_cafe_owner_password, name='reset_cafe_owner_password'),
    
    # System Management
    path('tapnex/system-analytics/', tapnex_views.system_analytics, name='system_analytics'),
    path('tapnex/settings/', superuser_views.system_settings, name='system_settings'),
    path('tapnex/database/', superuser_views.database_browser, name='database_browser'),
    path('tapnex/test-telegram/', superuser_views.test_telegram_notification, name='test_telegram_notification'),
    path('tapnex/password-reset/', superuser_views.superuser_password_reset, name='superuser_password_reset'),
]