"""
Telegram Notification Service for Gaming Cafe
Sends booking notifications to cafe owner via Telegram Bot
"""
import logging
import requests
from django.conf import settings
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """Service for sending Telegram notifications to cafe owner"""
    
    def __init__(self):
        """Initialize Telegram service with configuration from database"""
        self.bot_token = None
        self.chat_id = None
        self.enabled = False
        self.notification_type = 'PERSONAL'
        self._load_config()
    
    def _load_config(self):
        """Load Telegram configuration from database"""
        try:
            from authentication.models import TapNexSuperuser
            tapnex = TapNexSuperuser.objects.first()
            
            if tapnex:
                # Database settings override environment variables
                # If database field is empty, fallback to .env
                self.bot_token = tapnex.telegram_bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
                self.chat_id = tapnex.telegram_chat_id or getattr(settings, 'TELEGRAM_CHAT_ID', '')
                self.enabled = tapnex.telegram_enabled
                self.notification_type = tapnex.telegram_notification_type
            else:
                # Fallback to environment variables
                self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
                self.chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')
                self.enabled = False
                
        except Exception as e:
            logger.error(f"Failed to load Telegram config: {e}")
            self.enabled = False
    
    def _send_message(self, text, parse_mode='HTML', retry_count=3):
        """
        Send message to Telegram with retry logic
        
        Args:
            text: Message text to send
            parse_mode: 'HTML' or 'Markdown'
            retry_count: Number of retry attempts
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled or not self.bot_token or not self.chat_id:
            logger.warning("Telegram notifications disabled or not configured")
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Telegram notification sent successfully to {self.chat_id}")
                    return True
                else:
                    logger.warning(f"Telegram API error (attempt {attempt + 1}/{retry_count}): {response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Telegram request failed (attempt {attempt + 1}/{retry_count}): {e}")
        
        logger.error(f"Failed to send Telegram notification after {retry_count} attempts")
        return False
    
    def send_test_message(self):
        """
        Send a test message to verify Telegram configuration
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        if not self.bot_token:
            return {'success': False, 'message': 'Bot token not configured'}
        
        if not self.chat_id:
            return {'success': False, 'message': 'Chat ID not configured'}
        
        # For test messages, bypass the enabled check
        # Temporarily send message even if notifications are disabled
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        test_text = (
            "🎮 <b>Telegram Notification Test</b>\n\n"
            "✅ Your Gaming Cafe notification system is working!\n\n"
            f"📱 Chat Type: {self.notification_type}\n"
            f"🔔 Notifications: {'Enabled' if self.enabled else 'Disabled'}\n\n"
            f"⏰ Test Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        )
        
        payload = {
            'chat_id': self.chat_id,
            'text': test_text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Test notification sent successfully to {self.chat_id}")
                return {'success': True, 'message': 'Test notification sent successfully!'}
            else:
                error_msg = response.json().get('description', 'Unknown error')
                logger.error(f"Telegram API error: {error_msg}")
                return {'success': False, 'message': f'Telegram API error: {error_msg}'}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send test notification: {e}")
            return {'success': False, 'message': f'Connection error: {str(e)}'}

    
    def send_new_booking_notification(self, booking):
        """
        Send notification for new confirmed booking
        
        Args:
            booking: Booking model instance
        """
        if not self.enabled:
            return False
        
        try:
            # Extract booking details
            customer = booking.customer
            customer_name = customer.user.get_full_name() or customer.user.username
            customer_phone = customer.phone or 'N/A'
            customer_email = customer.user.email or 'N/A'
            
            # Game details
            if booking.game:
                game_name = booking.game.name
                slot_start = booking.game_slot.start_datetime if booking.game_slot else booking.start_datetime
                slot_end = booking.game_slot.end_datetime if booking.game_slot else booking.end_datetime
            else:
                # Fallback for old bookings
                game_name = booking.gaming_station.name if booking.gaming_station else 'Unknown'
                slot_start = booking.start_time
                slot_end = booking.end_time
            
            # Format date and time
            booking_date = slot_start.strftime('%b %d, %Y')
            start_time = slot_start.strftime('%I:%M %p')
            end_time = slot_end.strftime('%I:%M %p')
            
            # Calculate duration
            duration = slot_end - slot_start
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours} hour{'s' if hours != 1 else ''}"
            if minutes > 0:
                duration_str += f" {minutes} min"
            
            # Booking type
            booking_type = booking.get_booking_type_display() if hasattr(booking, 'booking_type') else 'Private Booking'
            
            # Amount
            amount = booking.total_amount or Decimal('0.00')
            
            # Booking ID (short version)
            booking_id_short = str(booking.id)[:8]
            
            # Construct message
            message = (
                "🎮 <b>NEW BOOKING CONFIRMED</b>\n\n"
                
                "👤 <b>Customer Details:</b>\n"
                f"   Name: {customer_name}\n"
                f"   Phone: {customer_phone}\n"
                f"   Email: {customer_email}\n\n"
                
                " <b>Booking Details:</b>\n"
                f"   Game: {game_name}\n"
                f"   Date: {booking_date}\n"
                f"   Time: {start_time} - {end_time} ({duration_str})\n"
                f"   Type: {booking_type}\n\n"
                
                "💰 <b>Payment:</b>\n"
                f"   Amount: ₹{amount}\n\n"
                
                f"🔗 <b>Booking ID:</b> {booking_id_short}\n"
                "✅ <b>Status:</b> CONFIRMED"
            )
            
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send new booking notification: {e}", exc_info=True)
            return False
    
    def send_cancellation_notification(self, booking, reason='Customer request'):
        """
        Send notification for booking cancellation
        
        Args:
            booking: Booking model instance
            reason: Cancellation reason
        """
        if not self.enabled:
            return False
        
        try:
            customer = booking.customer
            customer_name = customer.user.get_full_name() or customer.user.username
            
            if booking.game:
                game_name = booking.game.name
                slot_start = booking.game_slot.start_datetime if booking.game_slot else booking.start_datetime
            else:
                game_name = booking.gaming_station.name if booking.gaming_station else 'Unknown'
                slot_start = booking.start_time
            
            booking_date = slot_start.strftime('%b %d, %Y')
            start_time = slot_start.strftime('%I:%M %p')
            
            amount = booking.total_amount or Decimal('0.00')
            booking_id_short = str(booking.id)[:8]
            
            message = (
                "⚠️ <b>BOOKING CANCELLED</b>\n\n"
                f"👤 <b>Customer:</b> {customer_name}\n"
                f"🎯 <b>Game:</b> {game_name}\n"
                f"📅 <b>Was:</b> {booking_date}, {start_time}\n"
                f"💸 <b>Refund:</b> ₹{amount}\n\n"
                f"📝 <b>Reason:</b> {reason}\n"
                f"🔗 <b>Booking ID:</b> {booking_id_short}"
            )
            
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send cancellation notification: {e}", exc_info=True)
            return False


# Global instance
telegram_service = TelegramNotificationService()
