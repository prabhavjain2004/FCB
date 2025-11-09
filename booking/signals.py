from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from .models import Booking, BookingHistory, GamingStation, Game
from .supabase_client import supabase_realtime
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Booking)
def track_booking_status_change(sender, instance, **kwargs):
    """Track booking status changes for audit purposes"""
    if instance.pk:  # Only for existing bookings
        try:
            old_instance = Booking.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Store the old status to create history record after save
                instance._old_status = old_instance.status
                instance._status_changed = True
            else:
                instance._status_changed = False
        except Booking.DoesNotExist:
            instance._status_changed = False
    else:
        instance._status_changed = False


@receiver(post_save, sender=Booking)
def create_booking_history(sender, instance, created, **kwargs):
    """Create booking history record when status changes"""
    if hasattr(instance, '_status_changed') and instance._status_changed:
        BookingHistory.objects.create(
            booking=instance,
            previous_status=getattr(instance, '_old_status', ''),
            new_status=instance.status,
            reason="Status changed automatically"
        )


@receiver(post_save, sender=Booking)
def auto_update_booking_status(sender, instance, created, **kwargs):
    """Automatically update booking status based on time"""
    # Skip if this is a status update to prevent recursion
    if hasattr(instance, '_skip_auto_status_update'):
        return
    
    if not created:  # Only for existing bookings
        now = timezone.now()
        
        status_changed = False
        new_status = instance.status
        
        # 1. Check for EXPIRED status (PENDING bookings with expired reservation)
        if (instance.status == 'PENDING' and 
            instance.reservation_expires_at and 
            now >= instance.reservation_expires_at and
            not instance.is_reservation_expired):
            new_status = 'EXPIRED'
            status_changed = True
        
        # Get start and end times (supports both new game_slot and old start_time)
        start_dt = instance.start_datetime
        end_dt = instance.end_datetime
        
        if start_dt and end_dt:
            # 2. Auto-start confirmed bookings
            if (instance.status == 'CONFIRMED' and 
                start_dt <= now < end_dt):
                new_status = 'IN_PROGRESS'
                status_changed = True
            
            # 3. Auto-complete in-progress bookings (check if verified)
            elif (instance.status == 'IN_PROGRESS' and 
                  now >= end_dt):
                # Only mark as COMPLETED if QR was scanned (verified)
                if instance.is_verified:
                    new_status = 'COMPLETED'
                else:
                    new_status = 'NO_SHOW'
                status_changed = True
            
            # 4. Mark as NO_SHOW if confirmed but time passed and not verified
            elif (instance.status == 'CONFIRMED' and 
                  now >= end_dt and 
                  not instance.is_verified):
                new_status = 'NO_SHOW'
                status_changed = True
        
        # Update status if changed
        if status_changed:
            # Set flag to prevent recursion
            instance._skip_auto_status_update = True
            instance.status = new_status
            if new_status == 'EXPIRED':
                instance.is_reservation_expired = True
                instance.save(update_fields=['status', 'is_reservation_expired'])
            else:
                instance.save(update_fields=['status'])
            logger.info(f"Auto-updated booking {instance.id} status to {new_status}")


@receiver(post_save, sender=Booking)
def broadcast_booking_update(sender, instance, created, **kwargs):
    """Broadcast booking updates to real-time subscribers"""
    try:
        # Prepare booking data for broadcast
        booking_data = {
            'id': str(instance.id),
            'customer_id': str(instance.customer.id),
            'customer_name': instance.customer.user.get_full_name() or instance.customer.user.username,
            'status': instance.status,
            'total_amount': float(instance.total_amount),
            'is_walk_in': instance.is_walk_in,
            'created': created,
            'timestamp': timezone.now().isoformat()
        }
        
        # Add game-specific data if available
        if instance.game:
            booking_data['game_id'] = str(instance.game.id)
            booking_data['game_name'] = instance.game.name
        
        # Add gaming station data if available (backward compatibility)
        if instance.gaming_station:
            booking_data['gaming_station_id'] = str(instance.gaming_station.id)
            booking_data['gaming_station_name'] = instance.gaming_station.name
        
        # Add time data
        start_dt = instance.start_datetime
        end_dt = instance.end_datetime
        if start_dt:
            booking_data['start_time'] = start_dt.isoformat()
        if end_dt:
            booking_data['end_time'] = end_dt.isoformat()
        
        # Broadcast the update
        success = supabase_realtime.publish_booking_update(booking_data)
        
        if success:
            logger.info(f"Broadcasted booking update for booking {instance.id}")
        else:
            logger.warning(f"Failed to broadcast booking update for booking {instance.id}")
            
    except Exception as e:
        logger.error(f"Error broadcasting booking update: {e}")


@receiver(post_delete, sender=Booking)
def broadcast_booking_deletion(sender, instance, **kwargs):
    """Broadcast booking deletion to real-time subscribers"""
    try:
        # Prepare deletion data for broadcast
        deletion_data = {
            'id': str(instance.id),
            'action': 'deleted',
            'timestamp': timezone.now().isoformat()
        }
        
        # Add gaming station ID if available
        if instance.gaming_station:
            deletion_data['gaming_station_id'] = str(instance.gaming_station.id)
        
        # Add game ID if available
        if instance.game:
            deletion_data['game_id'] = str(instance.game.id)
        
        # Broadcast the deletion
        success = supabase_realtime.publish_booking_update(deletion_data)
        
        if success:
            logger.info(f"Broadcasted booking deletion for booking {instance.id}")
        else:
            logger.warning(f"Failed to broadcast booking deletion for booking {instance.id}")
            
    except Exception as e:
        logger.error(f"Error broadcasting booking deletion: {e}")





@receiver(post_save, sender=GamingStation)
def broadcast_station_availability_update(sender, instance, created, **kwargs):
    """Broadcast gaming station availability updates"""
    try:
        # Get current booking for the station
        current_booking = instance.get_current_booking()
        
        # Prepare availability data
        availability_data = {
            'station_id': str(instance.id),
            'station_name': instance.name,
            'station_type': instance.station_type,
            'is_available': instance.is_available,
            'is_active': instance.is_active,
            'is_maintenance': instance.is_maintenance,
            'hourly_rate': float(instance.hourly_rate),
            'current_booking': {
                'id': str(current_booking.id),
                'customer_name': current_booking.customer.user.get_full_name() or current_booking.customer.user.username,
                'end_time': current_booking.end_time.isoformat()
            } if current_booking else None,
            'timestamp': timezone.now().isoformat()
        }
        
        # Broadcast the availability update
        success = supabase_realtime.publish_availability_update(str(instance.id), availability_data)
        
        if success:
            logger.info(f"Broadcasted availability update for station {instance.name}")
        else:
            logger.warning(f"Failed to broadcast availability update for station {instance.name}")
            
    except Exception as e:
        logger.error(f"Error broadcasting station availability update: {e}")