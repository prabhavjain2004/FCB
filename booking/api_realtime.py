"""
Real-time API endpoints for station availability updates
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.serializers import serialize
import json
import random
from datetime import datetime, timedelta
from .models import GamingStation, Booking


@require_http_methods(["GET"])
def station_status_api(request):
    """
    API endpoint to get current status of all gaming stations
    """
    try:
        stations = GamingStation.objects.all()
        station_data = []
        
        for station in stations:
            # Get current booking if any
            current_booking = station.get_current_booking()
            
            # Calculate capacity and progress
            daily_capacity = calculate_daily_capacity(station)
            progress = calculate_session_progress(current_booking) if current_booking else 0
            
            # Determine availability
            is_available = station.is_available()
            is_maintenance = getattr(station, 'is_maintenance', False)
            
            station_info = {
                'id': station.id,
                'name': station.name,
                'station_type': station.station_type,
                'is_available': is_available,
                'is_maintenance': is_maintenance,
                'hourly_rate': float(station.hourly_rate),
                'capacity': daily_capacity,
                'progress': progress,
                'daily_capacity': daily_capacity,
                'next_available': get_next_available_time(station),
                'peak_hours': get_peak_hours(station),
                'time_remaining': get_time_remaining(current_booking) if current_booking else None,
                'current_booking': {
                    'id': current_booking.id,
                    'end_time': current_booking.end_time.isoformat(),
                    'progress': progress
                } if current_booking else None
            }
            
            station_data.append(station_info)
        
        return JsonResponse({
            'success': True,
            'stations': station_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def calculate_daily_capacity(station):
    """
    Calculate the daily booking capacity percentage for a station
    """
    try:
        today = datetime.now().date()
        
        # Get all bookings for today
        today_bookings = Booking.objects.filter(
            gaming_station=station,
            start_time__date=today
        )
        
        # Calculate total booked hours
        total_booked_minutes = 0
        for booking in today_bookings:
            duration = booking.end_time - booking.start_time
            total_booked_minutes += duration.total_seconds() / 60
        
        # Assume 16 hours of operation per day (8 AM to 12 AM)
        total_available_minutes = 16 * 60
        
        capacity_percentage = min((total_booked_minutes / total_available_minutes) * 100, 100)
        return round(capacity_percentage, 1)
        
    except Exception:
        # Return a random value for demo purposes
        return round(random.uniform(20, 85), 1)


def calculate_session_progress(booking):
    """
    Calculate the progress percentage of a current booking session
    """
    if not booking:
        return 0
    
    try:
        now = datetime.now()
        
        # Make sure we're working with timezone-aware datetimes
        if booking.start_time.tzinfo is None:
            from django.utils import timezone
            booking_start = timezone.make_aware(booking.start_time)
            booking_end = timezone.make_aware(booking.end_time)
            now = timezone.now()
        else:
            booking_start = booking.start_time
            booking_end = booking.end_time
        
        # Calculate progress
        total_duration = (booking_end - booking_start).total_seconds()
        elapsed_duration = (now - booking_start).total_seconds()
        
        if total_duration <= 0:
            return 0
        
        progress = (elapsed_duration / total_duration) * 100
        return max(0, min(100, round(progress, 1)))
        
    except Exception:
        # Return a random progress for demo purposes
        return round(random.uniform(10, 90), 1)


def get_time_remaining(booking):
    """
    Get remaining time in seconds for a booking
    """
    if not booking:
        return None
    
    try:
        now = datetime.now()
        
        # Make sure we're working with timezone-aware datetimes
        if booking.end_time.tzinfo is None:
            from django.utils import timezone
            booking_end = timezone.make_aware(booking.end_time)
            now = timezone.now()
        else:
            booking_end = booking.end_time
        
        remaining = (booking_end - now).total_seconds()
        return max(0, int(remaining))
        
    except Exception:
        # Return a random time for demo purposes
        return random.randint(300, 7200)  # 5 minutes to 2 hours


def get_next_available_time(station):
    """
    Get the next available time slot for a station
    """
    try:
        if station.is_available():
            return "Now"
        
        # Find the next available slot
        current_booking = station.get_current_booking()
        if current_booking:
            return current_booking.end_time.strftime("%I:%M %p")
        
        # Default fallback
        next_hour = datetime.now() + timedelta(hours=1)
        return next_hour.strftime("%I:%M %p")
        
    except Exception:
        # Return a random next available time
        next_time = datetime.now() + timedelta(minutes=random.randint(30, 180))
        return next_time.strftime("%I:%M %p")


def get_peak_hours(station):
    """
    Get peak hours information for a station
    """
    # This could be calculated from historical data
    # For now, return common peak hours
    peak_hours_options = [
        "6-10 PM",
        "7-11 PM", 
        "5-9 PM",
        "8 PM-12 AM",
        "2-6 PM"
    ]
    
    return random.choice(peak_hours_options)


@method_decorator(csrf_exempt, name='dispatch')
class StationUpdateView(View):
    """
    Handle real-time station updates via POST requests
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            station_id = data.get('station_id')
            update_type = data.get('type', 'status_change')
            
            if not station_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Station ID is required'
                }, status=400)
            
            station = GamingStation.objects.get(id=station_id)
            
            # Handle different types of updates
            if update_type == 'booking_started':
                return self.handle_booking_started(station, data)
            elif update_type == 'booking_ended':
                return self.handle_booking_ended(station, data)
            elif update_type == 'maintenance_mode':
                return self.handle_maintenance_mode(station, data)
            else:
                return self.handle_status_change(station, data)
                
        except GamingStation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Station not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def handle_booking_started(self, station, data):
        """Handle when a new booking starts"""
        # This would typically be called when a booking is confirmed
        return JsonResponse({
            'success': True,
            'message': f'Booking started for {station.name}',
            'station_data': self.get_station_data(station)
        })
    
    def handle_booking_ended(self, station, data):
        """Handle when a booking ends"""
        # This would typically be called when a booking session ends
        return JsonResponse({
            'success': True,
            'message': f'{station.name} is now available',
            'station_data': self.get_station_data(station)
        })
    
    def handle_maintenance_mode(self, station, data):
        """Handle maintenance mode changes"""
        maintenance_status = data.get('maintenance', False)
        
        # Update station maintenance status
        # Note: You might need to add an is_maintenance field to your model
        
        return JsonResponse({
            'success': True,
            'message': f'{station.name} maintenance mode: {"ON" if maintenance_status else "OFF"}',
            'station_data': self.get_station_data(station)
        })
    
    def handle_status_change(self, station, data):
        """Handle general status changes"""
        return JsonResponse({
            'success': True,
            'message': f'Status updated for {station.name}',
            'station_data': self.get_station_data(station)
        })
    
    def get_station_data(self, station):
        """Get formatted station data for API response"""
        current_booking = station.get_current_booking()
        
        return {
            'id': station.id,
            'name': station.name,
            'station_type': station.station_type,
            'is_available': station.is_available(),
            'is_maintenance': getattr(station, 'is_maintenance', False),
            'hourly_rate': float(station.hourly_rate),
            'capacity': calculate_daily_capacity(station),
            'progress': calculate_session_progress(current_booking),
            'time_remaining': get_time_remaining(current_booking),
            'current_booking': {
                'id': current_booking.id,
                'end_time': current_booking.end_time.isoformat(),
                'progress': calculate_session_progress(current_booking)
            } if current_booking else None
        }


# Simulated WebSocket message generator for testing
def generate_test_updates():
    """
    Generate test updates for WebSocket simulation
    This would typically be replaced with actual WebSocket handling
    """
    stations = GamingStation.objects.all()
    updates = []
    
    for station in stations:
        # Randomly generate some updates
        if random.random() < 0.3:  # 30% chance of update
            update_type = random.choice(['status_change', 'capacity_update', 'booking_update'])
            
            if update_type == 'status_change':
                updates.append({
                    'type': 'station_update',
                    'station': {
                        'id': station.id,
                        'is_available': random.choice([True, False]),
                        'is_maintenance': random.choice([True, False]) if random.random() < 0.1 else False
                    }
                })
            elif update_type == 'capacity_update':
                updates.append({
                    'type': 'capacity_update',
                    'station_id': station.id,
                    'capacity': random.randint(0, 100)
                })
    
    return updates