from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time, timedelta
from decimal import Decimal
from .models import Game, GameSlot
import json


class GameCreationForm(forms.ModelForm):
    """Comprehensive game creation form with all required fields"""
    
    # Custom field for available days with checkboxes
    available_days = forms.MultipleChoiceField(
        choices=Game.WEEKDAYS,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'checkbox-input'
        }),
        required=True,
        help_text="Select the days when this game is available"
    )
    
    class Meta:
        model = Game
        fields = [
            'name', 'description', 'capacity', 'booking_type',
            'opening_time', 'closing_time', 'slot_duration_minutes',
            'available_days', 'private_price', 'shared_price'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., 8-Ball Pool, Table Tennis, PS4 Console 1'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Detailed description of the game/activity',
                'rows': 4
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Maximum number of players (e.g., 1 for PC, 4 for pool table)',
                'min': 1
            }),
            'booking_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'onchange': 'toggleSharedPriceField(this.value)'
            }),
            'opening_time': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'time',
                'placeholder': '11:00'
            }),
            'closing_time': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'time',
                'placeholder': '23:00'
            }),
            'slot_duration_minutes': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Duration in minutes (e.g., 60 for 1 hour)',
                'min': 1,
                'step': 1
            }),
            'private_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Price for private booking (full capacity)',
                'min': 0.01,
                'step': 0.01
            }),
            'shared_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Price per spot for shared booking',
                'min': 0.01,
                'step': 0.01
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set field labels and help texts
        self.fields['name'].label = 'Game Name'
        self.fields['description'].label = 'Description'
        self.fields['capacity'].label = 'Maximum Players'
        self.fields['booking_type'].label = 'Booking Type'
        self.fields['opening_time'].label = 'Opening Time'
        self.fields['closing_time'].label = 'Closing Time'
        self.fields['slot_duration_minutes'].label = 'Slot Duration (minutes)'
        self.fields['private_price'].label = 'Private Booking Price (₹)'
        self.fields['shared_price'].label = 'Shared Booking Price per Person (₹)'
        
        # Set help texts
        self.fields['capacity'].help_text = 'Maximum number of players that can use this game simultaneously'
        self.fields['booking_type'].help_text = 'Single = Private bookings only, Hybrid = Both private and shared bookings'
        self.fields['opening_time'].help_text = 'Daily opening time for this game'
        self.fields['closing_time'].help_text = 'Daily closing time for this game'
        self.fields['slot_duration_minutes'].help_text = 'Duration of each time slot in minutes'
        self.fields['private_price'].help_text = 'Price for booking the entire game capacity'
        self.fields['shared_price'].help_text = 'Price per individual spot (only for hybrid games)'
        
        # If editing existing game, convert available_days from JSON to list
        if self.instance and self.instance.pk:
            if isinstance(self.instance.available_days, list):
                self.initial['available_days'] = self.instance.available_days
    
    def clean_available_days(self):
        """Convert selected days to list format for JSON field"""
        days = self.cleaned_data.get('available_days', [])
        if not days:
            raise ValidationError("Please select at least one day when the game is available")
        return list(days)
    
    def clean_closing_time(self):
        """Validate that closing time is after opening time"""
        opening_time = self.cleaned_data.get('opening_time')
        closing_time = self.cleaned_data.get('closing_time')
        
        if opening_time and closing_time:
            # Allow midnight (00:00) as valid closing time for overnight schedules
            # This enables schedules like 17:00 (5 PM) to 00:00 (midnight)
            if closing_time <= opening_time and closing_time != time(0, 0):
                raise ValidationError("Closing time must be after opening time (use 00:00 for midnight)")
        
        return closing_time
    
    def clean_slot_duration_minutes(self):
        """Validate slot duration"""
        duration = self.cleaned_data.get('slot_duration_minutes')
        opening_time = self.cleaned_data.get('opening_time')
        closing_time = self.cleaned_data.get('closing_time')
        
        if duration and opening_time and closing_time:
            # Calculate total operating hours
            opening_datetime = datetime.combine(datetime.today(), opening_time)
            closing_datetime = datetime.combine(datetime.today(), closing_time)
            
            # Handle overnight schedules (closing time is 00:00 or next day)
            if closing_time <= opening_time and closing_time == time(0, 0):
                # Add a day to closing time for midnight schedules
                closing_datetime = closing_datetime + timedelta(days=1)
            
            total_minutes = (closing_datetime - opening_datetime).total_seconds() / 60
            
            if duration > total_minutes:
                raise ValidationError(
                    f"Slot duration ({duration} minutes) cannot be longer than operating hours ({int(total_minutes)} minutes)"
                )
            
            # Check if duration creates reasonable number of slots
            slots_per_day = total_minutes / duration
            if slots_per_day < 1:
                raise ValidationError("Slot duration is too long - must allow at least 1 slot per day")
        
        return duration
    
    def clean_shared_price(self):
        """Validate shared price for hybrid games"""
        booking_type = self.cleaned_data.get('booking_type')
        shared_price = self.cleaned_data.get('shared_price')
        
        if booking_type == 'HYBRID':
            if not shared_price or shared_price <= 0:
                raise ValidationError("Shared price is required for hybrid games")
        elif booking_type == 'SINGLE':
            # Clear shared price for single games
            shared_price = None
        
        return shared_price
    
    def clean_private_price(self):
        """Validate private price"""
        private_price = self.cleaned_data.get('private_price')
        
        if not private_price or private_price <= 0:
            raise ValidationError("Private price must be greater than 0")
        
        return private_price
    
    def clean(self):
        """Additional validation for pricing logic"""
        cleaned_data = super().clean()
        booking_type = cleaned_data.get('booking_type')
        private_price = cleaned_data.get('private_price')
        shared_price = cleaned_data.get('shared_price')
        capacity = cleaned_data.get('capacity')
        
        # For hybrid games, validate pricing relationship
        if booking_type == 'HYBRID' and private_price and shared_price and capacity:
            # Private price should generally be less than shared_price * capacity
            # (to incentivize private bookings), but this is just a warning
            total_shared_price = shared_price * capacity
            if private_price > total_shared_price * Decimal('1.2'):  # 20% tolerance
                self.add_error('private_price', 
                    f"Private price (₹{private_price}) seems high compared to shared pricing "
                    f"(₹{shared_price} × {capacity} = ₹{total_shared_price}). Consider adjusting."
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save - DO NOT generate slots here (will be done via AJAX with progress bar)"""
        instance = super().save(commit=commit)
        # Slot generation is now handled separately via AJAX endpoint
        return instance


class GameUpdateForm(GameCreationForm):
    """Form for updating existing games with slot regeneration options"""
    
    regenerate_slots = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        }),
        help_text="Check this to manually regenerate time slots. "
                  "Slots will auto-regenerate if schedule settings change. "
                  "Existing bookings will be preserved."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add regenerate_slots field to the form
        self.fields['regenerate_slots'].label = 'Manually Regenerate Time Slots'
        
        # Store original values to detect changes
        if self.instance and self.instance.pk:
            self._original_opening_time = self.instance.opening_time
            self._original_closing_time = self.instance.closing_time
            self._original_slot_duration = self.instance.slot_duration_minutes
            self._original_available_days = self.instance.available_days.copy() if self.instance.available_days else []
            self._original_capacity = self.instance.capacity
    
    def _schedule_changed(self):
        """Check if schedule-related fields have changed"""
        if not self.instance or not self.instance.pk:
            return False
        
        schedule_changed = (
            self.cleaned_data.get('opening_time') != self._original_opening_time or
            self.cleaned_data.get('closing_time') != self._original_closing_time or
            self.cleaned_data.get('slot_duration_minutes') != self._original_slot_duration or
            set(self.cleaned_data.get('available_days', [])) != set(self._original_available_days)
        )
        
        return schedule_changed
    
    def save(self, commit=True):
        """Override save to handle slot regeneration and capacity updates"""
        instance = super(GameCreationForm, self).save(commit=commit)  # Skip GameCreationForm's save
        
        if commit:
            # Check if capacity changed
            capacity_changed = (
                hasattr(self, '_original_capacity') and 
                self.cleaned_data.get('capacity') != self._original_capacity
            )
            
            # Auto-regenerate if schedule changed OR if manually requested
            regenerate_manual = self.cleaned_data.get('regenerate_slots', False)
            regenerate_auto = self._schedule_changed()
            
            if regenerate_manual or regenerate_auto:
                # Regenerate slots while preserving existing bookings
                instance.generate_slots()
            elif capacity_changed:
                # If only capacity changed, update existing slot availabilities
                self._update_slot_capacities(instance)
        
        return instance
    
    def _update_slot_capacities(self, game):
        """Update total_capacity for all existing slot availabilities"""
        from .models import SlotAvailability
        from django.utils import timezone
        
        # Get all future active slots for this game
        future_slots = game.slots.filter(
            date__gte=timezone.now().date(),
            is_active=True
        )
        
        # Update capacity for each slot's availability
        updated_count = 0
        for slot in future_slots:
            availability, created = SlotAvailability.objects.get_or_create(
                game_slot=slot,
                defaults={'total_capacity': game.capacity}
            )
            
            if not created and availability.total_capacity != game.capacity:
                # Only update if not fully booked as private
                if not availability.is_private_booked:
                    availability.total_capacity = game.capacity
                    availability.save(update_fields=['total_capacity'])
                    updated_count += 1
        
        return updated_count


class CustomSlotForm(forms.ModelForm):
    """Form for adding custom temporary slots"""
    
    class Meta:
        model = GameSlot
        fields = ['game', 'date', 'start_time', 'end_time']
        widgets = {
            'game': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'time'
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'time'
            })
        }
    
    def __init__(self, *args, **kwargs):
        # Get cafe owner's games only
        cafe_owner = kwargs.pop('cafe_owner', None)
        super().__init__(*args, **kwargs)
        
        # Filter games to only show active games
        self.fields['game'].queryset = Game.objects.filter(is_active=True)
        
        # Set labels and help texts
        self.fields['game'].label = 'Game'
        self.fields['date'].label = 'Date'
        self.fields['start_time'].label = 'Start Time'
        self.fields['end_time'].label = 'End Time'
        
        self.fields['game'].help_text = 'Select the game for this custom slot'
        self.fields['date'].help_text = 'Date for the custom slot (must be in the future)'
        self.fields['start_time'].help_text = 'Start time for the custom slot'
        self.fields['end_time'].help_text = 'End time for the custom slot'
    
    def clean_date(self):
        """Validate that date is in the future"""
        date = self.cleaned_data.get('date')
        
        if date and date <= timezone.now().date():
            raise ValidationError("Custom slot date must be in the future")
        
        return date
    
    def clean_end_time(self):
        """Validate that end time is after start time"""
        start_time = self.cleaned_data.get('start_time')
        end_time = self.cleaned_data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError("End time must be after start time")
        
        return end_time
    
    def clean(self):
        """Validate for slot conflicts"""
        cleaned_data = super().clean()
        game = cleaned_data.get('game')
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if all([game, date, start_time, end_time]):
            # Check for overlapping slots
            overlapping_slots = GameSlot.objects.filter(
                game=game,
                date=date,
                start_time__lt=end_time,
                end_time__gt=start_time,
                is_active=True
            )
            
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                overlapping_slots = overlapping_slots.exclude(pk=self.instance.pk)
            
            if overlapping_slots.exists():
                raise ValidationError(
                    f"This time slot overlaps with existing slots for {game.name} on {date}. "
                    f"Overlapping slots: {', '.join([f'{slot.start_time}-{slot.end_time}' for slot in overlapping_slots])}"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to mark as custom slot and create availability tracking"""
        instance = super().save(commit=False)
        instance.is_custom = True
        
        if commit:
            instance.save()
            
            # Create availability tracking for the custom slot
            from .models import SlotAvailability
            SlotAvailability.objects.get_or_create(
                game_slot=instance,
                defaults={'total_capacity': instance.game.capacity}
            )
        
        return instance


class BulkScheduleUpdateForm(forms.Form):
    """Form for bulk schedule updates across multiple games"""
    
    games = forms.ModelMultipleChoiceField(
        queryset=Game.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'grid grid-cols-1 gap-2'
        }),
        required=True,
        help_text="Select games to update"
    )
    
    update_opening_time = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'onchange': 'toggleField("opening_time", this.checked)'
        })
    )
    
    opening_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'time',
            'disabled': True
        })
    )
    
    update_closing_time = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'onchange': 'toggleField("closing_time", this.checked)'
        })
    )
    
    closing_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'time',
            'disabled': True
        })
    )
    
    update_available_days = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'onchange': 'toggleField("available_days", this.checked)'
        })
    )
    
    available_days = forms.MultipleChoiceField(
        choices=Game.WEEKDAYS,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'grid grid-cols-2 gap-2',
            'disabled': True
        }),
        required=False
    )
    
    preserve_bookings = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        }),
        help_text="Keep existing bookings when regenerating slots"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set labels
        self.fields['games'].label = 'Select Games'
        self.fields['update_opening_time'].label = 'Update Opening Time'
        self.fields['opening_time'].label = 'New Opening Time'
        self.fields['update_closing_time'].label = 'Update Closing Time'
        self.fields['closing_time'].label = 'New Closing Time'
        self.fields['update_available_days'].label = 'Update Available Days'
        self.fields['available_days'].label = 'New Available Days'
        self.fields['preserve_bookings'].label = 'Preserve Existing Bookings'
    
    def clean(self):
        """Validate bulk update data"""
        cleaned_data = super().clean()
        
        # Check that at least one update option is selected
        update_fields = [
            cleaned_data.get('update_opening_time'),
            cleaned_data.get('update_closing_time'),
            cleaned_data.get('update_available_days')
        ]
        
        if not any(update_fields):
            raise ValidationError("Please select at least one field to update")
        
        # Validate required fields based on selected updates
        if cleaned_data.get('update_opening_time') and not cleaned_data.get('opening_time'):
            raise ValidationError("Opening time is required when updating opening time")
        
        if cleaned_data.get('update_closing_time') and not cleaned_data.get('closing_time'):
            raise ValidationError("Closing time is required when updating closing time")
        
        if cleaned_data.get('update_available_days') and not cleaned_data.get('available_days'):
            raise ValidationError("Available days are required when updating available days")
        
        # Validate time relationship
        opening_time = cleaned_data.get('opening_time')
        closing_time = cleaned_data.get('closing_time')
        
        if opening_time and closing_time and closing_time <= opening_time:
            raise ValidationError("Closing time must be after opening time")
        
        return cleaned_data