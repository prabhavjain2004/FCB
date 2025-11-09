from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, date
from authentication.decorators import cafe_owner_required
from .models import Game, GameSlot, SlotAvailability, Booking
from .forms import GameCreationForm, GameUpdateForm, CustomSlotForm, BulkScheduleUpdateForm
import json
import logging

logger = logging.getLogger(__name__)


@cafe_owner_required
def game_management_dashboard(request):
    """Main game management dashboard for cafe owners - REAL-TIME NO CACHE"""
    
    # Auto-update booking statuses for real-time accuracy
    from booking.booking_service import auto_update_bookings_status
    bookings_to_check = Booking.objects.filter(
        status__in=['PENDING', 'CONFIRMED', 'IN_PROGRESS']
    ).select_related('game_slot')
    auto_update_bookings_status(bookings_to_check)
    
    # Get all games with statistics (single query with annotations) - NO CACHE
    games = Game.objects.annotate(
        total_slots=Count('slots'),
        active_slots=Count('slots', filter=Q(slots__is_active=True)),
        total_bookings=Count('bookings'),
        confirmed_bookings=Count('bookings', filter=Q(bookings__status='CONFIRMED'))
    ).order_by('name')
    
    # Get today's statistics - REAL-TIME
    today = timezone.now().date()
    
    # Use aggregate for counts (single query) - NO CACHE
    today_stats = GameSlot.objects.filter(date=today, is_active=True).aggregate(
        slots_count=Count('id')
    )
    
    booking_stats = Booking.objects.filter(
        game_slot__date=today,
        status__in=['CONFIRMED', 'IN_PROGRESS']
    ).aggregate(
        bookings_count=Count('id'),
        revenue=Sum('total_amount')
    )
    
    # Get upcoming bookings (optimized with select_related) - REAL-TIME
    upcoming_bookings = Booking.objects.filter(
        game_slot__date__gte=today,
        status__in=['CONFIRMED', 'PENDING']
    ).select_related('customer__user', 'game', 'game_slot').only(
        'id', 'customer__user__first_name', 'customer__user__last_name',
        'game__name', 'game_slot__date', 'game_slot__start_time', 'status'
    ).order_by('game_slot__date', 'game_slot__start_time')[:10]
    
    context = {
        'games': games,
        'total_games': games.count(),
        'active_games': games.filter(is_active=True).count(),
        'today_slots_count': today_stats['slots_count'] or 0,
        'today_bookings_count': booking_stats['bookings_count'] or 0,
        'today_revenue': booking_stats['revenue'] or 0,
        'upcoming_bookings': upcoming_bookings,
        'today': today,
    }
    
    response = render(request, 'booking/game_management/dashboard.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def game_create(request):
    """Create a new game with comprehensive setup"""
    if request.method == 'POST':
        form = GameCreationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Save game WITHOUT generating slots (we'll do that via AJAX)
                    game = form.save(commit=False)
                    game.save()
                    # Don't call form.save() which triggers slot generation
                    
                    # Return JSON response for AJAX slot generation
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'game_id': str(game.id),
                            'game_name': game.name
                        })
                    
                    messages.success(
                        request,
                        f'Game "{game.name}" created successfully! Generating time slots...'
                    )
                    return redirect('booking:game_management:game_detail', game_id=game.id)
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=400)
                messages.error(request, f'Error creating game: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GameCreationForm()
    
    context = {
        'form': form,
        'title': 'Create New Game',
        'submit_text': 'Create Game',
    }
    
    response = render(request, 'booking/game_management/game_form.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def game_detail(request, game_id):
    """Detailed view of a game with slots and bookings - OPTIMIZED"""
    from django.db.models import Prefetch
    
    game = get_object_or_404(Game, id=game_id)
    
    # Get date range for filtering (default to next 7 days)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        date_from = timezone.now().date()
    else:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
    
    if not date_to:
        date_to = date_from + timedelta(days=6)  # 7 days total
    else:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Optimized query with prefetch_related for bookings
    slots = game.slots.filter(
        date__range=[date_from, date_to],
        is_active=True
    ).select_related('availability').prefetch_related(
        Prefetch(
            'bookings',
            queryset=Booking.objects.filter(
                status__in=['CONFIRMED', 'IN_PROGRESS', 'PENDING']
            ).select_related('customer__user').only(
                'id', 'status', 'booking_type', 'spots_booked',
                'customer__user__first_name', 'customer__user__last_name'
            )
        )
    ).order_by('date', 'start_time')
    
    # Group slots by date (in Python, more efficient than multiple queries)
    slots_by_date = {}
    for slot in slots:
        if slot.date not in slots_by_date:
            slots_by_date[slot.date] = []
        
        # Get slot info with availability
        slot_info = {
            'slot': slot,
            'bookings': slot.bookings.all(),  # Already prefetched
            'availability': getattr(slot, 'availability', None)
        }
        slots_by_date[slot.date].append(slot_info)
    
    # Get game statistics (single aggregate query)
    stats = game.bookings.aggregate(
        total_bookings=Count('id'),
        confirmed_bookings=Count('id', filter=Q(status='CONFIRMED')),
        revenue=Sum('total_amount', filter=Q(status='CONFIRMED'))
    )
    
    total_slots = game.slots.filter(is_active=True).count()
    
    context = {
        'game': game,
        'slots_by_date': slots_by_date,
        'date_from': date_from,
        'date_to': date_to,
        'total_slots': total_slots,
        'total_bookings': stats['total_bookings'] or 0,
        'confirmed_bookings': stats['confirmed_bookings'] or 0,
        'revenue': stats['revenue'] or 0,
        'date_range': [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)],
    }
    
    response = render(request, 'booking/game_management/game_detail.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def game_update(request, game_id):
    """Update an existing game with slot regeneration options"""
    game = get_object_or_404(Game, id=game_id)
    
    if request.method == 'POST':
        form = GameUpdateForm(request.POST, request.FILES, instance=game)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_game = form.save()
                    
                    regenerate = form.cleaned_data.get('regenerate_slots', False)
                    if regenerate:
                        messages.success(
                            request,
                            f'Game "{updated_game.name}" updated successfully! '
                            f'Time slots have been regenerated while preserving existing bookings.'
                        )
                    else:
                        messages.success(
                            request,
                            f'Game "{updated_game.name}" updated successfully!'
                        )
                    
                    return redirect('booking:game_detail', game_id=updated_game.id)
            except Exception as e:
                messages.error(request, f'Error updating game: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GameUpdateForm(instance=game)
    
    # Calculate active slots count
    active_slots_count = game.slots.filter(is_active=True).count()
    
    context = {
        'form': form,
        'game': game,
        'active_slots_count': active_slots_count,
        'title': f'Update {game.name}',
        'submit_text': 'Update Game',
    }
    
    response = render(request, 'booking/game_management/game_form.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def game_toggle_status(request, game_id):
    """Toggle game active status"""
    if request.method == 'POST':
        game = get_object_or_404(Game, id=game_id)
        
        try:
            game.is_active = not game.is_active
            game.save()
            
            status = 'activated' if game.is_active else 'deactivated'
            messages.success(request, f'Game "{game.name}" has been {status}.')
            
            return JsonResponse({
                'success': True,
                'is_active': game.is_active,
                'message': f'Game {status} successfully'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def custom_slot_create(request):
    """Create custom temporary slots with auto-generation"""
    from datetime import datetime, timedelta
    
    if request.method == 'POST':
        try:
            # Get form data
            game_id = request.POST.get('game')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            start_time_str = request.POST.get('start_time')
            end_time_str = request.POST.get('end_time')
            slot_duration = int(request.POST.get('slot_duration', 60))
            
            # Validate game
            game = Game.objects.get(id=game_id)
            
            # Parse dates
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date
            
            # Parse times
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
            
            slots_created = 0
            
            with transaction.atomic():
                # Iterate through date range
                current_date = start_date
                while current_date <= end_date:
                    # Generate slots for this day
                    current_time = datetime.combine(current_date, start_time)
                    end_datetime = datetime.combine(current_date, end_time)
                    
                    while current_time < end_datetime:
                        slot_end_time = current_time + timedelta(minutes=slot_duration)
                        
                        # Don't create slot if it exceeds end time
                        if slot_end_time.time() > end_time:
                            break
                        
                        # Check if slot already exists
                        existing = GameSlot.objects.filter(
                            game=game,
                            date=current_date,
                            start_time=current_time.time(),
                            end_time=slot_end_time.time()
                        ).exists()
                        
                        if not existing:
                            GameSlot.objects.create(
                                game=game,
                                date=current_date,
                                start_time=current_time.time(),
                                end_time=slot_end_time.time(),
                                is_available=True
                            )
                            slots_created += 1
                        
                        current_time = slot_end_time
                    
                    current_date += timedelta(days=1)
            
            messages.success(
                request,
                f'Successfully created {slots_created} custom slot(s) for {game.name} '
                f'from {start_date} to {end_date}.'
            )
            return redirect('authentication:owner_overview')
            
        except Game.DoesNotExist:
            messages.error(request, 'Selected game not found.')
        except ValueError as e:
            messages.error(request, f'Invalid date or time format: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating custom slots: {str(e)}')
    
    # Get all active games for selection
    games = Game.objects.filter(is_active=True).order_by('name')
    
    context = {
        'games': games,
        'today': datetime.now().date().isoformat(),
    }
    
    response = render(request, 'authentication/owner_custom_slots.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def custom_slot_delete(request, slot_id):
    """Delete a custom slot"""
    if request.method == 'POST':
        slot = get_object_or_404(GameSlot, id=slot_id, is_custom=True)
        
        # Check if slot has bookings
        if slot.bookings.filter(status__in=['CONFIRMED', 'IN_PROGRESS', 'PENDING']).exists():
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete slot with existing bookings'
            }, status=400)
        
        try:
            game_name = slot.game.name
            slot_info = f"{slot.date} {slot.start_time}-{slot.end_time}"
            slot.delete()
            
            messages.success(request, f'Custom slot for {game_name} on {slot_info} deleted successfully.')
            
            return JsonResponse({
                'success': True,
                'message': 'Custom slot deleted successfully'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def schedule_management(request):
    """Interface for managing game operating hours and days"""
    games = Game.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        form = BulkScheduleUpdateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    selected_games = form.cleaned_data['games']
                    preserve_bookings = form.cleaned_data.get('preserve_bookings', True)
                    
                    updated_count = 0
                    for game in selected_games:
                        updated = False
                        
                        # Update opening time
                        if form.cleaned_data.get('update_opening_time'):
                            game.opening_time = form.cleaned_data['opening_time']
                            updated = True
                        
                        # Update closing time
                        if form.cleaned_data.get('update_closing_time'):
                            game.closing_time = form.cleaned_data['closing_time']
                            updated = True
                        
                        # Update available days
                        if form.cleaned_data.get('update_available_days'):
                            game.available_days = list(form.cleaned_data['available_days'])
                            updated = True
                        
                        if updated:
                            game.save()
                            # Regenerate slots with booking preservation
                            if preserve_bookings:
                                game.generate_slots()
                            updated_count += 1
                    
                    messages.success(
                        request,
                        f'Successfully updated {updated_count} games. '
                        f'{"Existing bookings have been preserved." if preserve_bookings else ""}'
                    )
                    return redirect('booking:schedule_management')
            except Exception as e:
                messages.error(request, f'Error updating schedules: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkScheduleUpdateForm()
    
    context = {
        'form': form,
        'games': games,
    }
    
    response = render(request, 'booking/game_management/schedule_management.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def slot_preview(request):
    """AJAX endpoint to preview slots based on schedule settings"""
    if request.method == 'GET':
        try:
            opening_time = request.GET.get('opening_time')
            closing_time = request.GET.get('closing_time')
            slot_duration = int(request.GET.get('slot_duration_minutes', 60))
            available_days = request.GET.getlist('available_days[]')
            
            if not all([opening_time, closing_time, available_days]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required parameters'
                }, status=400)
            
            # Parse times
            opening_time = datetime.strptime(opening_time, '%H:%M').time()
            closing_time = datetime.strptime(closing_time, '%H:%M').time()
            
            # Generate preview slots for next 7 days
            preview_slots = []
            start_date = timezone.now().date()
            
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                day_name = current_date.strftime('%A').lower()
                
                if day_name in available_days:
                    # Generate slots for this day
                    current_time = opening_time
                    day_slots = []
                    
                    while current_time < closing_time:
                        # Calculate end time
                        current_datetime = datetime.combine(current_date, current_time)
                        end_datetime = current_datetime + timedelta(minutes=slot_duration)
                        end_time = end_datetime.time()
                        
                        if end_time <= closing_time:
                            day_slots.append({
                                'start_time': current_time.strftime('%H:%M'),
                                'end_time': end_time.strftime('%H:%M'),
                                'duration': slot_duration
                            })
                            current_time = end_time
                        else:
                            break
                    
                    if day_slots:
                        preview_slots.append({
                            'date': current_date.isoformat(),
                            'day_name': current_date.strftime('%A'),
                            'slots': day_slots,
                            'slot_count': len(day_slots)
                        })
            
            # Calculate statistics
            total_slots = sum(day['slot_count'] for day in preview_slots)
            slots_per_day = total_slots / len(preview_slots) if preview_slots else 0
            
            return JsonResponse({
                'success': True,
                'preview_slots': preview_slots,
                'statistics': {
                    'total_slots_7_days': total_slots,
                    'average_slots_per_day': round(slots_per_day, 1),
                    'operating_days': len(preview_slots),
                    'slot_duration_minutes': slot_duration
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def game_analytics(request, game_id):
    """Analytics view for a specific game"""
    game = get_object_or_404(Game, id=game_id)
    
    # Get date range (default to last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=29)  # 30 days total
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get bookings in date range
    bookings = game.bookings.filter(
        game_slot__date__range=[start_date, end_date]
    ).select_related('game_slot')
    
    # Calculate statistics
    total_bookings = bookings.count()
    confirmed_bookings = bookings.filter(status='CONFIRMED').count()
    cancelled_bookings = bookings.filter(status='CANCELLED').count()
    total_revenue = bookings.filter(status='CONFIRMED').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Booking type breakdown (for hybrid games)
    private_bookings = bookings.filter(booking_type='PRIVATE').count()
    shared_bookings = bookings.filter(booking_type='SHARED').count()
    
    # Daily statistics
    daily_stats = []
    current_date = start_date
    while current_date <= end_date:
        day_bookings = bookings.filter(game_slot__date=current_date)
        day_revenue = day_bookings.filter(status='CONFIRMED').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        daily_stats.append({
            'date': current_date,
            'bookings': day_bookings.count(),
            'revenue': float(day_revenue),
            'confirmed': day_bookings.filter(status='CONFIRMED').count()
        })
        current_date += timedelta(days=1)
    
    # Peak hours analysis
    hour_stats = {}
    for booking in bookings.filter(status='CONFIRMED'):
        hour = booking.game_slot.start_time.hour
        if hour not in hour_stats:
            hour_stats[hour] = {'count': 0, 'revenue': 0}
        hour_stats[hour]['count'] += 1
        hour_stats[hour]['revenue'] += float(booking.total_amount)
    
    # Convert to list for template
    peak_hours = [
        {
            'hour': f"{hour:02d}:00",
            'count': stats['count'],
            'revenue': stats['revenue']
        }
        for hour, stats in sorted(hour_stats.items())
    ]
    
    context = {
        'game': game,
        'start_date': start_date,
        'end_date': end_date,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'cancelled_bookings': cancelled_bookings,
        'total_revenue': total_revenue,
        'private_bookings': private_bookings,
        'shared_bookings': shared_bookings,
        'daily_stats': daily_stats,
        'peak_hours': peak_hours,
        'date_range_days': (end_date - start_date).days + 1,
    }
    
    response = render(request, 'booking/game_management/game_analytics.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def individual_schedule_management(request, game_id):
    """Individual game schedule management with real-time preview"""
    game = get_object_or_404(Game, id=game_id)
    
    if request.method == 'POST':
        form = GameUpdateForm(request.POST, request.FILES, instance=game)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_game = form.save()
                    
                    messages.success(
                        request,
                        f'Schedule for "{updated_game.name}" updated successfully! '
                        f'Time slots have been regenerated while preserving existing bookings.'
                    )
                    return redirect('booking:game_management:game_detail', game_id=updated_game.id)
            except Exception as e:
                messages.error(request, f'Error updating schedule: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GameUpdateForm(instance=game)
    
    # Get current slot statistics
    total_slots = game.slots.filter(is_active=True).count()
    upcoming_bookings = game.bookings.filter(
        game_slot__date__gte=timezone.now().date(),
        status__in=['CONFIRMED', 'PENDING']
    ).count()
    
    context = {
        'form': form,
        'game': game,
        'total_slots': total_slots,
        'upcoming_bookings': upcoming_bookings,
        'title': f'Schedule Management - {game.name}',
        'submit_text': 'Update Schedule',
    }
    
    response = render(request, 'booking/game_management/individual_schedule.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def bulk_schedule_update(request):
    """Enhanced bulk schedule update with detailed preview"""
    if request.method == 'POST':
        form = BulkScheduleUpdateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    selected_games = form.cleaned_data['games']
                    preserve_bookings = form.cleaned_data.get('preserve_bookings', True)
                    
                    updated_games = []
                    for game in selected_games:
                        original_schedule = {
                            'opening_time': game.opening_time,
                            'closing_time': game.closing_time,
                            'available_days': game.available_days.copy()
                        }
                        
                        updated = False
                        
                        # Update opening time
                        if form.cleaned_data.get('update_opening_time'):
                            game.opening_time = form.cleaned_data['opening_time']
                            updated = True
                        
                        # Update closing time
                        if form.cleaned_data.get('update_closing_time'):
                            game.closing_time = form.cleaned_data['closing_time']
                            updated = True
                        
                        # Update available days
                        if form.cleaned_data.get('update_available_days'):
                            game.available_days = list(form.cleaned_data['available_days'])
                            updated = True
                        
                        if updated:
                            game.save()
                            # Regenerate slots with booking preservation
                            if preserve_bookings:
                                game.generate_slots()
                            
                            updated_games.append({
                                'game': game,
                                'original': original_schedule,
                                'updated': True
                            })
                    
                    messages.success(
                        request,
                        f'Successfully updated {len(updated_games)} games. '
                        f'{"Existing bookings have been preserved." if preserve_bookings else ""}'
                    )
                    
                    # Store update summary in session for display
                    request.session['bulk_update_summary'] = {
                        'updated_count': len(updated_games),
                        'preserve_bookings': preserve_bookings,
                        'games': [g['game'].name for g in updated_games]
                    }
                    
                    return redirect('booking:game_management:schedule_management')
            except Exception as e:
                messages.error(request, f'Error updating schedules: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def schedule_preview(request):
    """Enhanced AJAX endpoint for schedule preview with detailed analysis"""
    if request.method == 'GET':
        try:
            # Get parameters
            opening_time = request.GET.get('opening_time')
            closing_time = request.GET.get('closing_time')
            slot_duration = int(request.GET.get('slot_duration_minutes', 60))
            available_days = request.GET.getlist('available_days[]')
            game_id = request.GET.get('game_id')  # Optional for individual game preview
            
            if not all([opening_time, closing_time, available_days]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required parameters'
                }, status=400)
            
            # Parse times
            opening_time = datetime.strptime(opening_time, '%H:%M').time()
            closing_time = datetime.strptime(closing_time, '%H:%M').time()
            
            # Validate time range
            if closing_time <= opening_time:
                return JsonResponse({
                    'success': False,
                    'error': 'Closing time must be after opening time'
                }, status=400)
            
            # Calculate operating hours
            opening_datetime = datetime.combine(date.today(), opening_time)
            closing_datetime = datetime.combine(date.today(), closing_time)
            total_minutes = (closing_datetime - opening_datetime).total_seconds() / 60
            
            if slot_duration > total_minutes:
                return JsonResponse({
                    'success': False,
                    'error': f'Slot duration ({slot_duration} minutes) cannot be longer than operating hours ({int(total_minutes)} minutes)'
                }, status=400)
            
            # Generate preview slots for next 14 days
            preview_slots = []
            start_date = timezone.now().date()
            
            for i in range(14):
                current_date = start_date + timedelta(days=i)
                day_name = current_date.strftime('%A').lower()
                
                if day_name in available_days:
                    # Generate slots for this day
                    current_time = opening_time
                    day_slots = []
                    
                    while current_time < closing_time:
                        # Calculate end time
                        current_datetime = datetime.combine(current_date, current_time)
                        end_datetime = current_datetime + timedelta(minutes=slot_duration)
                        end_time = end_datetime.time()
                        
                        if end_time <= closing_time:
                            day_slots.append({
                                'start_time': current_time.strftime('%H:%M'),
                                'end_time': end_time.strftime('%H:%M'),
                                'duration': slot_duration,
                                'datetime': current_datetime.isoformat()
                            })
                            current_time = end_time
                        else:
                            break
                    
                    if day_slots:
                        preview_slots.append({
                            'date': current_date.isoformat(),
                            'day_name': current_date.strftime('%A'),
                            'slots': day_slots,
                            'slot_count': len(day_slots)
                        })
            
            # Calculate detailed statistics
            total_slots = sum(day['slot_count'] for day in preview_slots)
            operating_days = len(preview_slots)
            slots_per_day = total_slots / operating_days if operating_days else 0
            slots_per_week = slots_per_day * len(available_days)
            
            # Calculate potential revenue (if game_id provided)
            revenue_analysis = None
            if game_id:
                try:
                    game = Game.objects.get(id=game_id)
                    # Estimate weekly revenue based on different booking scenarios
                    revenue_analysis = {
                        'private_only': {
                            'weekly_slots': slots_per_week,
                            'price_per_slot': float(game.private_price),
                            'potential_revenue': slots_per_week * float(game.private_price)
                        }
                    }
                    
                    if game.booking_type == 'HYBRID' and game.shared_price:
                        revenue_analysis['shared_only'] = {
                            'weekly_slots': slots_per_week,
                            'capacity_per_slot': game.capacity,
                            'price_per_spot': float(game.shared_price),
                            'potential_revenue': slots_per_week * game.capacity * float(game.shared_price)
                        }
                        
                        revenue_analysis['mixed_50_50'] = {
                            'weekly_slots': slots_per_week,
                            'private_revenue': (slots_per_week * 0.5) * float(game.private_price),
                            'shared_revenue': (slots_per_week * 0.5) * game.capacity * float(game.shared_price),
                            'total_revenue': ((slots_per_week * 0.5) * float(game.private_price)) + 
                                           ((slots_per_week * 0.5) * game.capacity * float(game.shared_price))
                        }
                except Game.DoesNotExist:
                    pass
            
            # Check for existing bookings impact (if game_id provided)
            booking_impact = None
            if game_id:
                try:
                    game = Game.objects.get(id=game_id)
                    future_bookings = game.bookings.filter(
                        game_slot__date__gte=start_date,
                        status__in=['CONFIRMED', 'PENDING']
                    ).count()
                    
                    booking_impact = {
                        'existing_bookings': future_bookings,
                        'will_be_preserved': True,
                        'message': f'{future_bookings} existing bookings will be preserved during schedule update'
                    }
                except Game.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'preview_slots': preview_slots,
                'statistics': {
                    'total_slots_14_days': total_slots,
                    'operating_days': operating_days,
                    'average_slots_per_day': round(slots_per_day, 1),
                    'slots_per_week': round(slots_per_week, 1),
                    'slot_duration_minutes': slot_duration,
                    'operating_hours_per_day': round(total_minutes / 60, 1),
                    'available_days_count': len(available_days),
                    'available_days': available_days
                },
                'revenue_analysis': revenue_analysis,
                'booking_impact': booking_impact,
                'schedule_info': {
                    'opening_time': opening_time.strftime('%H:%M'),
                    'closing_time': closing_time.strftime('%H:%M'),
                    'slot_duration': slot_duration,
                    'available_days': available_days
                }
            })
            
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid time format: {str(e)}'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def schedule_optimization_suggestions(request, game_id):
    """AJAX endpoint to provide schedule optimization suggestions"""
    if request.method == 'GET':
        try:
            if not game_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Game ID is required'
                }, status=400)
            
            game = get_object_or_404(Game, id=game_id)
            
            # Analyze current performance
            from datetime import datetime, timedelta
            from django.db.models import Count, Avg, Sum
            
            # Get last 30 days of data
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            
            # Analyze booking patterns by hour
            hourly_bookings = {}
            bookings = game.bookings.filter(
                game_slot__date__range=[start_date, end_date],
                status='CONFIRMED'
            ).select_related('game_slot')
            
            for booking in bookings:
                hour = booking.game_slot.start_time.hour
                if hour not in hourly_bookings:
                    hourly_bookings[hour] = {'count': 0, 'revenue': 0}
                hourly_bookings[hour]['count'] += 1
                hourly_bookings[hour]['revenue'] += float(booking.total_amount)
            
            # Analyze booking patterns by day of week
            daily_bookings = {}
            for booking in bookings:
                day = booking.game_slot.date.strftime('%A').lower()
                if day not in daily_bookings:
                    daily_bookings[day] = {'count': 0, 'revenue': 0}
                daily_bookings[day]['count'] += 1
                daily_bookings[day]['revenue'] += float(booking.total_amount)
            
            # Generate suggestions
            suggestions = []
            
            # Peak hours analysis
            if hourly_bookings:
                peak_hours = sorted(hourly_bookings.items(), key=lambda x: x[1]['count'], reverse=True)[:3]
                low_hours = sorted(hourly_bookings.items(), key=lambda x: x[1]['count'])[:3]
                
                if peak_hours:
                    peak_hour_list = [f"{hour}:00" for hour, _ in peak_hours]
                    suggestions.append({
                        'type': 'peak_hours',
                        'title': 'Peak Hours Identified',
                        'description': f'Your busiest hours are {", ".join(peak_hour_list)}. Consider shorter slots during peak times to maximize bookings.',
                        'impact': 'high',
                        'action': 'Consider reducing slot duration to 30-45 minutes during peak hours'
                    })
                
                if low_hours and len(hourly_bookings) > 3:
                    low_hour_list = [f"{hour}:00" for hour, _ in low_hours if _['count'] > 0]
                    if low_hour_list:
                        suggestions.append({
                            'type': 'low_hours',
                            'title': 'Low Demand Hours',
                            'description': f'Hours {", ".join(low_hour_list)} have lower demand. Consider promotional pricing or longer slots.',
                            'impact': 'medium',
                            'action': 'Offer discounted rates or extend slot duration during low-demand hours'
                        })
            
            # Day of week analysis
            if daily_bookings:
                peak_days = sorted(daily_bookings.items(), key=lambda x: x[1]['count'], reverse=True)[:2]
                low_days = sorted(daily_bookings.items(), key=lambda x: x[1]['count'])[:2]
                
                if peak_days:
                    peak_day_list = [day.title() for day, _ in peak_days]
                    suggestions.append({
                        'type': 'peak_days',
                        'title': 'Popular Days',
                        'description': f'{", ".join(peak_day_list)} are your busiest days. Consider extending hours or adding more slots.',
                        'impact': 'high',
                        'action': 'Extend operating hours or reduce slot duration on busy days'
                    })
            
            # Slot duration optimization
            avg_booking_duration = game.slot_duration_minutes
            if game.booking_type == 'HYBRID':
                # Analyze private vs shared booking patterns
                private_bookings = bookings.filter(booking_type='PRIVATE').count()
                shared_bookings = bookings.filter(booking_type='SHARED').count()
                
                if private_bookings > shared_bookings * 2:
                    suggestions.append({
                        'type': 'booking_type',
                        'title': 'Private Booking Preference',
                        'description': 'Customers prefer private bookings. Consider adjusting pricing to encourage shared bookings.',
                        'impact': 'medium',
                        'action': 'Reduce shared booking prices or increase private booking prices'
                    })
                elif shared_bookings > private_bookings * 2:
                    suggestions.append({
                        'type': 'booking_type',
                        'title': 'Shared Booking Preference',
                        'description': 'Customers prefer shared bookings. Consider optimizing for group activities.',
                        'impact': 'medium',
                        'action': 'Focus marketing on group activities and social gaming'
                    })
            
            # Revenue optimization
            total_revenue = sum(booking.total_amount for booking in bookings)
            total_slots_available = game.slots.filter(
                date__range=[start_date, end_date],
                is_active=True
            ).count()
            
            utilization_rate = 0
            if total_slots_available > 0:
                utilization_rate = len(bookings) / total_slots_available
                
                if utilization_rate < 0.3:
                    suggestions.append({
                        'type': 'low_utilization',
                        'title': 'Low Slot Utilization',
                        'description': f'Only {utilization_rate:.1%} of slots are booked. Consider reducing operating hours or adjusting pricing.',
                        'impact': 'high',
                        'action': 'Reduce operating hours during low-demand periods or offer promotional pricing'
                    })
                elif utilization_rate > 0.8:
                    suggestions.append({
                        'type': 'high_utilization',
                        'title': 'High Demand Detected',
                        'description': f'{utilization_rate:.1%} of slots are booked. Consider extending hours or increasing prices.',
                        'impact': 'high',
                        'action': 'Extend operating hours or implement dynamic pricing'
                    })
            
            # Seasonal patterns (if enough data)
            if len(bookings) > 50:
                # Group by week to identify trends
                weekly_bookings = {}
                for booking in bookings:
                    week = booking.game_slot.date.isocalendar()[1]
                    if week not in weekly_bookings:
                        weekly_bookings[week] = 0
                    weekly_bookings[week] += 1
                
                if len(weekly_bookings) >= 4:
                    weeks = list(weekly_bookings.keys())
                    recent_weeks = weeks[-2:]
                    earlier_weeks = weeks[:-2]
                    
                    recent_avg = sum(weekly_bookings[w] for w in recent_weeks) / len(recent_weeks)
                    earlier_avg = sum(weekly_bookings[w] for w in earlier_weeks) / len(earlier_weeks)
                    
                    if recent_avg > earlier_avg * 1.2:
                        suggestions.append({
                            'type': 'growing_demand',
                            'title': 'Growing Demand Trend',
                            'description': 'Bookings are increasing. Consider expanding capacity or adjusting prices.',
                            'impact': 'high',
                            'action': 'Plan for capacity expansion or implement premium pricing'
                        })
                    elif recent_avg < earlier_avg * 0.8:
                        suggestions.append({
                            'type': 'declining_demand',
                            'title': 'Declining Demand Trend',
                            'description': 'Bookings are decreasing. Consider promotional campaigns or schedule adjustments.',
                            'impact': 'medium',
                            'action': 'Launch promotional campaigns or review pricing strategy'
                        })
            
            return JsonResponse({
                'success': True,
                'suggestions': suggestions,
                'analytics': {
                    'total_bookings': len(bookings),
                    'total_revenue': float(total_revenue),
                    'utilization_rate': utilization_rate,
                    'peak_hours': dict(peak_hours[:3]) if 'peak_hours' in locals() else {},
                    'daily_patterns': daily_bookings,
                    'analysis_period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': 30
                    }
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@cafe_owner_required
def advanced_schedule_management(request, game_id):
    """Advanced schedule management with optimization suggestions and analytics"""
    game = get_object_or_404(Game, id=game_id)
    
    # Get current schedule statistics
    from datetime import datetime, timedelta
    from django.db.models import Count, Sum, Avg
    
    # Calculate statistics for the last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Booking statistics
    bookings = game.bookings.filter(
        game_slot__date__range=[start_date, end_date],
        status='CONFIRMED'
    )
    
    total_bookings = bookings.count()
    total_revenue = bookings.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Slot utilization
    total_slots = game.slots.filter(
        date__range=[start_date, end_date],
        is_active=True
    ).count()
    
    utilization_rate = (total_bookings / total_slots * 100) if total_slots > 0 else 0
    
    # Peak hours analysis
    hourly_stats = {}
    for booking in bookings:
        hour = booking.game_slot.start_time.hour
        if hour not in hourly_stats:
            hourly_stats[hour] = {'bookings': 0, 'revenue': 0}
        hourly_stats[hour]['bookings'] += 1
        hourly_stats[hour]['revenue'] += float(booking.total_amount)
    
    # Day of week analysis
    daily_stats = {}
    for booking in bookings:
        day = booking.game_slot.date.strftime('%A')
        if day not in daily_stats:
            daily_stats[day] = {'bookings': 0, 'revenue': 0}
        daily_stats[day]['bookings'] += 1
        daily_stats[day]['revenue'] += float(booking.total_amount)
    
    # Upcoming bookings
    upcoming_bookings = game.bookings.filter(
        game_slot__date__gte=timezone.now().date(),
        status__in=['CONFIRMED', 'PENDING']
    ).count()
    
    context = {
        'game': game,
        'statistics': {
            'total_bookings': total_bookings,
            'total_revenue': total_revenue,
            'utilization_rate': round(utilization_rate, 1),
            'upcoming_bookings': upcoming_bookings,
            'total_slots': total_slots,
            'analysis_period_days': 30
        },
        'hourly_stats': hourly_stats,
        'daily_stats': daily_stats,
        'current_schedule': {
            'opening_time': game.opening_time,
            'closing_time': game.closing_time,
            'slot_duration': game.slot_duration_minutes,
            'available_days': game.available_days
        }
    }
    
    response = render(request, 'booking/game_management/advanced_schedule.html', context)
    # Disable all caching for real-time updates
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def generate_slots_with_progress(request, game_id):
    """Generate slots for a game with progress tracking via streaming response"""
    from django.http import StreamingHttpResponse
    from .slot_generator import SlotGenerator
    from django.db import transaction
    import time
    
    game = get_object_or_404(Game, id=game_id)
    days_ahead = int(request.GET.get('days', 2))  # Changed from 7 to 2 days for Vercel timeout
    
    def slot_generation_progress():
        """Generator function that yields progress updates"""
        start_date = date.today()
        end_date = start_date + timedelta(days=days_ahead)
        
        total_days = (end_date - start_date).days + 1
        current_day = 0
        slots_created = 0
        
        yield f"data: {json.dumps({'progress': 0, 'status': 'Starting slot generation...', 'slots_created': 0})}\n\n"
        
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.strftime('%A').lower()
            
            if weekday in game.available_days:
                try:
                    # Use atomic transaction for each date
                    with transaction.atomic():
                        created = SlotGenerator._generate_slots_for_date(game, current_date)
                        slots_created += created
                    
                    current_day += 1
                    progress = int((current_day / total_days) * 100)
                    
                    yield f"data: {json.dumps({'progress': progress, 'status': f'Generated {created} slots for {current_date}', 'slots_created': slots_created, 'date': str(current_date)})}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error generating slots for {current_date}: {str(e)}")
                    yield f"data: {json.dumps({'progress': int((current_day / total_days) * 100), 'status': f'Error on {current_date}: {str(e)}', 'error': True})}\n\n"
            else:
                current_day += 1
                progress = int((current_day / total_days) * 100)
                yield f"data: {json.dumps({'progress': progress, 'status': f'Skipped {current_date} (not available)', 'slots_created': slots_created})}\n\n"
            
            current_date += timedelta(days=1)
            time.sleep(0.05)  # Small delay to show progress
        
        yield f"data: {json.dumps({'progress': 100, 'status': 'Slot generation completed!', 'slots_created': slots_created, 'complete': True})}\n\n"
    
    return StreamingHttpResponse(slot_generation_progress(), content_type='text/event-stream')


@cafe_owner_required
def delete_game_with_slots(request, game_id):
    """Delete a game and all its slots (used when cancelling slot generation)"""
    if request.method == 'POST':
        try:
            game = get_object_or_404(Game, id=game_id)
            game_name = game.name
            
            # Delete game (cascades to slots automatically due to ForeignKey)
            game.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Game "{game_name}" and all its slots have been deleted.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

