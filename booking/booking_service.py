"""
Booking service for hybrid booking logic and availability management
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models import Booking, GameSlot, SlotAvailability, Game
from authentication.models import Customer


class BookingService:
    """Service class for managing hybrid bookings"""
    
    @staticmethod
    def get_booking_options_fast(game_slot):
        """
        OPTIMIZED: Get booking options WITHOUT expiring reservations
        (Expiration should be done once in the view, not per-slot)
        """
        try:
            availability = game_slot.availability  # Use prefetched data
        except (SlotAvailability.DoesNotExist, AttributeError):
            availability = SlotAvailability.objects.create(
                game_slot=game_slot,
                total_capacity=game_slot.game.capacity
            )
        
        game = game_slot.game
        options = []
        restrictions = BookingService.get_booking_type_restrictions_fast(game_slot, availability)
        
        # Private booking option
        if game.booking_type in ['SINGLE', 'HYBRID']:
            private_option = {
                'type': 'PRIVATE',
                'price': float(game.private_price),
                'capacity': game.capacity,
                'spots_included': game.capacity,
                'description': f'Book entire {game.name} for your group',
                'available': restrictions['can_book_private'],
                'icon': '🔒',
                'benefits': [
                    'Exclusive access to the game',
                    f'Play with up to {game.capacity} friends',
                    'No waiting or sharing with strangers',
                    'Full control over game settings'
                ]
            }
            
            if not restrictions['can_book_private']:
                private_option['restriction_reason'] = restrictions.get('private_restriction_reason', 'Not available')
                private_option['disabled_message'] = f"Private booking blocked: {private_option['restriction_reason']}"
            
            options.append(private_option)
        
        # Shared booking option (only for hybrid games)
        if game.booking_type == 'HYBRID':
            shared_option = {
                'type': 'SHARED',
                'price': float(game.shared_price),
                'price_per_spot': float(game.shared_price),
                'available_spots': restrictions['available_spots'],
                'max_spots_per_booking': min(restrictions['available_spots'], game.capacity),
                'description': f'Book individual spot(s) - {restrictions["available_spots"]} remaining',
                'available': restrictions['can_book_shared'],
                'icon': '👥',
                'benefits': [
                    'More affordable option',
                    'Meet and play with other gamers',
                    'Book just the spots you need',
                    'Great for solo players or small groups'
                ]
            }
            
            if not restrictions['can_book_shared']:
                shared_option['restriction_reason'] = restrictions.get('shared_restriction_reason', 'Not available')
                shared_option['disabled_message'] = f"Shared booking blocked: {shared_option['restriction_reason']}"
            
            options.append(shared_option)
        
        # Add slot information to all options
        for option in options:
            option.update({
                'slot_info': {
                    'date': game_slot.date.isoformat(),
                    'start_time': game_slot.start_time.strftime('%H:%M'),
                    'end_time': game_slot.end_time.strftime('%H:%M'),
                    'duration_minutes': game.slot_duration_minutes,
                    'game_name': game.name,
                    'game_id': str(game.id),
                    'slot_id': str(game_slot.id)
                },
                'capacity_info': {
                    'total_capacity': restrictions['total_capacity'],
                    'booked_spots': restrictions['booked_spots'],
                    'available_spots': restrictions['available_spots'],
                    'is_private_locked': restrictions['is_private_locked'],
                    'is_shared_locked': restrictions['is_shared_locked']
                }
            })
        
        return options
    
    @staticmethod
    def get_booking_options(game_slot):
        """
        Get available booking options for a game slot with detailed information
        
        Args:
            game_slot: GameSlot instance
            
        Returns:
            List of available booking options with restrictions and pricing
        """
        try:
            availability = SlotAvailability.objects.get(game_slot=game_slot)
        except SlotAvailability.DoesNotExist:
            # Create availability if it doesn't exist
            availability = SlotAvailability.objects.create(
                game_slot=game_slot,
                total_capacity=game_slot.game.capacity
            )
        
        game = game_slot.game
        options = []
        restrictions = BookingService.get_booking_type_restrictions(game_slot)
        
        # Private booking option
        if game.booking_type in ['SINGLE', 'HYBRID']:
            private_option = {
                'type': 'PRIVATE',
                'price': float(game.private_price),
                'capacity': game.capacity,
                'spots_included': game.capacity,
                'description': f'Book entire {game.name} for your group',
                'available': restrictions['can_book_private'],
                'icon': '🔒',
                'benefits': [
                    'Exclusive access to the game',
                    f'Play with up to {game.capacity} friends',
                    'No waiting or sharing with strangers',
                    'Full control over game settings'
                ]
            }
            
            if not restrictions['can_book_private']:
                private_option['restriction_reason'] = restrictions.get('private_restriction_reason', 'Not available')
                private_option['disabled_message'] = f"Private booking blocked: {private_option['restriction_reason']}"
            
            options.append(private_option)
        
        # Shared booking option (only for hybrid games)
        if game.booking_type == 'HYBRID':
            shared_option = {
                'type': 'SHARED',
                'price': float(game.shared_price),
                'price_per_spot': float(game.shared_price),
                'available_spots': restrictions['available_spots'],
                'max_spots_per_booking': min(restrictions['available_spots'], game.capacity),
                'description': f'Book individual spot(s) - {restrictions["available_spots"]} remaining',
                'available': restrictions['can_book_shared'],
                'icon': '👥',
                'benefits': [
                    'More affordable option',
                    'Meet and play with other gamers',
                    'Book just the spots you need',
                    'Great for solo players or small groups'
                ]
            }
            
            if not restrictions['can_book_shared']:
                shared_option['restriction_reason'] = restrictions.get('shared_restriction_reason', 'Not available')
                shared_option['disabled_message'] = f"Shared booking blocked: {shared_option['restriction_reason']}"
            
            options.append(shared_option)
        
        # Add slot information to all options
        for option in options:
            option.update({
                'slot_info': {
                    'date': game_slot.date.isoformat(),
                    'start_time': game_slot.start_time.strftime('%H:%M'),
                    'end_time': game_slot.end_time.strftime('%H:%M'),
                    'duration_minutes': game.slot_duration_minutes,
                    'game_name': game.name,
                    'game_id': str(game.id),
                    'slot_id': str(game_slot.id)
                },
                'capacity_info': {
                    'total_capacity': restrictions['total_capacity'],
                    'booked_spots': restrictions['booked_spots'],
                    'available_spots': restrictions['available_spots'],
                    'is_private_locked': restrictions['is_private_locked'],
                    'is_shared_locked': restrictions['is_shared_locked']
                }
            })
        
        return options
    
    @staticmethod
    def create_booking(customer, game_slot, booking_type, spots_requested=1):
        """
        Create a booking with capacity validation and availability updates
        
        Args:
            customer: Customer instance
            game_slot: GameSlot instance
            booking_type: 'PRIVATE' or 'SHARED'
            spots_requested: Number of spots to book (for shared bookings)
            
        Returns:
            Booking instance
            
        Raises:
            ValidationError: If booking cannot be created
        """
        with transaction.atomic():
            # Validate booking time is in the future
            if game_slot.start_datetime <= timezone.now():
                raise ValidationError("Cannot book slots in the past")
            
            # Validate booking type lock-in logic
            BookingService.validate_booking_type_lock(game_slot, booking_type)
            
            # Handle potential conflicts
            BookingService.handle_booking_conflict(game_slot, booking_type, spots_requested)
            
            # Get availability with lock to prevent race conditions
            try:
                availability = SlotAvailability.objects.select_for_update().get(
                    game_slot=game_slot
                )
            except SlotAvailability.DoesNotExist:
                availability = SlotAvailability.objects.create(
                    game_slot=game_slot,
                    total_capacity=game_slot.game.capacity
                )
            
            game = game_slot.game
            
            # RE-CHECK availability under lock (race condition protection)
            # This ensures that even if two users clicked at the same time,
            # only one will succeed and the other will get an accurate error
            
            # Validate booking request
            if booking_type == 'PRIVATE':
                if not availability.can_book_private:
                    if availability.booked_spots > 0:
                        raise ValidationError(
                            f"Private booking no longer available. "
                            f"{availability.booked_spots} spot(s) were just booked by another user. "
                            f"Please select a different time slot or book individual spots."
                        )
                    else:
                        raise ValidationError("Private booking not available - slot already has bookings")
                
                if game.booking_type not in ['SINGLE', 'HYBRID']:
                    raise ValidationError("This game does not support private bookings")
                
                spots_booked = game.capacity
                price_per_spot = game.private_price / game.capacity
                total_price = game.private_price
                
                # Don't update availability here - let Booking.save() handle it
                # Availability will be updated based on booking status (PENDING vs CONFIRMED)
            
            elif booking_type == 'SHARED':
                if game.booking_type != 'HYBRID':
                    raise ValidationError("This game does not support shared bookings")
                
                if not availability.can_book_shared:
                    raise ValidationError(
                        "Shared booking no longer available. "
                        "This slot was just booked privately by another user. "
                        "Please select a different time slot."
                    )
                
                # CRITICAL: Re-check available spots under lock (including pending reservations)
                reserved_spots = availability.get_reserved_spots_count()
                truly_available = availability.available_spots - reserved_spots
                
                if spots_requested > truly_available:
                    if truly_available > 0:
                        if reserved_spots > 0:
                            raise ValidationError(
                                f"Only {truly_available} spot(s) available now. "
                                f"{reserved_spots} spot(s) are reserved by users completing payment. "
                                f"Please select {truly_available} or fewer spots, or wait a few minutes."
                            )
                        else:
                            raise ValidationError(
                                f"Only {truly_available} spot(s) available now. "
                                f"Another user just booked some spots. "
                                f"Please select {truly_available} or fewer spots."
                            )
                    else:
                        if reserved_spots > 0:
                            raise ValidationError(
                                f"All spots are currently reserved by users completing payment. "
                                f"Please wait a few minutes or select a different time slot."
                            )
                        else:
                            raise ValidationError(
                                "This time slot just became fully booked by another user. "
                                "Please select a different time slot."
                            )
                
                if spots_requested < 1:
                    raise ValidationError("Must book at least 1 spot")
                
                # AUTO-CONVERT TO PRIVATE: If booking all available spots in one booking, treat as private
                if spots_requested == game.capacity and availability.booked_spots == 0:
                    # User is booking all spots at once - convert to private booking with private pricing
                    booking_type = 'PRIVATE'
                    spots_booked = game.capacity
                    price_per_spot = game.private_price / game.capacity
                    total_price = game.private_price
                    
                    # Don't update availability here - let Booking.save() handle it
                else:
                    # Regular shared booking
                    spots_booked = spots_requested
                    price_per_spot = game.shared_price
                    total_price = price_per_spot * spots_requested
                    
                    # Don't update availability here - let Booking.save() handle it
            
            else:
                raise ValidationError("Invalid booking type")
            
            # Don't save availability here - Booking.save() will handle it based on status
            
            # Get platform fee from TapNex superuser settings
            from authentication.models import TapNexSuperuser
            try:
                tapnex_user = TapNexSuperuser.objects.first()
                if tapnex_user:
                    # Calculate platform fee based on type
                    if tapnex_user.platform_fee_type == 'PERCENT':
                        platform_fee = (total_price * tapnex_user.platform_fee) / 100
                    else:  # FIXED
                        platform_fee = tapnex_user.platform_fee
                else:
                    platform_fee = Decimal('0.00')
            except:
                platform_fee = Decimal('0.00')
            
            # Calculate final total with platform fee
            final_total = total_price + platform_fee
            
            # Create the booking
            booking = Booking.objects.create(
                customer=customer,
                game=game,
                game_slot=game_slot,
                booking_type=booking_type,
                spots_booked=spots_booked,
                price_per_spot=price_per_spot,
                subtotal=total_price,
                platform_fee=platform_fee,
                total_amount=final_total,
                status='PENDING'
            )
            
            # Broadcast real-time update
            from .realtime_service import RealTimeService
            RealTimeService.broadcast_availability_update(game_slot.id)
            
            return booking
    
    @staticmethod
    def cancel_booking(booking):
        """
        Cancel a booking and update availability
        
        Args:
            booking: Booking instance to cancel
        """
        with transaction.atomic():
            if booking.status in ['CANCELLED', 'COMPLETED']:
                raise ValidationError("Booking cannot be cancelled")
            
            # Update availability - ONLY if booking was CONFIRMED/IN_PROGRESS
            # PENDING bookings don't affect booked_spots (they're tracked via get_reserved_spots_count)
            if booking.status in ['CONFIRMED', 'IN_PROGRESS']:
                try:
                    availability = SlotAvailability.objects.select_for_update().get(
                        game_slot=booking.game_slot
                    )
                    
                    if booking.booking_type == 'PRIVATE':
                        availability.is_private_booked = False
                        availability.booked_spots = 0
                    else:  # SHARED
                        availability.booked_spots = max(0, availability.booked_spots - booking.spots_booked)
                    
                    availability.save()
                    
                except SlotAvailability.DoesNotExist:
                    pass  # Availability doesn't exist, nothing to update
            
            # Update booking status
            old_status = booking.status
            booking.status = 'CANCELLED'
            booking.save()
            
            # Create booking history record
            from .models import BookingHistory
            BookingHistory.objects.create(
                booking=booking,
                previous_status=old_status,
                new_status='CANCELLED',
                reason='Cancelled by customer'
            )
            
            # Send cancellation email and create in-app notification
            try:
                from .notifications import NotificationService, InAppNotification
                NotificationService.send_booking_cancellation_email(booking)
                InAppNotification.notify_booking_cancelled(booking)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send cancellation notification for booking {booking.id}: {e}")
                # Don't fail the cancellation if notification fails
            
            # Broadcast real-time update
            from .realtime_service import RealTimeService
            RealTimeService.broadcast_availability_update(booking.game_slot.id)
    
    @staticmethod
    def confirm_booking_payment(booking, payment_id=None, razorpay_payment_id=None, razorpay_order_id=None):
        """
        Confirm booking payment and update status
        
        Args:
            booking: Booking instance
            payment_id: Payment gateway transaction ID (deprecated, use razorpay_payment_id)
            razorpay_payment_id: Razorpay payment ID
            razorpay_order_id: Razorpay order ID
        """
        with transaction.atomic():
            if booking.status != 'PENDING':
                raise ValidationError("Only pending bookings can be confirmed")
            
            old_status = booking.status
            booking.status = 'CONFIRMED'
            
            # Support both old and new payment ID fields
            if razorpay_payment_id:
                booking.razorpay_payment_id = razorpay_payment_id
                booking.payment_status = 'PAID'
            elif payment_id:
                booking.payment_id = payment_id
                booking.payment_status = 'PAID'
            
            if razorpay_order_id:
                booking.razorpay_order_id = razorpay_order_id
            
            booking.save()
            
            # Create booking history record
            from .models import BookingHistory
            BookingHistory.objects.create(
                booking=booking,
                previous_status=old_status,
                new_status='CONFIRMED',
                reason=f'Payment confirmed - Razorpay Payment ID: {razorpay_payment_id or payment_id}'
            )
            
            # Send confirmation notification
            from .notifications import NotificationService
            NotificationService.send_booking_confirmation(booking)
    
    @staticmethod
    def get_available_slots(game, date_from=None, date_to=None):
        """
        Get available slots for a game within a date range
        ON-DEMAND: Automatically generates slots if they don't exist for requested dates
        
        Args:
            game: Game instance
            date_from: Start date (default: today)
            date_to: End date (default: 7 days from today)
            
        Returns:
            QuerySet of available GameSlots with availability info
        """
        from datetime import date, timedelta
        from .slot_generator import SlotGenerator
        
        if not date_from:
            date_from = date.today()
        if not date_to:
            date_to = date_from + timedelta(days=7)
        
        # 🎯 ON-DEMAND GENERATION: Ensure slots exist for the requested date range
        current_date = date_from
        while current_date <= date_to:
            SlotGenerator.ensure_slots_for_date(game, current_date)
            current_date += timedelta(days=1)
        
        # Get slots in date range
        slots = GameSlot.objects.filter(
            game=game,
            date__gte=date_from,
            date__lte=date_to,
            is_active=True
        ).select_related('game').prefetch_related('availability')
        
        # Filter out fully booked slots
        available_slots = []
        for slot in slots:
            try:
                availability = slot.availability
                if availability.can_book_private or availability.can_book_shared:
                    available_slots.append({
                        'slot': slot,
                        'availability': availability,
                        'options': BookingService.get_booking_options(slot)
                    })
            except SlotAvailability.DoesNotExist:
                # Create availability if missing
                availability = SlotAvailability.objects.create(
                    game_slot=slot,
                    total_capacity=game.capacity
                )
                available_slots.append({
                    'slot': slot,
                    'availability': availability,
                    'options': BookingService.get_booking_options(slot)
                })
        
        return available_slots
    
    @staticmethod
    def handle_booking_conflict(game_slot, booking_type, spots_requested):
        """
        Handle simultaneous booking attempts with conflict resolution
        
        Args:
            game_slot: GameSlot instance
            booking_type: 'PRIVATE' or 'SHARED'
            spots_requested: Number of spots requested
            
        Returns:
            True if booking can proceed, raises ValidationError otherwise
        """
        try:
            with transaction.atomic():
                availability = SlotAvailability.objects.select_for_update().get(
                    game_slot=game_slot
                )
                
                # Validate availability under lock
                if booking_type == 'PRIVATE' and not availability.can_book_private:
                    raise ValidationError("Slot no longer available for private booking")
                
                if booking_type == 'SHARED':
                    if not availability.can_book_shared:
                        raise ValidationError("Slot no longer available for shared booking")
                    if spots_requested > availability.available_spots:
                        raise ValidationError(f"Only {availability.available_spots} spots remaining")
                
                return True
                
        except SlotAvailability.DoesNotExist:
            # Create availability if it doesn't exist
            SlotAvailability.objects.create(
                game_slot=game_slot,
                total_capacity=game_slot.game.capacity
            )
            return True
        except ValidationError as e:
            # Broadcast updated availability to all clients
            from .realtime_service import RealTimeService
            RealTimeService.broadcast_availability_update(game_slot.id)
            raise e
    
    @staticmethod
    def validate_booking_type_lock(game_slot, booking_type):
        """
        Validate booking type lock-in logic:
        - Private booking blocks all shared bookings
        - Shared bookings block private booking
        
        Args:
            game_slot: GameSlot instance
            booking_type: 'PRIVATE' or 'SHARED'
            
        Returns:
            True if booking type is allowed, raises ValidationError otherwise
        """
        try:
            availability = SlotAvailability.objects.get(game_slot=game_slot)
            
            if booking_type == 'PRIVATE':
                if availability.booked_spots > 0 and not availability.is_private_booked:
                    raise ValidationError(
                        "Cannot book private - slot already has shared bookings. "
                        f"{availability.booked_spots} spots are already booked by other customers."
                    )
            
            elif booking_type == 'SHARED':
                if availability.is_private_booked:
                    raise ValidationError(
                        "Cannot book shared - slot is privately booked. "
                        "The entire slot is reserved for a private group."
                    )
            
            return True
            
        except SlotAvailability.DoesNotExist:
            # No existing bookings, all types allowed
            return True
    
    @staticmethod
    def get_booking_type_restrictions_fast(game_slot, availability):
        """
        OPTIMIZED: Get restrictions WITHOUT expiring (expiration done in view)
        """
        from django.utils import timezone
        
        # Get pending reservations count
        reserved_spots = availability.get_reserved_spots_count()
        truly_available = availability.get_truly_available_spots()
        
        # Check if there are any pending private bookings (use prefetched data)
        has_pending_private = any(
            b.status == 'PENDING' and 
            b.booking_type == 'PRIVATE' and 
            b.reservation_expires_at > timezone.now()
            for b in game_slot.bookings.all()
        )
        
        # Check if there are any pending shared bookings (use prefetched data)
        has_pending_shared = any(
            b.status == 'PENDING' and 
            b.booking_type == 'SHARED' and 
            b.reservation_expires_at > timezone.now()
            for b in game_slot.bookings.all()
        )
        
        # Private booking is blocked if there are any pending private OR shared bookings
        can_book_private = availability.can_book_private and not has_pending_private and not has_pending_shared
        
        # Shared booking is blocked if there are any pending private bookings
        can_book_shared = availability.can_book_shared and not has_pending_private
        
        restrictions = {
            'can_book_private': can_book_private,
            'can_book_shared': can_book_shared,
            'is_private_locked': availability.is_private_booked or has_pending_private or has_pending_shared,
            'is_shared_locked': availability.booked_spots > 0 and not availability.is_private_booked,
            'available_spots': truly_available,
            'booked_spots': availability.booked_spots,
            'reserved_spots': reserved_spots,
            'truly_available_spots': truly_available,
            'total_capacity': availability.total_capacity,
            'has_pending_reservations': reserved_spots > 0,
            'has_pending_private': has_pending_private,
            'has_pending_shared': has_pending_shared
        }
        
        # Add restriction reasons
        if not restrictions['can_book_private']:
            if has_pending_private:
                restrictions['private_restriction_reason'] = "Someone is currently completing payment for private booking"
            elif has_pending_shared:
                restrictions['private_restriction_reason'] = "Someone is currently completing payment for shared booking"
            elif restrictions['is_shared_locked']:
                restrictions['private_restriction_reason'] = f"Slot has {availability.booked_spots} shared bookings"
            else:
                restrictions['private_restriction_reason'] = "Slot is fully booked"
        
        if not restrictions['can_book_shared']:
            if has_pending_private:
                restrictions['shared_restriction_reason'] = "Someone is currently completing payment for private booking"
            elif restrictions['is_private_locked']:
                restrictions['shared_restriction_reason'] = "Slot is privately booked"
            else:
                restrictions['shared_restriction_reason'] = "No spots available"
        
        return restrictions
    
    @staticmethod
    def get_booking_type_restrictions(game_slot):
        """
        Get current booking type restrictions for a slot
        
        Args:
            game_slot: GameSlot instance
            
        Returns:
            Dict with restriction information including pending reservations
        """
        from django.utils import timezone
        
        try:
            availability = SlotAvailability.objects.get(game_slot=game_slot)
            
            # Expire old pending reservations first
            BookingService.expire_old_reservations(game_slot)
            
            # Get pending reservations count
            reserved_spots = availability.get_reserved_spots_count()
            truly_available = availability.get_truly_available_spots()
            
            # Check if there are any pending private bookings
            has_pending_private = game_slot.bookings.filter(
                status='PENDING',
                booking_type='PRIVATE',
                reservation_expires_at__gt=timezone.now()
            ).exists()
            
            # Check if there are any pending shared bookings
            has_pending_shared = game_slot.bookings.filter(
                status='PENDING',
                booking_type='SHARED',
                reservation_expires_at__gt=timezone.now()
            ).exists()
            
            # Private booking is blocked if:
            # 1. There are any confirmed shared bookings (availability.can_book_private checks this)
            # 2. There are any pending private bookings
            # 3. There are any pending shared bookings (NEW FIX)
            can_book_private = availability.can_book_private and not has_pending_private and not has_pending_shared
            
            # Shared booking is blocked if:
            # 1. There's a confirmed private booking
            # 2. There are any pending private bookings
            can_book_shared = availability.can_book_shared and not has_pending_private
            
            restrictions = {
                'can_book_private': can_book_private,
                'can_book_shared': can_book_shared,
                'is_private_locked': availability.is_private_booked or has_pending_private or has_pending_shared,
                'is_shared_locked': availability.booked_spots > 0 and not availability.is_private_booked,
                'available_spots': truly_available,  # FIXED: Use truly_available instead of availability.available_spots
                'booked_spots': availability.booked_spots,
                'reserved_spots': reserved_spots,
                'truly_available_spots': truly_available,
                'total_capacity': availability.total_capacity,
                'has_pending_reservations': reserved_spots > 0,
                'has_pending_private': has_pending_private,
                'has_pending_shared': has_pending_shared
            }
            
            # Add restriction reasons
            if not restrictions['can_book_private']:
                if has_pending_private:
                    restrictions['private_restriction_reason'] = "Someone is currently completing payment for private booking"
                elif has_pending_shared:
                    restrictions['private_restriction_reason'] = "Someone is currently completing payment for shared booking"
                elif restrictions['is_shared_locked']:
                    restrictions['private_restriction_reason'] = f"Slot has {availability.booked_spots} shared bookings"
                else:
                    restrictions['private_restriction_reason'] = "Slot is fully booked"
            
            if not restrictions['can_book_shared']:
                if has_pending_private:
                    restrictions['shared_restriction_reason'] = "Someone is currently completing payment for private booking"
                elif restrictions['is_private_locked']:
                    restrictions['shared_restriction_reason'] = "Slot is privately booked"
                else:
                    restrictions['shared_restriction_reason'] = "No spots available"
            
            return restrictions
            
        except SlotAvailability.DoesNotExist:
            # No existing bookings, all types allowed
            return {
                'can_book_private': True,
                'can_book_shared': game_slot.game.booking_type == 'HYBRID',
                'is_private_locked': False,
                'is_shared_locked': False,
                'available_spots': game_slot.game.capacity,
                'booked_spots': 0,
                'reserved_spots': 0,
                'truly_available_spots': game_slot.game.capacity,
                'total_capacity': game_slot.game.capacity,
                'has_pending_reservations': False
            }
    
    @staticmethod
    def expire_old_reservations(game_slot):
        """Expire old pending reservations for a slot"""
        from django.utils import timezone
        
        expired_bookings = game_slot.bookings.filter(
            status='PENDING',
            reservation_expires_at__lte=timezone.now()
        )
        
        for booking in expired_bookings:
            booking.check_and_expire_reservation()

def auto_update_booking_status(booking):
    """
    Helper function to automatically update a single booking's status based on current time.
    
    Handles all status transitions:
    - PENDING → EXPIRED (payment reservation expired)
    - CONFIRMED → IN_PROGRESS (start time reached)
    - IN_PROGRESS → COMPLETED (end time passed)
    - CONFIRMED → NO_SHOW (end time passed without verification)
    
    Args:
        booking: Booking instance to check and update
        
    Returns:
        tuple: (status_changed: bool, old_status: str, new_status: str)
    """
    now = timezone.now()
    old_status = booking.status
    status_changed = False
    
    # 1. Check for EXPIRED status (PENDING bookings with expired reservation)
    if (booking.status == 'PENDING' and 
        booking.reservation_expires_at and 
        now >= booking.reservation_expires_at and
        not booking.is_reservation_expired):
        booking.status = 'EXPIRED'
        booking.is_reservation_expired = True
        booking.save(update_fields=['status', 'is_reservation_expired'])
        status_changed = True
    
    # Get start and end times
    start_dt = booking.start_datetime
    end_dt = booking.end_datetime
    
    if start_dt and end_dt:
        # 2. Auto-start confirmed bookings (CONFIRMED → IN_PROGRESS)
        if booking.status == 'CONFIRMED' and start_dt <= now < end_dt:
            booking.status = 'IN_PROGRESS'
            booking.save(update_fields=['status'])
            status_changed = True
        
        # 3. Auto-complete in-progress bookings (IN_PROGRESS → COMPLETED or NO_SHOW)
        elif booking.status == 'IN_PROGRESS' and now >= end_dt:
            # Only mark as COMPLETED if QR was scanned (verified)
            if booking.is_verified:
                booking.status = 'COMPLETED'
            else:
                booking.status = 'NO_SHOW'
            booking.save(update_fields=['status'])
            status_changed = True
        
        # 4. Mark as NO_SHOW if confirmed but time passed and not verified (CONFIRMED → NO_SHOW)
        elif booking.status == 'CONFIRMED' and now >= end_dt and not booking.is_verified:
            booking.status = 'NO_SHOW'
            booking.save(update_fields=['status'])
            status_changed = True
    
    return status_changed, old_status, booking.status


def auto_update_bookings_status(bookings_queryset=None):
    """
    Helper function to automatically update multiple bookings' statuses.
    
    Args:
        bookings_queryset: QuerySet of bookings to update. If None, updates all active bookings.
        
    Returns:
        dict: Summary of status changes
    """
    if bookings_queryset is None:
        # Default: check all bookings that might need status updates
        bookings_queryset = Booking.objects.filter(
            status__in=['PENDING', 'CONFIRMED', 'IN_PROGRESS']
        ).select_related('game_slot')
    
    summary = {
        'expired': 0,
        'started': 0,
        'completed': 0,
        'no_show': 0,
        'total_checked': 0,
        'total_updated': 0
    }
    
    for booking in bookings_queryset:
        summary['total_checked'] += 1
        status_changed, old_status, new_status = auto_update_booking_status(booking)
        
        if status_changed:
            summary['total_updated'] += 1
            
            # Track specific transitions
            if new_status == 'EXPIRED':
                summary['expired'] += 1
            elif new_status == 'IN_PROGRESS':
                summary['started'] += 1
            elif new_status == 'COMPLETED':
                summary['completed'] += 1
            elif new_status == 'NO_SHOW':
                summary['no_show'] += 1
    
    return summary
