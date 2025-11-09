import json
import asyncio
import logging
from typing import Dict, List, Set, Optional, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .models import Game, GameSlot, SlotAvailability, Booking, GamingStation
from .booking_service import BookingService
from .supabase_client import supabase_realtime, conflict_resolver

logger = logging.getLogger(__name__)


class RealTimeService:
    """Service for handling real-time booking operations and capacity updates"""
    
    def __init__(self):
        self.active_connections: Set[str] = set()
        self.slot_watchers: Dict[str, List[str]] = {}  # game_slot_id -> [connection_ids]
        self.game_watchers: Dict[str, List[str]] = {}  # game_id -> [connection_ids]
        self.pending_bookings: Dict[str, Dict] = {}  # booking_key -> booking_data
        self.conflict_queue: List[Dict] = []
        
        # Initialize Supabase subscriptions
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Set up Supabase real-time subscriptions"""
        try:
            # Subscribe to booking changes
            booking_subscription = supabase_realtime.subscribe_to_booking_changes(
                self._handle_booking_change
            )
            
            # Subscribe to slot availability changes
            availability_subscription = supabase_realtime.subscribe_to_availability_changes(
                self._handle_availability_change
            )
            
            # Subscribe to game changes
            game_subscription = supabase_realtime.subscribe_to_game_changes(
                self._handle_game_change
            )
            
            if booking_subscription and availability_subscription and game_subscription:
                logger.info("Real-time subscriptions established successfully")
            else:
                logger.warning("Failed to establish some real-time subscriptions")
                
        except Exception as e:
            logger.error(f"Error setting up real-time subscriptions: {e}")
    
    def _handle_booking_change(self, payload: Dict):
        """Handle booking change events from Supabase"""
        try:
            event_type = payload.get('eventType')
            booking_data = payload.get('new', {})
            
            logger.info(f"Received booking change event: {event_type}")
            
            if event_type in ['INSERT', 'UPDATE']:
                self._process_booking_update(booking_data)
            elif event_type == 'DELETE':
                self._process_booking_deletion(payload.get('old', {}))
                
        except Exception as e:
            logger.error(f"Error handling booking change: {e}")
    
    def _handle_availability_change(self, payload: Dict):
        """Handle slot availability change events from Supabase"""
        try:
            event_type = payload.get('eventType')
            availability_data = payload.get('new', {})
            
            logger.info(f"Received availability change event: {event_type}")
            
            if event_type in ['INSERT', 'UPDATE']:
                self._process_availability_update(availability_data)
                
        except Exception as e:
            logger.error(f"Error handling availability change: {e}")
    
    def _handle_game_change(self, payload: Dict):
        """Handle game change events from Supabase"""
        try:
            event_type = payload.get('eventType')
            game_data = payload.get('new', {})
            
            logger.info(f"Received game change event: {event_type}")
            
            if event_type in ['INSERT', 'UPDATE']:
                self._process_game_update(game_data)
                
        except Exception as e:
            logger.error(f"Error handling game change: {e}")
    
    def _process_booking_update(self, booking_data: Dict):
        """Process booking update and notify relevant connections"""
        station_id = booking_data.get('gaming_station_id')
        if not station_id:
            return
        
        # Notify watchers of this station
        watchers = self.booking_watchers.get(station_id, [])
        for connection_id in watchers:
            self._notify_connection(connection_id, {
                'type': 'booking_update',
                'data': booking_data
            })
        
        # Update availability for the station
        self._update_station_availability(station_id)
    
    def _process_booking_deletion(self, booking_data: Dict):
        """Process booking deletion and notify relevant connections"""
        station_id = booking_data.get('gaming_station_id')
        if not station_id:
            return
        
        # Notify watchers of this station
        watchers = self.booking_watchers.get(station_id, [])
        for connection_id in watchers:
            self._notify_connection(connection_id, {
                'type': 'booking_deleted',
                'data': booking_data
            })
        
        # Update availability for the station
        self._update_station_availability(station_id)
    
    def _process_station_update(self, station_data: Dict):
        """Process station update and notify relevant connections"""
        station_id = station_data.get('id')
        if not station_id:
            return
        
        # Notify all connections about station availability change
        for connection_id in self.active_connections:
            self._notify_connection(connection_id, {
                'type': 'station_update',
                'data': station_data
            })
    
    def _update_station_availability(self, station_id: str):
        """Update and broadcast station availability"""
        try:
            station = GamingStation.objects.get(id=station_id)
            time_manager = TimeSlotManager(station)
            
            # Get availability for today and tomorrow
            today = timezone.now().date()
            tomorrow = today + timedelta(days=1)
            
            availability_data = {
                'station_id': station_id,
                'today_slots': time_manager.get_available_slots(today),
                'tomorrow_slots': time_manager.get_available_slots(tomorrow),
                'is_available': station.is_available,
                'current_booking': None
            }
            
            # Get current booking if any
            current_booking = station.get_current_booking()
            if current_booking:
                availability_data['current_booking'] = {
                    'id': str(current_booking.id),
                    'customer_name': current_booking.customer.user.get_full_name(),
                    'end_time': current_booking.end_time.isoformat()
                }
            
            # Broadcast availability update
            supabase_realtime.publish_availability_update(station_id, availability_data)
            
        except GamingStation.DoesNotExist:
            logger.warning(f"Station {station_id} not found for availability update")
        except Exception as e:
            logger.error(f"Error updating station availability: {e}")
    
    def _notify_connection(self, connection_id: str, message: Dict):
        """Notify a specific connection (placeholder for WebSocket implementation)"""
        # This would be implemented with actual WebSocket connections
        logger.info(f"Notifying connection {connection_id}: {message['type']}")
    
    def register_connection(self, connection_id: str):
        """Register a new real-time connection"""
        self.active_connections.add(connection_id)
        logger.info(f"Registered connection: {connection_id}")
    
    def unregister_connection(self, connection_id: str):
        """Unregister a real-time connection"""
        self.active_connections.discard(connection_id)
        
        # Remove from all station watchers
        for station_id, watchers in self.booking_watchers.items():
            if connection_id in watchers:
                watchers.remove(connection_id)
        
        logger.info(f"Unregistered connection: {connection_id}")
    
    def watch_station(self, connection_id: str, station_id: str):
        """Register connection to watch a specific station"""
        if station_id not in self.booking_watchers:
            self.booking_watchers[station_id] = []
        
        if connection_id not in self.booking_watchers[station_id]:
            self.booking_watchers[station_id].append(connection_id)
        
        logger.info(f"Connection {connection_id} watching station {station_id}")
    
    def unwatch_station(self, connection_id: str, station_id: str):
        """Unregister connection from watching a specific station"""
        if station_id in self.booking_watchers:
            watchers = self.booking_watchers[station_id]
            if connection_id in watchers:
                watchers.remove(connection_id)
        
        logger.info(f"Connection {connection_id} stopped watching station {station_id}")
    
    def handle_booking_attempt(self, booking_request: Dict) -> Dict:
        """
        Handle real-time booking attempt with conflict resolution
        
        Args:
            booking_request: Booking request data
        
        Returns:
            Booking result with success/failure status
        """
        try:
            station_id = booking_request.get('station_id')
            start_time_str = booking_request.get('start_time')
            end_time_str = booking_request.get('end_time')
            customer_id = booking_request.get('customer_id')
            
            # Parse times
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            
            # Get station and customer
            station = GamingStation.objects.get(id=station_id)
            from authentication.models import Customer
            customer = Customer.objects.get(id=customer_id)
            
            # Check for simultaneous booking attempts
            booking_key = f"{station_id}_{start_time_str}_{end_time_str}"
            
            if booking_key in self.pending_bookings:
                # Add to conflict queue
                self.conflict_queue.append({
                    'booking_request': booking_request,
                    'timestamp': timezone.now().timestamp()
                })
                
                # Process conflict queue
                return self._process_conflict_queue(booking_key)
            
            # Mark as pending
            self.pending_bookings[booking_key] = booking_request
            
            try:
                # Attempt to create booking
                booking = BookingManager.create_booking(
                    customer=customer,
                    station=station,
                    start_time=start_time,
                    end_time=end_time,
                    notes=booking_request.get('notes', '')
                )
                
                # Success - remove from pending
                del self.pending_bookings[booking_key]
                
                return {
                    'success': True,
                    'booking_id': str(booking.id),
                    'message': 'Booking created successfully',
                    'booking_data': {
                        'id': str(booking.id),
                        'status': booking.status,
                        'total_amount': float(booking.total_amount)
                    }
                }
                
            except Exception as e:
                # Failed - remove from pending
                del self.pending_bookings[booking_key]
                
                return {
                    'success': False,
                    'error': str(e),
                    'message': 'Failed to create booking'
                }
                
        except Exception as e:
            logger.error(f"Error handling booking attempt: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Internal error processing booking'
            }
    
    def _process_conflict_queue(self, booking_key: str) -> Dict:
        """Process conflicting booking requests"""
        # Get all requests for this booking key
        conflicting_requests = [
            req for req in self.conflict_queue 
            if f"{req['booking_request']['station_id']}_{req['booking_request']['start_time']}_{req['booking_request']['end_time']}" == booking_key
        ]
        
        # Add the pending booking
        if booking_key in self.pending_bookings:
            conflicting_requests.append({
                'booking_request': self.pending_bookings[booking_key],
                'timestamp': timezone.now().timestamp()
            })
        
        # Resolve conflicts
        resolution = conflict_resolver.resolve_simultaneous_bookings([
            req['booking_request'] for req in conflicting_requests
        ])
        
        # Clean up
        self.conflict_queue = [
            req for req in self.conflict_queue 
            if f"{req['booking_request']['station_id']}_{req['booking_request']['start_time']}_{req['booking_request']['end_time']}" != booking_key
        ]
        
        if booking_key in self.pending_bookings:
            del self.pending_bookings[booking_key]
        
        return {
            'success': False,
            'conflict': True,
            'message': 'Booking conflict detected',
            'resolution': resolution
        }
    
    def get_real_time_availability(self, date_str: Optional[str] = None) -> Dict:
        """
        Get real-time availability for all stations
        
        Args:
            date_str: Date string (YYYY-MM-DD) or None for today
        
        Returns:
            Real-time availability data
        """
        try:
            if date_str:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                target_date = timezone.now().date()
            
            availability_data = {}
            stations = GamingStation.objects.filter(is_active=True)
            
            for station in stations:
                time_manager = TimeSlotManager(station)
                available_slots = time_manager.get_available_slots(target_date)
                current_booking = station.get_current_booking()
                
                availability_data[str(station.id)] = {
                    'station': {
                        'id': str(station.id),
                        'name': station.name,
                        'type': station.station_type,
                        'hourly_rate': float(station.hourly_rate),
                        'is_available': station.is_available
                    },
                    'available_slots': available_slots,
                    'current_booking': {
                        'id': str(current_booking.id),
                        'customer_name': current_booking.customer.user.get_full_name(),
                        'end_time': current_booking.end_time.isoformat()
                    } if current_booking else None,
                    'last_updated': timezone.now().isoformat()
                }
            
            return {
                'date': target_date.isoformat(),
                'stations': availability_data,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time availability: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


    @staticmethod
    def broadcast_availability_update(game_slot_id):
        """
        Static method to broadcast availability changes to all connected clients
        
        Args:
            game_slot_id: ID of the GameSlot that had availability changes
        """
        try:
            game_slot = GameSlot.objects.get(id=game_slot_id)
            availability = SlotAvailability.objects.get(game_slot=game_slot)
            
            # Prepare availability data
            availability_data = {
                'game_slot_id': str(game_slot_id),
                'game_id': str(game_slot.game.id),
                'date': game_slot.date.isoformat(),
                'start_time': game_slot.start_time.isoformat(),
                'end_time': game_slot.end_time.isoformat(),
                'total_capacity': availability.total_capacity,
                'booked_spots': availability.booked_spots,
                'available_spots': availability.available_spots,
                'can_book_private': availability.can_book_private,
                'can_book_shared': availability.can_book_shared,
                'is_private_booked': availability.is_private_booked,
                'booking_options': BookingService.get_booking_options(game_slot),
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to Supabase real-time channel
            supabase_realtime.publish_availability_update(game_slot_id, availability_data)
            
            logger.info(f"Broadcasted availability update for slot {game_slot_id}")
            
        except (GameSlot.DoesNotExist, SlotAvailability.DoesNotExist) as e:
            logger.warning(f"Could not broadcast availability update for slot {game_slot_id}: {e}")
        except Exception as e:
            logger.error(f"Error broadcasting availability update: {e}")
    
    @staticmethod
    def broadcast_game_update(game_id):
        """
        Static method to broadcast game changes to all connected clients
        
        Args:
            game_id: ID of the Game that was updated
        """
        try:
            game = Game.objects.get(id=game_id)
            
            # Prepare game data
            game_data = {
                'game_id': str(game_id),
                'name': game.name,
                'description': game.description,
                'capacity': game.capacity,
                'booking_type': game.booking_type,
                'private_price': float(game.private_price),
                'shared_price': float(game.shared_price) if game.shared_price else None,
                'is_active': game.is_active,
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to Supabase real-time channel
            supabase_realtime.publish_game_update(game_id, game_data)
            
            logger.info(f"Broadcasted game update for game {game_id}")
            
        except Game.DoesNotExist as e:
            logger.warning(f"Could not broadcast game update for game {game_id}: {e}")
        except Exception as e:
            logger.error(f"Error broadcasting game update: {e}")


# Global service instance
realtime_service = RealTimeService()