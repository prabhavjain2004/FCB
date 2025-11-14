"""
Management command to retry failed Telegram notifications for confirmed bookings
Usage: python manage.py retry_failed_notifications [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from booking.models import Booking
from booking.telegram_service import telegram_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Retry failed Telegram notifications for confirmed bookings without owner_notified flag'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually sending notifications',
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Only process bookings confirmed within last N hours (default: 24)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hours = options['hours']
        
        # Find confirmed bookings without notification sent
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        bookings = Booking.objects.filter(
            status='CONFIRMED',
            payment_status='PAID',
            owner_notified=False,
            updated_at__gte=cutoff_time
        ).order_by('updated_at')
        
        count = bookings.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✓ No bookings found needing notifications'))
            return
        
        self.stdout.write(f'Found {count} booking(s) without notifications')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No notifications will be sent'))
            for booking in bookings:
                self.stdout.write(f'  - Booking {str(booking.id)[:8]} ({booking.customer.user.username})')
            return
        
        # Send notifications
        success_count = 0
        failed_count = 0
        
        for booking in bookings:
            booking_id_short = str(booking.id)[:8]
            
            try:
                self.stdout.write(f'Sending notification for booking {booking_id_short}...')
                
                notification_sent = telegram_service.send_new_booking_notification(booking)
                
                if notification_sent:
                    # Mark as notified
                    booking.owner_notified = True
                    booking.save(update_fields=['owner_notified'])
                    
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Sent successfully'))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed to send'))
                    
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Exception: {str(e)}'))
                logger.error(f"Failed to retry notification for booking {booking.id}: {e}", exc_info=True)
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully sent: {success_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Failed: {failed_count}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ All notifications sent successfully!'))
