"""
Enhanced slot generation utility for automatic time slot creation
Supports automatic slot generation based on game schedule settings,
slot regeneration with booking preservation, and custom slot management.
"""
from datetime import datetime, timedelta, time, date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Import models at module level to avoid circular imports
from .models import GameSlot, SlotAvailability


class SlotGenerator:
    """Enhanced utility class for generating game time slots"""
    
    @staticmethod
    def generate_slots_for_game(game, start_date, end_date):
        """
        Generate time slots for a game based on its schedule settings
        
        Args:
            game: Game instance
            start_date: Start date for slot generation
            end_date: End date for slot generation
            
        Returns:
            dict: Summary of slot generation results
        """
        if not game.is_active:
            logger.warning(f"Skipping slot generation for inactive game: {game.name}")
            return {'created': 0, 'skipped': 0, 'errors': []}
        
        if not game.available_days:
            logger.warning(f"Game {game.name} has no available days configured")
            return {'created': 0, 'skipped': 0, 'errors': ['No available days configured']}
        
        slots_created = 0
        slots_skipped = 0
        errors = []
        
        try:
            with transaction.atomic():
                current_date = start_date
                
                while current_date <= end_date:
                    # Check if this day is available for the game
                    weekday = current_date.strftime('%A').lower()
                    
                    if weekday in game.available_days:
                        try:
                            created = SlotGenerator._generate_slots_for_date(game, current_date)
                            slots_created += created
                            
                            if created == 0:
                                slots_skipped += 1
                                
                        except Exception as e:
                            error_msg = f"Error generating slots for {current_date}: {str(e)}"
                            errors.append(error_msg)
                            logger.error(error_msg)
                    else:
                        slots_skipped += 1
                    
                    current_date += timedelta(days=1)
                    
        except Exception as e:
            error_msg = f"Transaction failed during slot generation: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            raise
        
        logger.info(f"Slot generation completed for {game.name}: {slots_created} created, {slots_skipped} skipped")
        
        return {
            'created': slots_created,
            'skipped': slots_skipped,
            'errors': errors
        }
    
    @staticmethod
    def _generate_slots_for_date(game, target_date):
        """
        Generate slots for a specific date with enhanced validation
        OPTIMIZED for fast generation using bulk_create (for on-demand generation)
        
        Args:
            game: Game instance
            target_date: Date to generate slots for
            
        Returns:
            int: Number of slots created
        """
        if target_date < date.today():
            logger.warning(f"Skipping slot generation for past date: {target_date}")
            return 0
        
        # Validate game schedule
        if game.opening_time >= game.closing_time:
            raise ValidationError(f"Invalid schedule for {game.name}: opening time must be before closing time")
        
        if game.slot_duration_minutes <= 0:
            raise ValidationError(f"Invalid slot duration for {game.name}: must be greater than 0")
        
        # Check if slots already exist for this date (avoid duplicate generation)
        existing_slots = GameSlot.objects.filter(
            game=game,
            date=target_date
        ).exists()
        
        if existing_slots:
            logger.debug(f"Slots already exist for {game.name} on {target_date}")
            return 0
        
        # OPTIMIZATION: Build all slots in memory first, then bulk_create
        slots_to_create = []
        availabilities_to_create = []
        current_time = game.opening_time
        
        while current_time < game.closing_time:
            # Calculate end time for this slot
            start_datetime = datetime.combine(target_date, current_time)
            end_datetime = start_datetime + timedelta(minutes=game.slot_duration_minutes)
            end_time = end_datetime.time()
            
            # Don't create slot if it goes beyond closing time
            if end_time > game.closing_time:
                logger.debug(f"Slot {current_time}-{end_time} extends beyond closing time for {game.name}")
                break
            
            # Add slot to bulk list
            slots_to_create.append(GameSlot(
                game=game,
                date=target_date,
                start_time=current_time,
                end_time=end_time,
                is_custom=False,
                is_active=True
            ))
            
            # Move to next slot time
            current_time = end_time
        
        # BULK CREATE - Much faster than individual creates!
        if slots_to_create:
            try:
                created_slots = GameSlot.objects.bulk_create(slots_to_create, ignore_conflicts=True)
                slots_created = len(created_slots)
                
                # Create availability tracking for all new slots
                for slot in created_slots:
                    availabilities_to_create.append(SlotAvailability(
                        game_slot=slot,
                        total_capacity=game.capacity,
                        booked_spots=0,
                        is_private_booked=False
                    ))
                
                # Bulk create availabilities
                if availabilities_to_create:
                    SlotAvailability.objects.bulk_create(availabilities_to_create, ignore_conflicts=True)
                
                logger.info(f"Bulk created {slots_created} slots for {game.name} on {target_date}")
                return slots_created
                
            except Exception as e:
                logger.error(f"Error bulk creating slots for {game.name} on {target_date}: {e}")
                # Fallback to slower method if bulk_create fails
                return SlotGenerator._generate_slots_for_date_legacy(game, target_date)
        
        return 0
    
    @staticmethod
    def _generate_slots_for_date_legacy(game, target_date):
        """
        Legacy slot generation method (slower but more reliable)
        Used as fallback if bulk_create fails
        """
        slots_created = 0
        current_time = game.opening_time
        
        while current_time < game.closing_time:
            start_datetime = datetime.combine(target_date, current_time)
            end_datetime = start_datetime + timedelta(minutes=game.slot_duration_minutes)
            end_time = end_datetime.time()
            
            if end_time > game.closing_time:
                break
            
            try:
                slot, created = GameSlot.objects.get_or_create(
                    game=game,
                    date=target_date,
                    start_time=current_time,
                    defaults={
                        'end_time': end_time,
                        'is_custom': False,
                        'is_active': True
                    }
                )
                
                if created:
                    SlotAvailability.objects.get_or_create(
                        game_slot=slot,
                        defaults={
                            'total_capacity': game.capacity,
                            'booked_spots': 0,
                            'is_private_booked': False
                        }
                    )
                    slots_created += 1
                
            except Exception as e:
                logger.error(f"Error creating slot {current_time}-{end_time}: {e}")
                
            current_time = end_time
        
        return slots_created
    
    @staticmethod
    def create_custom_slot(game, target_date, start_time, end_time, validate_conflicts=True):
        """
        Create a custom slot for a game with enhanced validation
        
        Args:
            game: Game instance
            target_date: Date for the custom slot
            start_time: Start time for the slot
            end_time: End time for the slot
            validate_conflicts: Whether to check for conflicts with existing slots
            
        Returns:
            dict: Result with slot instance or error information
        """
        try:
            # Validate input parameters
            validation_result = SlotGenerator._validate_custom_slot_params(
                game, target_date, start_time, end_time
            )
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'slot': None,
                    'errors': validation_result['errors']
                }
            
            with transaction.atomic():
                # Check for conflicts with existing slots if requested
                if validate_conflicts:
                    conflict_result = SlotGenerator._check_slot_conflicts(
                        game, target_date, start_time, end_time
                    )
                    
                    if not conflict_result['valid']:
                        return {
                            'success': False,
                            'slot': None,
                            'errors': conflict_result['errors'],
                            'conflicting_slots': conflict_result.get('conflicting_slots', [])
                        }
                
                # Create the custom slot
                slot = GameSlot.objects.create(
                    game=game,
                    date=target_date,
                    start_time=start_time,
                    end_time=end_time,
                    is_custom=True,
                    is_active=True
                )
                
                # Create availability tracking
                SlotAvailability.objects.create(
                    game_slot=slot,
                    total_capacity=game.capacity,
                    booked_spots=0,
                    is_private_booked=False
                )
                
                logger.info(f"Created custom slot: {slot}")
                
                return {
                    'success': True,
                    'slot': slot,
                    'errors': []
                }
                
        except Exception as e:
            error_msg = f"Error creating custom slot: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'slot': None,
                'errors': [error_msg]
            }
    
    @staticmethod
    def _validate_custom_slot_params(game, target_date, start_time, end_time):
        """
        Validate parameters for custom slot creation
        
        Returns:
            dict: Validation result with errors if any
        """
        errors = []
        
        # Validate game
        if not game or not game.is_active:
            errors.append("Game must be active")
        
        # Validate date
        if target_date < date.today():
            errors.append("Cannot create slots for past dates")
        
        # Validate times
        if start_time >= end_time:
            errors.append("Start time must be before end time")
        
        # Calculate duration
        start_datetime = datetime.combine(target_date, start_time)
        end_datetime = datetime.combine(target_date, end_time)
        duration_minutes = (end_datetime - start_datetime).total_seconds() / 60
        
        if duration_minutes <= 0:
            errors.append("Slot duration must be greater than 0 minutes")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    def _check_slot_conflicts(game, target_date, start_time, end_time, exclude_slot_id=None):
        """
        Check for conflicts with existing slots
        
        Returns:
            dict: Conflict check result
        """
        # Find overlapping slots
        conflicting_slots_query = GameSlot.objects.filter(
            game=game,
            date=target_date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            is_active=True
        )
        
        # Exclude specific slot if provided (for updates)
        if exclude_slot_id:
            conflicting_slots_query = conflicting_slots_query.exclude(id=exclude_slot_id)
        
        conflicting_slots = list(conflicting_slots_query)
        
        if conflicting_slots:
            conflict_details = []
            for slot in conflicting_slots:
                conflict_details.append({
                    'id': slot.id,
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'is_custom': slot.is_custom,
                    'has_bookings': slot.bookings.exists()
                })
            
            return {
                'valid': False,
                'errors': [f"Custom slot conflicts with {len(conflicting_slots)} existing slot(s)"],
                'conflicting_slots': conflict_details
            }
        
        return {
            'valid': True,
            'errors': [],
            'conflicting_slots': []
        }
    
    @staticmethod
    def update_custom_slot(slot_id, new_start_time=None, new_end_time=None, new_date=None):
        """
        Update an existing custom slot
        
        Args:
            slot_id: ID of the slot to update
            new_start_time: New start time (optional)
            new_end_time: New end time (optional)
            new_date: New date (optional)
            
        Returns:
            dict: Update result
        """
        try:
            with transaction.atomic():
                slot = GameSlot.objects.select_for_update().get(
                    id=slot_id,
                    is_custom=True
                )
                
                # Check if slot has bookings
                if slot.bookings.filter(status__in=['CONFIRMED', 'IN_PROGRESS']).exists():
                    return {
                        'success': False,
                        'errors': ['Cannot update slot with confirmed bookings']
                    }
                
                # Use current values if new ones not provided
                target_date = new_date or slot.date
                start_time = new_start_time or slot.start_time
                end_time = new_end_time or slot.end_time
                
                # Validate new parameters
                validation_result = SlotGenerator._validate_custom_slot_params(
                    slot.game, target_date, start_time, end_time
                )
                
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'errors': validation_result['errors']
                    }
                
                # Check for conflicts (excluding current slot)
                conflict_result = SlotGenerator._check_slot_conflicts(
                    slot.game, target_date, start_time, end_time, exclude_slot_id=slot.id
                )
                
                if not conflict_result['valid']:
                    return {
                        'success': False,
                        'errors': conflict_result['errors'],
                        'conflicting_slots': conflict_result.get('conflicting_slots', [])
                    }
                
                # Update slot
                slot.date = target_date
                slot.start_time = start_time
                slot.end_time = end_time
                slot.save()
                
                logger.info(f"Updated custom slot: {slot}")
                
                return {
                    'success': True,
                    'slot': slot,
                    'errors': []
                }
                
        except GameSlot.DoesNotExist:
            return {
                'success': False,
                'errors': ['Custom slot not found']
            }
        except Exception as e:
            error_msg = f"Error updating custom slot: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'errors': [error_msg]
            }
    
    @staticmethod
    def delete_custom_slot(slot_id, force=False):
        """
        Delete a custom slot
        
        Args:
            slot_id: ID of the slot to delete
            force: Whether to force deletion even with bookings
            
        Returns:
            dict: Deletion result
        """
        try:
            with transaction.atomic():
                slot = GameSlot.objects.select_for_update().get(
                    id=slot_id,
                    is_custom=True
                )
                
                # Check for bookings
                active_bookings = slot.bookings.filter(
                    status__in=['CONFIRMED', 'IN_PROGRESS', 'PENDING']
                )
                
                if active_bookings.exists() and not force:
                    return {
                        'success': False,
                        'errors': [f'Cannot delete slot with {active_bookings.count()} active booking(s)'],
                        'active_bookings': active_bookings.count()
                    }
                
                # Cancel any pending bookings if force deletion
                if force and active_bookings.exists():
                    cancelled_count = active_bookings.update(status='CANCELLED')
                    logger.warning(f"Force deleted slot {slot_id}, cancelled {cancelled_count} bookings")
                
                slot_info = str(slot)
                slot.delete()
                
                logger.info(f"Deleted custom slot: {slot_info}")
                
                return {
                    'success': True,
                    'errors': []
                }
                
        except GameSlot.DoesNotExist:
            return {
                'success': False,
                'errors': ['Custom slot not found']
            }
        except Exception as e:
            error_msg = f"Error deleting custom slot: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'errors': [error_msg]
            }
    
    @staticmethod
    def get_custom_slots_for_game(game, start_date=None, end_date=None):
        """
        Get all custom slots for a game within a date range
        
        Args:
            game: Game instance
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            QuerySet: Custom slots for the game
        """
        slots = GameSlot.objects.filter(
            game=game,
            is_custom=True,
            is_active=True
        ).select_related('game').prefetch_related('bookings', 'availability')
        
        if start_date:
            slots = slots.filter(date__gte=start_date)
        
        if end_date:
            slots = slots.filter(date__lte=end_date)
        
        return slots.order_by('date', 'start_time')
    
    @staticmethod
    def bulk_create_custom_slots(game, slot_definitions):
        """
        Create multiple custom slots at once
        
        Args:
            game: Game instance
            slot_definitions: List of dicts with 'date', 'start_time', 'end_time'
            
        Returns:
            dict: Bulk creation result
        """
        created_slots = []
        errors = []
        
        try:
            with transaction.atomic():
                for i, slot_def in enumerate(slot_definitions):
                    try:
                        result = SlotGenerator.create_custom_slot(
                            game=game,
                            target_date=slot_def['date'],
                            start_time=slot_def['start_time'],
                            end_time=slot_def['end_time'],
                            validate_conflicts=True
                        )
                        
                        if result['success']:
                            created_slots.append(result['slot'])
                        else:
                            errors.extend([f"Slot {i+1}: {error}" for error in result['errors']])
                            
                    except KeyError as e:
                        errors.append(f"Slot {i+1}: Missing required field {e}")
                    except Exception as e:
                        errors.append(f"Slot {i+1}: {str(e)}")
                
                # If any errors occurred, rollback the transaction
                if errors:
                    raise ValidationError("Bulk creation failed due to validation errors")
                
        except Exception as e:
            logger.error(f"Bulk custom slot creation failed: {e}")
            return {
                'success': False,
                'created_count': 0,
                'created_slots': [],
                'errors': errors or [str(e)]
            }
        
        logger.info(f"Bulk created {len(created_slots)} custom slots for {game.name}")
        
        return {
            'success': True,
            'created_count': len(created_slots),
            'created_slots': created_slots,
            'errors': []
        }
    
    @staticmethod
    def regenerate_slots_for_game(game, preserve_bookings=True, days_ahead=30):
        """
        Regenerate all slots for a game (useful when schedule changes)
        
        Args:
            game: Game instance
            preserve_bookings: Whether to preserve existing bookings
            days_ahead: Number of days ahead to generate slots for
            
        Returns:
            dict: Summary of regeneration results
        """
        logger.info(f"Starting slot regeneration for game: {game.name}")
        
        try:
            with transaction.atomic():
                if preserve_bookings:
                    # Only delete slots without bookings (future slots only)
                    slots_to_delete = GameSlot.objects.filter(
                        game=game,
                        is_custom=False,
                        bookings__isnull=True,
                        date__gte=date.today()  # Only future slots
                    )
                    
                    # Count slots with bookings that will be preserved
                    preserved_slots = GameSlot.objects.filter(
                        game=game,
                        is_custom=False,
                        bookings__isnull=False,
                        date__gte=date.today()
                    ).count()
                    
                else:
                    # Delete all auto-generated slots (including those with bookings)
                    slots_to_delete = GameSlot.objects.filter(
                        game=game,
                        is_custom=False,
                        date__gte=date.today()
                    )
                    preserved_slots = 0
                
                deleted_count = slots_to_delete.count()
                
                # Log what will be deleted
                if deleted_count > 0:
                    logger.info(f"Deleting {deleted_count} existing slots for {game.name}")
                    slots_to_delete.delete()
                
                # Generate new slots for specified period
                start_date = date.today()
                end_date = start_date + timedelta(days=days_ahead)
                
                generation_result = SlotGenerator.generate_slots_for_game(game, start_date, end_date)
                created_count = generation_result['created']
                
                result = {
                    'deleted': deleted_count,
                    'created': created_count,
                    'preserved': preserved_slots,
                    'errors': generation_result.get('errors', [])
                }
                
                logger.info(f"Slot regeneration completed for {game.name}: {result}")
                return result
                
        except Exception as e:
            error_msg = f"Failed to regenerate slots for {game.name}: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
    
    @staticmethod
    def daily_slot_generation(days_ahead=30):
        """
        Daily task to generate slots for all active games
        Should be run as a scheduled task (e.g., Django management command)
        
        Args:
            days_ahead: Number of days ahead to generate slots for
            
        Returns:
            dict: Summary of daily generation results
        """
        from .models import Game
        
        logger.info(f"Starting daily slot generation for {days_ahead} days ahead")
        
        # Generate slots for the target date (days_ahead from today)
        target_date = date.today() + timedelta(days=days_ahead)
        
        active_games = Game.objects.filter(is_active=True)
        total_created = 0
        total_errors = []
        games_processed = 0
        games_skipped = 0
        
        for game in active_games:
            try:
                weekday = target_date.strftime('%A').lower()
                if weekday in game.available_days:
                    created = SlotGenerator._generate_slots_for_date(game, target_date)
                    total_created += created
                    games_processed += 1
                    
                    if created > 0:
                        logger.debug(f"Created {created} slots for {game.name} on {target_date}")
                else:
                    games_skipped += 1
                    logger.debug(f"Skipped {game.name} - not available on {weekday}")
                    
            except Exception as e:
                error_msg = f"Error processing {game.name}: {str(e)}"
                total_errors.append(error_msg)
                logger.error(error_msg)
        
        result = {
            'target_date': target_date,
            'games_processed': games_processed,
            'games_skipped': games_skipped,
            'total_created': total_created,
            'errors': total_errors
        }
        
        logger.info(f"Daily slot generation completed: {result}")
        return result
    
    @staticmethod
    def validate_slot_generation_settings(game):
        """
        Validate game settings for slot generation
        
        Args:
            game: Game instance
            
        Returns:
            dict: Validation results with any errors
        """
        errors = []
        warnings = []
        
        # Check basic requirements
        if not game.is_active:
            warnings.append("Game is not active")
        
        if not game.available_days:
            errors.append("No available days configured")
        
        if game.opening_time >= game.closing_time:
            errors.append("Opening time must be before closing time")
        
        if game.slot_duration_minutes <= 0:
            errors.append("Slot duration must be greater than 0")
        
        if game.capacity <= 0:
            errors.append("Game capacity must be greater than 0")
        
        # Check if slot duration allows for at least one slot per day
        if game.opening_time < game.closing_time:
            opening_datetime = datetime.combine(date.today(), game.opening_time)
            closing_datetime = datetime.combine(date.today(), game.closing_time)
            available_minutes = (closing_datetime - opening_datetime).total_seconds() / 60
            
            if available_minutes < game.slot_duration_minutes:
                errors.append(f"Slot duration ({game.slot_duration_minutes} min) is longer than available time ({available_minutes} min)")
        
        # Check pricing
        if game.private_price <= 0:
            errors.append("Private price must be greater than 0")
        
        if game.booking_type == 'HYBRID' and (not game.shared_price or game.shared_price <= 0):
            errors.append("Hybrid games must have a valid shared price")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def get_slot_generation_preview(game, target_date):
        """
        Preview what slots would be generated for a game on a specific date
        
        Args:
            game: Game instance
            target_date: Date to preview slots for
            
        Returns:
            list: List of slot dictionaries that would be created
        """
        preview_slots = []
        
        # Validate settings first
        validation = SlotGenerator.validate_slot_generation_settings(game)
        if not validation['valid']:
            return {
                'slots': [],
                'errors': validation['errors'],
                'warnings': validation['warnings']
            }
        
        # Check if date is available
        weekday = target_date.strftime('%A').lower()
        if weekday not in game.available_days:
            return {
                'slots': [],
                'errors': [f"Game is not available on {weekday.title()}"],
                'warnings': validation['warnings']
            }
        
        current_time = game.opening_time
        
        while current_time < game.closing_time:
            # Calculate end time for this slot
            start_datetime = datetime.combine(target_date, current_time)
            end_datetime = start_datetime + timedelta(minutes=game.slot_duration_minutes)
            end_time = end_datetime.time()
            
            # Don't include slot if it goes beyond closing time
            if end_time > game.closing_time:
                break
            
            preview_slots.append({
                'start_time': current_time,
                'end_time': end_time,
                'duration_minutes': game.slot_duration_minutes,
                'capacity': game.capacity,
                'private_price': float(game.private_price),
                'shared_price': float(game.shared_price) if game.shared_price else None,
                'booking_type': game.booking_type
            })
            
            # Move to next slot time
            current_time = end_time
        
        return {
            'slots': preview_slots,
            'errors': [],
            'warnings': validation['warnings']
        }