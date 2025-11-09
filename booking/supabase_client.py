import os
import json
import logging
from typing import Dict, List, Optional, Callable
from django.conf import settings
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)


class SupabaseRealTimeClient:
    """
    Supabase real-time client for gaming cafe booking system
    
    Note: This implementation provides the foundation for real-time features.
    Full real-time subscriptions require WebSocket implementation or async client.
    Currently focuses on data synchronization and conflict resolution.
    """
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.subscriptions: Dict[str, any] = {}
        self.event_log: List[Dict] = []  # Store events for conflict resolution
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client with configuration"""
        try:
            supabase_url = getattr(settings, 'SUPABASE_URL', '')
            supabase_key = getattr(settings, 'SUPABASE_KEY', '')
            
            if not supabase_url or not supabase_key:
                logger.info("Supabase credentials not configured. Using local conflict resolution.")
                return
            
            # Create client with the new API (v2.23.3+)
            self.client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if Supabase client is connected"""
        return self.client is not None
    
    def subscribe_to_booking_changes(self, callback: Callable[[Dict], None]) -> Optional[str]:
        """
        Subscribe to real-time booking changes
        
        Note: This is a placeholder for future WebSocket implementation.
        Currently logs the subscription request.
        
        Args:
            callback: Function to call when booking changes occur
        
        Returns:
            Subscription ID or None if failed
        """
        subscription_id = f"booking_changes_{datetime.now().timestamp()}"
        
        # Store callback for future use
        self.subscriptions[subscription_id] = {
            'type': 'booking_changes',
            'callback': callback,
            'created_at': datetime.now()
        }
        
        logger.info(f"Registered booking changes subscription: {subscription_id}")
        logger.info("Note: Full real-time subscriptions will be implemented with WebSocket support")
        
        return subscription_id
    
    def subscribe_to_availability_changes(self, callback: Callable[[Dict], None]) -> Optional[str]:
        """
        Subscribe to real-time slot availability changes
        
        Note: This is a placeholder for future WebSocket implementation.
        Currently logs the subscription request.
        
        Args:
            callback: Function to call when availability changes occur
        
        Returns:
            Subscription ID or None if failed
        """
        subscription_id = f"availability_changes_{datetime.now().timestamp()}"
        
        # Store callback for future use
        self.subscriptions[subscription_id] = {
            'type': 'availability_changes',
            'callback': callback,
            'created_at': datetime.now()
        }
        
        logger.info(f"Registered availability changes subscription: {subscription_id}")
        logger.info("Note: Full real-time subscriptions will be implemented with WebSocket support")
        
        return subscription_id

    def subscribe_to_game_changes(self, callback: Callable[[Dict], None]) -> Optional[str]:
        """
        Subscribe to real-time game changes
        
        Note: This is a placeholder for future WebSocket implementation.
        Currently logs the subscription request.
        
        Args:
            callback: Function to call when game changes occur
        
        Returns:
            Subscription ID or None if failed
        """
        subscription_id = f"game_changes_{datetime.now().timestamp()}"
        
        # Store callback for future use
        self.subscriptions[subscription_id] = {
            'type': 'game_changes',
            'callback': callback,
            'created_at': datetime.now()
        }
        
        logger.info(f"Registered game changes subscription: {subscription_id}")
        logger.info("Note: Full real-time subscriptions will be implemented with WebSocket support")
        
        return subscription_id

    def subscribe_to_station_changes(self, callback: Callable[[Dict], None]) -> Optional[str]:
        """
        Subscribe to real-time gaming station changes
        
        Note: This is a placeholder for future WebSocket implementation.
        Currently logs the subscription request.
        
        Args:
            callback: Function to call when station changes occur
        
        Returns:
            Subscription ID or None if failed
        """
        subscription_id = f"station_changes_{datetime.now().timestamp()}"
        
        # Store callback for future use
        self.subscriptions[subscription_id] = {
            'type': 'station_changes',
            'callback': callback,
            'created_at': datetime.now()
        }
        
        logger.info(f"Registered station changes subscription: {subscription_id}")
        logger.info("Note: Full real-time subscriptions will be implemented with WebSocket support")
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from real-time updates
        
        Args:
            subscription_id: ID of the subscription to remove
        
        Returns:
            True if successful, False otherwise
        """
        if subscription_id not in self.subscriptions:
            logger.warning(f"Subscription ID {subscription_id} not found")
            return False
        
        try:
            del self.subscriptions[subscription_id]
            logger.info(f"Unsubscribed from {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {subscription_id}: {e}")
            return False
    
    def unsubscribe_all(self):
        """Unsubscribe from all real-time updates"""
        subscription_ids = list(self.subscriptions.keys())
        for subscription_id in subscription_ids:
            self.unsubscribe(subscription_id)
    
    def publish_booking_update(self, booking_data: Dict) -> bool:
        """
        Publish booking update to real-time channel
        
        Args:
            booking_data: Booking data to broadcast
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Log the event for conflict resolution
            event = {
                'type': 'booking_update',
                'data': booking_data,
                'timestamp': datetime.now().isoformat()
            }
            self.event_log.append(event)
            
            # Keep only recent events (last 100)
            if len(self.event_log) > 100:
                self.event_log = self.event_log[-100:]
            
            # Notify local subscribers
            self._notify_local_subscribers('booking_changes', event)
            
            logger.info(f"Logged booking update for booking {booking_data.get('id', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish booking update: {e}")
            return False
    
    def publish_availability_update(self, game_slot_id: str, availability_data: Dict) -> bool:
        """
        Publish slot availability update to real-time channel
        
        Args:
            game_slot_id: Game slot ID
            availability_data: Availability data to broadcast
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Log the event for conflict resolution
            event = {
                'type': 'availability_update',
                'game_slot_id': game_slot_id,
                'data': availability_data,
                'timestamp': datetime.now().isoformat()
            }
            self.event_log.append(event)
            
            # Keep only recent events (last 100)
            if len(self.event_log) > 100:
                self.event_log = self.event_log[-100:]
            
            # Notify local subscribers
            self._notify_local_subscribers('availability_changes', event)
            
            logger.info(f"Logged availability update for slot {game_slot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish availability update: {e}")
            return False
    
    def publish_game_update(self, game_id: str, game_data: Dict) -> bool:
        """
        Publish game update to real-time channel
        
        Args:
            game_id: Game ID
            game_data: Game data to broadcast
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Log the event for conflict resolution
            event = {
                'type': 'game_update',
                'game_id': game_id,
                'data': game_data,
                'timestamp': datetime.now().isoformat()
            }
            self.event_log.append(event)
            
            # Keep only recent events (last 100)
            if len(self.event_log) > 100:
                self.event_log = self.event_log[-100:]
            
            # Notify local subscribers
            self._notify_local_subscribers('game_changes', event)
            
            logger.info(f"Logged game update for game {game_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish game update: {e}")
            return False

    def _notify_local_subscribers(self, subscription_type: str, event: Dict):
        """Notify local subscribers of events"""
        for subscription_id, subscription in self.subscriptions.items():
            if subscription['type'] == subscription_type:
                try:
                    subscription['callback'](event)
                except Exception as e:
                    logger.error(f"Error notifying subscriber {subscription_id}: {e}")
    
    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Get recent events for conflict resolution
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return
        
        Returns:
            List of recent events
        """
        events = self.event_log
        
        if event_type:
            events = [e for e in events if e['type'] == event_type]
        
        return events[-limit:] if limit else events


class BookingConflictResolver:
    """Handle booking conflicts in real-time scenarios"""
    
    def __init__(self, supabase_client: SupabaseRealTimeClient):
        self.supabase_client = supabase_client
    
    def resolve_simultaneous_bookings(self, booking_requests: List[Dict]) -> Dict:
        """
        Resolve conflicts when multiple users try to book the same slot
        
        Args:
            booking_requests: List of simultaneous booking requests
        
        Returns:
            Resolution result with accepted and rejected bookings
        """
        if not booking_requests:
            return {'accepted': [], 'rejected': []}
        
        # Sort by timestamp (first come, first served)
        sorted_requests = sorted(
            booking_requests, 
            key=lambda x: x.get('timestamp', datetime.now().timestamp())
        )
        
        accepted = []
        rejected = []
        occupied_slots = set()
        
        for request in sorted_requests:
            station_id = request.get('station_id')
            start_time = request.get('start_time')
            end_time = request.get('end_time')
            
            # Create slot identifier
            slot_key = f"{station_id}_{start_time}_{end_time}"
            
            if slot_key not in occupied_slots:
                # Accept the booking
                accepted.append(request)
                occupied_slots.add(slot_key)
                
                # Notify about successful booking
                self.supabase_client.publish_booking_update({
                    'status': 'accepted',
                    'booking_id': request.get('booking_id'),
                    'message': 'Booking confirmed'
                })
            else:
                # Reject the booking
                rejected.append(request)
                
                # Notify about rejected booking
                self.supabase_client.publish_booking_update({
                    'status': 'rejected',
                    'booking_id': request.get('booking_id'),
                    'message': 'Time slot no longer available',
                    'reason': 'conflict'
                })
        
        return {
            'accepted': accepted,
            'rejected': rejected,
            'total_requests': len(booking_requests)
        }
    
    def handle_booking_conflict(self, existing_booking: Dict, new_booking_request: Dict) -> Dict:
        """
        Handle conflict between existing booking and new request
        
        Args:
            existing_booking: Current booking data
            new_booking_request: New booking request data
        
        Returns:
            Conflict resolution result
        """
        # Check if times actually overlap
        existing_start = datetime.fromisoformat(existing_booking['start_time'])
        existing_end = datetime.fromisoformat(existing_booking['end_time'])
        new_start = datetime.fromisoformat(new_booking_request['start_time'])
        new_end = datetime.fromisoformat(new_booking_request['end_time'])
        
        # No actual conflict
        if new_end <= existing_start or new_start >= existing_end:
            return {
                'conflict': False,
                'action': 'accept',
                'message': 'No time conflict detected'
            }
        
        # Conflict exists - reject new booking
        return {
            'conflict': True,
            'action': 'reject',
            'message': 'Time slot conflicts with existing booking',
            'existing_booking_id': existing_booking.get('id'),
            'conflicting_period': {
                'start': max(existing_start, new_start).isoformat(),
                'end': min(existing_end, new_end).isoformat()
            }
        }


# Global instance
supabase_realtime = SupabaseRealTimeClient()
conflict_resolver = BookingConflictResolver(supabase_realtime)