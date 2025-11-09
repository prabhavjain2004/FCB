from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, F
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
from authentication.decorators import customer_required
from .models import GamingStation, Booking, Notification, Game
from .notifications import NotificationService, InAppNotification
from .qr_service_enhanced import QRCodeServiceEnhanced as QRCodeService  # Use enhanced version
from authentication.models import Customer
import json
import logging

logger = logging.getLogger(__name__)


@customer_required
def get_game_availability(request, game_id):
    """AJAX endpoint to get available slots for a specific game - OPTIMIZED"""
    from .booking_service import BookingService
    
    date_str = request.GET.get('date')
    
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        selected_date = timezone.now().date()
    
    try:
        game = Game.objects.get(id=game_id, is_active=True)
    except Game.DoesNotExist:
        return JsonResponse({'error': 'Game not found'}, status=404)
    
    # Get available slots for this game
    available_slots = BookingService.get_available_slots(
        game,
        date_from=selected_date,
        date_to=selected_date
    )
    
    # Format response
    slots_data = []
    for slot_info in available_slots:
        slot = slot_info['slot']
        availability = slot_info['availability']
        options = slot_info['options']
        
        slots_data.append({
            'id': str(slot.id),
            'start_time': slot.start_time.strftime('%I:%M %p'),
            'end_time': slot.end_time.strftime('%I:%M %p'),
            'date': slot.date.isoformat(),
            'can_book_private': availability.can_book_private,
            'can_book_shared': availability.can_book_shared,
            'available_spots': availability.available_spots,
            'options': options
        })
    
    return JsonResponse({
        'success': True,
        'game_id': str(game.id),
        'game_name': game.name,
        'slots': slots_data,
        'has_availability': len(slots_data) > 0
    })


@customer_required
def get_availability(request):
    """AJAX endpoint to get real-time availability"""
    date_str = request.GET.get('date')
    station_id = request.GET.get('station_id')
    
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Generate time slots
    time_slots = []
    for hour in range(9, 23):  # 9 AM to 11 PM
        time_slots.append({
            'time': f"{hour:02d}:00",
            'datetime': timezone.make_aware(
                datetime.combine(selected_date, datetime.min.time().replace(hour=hour)),
                timezone=timezone.get_current_timezone()
            )
        })
    
    if station_id:
        # Get availability for specific station
        try:
            station = GamingStation.objects.get(id=station_id, is_active=True)
        except GamingStation.DoesNotExist:
            return JsonResponse({'error': 'Station not found'}, status=404)
        
        availability = {}
        for slot in time_slots:
            slot_end = slot['datetime'] + timedelta(hours=1)
            is_available = station.is_available_at_time(slot['datetime'], slot_end)
            availability[slot['time']] = is_available
        
        return JsonResponse({'availability': availability})
    else:
        # Get availability for all stations
        stations = GamingStation.objects.filter(is_active=True, is_maintenance=False)
        availability = {}
        
        for station in stations:
            availability[str(station.id)] = {}
            for slot in time_slots:
                slot_end = slot['datetime'] + timedelta(hours=1)
                is_available = station.is_available_at_time(slot['datetime'], slot_end)
                availability[str(station.id)][slot['time']] = is_available
        
        return JsonResponse({'availability': availability})


@customer_required
def my_bookings(request):
    """Customer's booking history and management"""
    customer = request.user.customer_profile
    
    # Get bookings with filters
    status_filter = request.GET.get('status', 'all')
    
    # Auto-update booking statuses before displaying
    from .booking_service import auto_update_bookings_status
    
    bookings_to_check = customer.bookings.filter(
        status__in=['PENDING', 'CONFIRMED', 'IN_PROGRESS']
    ).select_related('game_slot')
    
    auto_update_bookings_status(bookings_to_check)
    
    # Optimize query with select_related to avoid N+1 queries
    bookings = customer.bookings.select_related(
        'game', 
        'game_slot'
    ).order_by('-created_at')
    
    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter.upper())
    
    # Pass queryset directly to template (filtering is done in JavaScript)
    context = {
        'bookings': bookings,  # Pass queryset, not list
        'status_filter': status_filter,
    }
    
    return render(request, 'booking/my_bookings.html', context)


