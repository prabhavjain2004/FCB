"""
Complete custom superuser dashboard views
Replaces Django Admin with full-featured custom dashboard
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta, date
from decimal import Decimal
import json

from .models import TapNexSuperuser, CafeOwner, Customer
from .decorators import tapnex_superuser_required
from .commission_service import CommissionCalculator, RevenueTracker
from .forms import CommissionSettingsForm, CafeOwnerManagementForm
from booking.models import Booking, Game, GameSlot


class SuperuserLoginView(LoginView):
    """Custom login view for TapNex superusers and Cafe Owners (Staff Login)"""
    template_name = 'authentication/superuser_login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        # Check if user is superuser
        if self.request.user.is_superuser:
            # Create TapNexSuperuser profile if doesn't exist
            TapNexSuperuser.objects.get_or_create(
                user=self.request.user,
                defaults={
                    'contact_email': self.request.user.email or 'admin@tapnex.com',
                    'commission_rate': Decimal('10.00'),
                    'platform_fee': Decimal('0.00')
                }
            )
            return '/accounts/tapnex/dashboard/'
        # Check if user is cafe owner
        elif hasattr(self.request.user, 'cafe_owner_profile'):
            return '/accounts/owner/dashboard/'
        else:
            messages.error(self.request, 'Access denied. This login is for TapNex administrators and cafe owners only.')
            from django.contrib.auth import logout
            logout(self.request)
            return '/accounts/cafe-owner/login/'
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid credentials or insufficient permissions.')
        return super().form_invalid(form)


@tapnex_superuser_required
def superuser_dashboard(request):
    """Main superuser dashboard - replaces Django admin homepage - OPTIMIZED FOR REAL-TIME"""
    # Get or create TapNex superuser profile
    tapnex_user, created = TapNexSuperuser.objects.get_or_create(
        user=request.user,
        defaults={
            'contact_email': request.user.email or 'admin@tapnex.com',
            'commission_rate': Decimal('10.00'),
            'platform_fee': Decimal('0.00')
        }
    )
    
    # Real-time stats (NO CACHE for instant updates)
    stats = {
        'total_users': User.objects.count(),
        'total_customers': Customer.objects.count(),
        'total_cafe_owners': CafeOwner.objects.count(),
        'total_games': Game.objects.count(),
        'active_games': Game.objects.filter(is_active=True).count(),
        'total_bookings': Booking.objects.filter(status='CONFIRMED').count(),
        'today_bookings': Booking.objects.filter(
            created_at__date=date.today(),
            status='CONFIRMED'
        ).count(),
        'pending_bookings': Booking.objects.filter(status='PENDING').count(),
    }
    
    # Revenue metrics (real-time)
    real_time_metrics = RevenueTracker.get_real_time_metrics()
    
    # Recent activity (optimized with select_related) - Only confirmed bookings
    recent_bookings = Booking.objects.filter(
        status='CONFIRMED'
    ).select_related(
        'customer__user', 'game'
    ).only(
        'id', 'created_at', 'status', 'total_amount',
        'customer__user__first_name', 'customer__user__last_name',
        'game__name'
    ).order_by('-created_at')[:10]
    
    recent_users = User.objects.only(
        'id', 'username', 'email', 'date_joined', 'is_active'
    ).order_by('-date_joined')[:10]
    
    # System alerts (real-time)
    alerts = []
    if stats['pending_bookings'] > 5:
        alerts.append({
            'type': 'warning',
            'message': f"{stats['pending_bookings']} pending bookings require attention"
        })
    
    inactive_games = Game.objects.filter(is_active=False).count()
    if inactive_games > 0:
        alerts.append({
            'type': 'info',
            'message': f"{inactive_games} games are currently inactive"
        })
    
    # Get cafe owner if exists (real-time)
    try:
        cafe_owner = CafeOwner.objects.select_related('user').first()
    except CafeOwner.DoesNotExist:
        cafe_owner = None
    
    context = {
        'tapnex_user': tapnex_user,
        'stats': stats,
        'real_time_metrics': real_time_metrics,
        'recent_bookings': recent_bookings,
        'recent_users': recent_users,
        'alerts': alerts,
        'cafe_owner': cafe_owner,
    }
    
    response = render(request, 'authentication/superuser_dashboard.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
def manage_users(request):
    """User management - view, edit, create, delete users"""
    
    # Filters
    user_type = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset with related profiles for phone numbers
    users = User.objects.select_related(
        'customer_profile', 'cafe_owner_profile', 'tapnex_superuser_profile'
    ).all().order_by('-date_joined')
    
    # Apply filters
    if user_type == 'customers':
        users = users.filter(customer_profile__isnull=False)
    elif user_type == 'cafe_owners':
        users = users.filter(cafe_owner_profile__isnull=False)
    elif user_type == 'superusers':
        users = users.filter(is_superuser=True)
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(customer_profile__phone__icontains=search_query) |
            Q(cafe_owner_profile__phone__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'user_type': user_type,
        'search_query': search_query,
        'total_users': users.count(),
    }
    
    response = render(request, 'authentication/manage_users.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
def user_detail(request, user_id):
    """View and edit specific user details"""
    
    user = get_object_or_404(User, id=user_id)
    
    # Get user's bookings if customer
    user_bookings = []
    if hasattr(user, 'customer_profile'):
        user_bookings = Booking.objects.filter(
            customer=user.customer_profile
        ).select_related('game').order_by('-created_at')[:20]
    
    context = {
        'user_obj': user,
        'user_bookings': user_bookings,
        'is_customer': hasattr(user, 'customer_profile'),
        'is_cafe_owner': hasattr(user, 'cafe_owner_profile'),
    }
    
    response = render(request, 'authentication/user_detail.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
@require_http_methods(["POST"])
def user_action(request, user_id):
    """Handle user actions: activate, deactivate, delete, make_staff"""
    
    user = get_object_or_404(User, id=user_id)
    action = request.POST.get('action')
    
    # Prevent self-deletion
    if user == request.user and action == 'delete':
        messages.error(request, 'You cannot delete your own account.')
        return redirect('authentication:user_detail', user_id=user_id)
    
    if action == 'activate':
        user.is_active = True
        user.save()
        messages.success(request, f'User {user.username} activated successfully.')
    
    elif action == 'deactivate':
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.username} deactivated successfully.')
    
    elif action == 'make_staff':
        user.is_staff = True
        user.save()
        messages.success(request, f'User {user.username} is now staff.')
    
    elif action == 'remove_staff':
        user.is_staff = False
        user.save()
        messages.success(request, f'Staff privileges removed from {user.username}.')
    
    elif action == 'delete':
        username = user.username
        user.delete()
        messages.success(request, f'User {username} deleted successfully.')
        return redirect('authentication:manage_users')
    
    elif action == 'reset_password':
        new_password = request.POST.get('new_password')
        if new_password and len(new_password) >= 8:
            user.set_password(new_password)
            user.save()
            messages.success(request, f'Password reset for {user.username}.')
        else:
            messages.error(request, 'Password must be at least 8 characters.')
    
    return redirect('authentication:user_detail', user_id=user_id)


@tapnex_superuser_required
def manage_bookings(request):
    """Booking management - view, edit, cancel bookings - OPTIMIZED"""
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    booking_type = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Optimized base queryset with select_related and only()
    bookings = Booking.objects.select_related(
        'customer__user', 'game', 'game_slot'
    ).only(
        'id', 'created_at', 'status', 'booking_type', 'total_amount', 'payment_status',
        'customer__user__username', 'customer__user__email', 'customer__user__first_name',
        'game__name', 'game_slot__date', 'game_slot__start_time'
    ).order_by('-created_at')
    
    # Apply filters
    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter.upper())
    
    if booking_type != 'all':
        bookings = bookings.filter(booking_type=booking_type.upper())
    
    if search_query:
        bookings = bookings.filter(
            Q(customer__user__username__icontains=search_query) |
            Q(customer__user__email__icontains=search_query) |
            Q(game__name__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    if date_from:
        bookings = bookings.filter(created_at__date__gte=date_from)
    
    if date_to:
        bookings = bookings.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(bookings, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Summary stats - separate for confirmed and cancelled
    confirmed_bookings = Booking.objects.filter(status='CONFIRMED')
    cancelled_bookings = Booking.objects.filter(status='CANCELLED')
    
    summary = {
        'total_confirmed': confirmed_bookings.count(),
        'total_revenue': confirmed_bookings.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'total_cancelled': cancelled_bookings.count(),
    }
    
    context = {
        'bookings': page_obj,
        'status_filter': status_filter,
        'booking_type': booking_type,
        'search_query': search_query,
        'summary': summary,
    }
    
    response = render(request, 'authentication/manage_bookings.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
def booking_detail(request, booking_id):
    """View detailed booking information"""
    
    booking = get_object_or_404(
        Booking.objects.select_related('customer__user', 'game', 'game_slot'),
        id=booking_id
    )
    
    context = {
        'booking': booking,
    }
    
    response = render(request, 'authentication/booking_detail.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
@require_http_methods(["POST"])
def booking_action(request, booking_id):
    """Handle booking actions: confirm, cancel, complete"""
    
    booking = get_object_or_404(Booking, id=booking_id)
    action = request.POST.get('action')
    
    if action == 'confirm':
        booking.status = 'CONFIRMED'
        booking.save()
        messages.success(request, f'Booking {booking.booking_id} confirmed.')
    
    elif action == 'cancel':
        booking.status = 'CANCELLED'
        booking.save()
        messages.success(request, f'Booking {booking.booking_id} cancelled.')
    
    elif action == 'complete':
        booking.status = 'COMPLETED'
        booking.save()
        messages.success(request, f'Booking {booking.booking_id} completed.')
    
    elif action == 'delete':
        booking_id_str = booking.booking_id
        booking.delete()
        messages.success(request, f'Booking {booking_id_str} deleted.')
        return redirect('authentication:manage_bookings')
    
    return redirect('authentication:booking_detail', booking_id=booking_id)


@tapnex_superuser_required
def manage_games(request):
    """Game management - view, create, edit, delete games"""
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset - fetch all fields
    games = Game.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter == 'active':
        games = games.filter(is_active=True)
    elif status_filter == 'inactive':
        games = games.filter(is_active=False)
    
    if search_query:
        games = games.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(games, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'games': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_games': games.count(),
    }
    
    response = render(request, 'authentication/manage_games.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
def game_detail(request, game_id):
    """View and edit specific game details"""
    
    game = get_object_or_404(Game, id=game_id)
    
    # Get game statistics
    total_bookings = Booking.objects.filter(game=game).count()
    total_revenue = Booking.objects.filter(
        game=game,
        status__in=['CONFIRMED', 'COMPLETED']
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Recent bookings for this game
    recent_bookings = Booking.objects.filter(
        game=game
    ).select_related('customer__user').order_by('-created_at')[:10]
    
    # Get game slots
    game_slots = GameSlot.objects.filter(game=game).order_by('start_time')[:20]
    
    context = {
        'game': game,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'recent_bookings': recent_bookings,
        'game_slots': game_slots,
    }
    
    response = render(request, 'authentication/game_detail.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
@require_http_methods(["POST"])
def game_action(request, game_id):
    """Handle game actions: activate, deactivate, delete"""
    
    game = get_object_or_404(Game, id=game_id)
    action = request.POST.get('action')
    
    if action == 'activate':
        game.is_active = True
        game.save()
        messages.success(request, f'Game "{game.name}" activated.')
    
    elif action == 'deactivate':
        game.is_active = False
        game.save()
        messages.success(request, f'Game "{game.name}" deactivated.')
    
    elif action == 'delete':
        game_name = game.name
        game.delete()
        messages.success(request, f'Game "{game_name}" deleted.')
        return redirect('authentication:manage_games')
    
    elif action == 'update':
        # Update game details
        game.name = request.POST.get('name', game.name)
        game.description = request.POST.get('description', game.description)
        game.hourly_rate = request.POST.get('hourly_rate', game.hourly_rate)
        game.max_players = request.POST.get('max_players', game.max_players)
        game.save()
        messages.success(request, f'Game "{game.name}" updated.')
    
    return redirect('authentication:game_detail', game_id=game_id)


@tapnex_superuser_required
def system_settings(request):
    """System-wide settings and configuration"""
    
    tapnex_user = get_object_or_404(TapNexSuperuser, user=request.user)
    cafe_owner = CafeOwner.objects.first()  # Get cafe owner for Razorpay settings
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_commission':
            tapnex_user.commission_rate = request.POST.get('commission_rate', tapnex_user.commission_rate)
            tapnex_user.platform_fee = request.POST.get('platform_fee', tapnex_user.platform_fee)
            tapnex_user.platform_fee_type = request.POST.get('platform_fee_type', tapnex_user.platform_fee_type)
            tapnex_user.save()
            messages.success(request, 'Commission settings updated.')
        
        elif action == 'update_profile':
            tapnex_user.contact_email = request.POST.get('contact_email', tapnex_user.contact_email)
            tapnex_user.phone = request.POST.get('phone', tapnex_user.phone)
            tapnex_user.save()
            messages.success(request, 'Profile updated.')
        
        elif action == 'update_telegram':
            tapnex_user.telegram_bot_token = request.POST.get('telegram_bot_token', '').strip()
            tapnex_user.telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()
            tapnex_user.telegram_notification_type = request.POST.get('telegram_notification_type', 'PERSONAL')
            tapnex_user.telegram_enabled = request.POST.get('telegram_enabled') == 'on'
            tapnex_user.save()
            messages.success(request, 'Telegram notification settings updated.')
        
        elif action == 'update_razorpay':
            if cafe_owner:
                cafe_owner.razorpay_account_id = request.POST.get('razorpay_account_id', '').strip()
                cafe_owner.razorpay_account_email = request.POST.get('razorpay_account_email', '').strip()
                
                # Set status to ACTIVE if account ID is provided
                if cafe_owner.razorpay_account_id:
                    cafe_owner.razorpay_account_status = 'ACTIVE'
                else:
                    cafe_owner.razorpay_account_status = 'PENDING'
                
                cafe_owner.save()
                messages.success(request, '💳 Razorpay account settings updated successfully!')
            else:
                messages.error(request, 'No cafe owner found. Please create a cafe owner account first.')
    
    # Get system statistics
    system_stats = {
        'database_size': 'N/A',  # Can implement actual DB size query
        'last_backup': 'N/A',
        'total_revenue': Booking.objects.filter(
            status__in=['CONFIRMED', 'COMPLETED']
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
    }
    
    context = {
        'tapnex_user': tapnex_user,
        'cafe_owner': cafe_owner,
        'system_stats': system_stats,
    }
    
    response = render(request, 'authentication/system_settings.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
def database_browser(request):
    """Browse all database tables and records"""
    
    # List of available models to browse
    models_list = [
        {'name': 'Users', 'model': 'User', 'count': User.objects.count()},
        {'name': 'Customers', 'model': 'Customer', 'count': Customer.objects.count()},
        {'name': 'Cafe Owners', 'model': 'CafeOwner', 'count': CafeOwner.objects.count()},
        {'name': 'Games', 'model': 'Game', 'count': Game.objects.count()},
        {'name': 'Bookings', 'model': 'Booking', 'count': Booking.objects.count()},
        {'name': 'Game Slots', 'model': 'GameSlot', 'count': GameSlot.objects.count()},
    ]
    
    context = {
        'models_list': models_list,
    }
    
    response = render(request, 'authentication/database_browser.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@tapnex_superuser_required
@require_http_methods(["POST"])
def test_telegram_notification(request):
    """Test Telegram notification configuration"""
    from booking.telegram_service import TelegramNotificationService
    
    # Reload configuration from database
    service = TelegramNotificationService()
    result = service.send_test_message()
    
    return JsonResponse(result)
