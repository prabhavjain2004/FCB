from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import Booking
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling booking notifications"""
    
    @staticmethod
    def send_booking_confirmation_email(booking):
        """Send booking confirmation email to customer"""
        try:
            subject = f'Booking Confirmation - {booking.gaming_station.name}'
            
            # Render email template
            html_message = render_to_string('booking/emails/confirmation.html', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            plain_message = render_to_string('booking/emails/confirmation.txt', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[booking.customer.user.email],
                fail_silently=False,
            )
            
            logger.info(f"Booking confirmation email sent to {booking.customer.user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email for booking {booking.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_booking_cancellation_email(booking):
        """Send booking cancellation email to customer"""
        try:
            subject = f'Booking Cancelled - {booking.gaming_station.name}'
            
            # Render email template
            html_message = render_to_string('booking/emails/cancellation.html', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            plain_message = render_to_string('booking/emails/cancellation.txt', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[booking.customer.user.email],
                fail_silently=False,
            )
            
            logger.info(f"Booking cancellation email sent to {booking.customer.user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send booking cancellation email for booking {booking.id}: {str(e)}")
            return False
    
    @staticmethod
    def send_booking_reminder_email(booking):
        """Send booking reminder email to customer"""
        try:
            subject = f'Gaming Session Reminder - {booking.gaming_station.name}'
            
            # Render email template
            html_message = render_to_string('booking/emails/reminder.html', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            plain_message = render_to_string('booking/emails/reminder.txt', {
                'booking': booking,
                'customer': booking.customer,
                'user': booking.customer.user,
            })
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[booking.customer.user.email],
                fail_silently=False,
            )
            
            logger.info(f"Booking reminder email sent to {booking.customer.user.email} for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send booking reminder email for booking {booking.id}: {str(e)}")
            return False


class InAppNotification:
    """In-app notification system"""
    
    @staticmethod
    def create_notification(user, title, message, notification_type='info', booking=None):
        """Create an in-app notification - REAL-TIME (NO CACHE)"""
        from .models import Notification
        
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            booking=booking
        )
        
        return notification
    
    @staticmethod
    def notify_booking_confirmed(booking):
        """Create notification for booking confirmation"""
        return InAppNotification.create_notification(
            user=booking.customer.user,
            title='Booking Confirmed!',
            message=f'Your booking for {booking.gaming_station.name} on {booking.start_time.strftime("%B %d, %Y at %I:%M %p")} has been confirmed.',
            notification_type='success',
            booking=booking
        )
    
    @staticmethod
    def notify_booking_cancelled(booking):
        """Create notification for booking cancellation"""
        return InAppNotification.create_notification(
            user=booking.customer.user,
            title='Booking Cancelled',
            message=f'Your booking for {booking.gaming_station.name} on {booking.start_time.strftime("%B %d, %Y at %I:%M %p")} has been cancelled.',
            notification_type='warning',
            booking=booking
        )
    
    @staticmethod
    def notify_booking_reminder(booking):
        """Create notification for booking reminder"""
        return InAppNotification.create_notification(
            user=booking.customer.user,
            title='Gaming Session Starting Soon!',
            message=f'Your gaming session at {booking.gaming_station.name} starts in 30 minutes.',
            notification_type='info',
            booking=booking
        )