@customer_required
def booking_details(request, booking_id):
    """View booking details for any confirmed/completed booking"""
    booking = get_object_or_404(
        Booking, 
        id=booking_id, 
        customer=request.user.customer_profile
    )
    
    # Auto-update booking status before displaying
    from .booking_service import auto_update_booking_status
    auto_update_booking_status(booking)
    
    # Redirect to confirmation page if still pending
    if booking.status == 'PENDING':
        return redirect('booking:hybrid_booking_confirm', booking_id=booking_id)
    
    context = {
        'booking': booking,
        'is_hybrid': booking.game.booking_type == 'HYBRID',
        'is_private': booking.booking_type == 'PRIVATE',
        'is_shared': booking.booking_type == 'SHARED',
    }
    
    return render(request, 'booking/booking_details.html', context)


@customer_required
def booking_success(request, booking_id):
    """
    Booking success page with animations and notifications
    SECURITY: Only accessible for CONFIRMED bookings with verified payment
    """
    booking = get_object_or_404(
        Booking, 
        id=booking_id, 
        customer=request.user.customer_profile
    )
    
    # SECURITY CHECK: Prevent access to success page without payment verification
    if booking.status != 'CONFIRMED':
        messages.error(request, 'This booking is not confirmed. Please complete the payment first.')
        return redirect('booking:hybrid_booking_confirm', booking_id=booking_id)
    
    # SECURITY CHECK: Verify payment exists (either razorpay_payment_id or old payment_id)
    if not booking.razorpay_payment_id and not booking.payment_id:
        messages.error(request, 'Payment verification required.')
        return redirect('booking:hybrid_booking_confirm', booking_id=booking_id)
    
    context = {
        'booking': booking,
    }
    
    return render(request, 'booking/success.html', context)


@customer_required
def simulate_payment(request, booking_id):
    """Simulate payment processing for demo purposes"""
    if request.method == 'POST':
        booking = get_object_or_404(
            Booking, 
            id=booking_id, 
            customer=request.user.customer_profile,
            status='PENDING'
        )
        
        try:
            # Simulate payment processing
            booking.status = 'CONFIRMED'
            booking.payment_id = f'pay_{timezone.now().strftime("%Y%m%d%H%M%S")}'
            booking.payment_status = 'PAID'
            booking.save()
            
            # Send confirmation email
            NotificationService.send_booking_confirmation_email(booking)
            
            # Create in-app notification
            InAppNotification.notify_booking_confirmed(booking)
            
            # Add success message
            messages.success(request, 'Payment successful! Your booking has been confirmed.')
            
            return JsonResponse({
                'success': True,
                'redirect_url': f'/booking/success/{booking.id}/'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# Removed duplicate cancel_booking function - using the one at line 709 which uses BookingService


@customer_required
def get_notifications(request):
    """Get user's notifications - REAL-TIME (NO CACHE)"""
    # Optimized query - get unread notifications with single database hit
    notifications = request.user.notifications.filter(
        is_read=False
    ).select_related('booking').order_by('-created_at')[:10]
    
    # Convert to list to get count without extra query
    notifications_list = list(notifications)
    
    notification_data = []
    for notification in notifications_list:
        notification_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'created_at': notification.created_at.isoformat(),
            'booking_id': str(notification.booking.id) if notification.booking else None
        })
    
    response_data = {
        'notifications': notification_data,
        'unread_count': len(notifications_list)
    }
    
    return JsonResponse(response_data)


