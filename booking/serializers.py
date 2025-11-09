"""
API Serializers for Booking System
Provides efficient JSON serialization for REST API endpoints
"""
from rest_framework import serializers
from .models import Game, GameSlot, SlotAvailability, Booking
from django.utils import timezone


class GameSerializer(serializers.ModelSerializer):
    """Serializer for Game model - basic info for fast loading"""
    
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Game
        fields = [
            'id', 'name', 'description', 'capacity', 
            'slot_duration_minutes', 'booking_type',
            'private_price', 'shared_price', 'shared_price_per_person',
            'image_url', 'is_active'
        ]
    
    def get_image_url(self, obj):
        """Get absolute URL for game image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class SlotAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for slot availability information with reservation tracking"""
    
    available_spots = serializers.SerializerMethodField()  # Changed to use truly_available_spots
    can_book_private = serializers.BooleanField(read_only=True)
    can_book_shared = serializers.BooleanField(read_only=True)
    reserved_spots = serializers.SerializerMethodField()
    truly_available_spots = serializers.SerializerMethodField()
    pending_reservations = serializers.SerializerMethodField()
    
    class Meta:
        model = SlotAvailability
        fields = [
            'total_capacity', 'booked_spots', 'is_private_booked',
            'available_spots', 'can_book_private', 'can_book_shared',
            'reserved_spots', 'truly_available_spots', 'pending_reservations'
        ]
    
    def get_available_spots(self, obj):
        """Get truly available spots (accounting for reserved spots)"""
        return obj.get_truly_available_spots()
    
    def get_reserved_spots(self, obj):
        """Get count of spots reserved by pending payments"""
        return obj.get_reserved_spots_count()
    
    def get_truly_available_spots(self, obj):
        """Get spots that are neither booked nor reserved"""
        return obj.get_truly_available_spots()
    
    def get_pending_reservations(self, obj):
        """Get list of pending reservations with expiry times"""
        pending = obj.get_pending_reservations()
        return [{
            'booking_id': str(booking.id),
            'spots': booking.spots_booked,
            'booking_type': booking.booking_type,
            'expires_at': booking.reservation_expires_at.isoformat() if booking.reservation_expires_at else None,
            'time_remaining_seconds': booking.time_remaining_seconds
        } for booking in pending]


class BookingOptionSerializer(serializers.Serializer):
    """Serializer for booking options (private/shared)"""
    
    type = serializers.CharField()
    price = serializers.FloatField()
    capacity = serializers.IntegerField(required=False)
    spots_included = serializers.IntegerField(required=False)
    description = serializers.CharField()
    available = serializers.BooleanField()
    icon = serializers.CharField()
    benefits = serializers.ListField(child=serializers.CharField())
    restriction_reason = serializers.CharField(required=False)
    disabled_message = serializers.CharField(required=False)
    available_spots = serializers.IntegerField(required=False)
    max_spots_per_booking = serializers.IntegerField(required=False)
    price_per_spot = serializers.FloatField(required=False)


class GameSlotSerializer(serializers.ModelSerializer):
    """Serializer for GameSlot with availability and booking options"""
    
    availability = SlotAvailabilitySerializer(read_only=True)
    booking_options = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    time_display = serializers.SerializerMethodField()
    
    class Meta:
        model = GameSlot
        fields = [
            'id', 'date', 'start_time', 'end_time', 
            'is_active', 'availability', 'booking_options',
            'is_past', 'time_display'
        ]
    
    def get_booking_options(self, obj):
        """Get booking options for this slot (optimized - no expiration here)"""
        from .booking_service import BookingService
        
        try:
            # Use optimized version that skips expiration (already done in view)
            options = BookingService.get_booking_options_fast(obj)
            return BookingOptionSerializer(options, many=True).data
        except Exception as e:
            return []
    
    def get_is_past(self, obj):
        """Check if slot is in the past"""
        now = timezone.now()
        slot_datetime = timezone.make_aware(
            timezone.datetime.combine(obj.date, obj.start_time)
        )
        return slot_datetime < now
    
    def get_time_display(self, obj):
        """Format time range for display"""
        return f"{obj.start_time.strftime('%I:%M %p')} - {obj.end_time.strftime('%I:%M %p')}"


class SlotsByDateSerializer(serializers.Serializer):
    """Serializer for slots grouped by date"""
    
    date = serializers.DateField()
    slots = GameSlotSerializer(many=True)
    total_slots = serializers.IntegerField()
    available_slots = serializers.IntegerField()
