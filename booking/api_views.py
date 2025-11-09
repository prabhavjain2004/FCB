"""
REST API Views for Booking System
Provides fast, real-time endpoints for game and slot data
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from datetime import datetime, timedelta
from django.utils import timezone

from .models import Game, GameSlot, SlotAvailability, Booking
from .serializers import GameSerializer, GameSlotSerializer, SlotsByDateSerializer
from .booking_service import BookingService


class GameDetailAPI(APIView):
    """
    GET /api/games/{game_id}/
    Returns basic game information for fast initial page load
    """
    
    def get(self, request, game_id):
        """Get game details - REAL-TIME (NO CACHE)"""
        # Get game from database (real-time)
        game = get_object_or_404(Game, id=game_id, is_active=True)
        
        # Serialize
        serializer = GameSerializer(game, context={'request': request})
        data = serializer.data
        
        return Response(data)


class GameSlotsAPI(APIView):
    """
    GET /api/games/{game_id}/slots/?date=2024-11-02
    Returns available slots for a specific date
    
    Query Parameters:
    - date: ISO format date (YYYY-MM-DD), defaults to today
    """
    
    def get(self, request, game_id):
        """Get slots for a specific date with ON-DEMAND GENERATION"""
        
        # Get game
        game = get_object_or_404(Game, id=game_id, is_active=True)
        
        # Get date from query params
        date_str = request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            selected_date = timezone.now().date()
        
        # ====== ON-DEMAND SLOT GENERATION ======
        # Check if slots exist for this date, if not, generate them NOW!
        # This is FAST because we generate only 1 day at a time using bulk_create
        existing_slots_count = GameSlot.objects.filter(
            game=game,
            date=selected_date
        ).count()
        
        if existing_slots_count == 0:
            # Check if this date is available for the game
            weekday = selected_date.strftime('%A').lower()
            
            if weekday in game.available_days:
                # Generate slots for this date (FAST - uses bulk_create)
                from .slot_generator import SlotGenerator
                try:
                    created_count = SlotGenerator._generate_slots_for_date(game, selected_date)
                    if created_count > 0:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"ON-DEMAND: Generated {created_count} slots for {game.name} on {selected_date}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"ON-DEMAND: Error generating slots for {selected_date}: {str(e)}")
        # ====== END ON-DEMAND GENERATION ======
        
        # Get slots with optimized queries
        slots = GameSlot.objects.filter(
            game=game,
            date=selected_date,
            is_active=True
        ).select_related(
            'game',
            'availability'
        ).prefetch_related(
            Prefetch(
                'bookings',
                queryset=Booking.objects.filter(
                    status__in=['CONFIRMED', 'COMPLETED', 'PENDING']
                ).select_related('customer')
            )
        ).order_by('start_time')
        
        # Expire old reservations in bulk BEFORE processing slots (performance optimization)
        # Only expire if there are any to avoid unnecessary queries
        expired_count = Booking.objects.filter(
            game_slot__game=game,
            game_slot__date=selected_date,
            status='PENDING',
            reservation_expires_at__lte=timezone.now()
        ).update(status='EXPIRED', is_reservation_expired=True)
        
        # CRITICAL: Refresh slots from database after expiring reservations
        # The .select_related('availability') loaded stale data before expiration
        if expired_count > 0:
            slots = GameSlot.objects.filter(
                game=game,
                date=selected_date,
                is_active=True
            ).select_related(
                'game',
                'availability'
            ).prefetch_related(
                Prefetch(
                    'bookings',
                    queryset=Booking.objects.filter(
                        status__in=['CONFIRMED', 'COMPLETED', 'PENDING']
                    ).select_related('customer')
                )
            ).order_by('start_time')
        
        # Filter past slots
        now = timezone.now()
        available_slots = []
        
        for slot in slots:
            # Convert slot time to timezone-aware datetime in IST
            slot_datetime = timezone.make_aware(
                timezone.datetime.combine(slot.date, slot.start_time),
                timezone=timezone.get_current_timezone()
            )
            
            # Skip past slots
            if slot_datetime < now:
                continue
            
            # Check availability
            try:
                availability = slot.availability
                if availability.can_book_private or availability.can_book_shared:
                    available_slots.append(slot)
            except SlotAvailability.DoesNotExist:
                # Create availability if missing
                SlotAvailability.objects.create(
                    game_slot=slot,
                    total_capacity=game.capacity
                )
                available_slots.append(slot)
        
        # Serialize
        serializer = GameSlotSerializer(
            available_slots, 
            many=True,
            context={'request': request}
        )
        
        response_data = {
            'date': selected_date.isoformat(),
            'game_id': str(game.id),
            'game_name': game.name,
            'total_slots': len(available_slots),
            'slots': serializer.data
        }
        
        # Create response with no-cache headers to prevent browser caching
        response = Response(response_data)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class GameSlotsWeekAPI(APIView):
    """
    GET /api/games/{game_id}/slots/week/
    Returns slots grouped by date for the next 7 days
    """
    
    def get(self, request, game_id):
        """Get slots for next 7 days"""
        
        game = get_object_or_404(Game, id=game_id, is_active=True)
        
        # Get date range
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=6)
        
        # Get slots with optimized queries
        slots = GameSlot.objects.filter(
            game=game,
            date__gte=start_date,
            date__lte=end_date,
            is_active=True
        ).select_related(
            'game',
            'availability'
        ).prefetch_related(
            Prefetch(
                'bookings',
                queryset=Booking.objects.filter(
                    status__in=['CONFIRMED', 'COMPLETED', 'PENDING']
                )
            )
        ).order_by('date', 'start_time')
        
        # Group by date and filter past slots
        now = timezone.now()
        slots_by_date = {}
        
        for slot in slots:
            # Convert slot time to timezone-aware datetime in IST
            slot_datetime = timezone.make_aware(
                timezone.datetime.combine(slot.date, slot.start_time),
                timezone=timezone.get_current_timezone()
            )
            
            # Skip past slots
            if slot_datetime < now:
                continue
            
            date_key = slot.date.isoformat()
            if date_key not in slots_by_date:
                slots_by_date[date_key] = []
            
            # Check if available
            try:
                availability = slot.availability
                if availability.can_book_private or availability.can_book_shared:
                    slots_by_date[date_key].append(slot)
            except SlotAvailability.DoesNotExist:
                SlotAvailability.objects.create(
                    game_slot=slot,
                    total_capacity=game.capacity
                )
                slots_by_date[date_key].append(slot)
        
        # Serialize grouped data
        grouped_data = []
        for date_str, date_slots in slots_by_date.items():
            grouped_data.append({
                'date': date_str,
                'slots': GameSlotSerializer(date_slots, many=True, context={'request': request}).data,
                'total_slots': len(date_slots),
                'available_slots': len(date_slots)
            })
        
        response_data = {
            'game_id': str(game.id),
            'game_name': game.name,
            'dates': grouped_data
        }
        
        return Response(response_data)


class AvailableDatesAPI(APIView):
    """
    GET /api/games/{game_id}/available-dates/
    Returns list of dates that have available slots (for date picker)
    """
    
    def get(self, request, game_id):
        """Get dates with available slots"""
        
        game = get_object_or_404(Game, id=game_id, is_active=True)
        
        # Get date range
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=30)  # Next 30 days
        
        # Get dates with available slots
        available_dates = GameSlot.objects.filter(
            game=game,
            date__gte=start_date,
            date__lte=end_date,
            is_active=True,
            availability__is_private_booked=False
        ).values_list('date', flat=True).distinct().order_by('date')
        
        return Response({
            'game_id': str(game.id),
            'available_dates': [date.isoformat() for date in available_dates]
        })