@customer_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read - REAL-TIME (NO CACHE)"""
    if request.method == 'POST':
        try:
            notification = get_object_or_404(
                Notification,
                id=notification_id,
                user=request.user
            )
            notification.mark_as_read()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# NEW HYBRID BOOKING VIEWS

@customer_required
def game_selection(request):
    """Game selection interface with hybrid booking options - OPTIMIZED"""
    from .models import Game, GameSlot, SlotAvailability
    from .auto_slot_generator import auto_generate_slots_all_games
    from datetime import date, timedelta
    from django.db.models import Exists, OuterRef, Q, F
    from .timezone_utils import get_local_now, get_local_today, get_local_time
    
    # Ensure slots are available (runs in background, doesn't block)
    auto_generate_slots_all_games(async_mode=True)
    
    # Get current time in local timezone (IST)
    now_local = get_local_now()
    today_local = get_local_today()
    current_time_local = get_local_time()
    
    # Get selected date (default to today in local timezone)
    selected_date = request.GET.get('date', today_local.isoformat())
    try:
        selected_date = datetime.fromisoformat(selected_date).date()
    except ValueError:
        selected_date = today_local
    
    # OPTIMIZED: Use a single query with subquery to check availability
    # This checks if any slot exists with availability, without loading all slot data
    # can_book_private = booked_spots == 0
    # can_book_shared = not is_private_booked AND available_spots > 0
    
    # Use local time for filtering
    now = now_local
    current_time = current_time_local
    
    # Build the availability filter
    availability_filter = GameSlot.objects.filter(
        game=OuterRef('pk'),
        date=selected_date,
        is_active=True,
        availability__isnull=False
    )
    
    # If selected date is today, only show slots that haven't started yet
    if selected_date == now_local.date():
        availability_filter = availability_filter.filter(start_time__gt=current_time)
    
    # Add availability conditions
    available_slots_subquery = availability_filter.filter(
        Q(availability__booked_spots=0) |  # Can book private
        Q(availability__is_private_booked=False, availability__booked_spots__lt=F('availability__total_capacity'))  # Can book shared
    )
    
    # Get all active games with availability annotation
    games = Game.objects.filter(is_active=True).annotate(
        has_availability=Exists(available_slots_subquery)
    ).only(
        'id', 'name', 'description', 'image', 'booking_type', 
        'capacity', 'private_price', 'shared_price', 'slot_duration_minutes'
    ).order_by('name')
    
    # Convert to list with game_data structure for template compatibility
    games_with_availability = []
    for game in games:
        games_with_availability.append({
            'game': game,
            'has_availability': game.has_availability
        })
    
    context = {
        'games_with_availability': games_with_availability,
        'selected_date': selected_date,
        'today': today_local,
        'date_range': [today_local + timedelta(days=i) for i in range(7)]  # Next 7 days from today
    }
    
    return render(request, 'booking/game_selection.html', context)


@customer_required
def hybrid_booking_create(request):
    """Create a hybrid booking (private or shared) with enhanced validation"""
    if request.method == 'POST':
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required',
                    'details': 'Please log in to create a booking',
                    'redirect_url': f'/accounts/login/?next={request.path}'
                }, status=401)
            
            # Check if user has customer profile
            if not hasattr(request.user, 'customer_profile'):
                return JsonResponse({
                    'success': False,
                    'error': 'Customer profile required',
                    'details': 'Only customers can create bookings',
                }, status=403)
            
            # Parse JSON body
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON',
                    'details': f'Failed to parse request body: {str(e)}'
                }, status=400)
            
            game_slot_id = data.get('game_slot_id')
            booking_type = data.get('booking_type')  # 'PRIVATE' or 'SHARED'
            spots_requested = int(data.get('spots_requested', 1))
            
            # Validate inputs
            if not all([game_slot_id, booking_type]):
                logger.warning(f"Missing required fields for booking request. Parsed data: game_slot_id={game_slot_id}, booking_type={booking_type}, spots_requested={spots_requested}")
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields',
                    'details': 'Game slot ID and booking type are required',
                    'parsed': {
                        'game_slot_id': game_slot_id,
                        'booking_type': booking_type,
                        'spots_requested': spots_requested
                    }
                }, status=400)
            
            if booking_type not in ['PRIVATE', 'SHARED']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid booking type',
                    'details': 'Booking type must be PRIVATE or SHARED'
                }, status=400)
            
            if spots_requested < 1:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid spots requested',
                    'details': 'Must request at least 1 spot'
                }, status=400)
            
            # Get game slot
            from .models import GameSlot
            game_slot = get_object_or_404(GameSlot, id=game_slot_id, is_active=True)
            
            # Get customer
            customer = request.user.customer_profile
            
            # Get current booking options to validate request
            from .booking_service import BookingService
            available_options = BookingService.get_booking_options(game_slot)
            
            # Find the requested booking option
            requested_option = None
            for option in available_options:
                if option['type'] == booking_type and option['available']:
                    requested_option = option
                    break
            
            if not requested_option:
                return JsonResponse({
                    'success': False,
                    'error': 'Booking option not available',
                    'details': f'{booking_type} booking is not available for this slot',
                    'available_options': available_options
                }, status=400)
            
            # Validate spots for shared booking
            if booking_type == 'SHARED':
                max_spots = requested_option.get('max_spots_per_booking', requested_option['available_spots'])
                if spots_requested > max_spots:
                    return JsonResponse({
                        'success': False,
                        'error': 'Too many spots requested',
                        'details': f'Maximum {max_spots} spots can be booked at once',
                        'max_spots_allowed': max_spots
                    }, status=400)
            
            # Create booking using BookingService
            booking = BookingService.create_booking(
                customer=customer,
                game_slot=game_slot,
                booking_type=booking_type,
                spots_requested=spots_requested
            )
            
            return JsonResponse({
                'success': True,
                'booking_id': str(booking.id),
                'booking_type': booking.booking_type,
                'spots_booked': booking.spots_booked,
                'price_per_spot': str(booking.price_per_spot),
                'total_amount': str(booking.total_amount),
                'game_name': booking.game.name,
                'slot_time': f"{booking.game_slot.start_time.strftime('%H:%M')} - {booking.game_slot.end_time.strftime('%H:%M')}",
                'slot_date': booking.game_slot.date.isoformat(),
                'redirect_url': f'/booking/games/confirm/{booking.id}/',
                'message': f'Successfully booked {booking.spots_booked} spot{"s" if booking.spots_booked > 1 else ""} for {booking.game.name}'
            })
            
        except ValidationError as e:
            logger.error(f"Validation Error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Booking validation failed',
                'details': str(e),
                'error_type': 'validation'
            }, status=400)
        except Exception as e:
            logger.error(f"System Error: {type(e).__name__}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Booking creation failed',
                'details': str(e),
                'error_type': 'system'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@customer_required
def hybrid_booking_confirm(request, booking_id):
    """Hybrid booking confirmation page"""
    booking = get_object_or_404(
        Booking, 
        id=booking_id, 
        customer=request.user.customer_profile,
        status='PENDING'
    )
    
    # Fix for old bookings without reservation_expires_at
    if not booking.reservation_expires_at:
        from django.utils import timezone
        from datetime import timedelta
        booking.reservation_expires_at = timezone.now() + timedelta(minutes=5)
        booking.save()
    
    # Get booking options that were available
    from .booking_service import BookingService
    available_options = BookingService.get_booking_options(booking.game_slot)
    
    # Calculate max spots that can be booked
    max_additional_spots = 0
    if booking.booking_type == 'SHARED':
        current_availability = booking.game_slot.availability
        
        # Get truly available spots (excluding other pending reservations)
        reserved_spots = current_availability.get_reserved_spots_count()
        truly_available = current_availability.available_spots - reserved_spots
        
        # Add back the current booking's spots since we're modifying it
        truly_available += booking.spots_booked
        
        # Max spots = current spots + truly available (capped at game capacity)
        game_capacity = booking.game.capacity
        max_additional_spots = min(
            truly_available - booking.spots_booked,
            game_capacity - booking.spots_booked  # Cap at game capacity
        )
    
    context = {
        'booking': booking,
        'available_options': available_options,
        'is_hybrid': booking.game.booking_type == 'HYBRID',
        'is_private': booking.booking_type == 'PRIVATE',
        'is_shared': booking.booking_type == 'SHARED',
        'max_total_spots': min(booking.spots_booked + max_additional_spots, game_capacity) if booking.booking_type == 'SHARED' else booking.spots_booked,
        'can_modify_spots': booking.booking_type == 'SHARED' and max_additional_spots > 0,
    }
    
    return render(request, 'booking/hybrid_confirm.html', context)


@customer_required
def update_booking_spots(request, booking_id):
    """Update the number of spots for a shared booking"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        import json
        from .booking_service import BookingService
        from django.db import transaction
        
        data = json.loads(request.body)
        new_spots = int(data.get('spots', 0))
        
        # Get booking
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile,
            status='PENDING'
        )
        
        # Validate it's a shared booking
        if booking.booking_type != 'SHARED':
            return JsonResponse({
                'success': False,
                'error': 'Can only modify spots for shared bookings'
            }, status=400)
        
        # Validate new spots
        if new_spots < 1:
            return JsonResponse({
                'success': False,
                'error': 'Must book at least 1 spot'
            }, status=400)
        
        game_capacity = booking.game.capacity
        if new_spots > game_capacity:
            return JsonResponse({
                'success': False,
                'error': f'Cannot book more than {game_capacity} spots per booking'
            }, status=400)
        
        # Check if spots are available
        with transaction.atomic():
            availability = booking.game_slot.availability
            
            # Calculate spot difference
            spot_difference = new_spots - booking.spots_booked
            
            if spot_difference > 0:
                # Increasing spots - check truly available spots (accounting for other pending reservations)
                reserved_spots = availability.get_reserved_spots_count()
                truly_available = availability.available_spots - reserved_spots
                
                # Add back the current booking's spots since we're modifying it
                truly_available += booking.spots_booked
                
                if new_spots > truly_available:
                    return JsonResponse({
                        'success': False,
                        'error': f'Only {truly_available} total spots available (including your current {booking.spots_booked})'
                    }, status=400)
            
            # Update booking
            old_spots = booking.spots_booked
            booking.spots_booked = new_spots
            booking.subtotal = booking.price_per_spot * new_spots
            booking.total_amount = booking.subtotal + booking.platform_fee
            
            # CRITICAL: Do NOT update availability.booked_spots for PENDING bookings
            # PENDING bookings are tracked separately via get_reserved_spots_count()
            # Only CONFIRMED bookings update booked_spots (handled in Booking.save())
            
            # Save booking (this will NOT update availability.booked_spots since status is PENDING)
            booking.save(update_fields=['spots_booked', 'subtotal', 'total_amount'])
            
            return JsonResponse({
                'success': True,
                'message': f'Booking updated from {old_spots} to {new_spots} spot(s)',
                'new_total': str(booking.total_amount),
                'new_subtotal': str(booking.subtotal),
                'new_spots': new_spots
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid spot number'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@customer_required
def get_slot_availability(request, game_slot_id):
    """AJAX endpoint to get real-time slot availability with detailed information"""
    try:
        from .models import GameSlot
        from .booking_service import BookingService
        
        game_slot = get_object_or_404(GameSlot, id=game_slot_id, is_active=True)
        
        # Get current booking options with detailed information
        booking_options = BookingService.get_booking_options(game_slot)
        
        # Get booking type restrictions
        restrictions = BookingService.get_booking_type_restrictions(game_slot)
        
        # Get existing bookings for this slot
        existing_bookings = game_slot.bookings.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'PENDING']
        ).select_related('customer__user')
        
        booking_details = []
        for booking in existing_bookings:
            booking_details.append({
                'booking_type': booking.booking_type,
                'spots_booked': booking.spots_booked,
                'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
                'status': booking.status,
                'created_at': booking.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'game_slot_id': str(game_slot_id),
            'game_info': {
                'id': str(game_slot.game.id),
                'name': game_slot.game.name,
                'description': game_slot.game.description,
                'capacity': game_slot.game.capacity,
                'booking_type': game_slot.game.booking_type,
                'private_price': float(game_slot.game.private_price),
                'shared_price': float(game_slot.game.shared_price) if game_slot.game.shared_price else None
            },
            'slot_info': {
                'date': game_slot.date.isoformat(),
                'start_time': game_slot.start_time.strftime('%H:%M'),
                'end_time': game_slot.end_time.strftime('%H:%M'),
                'duration_minutes': game_slot.game.slot_duration_minutes,
                'is_custom': game_slot.is_custom
            },
            'availability': {
                'total_capacity': restrictions['total_capacity'],
                'booked_spots': restrictions['booked_spots'],
                'available_spots': restrictions['available_spots'],
                'can_book_private': restrictions['can_book_private'],
                'can_book_shared': restrictions['can_book_shared'],
                'is_private_locked': restrictions['is_private_locked'],
                'is_shared_locked': restrictions['is_shared_locked']
            },
            'booking_options': booking_options,
            'existing_bookings': booking_details,
            'restrictions': restrictions,
            'timestamp': timezone.now().isoformat(),
            'is_past_slot': game_slot.start_datetime <= timezone.now()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': 'system'
        }, status=400)


