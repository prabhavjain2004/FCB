"""
Management command to fix QR verification tokens for existing bookings
Run after applying the security migration
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from booking.models import Booking
from booking.qr_service_enhanced import QRCodeServiceEnhanced


class Command(BaseCommand):
    help = 'Add verification tokens to existing bookings and fix token expiration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--regenerate-all',
            action='store_true',
            help='Regenerate tokens for all bookings (even those with tokens)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        regenerate_all = options['regenerate_all']
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('QR Token Fix Utility'))
        self.stdout.write(self.style.WARNING('=' * 70))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be made\n'))
        
        # Get bookings that need tokens
        if regenerate_all:
            bookings = Booking.objects.filter(
                status__in=['CONFIRMED', 'IN_PROGRESS'],
                game_slot__isnull=False
            ).select_related('game_slot')
            self.stdout.write(f'\n📋 Found {bookings.count()} bookings to regenerate tokens\n')
        else:
            bookings = Booking.objects.filter(
                status__in=['CONFIRMED', 'IN_PROGRESS'],
                game_slot__isnull=False,
                verification_token__isnull=True
            ).select_related('game_slot')
            self.stdout.write(f'\n📋 Found {bookings.count()} bookings without tokens\n')
        
        if bookings.count() == 0:
            self.stdout.write(self.style.SUCCESS('✅ No bookings need token updates'))
            return
        
        # Process bookings
        updated_count = 0
        error_count = 0
        
        for booking in bookings:
            try:
                if dry_run:
                    self.stdout.write(
                        f'  Would update booking {booking.id} '
                        f'({booking.game.name if booking.game else "Unknown"} - '
                        f'{booking.game_slot.date})'
                    )
                else:
                    # Generate or regenerate token
                    booking.verification_token = QRCodeServiceEnhanced.generate_verification_token()
                    
                    # Set expiration (24 hours after slot end)
                    booking.token_expires_at = booking.game_slot.end_datetime + timedelta(hours=24)
                    
                    # Reset verification attempts
                    booking.verification_attempts = 0
                    
                    # Save
                    booking.save(update_fields=[
                        'verification_token', 
                        'token_expires_at',
                        'verification_attempts'
                    ])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ Updated booking {booking.id} '
                            f'({booking.game.name if booking.game else "Unknown"} - '
                            f'{booking.game_slot.date})'
                        )
                    )
                
                updated_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ Error updating booking {booking.id}: {str(e)}'
                    )
                )
        
        # Summary
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.WARNING('Summary'))
        self.stdout.write(self.style.WARNING('=' * 70))
        
        if dry_run:
            self.stdout.write(f'\n📊 Would update: {updated_count} bookings')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully updated: {updated_count} bookings'))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errors: {error_count} bookings'))
        
        self.stdout.write('\n')
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    '💡 Run without --dry-run to apply changes:\n'
                    '   python manage.py fix_qr_tokens'
                )
            )
