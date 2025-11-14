from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone
from authentication.models import Customer
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, time, date


class Game(models.Model):
    """Game model for bookable gaming resources (replaces GamingStation)"""
    
    BOOKING_TYPES = [
        ('SINGLE', 'Single Booking (Private Only)'),
        ('HYBRID', 'Hybrid Booking (Private + Shared)'),
    ]
    
    WEEKDAYS = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text="Game name (e.g., '8-Ball Pool', 'Table Tennis', 'PS4 Console 1')")
    description = models.TextField(help_text="Detailed description of the game/activity")
    
    # Capacity and Booking Type
    capacity = models.PositiveIntegerField(help_text="Maximum number of players (1 for PC, 4 for pool table)")
    booking_type = models.CharField(max_length=10, choices=BOOKING_TYPES, help_text="Single (private only) or Hybrid (private + shared)")
    
    # Schedule Settings
    opening_time = models.TimeField(help_text="Daily opening time (e.g., 11:00 AM)")
    closing_time = models.TimeField(help_text="Daily closing time (e.g., 11:00 PM)")
    slot_duration_minutes = models.PositiveIntegerField(default=60, help_text="Duration of each slot in minutes")
    available_days = models.JSONField(default=list, help_text="List of available weekdays ['monday', 'tuesday', ...]")
    
    # Pricing
    private_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price for private booking (full capacity)"
    )
    shared_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank=True,
        help_text="Price per spot for shared booking (only for hybrid games)"
    )
    
    # Status and Media
    is_active = models.BooleanField(default=True, help_text="Whether the game is available for booking")
    image = models.ImageField(upload_to='games/', blank=True, null=True, help_text="Game photo")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Game"
        verbose_name_plural = "Games"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_booking_type_display()})"
    
    def clean(self):
        """Validate game data"""
        from django.core.exceptions import ValidationError
        
        # Hybrid games must have shared_price
        if self.booking_type == 'HYBRID' and not self.shared_price:
            raise ValidationError("Hybrid games must have a shared price")
        
        # Single games don't need shared_price
        if self.booking_type == 'SINGLE':
            self.shared_price = None
        
        # Validate time range (allow 00:00 midnight as valid closing time)
        if self.closing_time <= self.opening_time and self.closing_time != time(0, 0):
            raise ValidationError("Closing time must be after opening time (use 00:00 for midnight)")
    
    def save(self, *args, **kwargs):
        """Override save to generate slots after game creation/update"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generate slots for the next 7 days after saving (reduced from 30 for performance)
        if is_new or 'update_slots' in kwargs:
            self.generate_slots(days_ahead=7)
    
    def generate_slots(self, days_ahead=30):
        """Generate time slots for this game based on schedule settings"""
        from .slot_generator import SlotGenerator
        
        start_date = date.today()
        end_date = start_date + timedelta(days=days_ahead)
        
        SlotGenerator.generate_slots_for_game(self, start_date, end_date)


class GameSlot(models.Model):
    """Time slots for games (auto-generated + custom)"""
    
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_custom = models.BooleanField(default=False, help_text="True for manually added slots")
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['game', 'date', 'start_time']
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['game', 'date', 'is_active'], name='gameslot_game_date_active_idx'),
            models.Index(fields=['date', 'start_time'], name='gameslot_date_time_idx'),
            models.Index(fields=['is_active', 'date'], name='gameslot_active_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.game.name} - {self.date} {self.start_time}-{self.end_time}"
    
    @property
    def start_datetime(self):
        """Get full datetime for slot start (timezone-aware)"""
        from django.utils import timezone
        naive_dt = datetime.combine(self.date, self.start_time)
        return timezone.make_aware(naive_dt, timezone=timezone.get_current_timezone())
    
    @property
    def end_datetime(self):
        """Get full datetime for slot end (timezone-aware)"""
        from django.utils import timezone
        naive_dt = datetime.combine(self.date, self.end_time)
        return timezone.make_aware(naive_dt, timezone=timezone.get_current_timezone())


class SlotAvailability(models.Model):
    """Real-time availability tracking for each slot"""
    
    game_slot = models.OneToOneField(GameSlot, on_delete=models.CASCADE, related_name='availability')
    total_capacity = models.PositiveIntegerField()
    booked_spots = models.PositiveIntegerField(default=0)
    is_private_booked = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Slot Availability"
        verbose_name_plural = "Slot Availabilities"
        indexes = [
            models.Index(fields=['game_slot'], name='slotavail_gameslot_idx'),
        ]
    
    def __str__(self):
        return f"{self.game_slot} - {self.available_spots}/{self.total_capacity} available"
    
    def get_pending_reservations(self):
        """Get active pending reservations for this slot"""
        from django.utils import timezone
        
        # Get all PENDING bookings that haven't expired
        pending_bookings = self.game_slot.bookings.filter(
            status='PENDING',
            reservation_expires_at__gt=timezone.now()
        )
        
        return pending_bookings
    
    def get_reserved_spots_count(self):
        """Get count of spots currently reserved by pending payments (uses prefetched data)"""
        from django.utils import timezone
        
        # Use prefetched bookings if available (much faster)
        try:
            bookings = self.game_slot.bookings.all()
            # Filter in Python to use prefetched data
            reserved = sum(
                b.spots_booked for b in bookings 
                if b.status == 'PENDING' and b.reservation_expires_at > timezone.now()
            )
            return reserved
        except AttributeError:
            # Fallback to query if not prefetched
            pending_bookings = self.get_pending_reservations()
            return sum(booking.spots_booked for booking in pending_bookings)
    
    def get_truly_available_spots(self):
        """Get spots that are neither booked nor reserved"""
        reserved = self.get_reserved_spots_count()
        return max(0, self.available_spots - reserved)
    
    @property
    def available_spots(self):
        """Get number of available spots"""
        return self.total_capacity - self.booked_spots if not self.is_private_booked else 0
    
    @property
    def can_book_private(self):
        """Check if private booking is available"""
        return self.booked_spots == 0
    
    @property
    def can_book_shared(self):
        """Check if shared booking is available"""
        return not self.is_private_booked and self.available_spots > 0
    
    def save(self, *args, **kwargs):
        """Set total capacity from game on creation"""
        if not self.pk:
            self.total_capacity = self.game_slot.game.capacity
        super().save(*args, **kwargs)


# Keep GamingStation for backward compatibility (will be removed after migration)
class GamingStation(models.Model):
    """DEPRECATED: Use Game model instead. Kept for backward compatibility during migration."""
    
    STATION_TYPES = [
        ('PC', 'Gaming PC'),
        ('PS5', 'PlayStation 5'),
        ('XBOX', 'Xbox Series X'),
        ('SWITCH', 'Nintendo Switch'),
        ('VR', 'VR Gaming Setup'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, help_text="Unique name for the gaming station")
    station_type = models.CharField(max_length=10, choices=STATION_TYPES, help_text="Type of gaming station")
    description = models.TextField(blank=True, help_text="Detailed description of the gaming station")
    
    # Pricing
    hourly_rate = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Hourly rate in dollars"
    )
    
    # Availability Management
    is_active = models.BooleanField(default=True, help_text="Whether the station is available for booking")
    is_maintenance = models.BooleanField(default=False, help_text="Whether the station is under maintenance")
    
    # Technical Specifications (JSON field for flexibility)
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Technical specifications like CPU, GPU, RAM, etc."
    )
    
    # Media
    image = models.ImageField(
        upload_to='stations/',
        blank=True,
        null=True,
        help_text="Station photo"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gaming Station (DEPRECATED)"
        verbose_name_plural = "Gaming Stations (DEPRECATED)"
        ordering = ['station_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_station_type_display()})"
    
    @property
    def is_available(self):
        """Check if station is available for booking"""
        return self.is_active and not self.is_maintenance
    
    def get_current_booking(self):
        """Get current active booking for this station"""
        from django.utils import timezone
        now = timezone.now()
        
        return self.bookings.filter(
            start_time__lte=now,
            end_time__gte=now,
            status__in=['CONFIRMED', 'IN_PROGRESS']
        ).first()
    
    def is_available_at_time(self, start_time, end_time):
        """Check if station is available during a specific time period"""
        if not self.is_available:
            return False
        
        # Check for overlapping bookings
        overlapping_bookings = self.bookings.filter(
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['CONFIRMED', 'IN_PROGRESS', 'PENDING']
        )
        
        return not overlapping_bookings.exists()


class Booking(models.Model):
    """Booking model with hybrid booking support (private/shared)"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
        ('EXPIRED', 'Payment Expired'),
    ]
    
    BOOKING_TYPES = [
        ('PRIVATE', 'Private Booking (Full Capacity)'),
        ('SHARED', 'Shared Booking (Individual Spots)'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="Customer who made the booking"
    )
    
    # Game and Slot Information (New)
    game = models.ForeignKey(
        Game, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="Game being booked",
        null=True,
        blank=True
    )
    game_slot = models.ForeignKey(
        GameSlot, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="Specific time slot being booked",
        null=True,
        blank=True
    )
    
    # Hybrid Booking Fields (New)
    booking_type = models.CharField(
        max_length=10, 
        choices=BOOKING_TYPES,
        default='PRIVATE',
        help_text="Private (full capacity) or Shared (individual spots)"
    )
    spots_booked = models.PositiveIntegerField(
        help_text="Number of spots booked (1-capacity for shared, full capacity for private)",
        null=True,
        blank=True
    )
    
    # Pricing Information (Updated)
    price_per_spot = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="Price per spot at time of booking",
        null=True,
        blank=True
    )
    platform_fee = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        default=0.00,
        help_text="Platform fee charged for this booking"
    )
    subtotal = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="Subtotal (price_per_spot * spots_booked) before platform fee",
        null=True,
        blank=True
    )
    total_amount = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="Total amount for the booking (subtotal + platform_fee)",
        null=True,
        blank=True
    )
    
    # Status and Payment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_id = models.CharField(max_length=100, blank=True, help_text="Payment gateway transaction ID (DEPRECATED)")
    payment_status = models.CharField(max_length=20, blank=True, help_text="Payment status from gateway")
    
    # Payment Reservation System (5-minute payment window)
    reservation_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when payment reservation expires (5 minutes from booking creation)"
    )
    is_reservation_expired = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the payment reservation has expired"
    )
    
    # Razorpay Payment Fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, help_text="Razorpay order ID")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, help_text="Razorpay payment ID")
    razorpay_signature = models.CharField(max_length=500, blank=True, help_text="Razorpay payment signature")
    
    # Razorpay Route/Transfer Fields
    commission_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Commission amount deducted from owner's share (7%)"
    )
    owner_payout = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount transferred to owner after commission deduction"
    )
    razorpay_transfer_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Razorpay transfer ID for route payment to owner"
    )
    transfer_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSED', 'Processed'),
            ('FAILED', 'Failed')
        ],
        default='PENDING',
        help_text="Status of transfer to owner account"
    )
    transfer_processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when transfer was processed"
    )
    
    # QR Code Verification Fields
    verification_token = models.CharField(
        max_length=100, 
        unique=True,  # SECURITY: Enforce unique tokens
        db_index=True,
        blank=True,
        null=True,
        help_text="Unique token for QR code verification (dynamically generated, no file storage)"
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when verification token expires (24 hours after slot end)"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether booking has been verified by scanning QR code"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when booking was verified"
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_bookings',
        help_text="Owner/staff who verified the booking"
    )
    verification_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed verification attempts (security audit)"
    )
    last_verification_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last verification attempt"
    )
    
    # Notification Tracking
    owner_notified = models.BooleanField(
        default=False,
        help_text="Whether owner has been notified via Telegram about this booking"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Additional notes for the booking")
    
    # Backward Compatibility (DEPRECATED - will be removed)
    gaming_station = models.ForeignKey(
        GamingStation, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="DEPRECATED: Use game field instead",
        null=True,
        blank=True
    )
    start_time = models.DateTimeField(help_text="DEPRECATED: Use game_slot instead", null=True, blank=True)
    end_time = models.DateTimeField(help_text="DEPRECATED: Use game_slot instead", null=True, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        help_text="DEPRECATED: Use price_per_spot instead",
        null=True,
        blank=True
    )
    is_walk_in = models.BooleanField(default=False, help_text="DEPRECATED: Online-only bookings")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['game_slot', 'status'], name='booking_slot_status_idx'),
            models.Index(fields=['status', 'reservation_expires_at'], name='booking_status_expires_idx'),
            models.Index(fields=['customer', 'status'], name='booking_customer_status_idx'),
            models.Index(fields=['game', 'status'], name='booking_game_status_idx'),
            models.Index(fields=['customer', '-created_at'], name='booking_customer_created_idx'),
        ]
    
    def __str__(self):
        if self.game:
            return f"Booking {self.id} - {self.customer} - {self.game.name} ({self.booking_type})"
        else:
            # Backward compatibility
            return f"Booking {self.id} - {self.customer} - {self.gaming_station.name if self.gaming_station else 'Unknown'}"
    
    @property
    def start_datetime(self):
        """Get booking start datetime"""
        if self.game_slot:
            return self.game_slot.start_datetime
        return self.start_time  # Backward compatibility
    
    @property
    def end_datetime(self):
        """Get booking end datetime"""
        if self.game_slot:
            return self.game_slot.end_datetime
        return self.end_time  # Backward compatibility
    
    @property
    def duration_hours(self):
        """Calculate booking duration in hours"""
        if self.game_slot:
            duration = self.game_slot.end_datetime - self.game_slot.start_datetime
        else:
            duration = self.end_time - self.start_time  # Backward compatibility
        return duration.total_seconds() / 3600
    
    def calculate_total_amount(self):
        """Calculate total amount based on spots, price per spot, and platform fee"""
        subtotal = Decimal(str(self.price_per_spot)) * Decimal(str(self.spots_booked))
        total = subtotal + Decimal(str(self.platform_fee))
        return total.quantize(Decimal('0.01'))
    
    def calculate_subtotal(self):
        """Calculate subtotal (before platform fee)"""
        subtotal = Decimal(str(self.price_per_spot)) * Decimal(str(self.spots_booked))
        return subtotal.quantize(Decimal('0.01'))
    
    def check_and_expire_reservation(self):
        """
        Check if reservation has expired and update status accordingly
        Returns True if expired, False otherwise
        """
        from django.utils import timezone
        
        if self.status != 'PENDING':
            return False
        
        if not self.reservation_expires_at:
            return False
        
        if timezone.now() >= self.reservation_expires_at:
            # Reservation has expired
            self.status = 'EXPIRED'
            self.is_reservation_expired = True
            self.save()
            return True
        
        return False
    
    @property
    def is_payment_window_active(self):
        """Check if payment window is still active"""
        from django.utils import timezone
        
        if self.status != 'PENDING':
            return False
        
        if not self.reservation_expires_at:
            return False
        
        return timezone.now() < self.reservation_expires_at
    
    @property
    def time_remaining_seconds(self):
        """Get remaining time in seconds for payment"""
        from django.utils import timezone
        
        if not self.is_payment_window_active:
            return 0
        
        remaining = (self.reservation_expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining))
    
    def save(self, *args, **kwargs):
        """Override save to calculate total amount and update availability"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate subtotal and total amount if not set
        if self.price_per_spot and self.spots_booked:
            if not self.subtotal:
                self.subtotal = self.calculate_subtotal()
            if not self.total_amount:
                self.total_amount = self.calculate_total_amount()
        
        # Set reservation expiry time for new PENDING bookings
        is_new = self.pk is None
        if is_new and self.status == 'PENDING' and not self.reservation_expires_at:
            # Set expiry to 5 minutes from now
            self.reservation_expires_at = timezone.now() + timedelta(minutes=5)
        
        # Update slot availability when booking is confirmed
        old_status = None
        if not is_new:
            # Only get old booking if it exists (updating existing booking)
            try:
                old_booking = Booking.objects.get(pk=self.pk)
                old_status = old_booking.status
            except Booking.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Update availability when booking status changes
        if self.game_slot and (is_new or old_status != self.status):
            self.update_slot_availability(old_status)
    
    def update_slot_availability(self, old_status=None):
        """Update slot availability based on booking status
        
        Args:
            old_status: Previous status of the booking (if updating existing booking)
        """
        availability, created = SlotAvailability.objects.get_or_create(
            game_slot=self.game_slot,
            defaults={'total_capacity': self.game.capacity}
        )
        
        if self.status in ['CONFIRMED', 'IN_PROGRESS']:
            # Add booking to availability (permanent)
            if self.booking_type == 'PRIVATE':
                availability.is_private_booked = True
                availability.booked_spots = availability.total_capacity
            else:  # SHARED
                # Only add if transitioning from PENDING or new booking
                # PENDING bookings were never in booked_spots
                if old_status in ['PENDING', None]:
                    availability.booked_spots += self.spots_booked
        elif self.status == 'PENDING':
            # PENDING bookings reserve spots temporarily
            # These are tracked separately via get_reserved_spots_count()
            # Don't modify booked_spots for PENDING bookings
            pass
        elif self.status in ['CANCELLED', 'NO_SHOW', 'EXPIRED']:
            # Only subtract if the booking was previously CONFIRMED/IN_PROGRESS
            # PENDING bookings were never added to booked_spots, so don't subtract
            if old_status in ['CONFIRMED', 'IN_PROGRESS']:
                if self.booking_type == 'PRIVATE':
                    availability.is_private_booked = False
                    availability.booked_spots = 0
                else:  # SHARED
                    availability.booked_spots = max(0, availability.booked_spots - self.spots_booked)
            # If old_status was PENDING, no need to modify booked_spots
        
        availability.save()
        
        # Broadcast real-time update
        from .realtime_service import RealTimeService
        RealTimeService.broadcast_availability_update(self.game_slot.id)
    
    def clean(self):
        """Validate booking data"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        if self.game_slot:
            # Check if booking is in the future (for new bookings)
            if not self.pk and self.game_slot.start_datetime <= timezone.now():
                raise ValidationError("Booking start time must be in the future")
            
            # Validate spots requested
            if self.spots_booked > self.game.capacity:
                raise ValidationError(f"Cannot book more than {self.game.capacity} spots")
            
            # Validate booking type compatibility
            if self.booking_type == 'SHARED' and self.game.booking_type == 'SINGLE':
                raise ValidationError("This game only supports private bookings")
            
            if self.booking_type == 'PRIVATE' and self.spots_booked != self.game.capacity:
                raise ValidationError("Private bookings must book full capacity")
        
        # Backward compatibility validation (only if old fields are populated)
        elif self.gaming_station and self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValidationError("End time must be after start time")
            
            if not self.pk and self.start_time <= timezone.now():
                raise ValidationError("Booking start time must be in the future")


class BookingHistory(models.Model):
    """Track booking status changes for audit purposes"""
    
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='history'
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    reason = models.TextField(blank=True, help_text="Reason for status change")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Booking History"
        verbose_name_plural = "Booking Histories"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Booking {self.booking.id} - {self.previous_status} → {self.new_status}"


class Notification(models.Model):
    """In-app notifications for users"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=10,
        choices=NOTIFICATION_TYPES,
        default='info'
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()