@customer_required
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    if request.method == 'POST':
        try:
            booking = get_object_or_404(
                Booking, 
                id=booking_id, 
                customer=request.user.customer_profile
            )
            
            if booking.status not in ['PENDING', 'CONFIRMED']:
                return JsonResponse({'error': 'Booking cannot be cancelled'}, status=400)
            
            # Cancel using BookingService
            from .booking_service import BookingService
            BookingService.cancel_booking(booking)
            
            messages.success(request, 'Booking cancelled successfully')
            
            return JsonResponse({
                'success': True,
                'message': 'Booking cancelled successfully'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def game_detail(request, game_id):
    """
    Game detail page - PUBLIC ACCESS
    Shows full game information - slots loaded via AJAX for performance
    Users can view without login, but need to login to book
    
    OPTIMIZED VERSION: Only loads game details, slots fetched via API
    """
    from datetime import timedelta
    
    # Get the game (optimized query)
    game = get_object_or_404(Game, id=game_id, is_active=True)
    
    # Get selected date (default to today in IST)
    from .timezone_utils import get_local_today
    today_local = get_local_today()
    
    selected_date = request.GET.get('date', today_local.isoformat())
    try:
        selected_date = datetime.fromisoformat(selected_date).date()
    except ValueError:
        selected_date = today_local
    
    # Generate date range for navigation (7 days)
    date_range = [selected_date + timedelta(days=i) for i in range(7)]
    
    # Lightweight context - no slot processing on initial load
    context = {
        'game': game,
        'selected_date': selected_date,
        'date_range': date_range,
        'today': today_local,
        'is_authenticated': request.user.is_authenticated,
        'use_ajax_loading': True,  # Flag to enable AJAX loading in template
    }
    
    return render(request, 'booking/game_detail.html', context)


@customer_required
@require_http_methods(["GET"])
def get_qr_data(request, booking_id):
    """
    Get QR code data for a booking (for dynamic frontend generation)
    
    GET /booking/api/qr-data/<booking_id>/
    
    Returns:
        JSON with QR data string: "booking_id|verification_token|booking"
    """
    try:
        # Get booking - must be owned by current user
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile
        )
        
        # Only allow QR data for confirmed bookings
        if booking.status not in ['CONFIRMED', 'IN_PROGRESS']:
            return JsonResponse({
                'success': False,
                'error': 'QR code only available for confirmed bookings'
            }, status=400)
        
        # Auto-generate token for old bookings that don't have one
        if not booking.verification_token:
            logger.info(f"Auto-generating verification token for existing booking {booking_id}")
            booking.verification_token = QRCodeService.generate_verification_token()
            booking.save(update_fields=['verification_token'])
        
        # Generate QR data string
        qr_data = QRCodeService.generate_qr_data(booking)
        
        if not qr_data:
            return JsonResponse({
                'success': False,
                'error': 'Failed to generate QR data'
            }, status=500)
        
        return JsonResponse({
            'success': True,
            'qr_data': qr_data,
            'booking_id': str(booking.id),
            'game_name': booking.game.name,
            'slot_date': booking.game_slot.date.isoformat(),
            'slot_time': f"{booking.game_slot.start_time.strftime('%I:%M %p')} - {booking.game_slot.end_time.strftime('%I:%M %p')}",
            'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
        })
        
    except Exception as e:
        logger.error(f"Error getting QR data for booking {booking_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

