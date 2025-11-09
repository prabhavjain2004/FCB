"""
Management command to clean up old, unused slots
Deletes slots that:
1. Have a date in the past
2. Have NOT been booked (no associated bookings)
3. Are not part of any active bookings

This should be run via cron job every Tuesday
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from datetime import date, timedelta
from booking.models import GameSlot, SlotAvailability
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete old, unused slots (slots in the past with no bookings) - Run every Tuesday'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete slots older than X days (default: 7 days)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        days_old = options['days']
        dry_run = options['dry_run']
        force = options['force']
        
        # Calculate the cutoff date
        cutoff_date = date.today() - timedelta(days=days_old)
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("🗑️  OLD SLOT CLEANUP - TUESDAY MAINTENANCE"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"\n📅 Run Date: {date.today()}")
        self.stdout.write(f"🗓️  Cutoff Date: {cutoff_date} (older than {days_old} days)")
        self.stdout.write(f"{'🧪 DRY RUN MODE' if dry_run else '🔴 LIVE MODE'}\n")
        
        # Find old slots WITHOUT any bookings
        # We use Count to check if slot has bookings
        old_unused_slots = GameSlot.objects.filter(
            date__lt=cutoff_date,  # Older than cutoff date
            is_active=True  # Only active slots
        ).annotate(
            booking_count=Count('bookings')
        ).filter(
            booking_count=0  # No bookings at all
        ).select_related('game')
        
        total_old_unused = old_unused_slots.count()
        
        if total_old_unused == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ No old unused slots found. Database is clean!"))
            return
        
        # Get statistics before deletion
        self.stdout.write("\n📊 CLEANUP STATISTICS:")
        self.stdout.write("-" * 70)
        
        # Group by game for better reporting
        slots_by_game = {}
        for slot in old_unused_slots:
            game_name = slot.game.name
            if game_name not in slots_by_game:
                slots_by_game[game_name] = {
                    'count': 0,
                    'oldest_date': slot.date,
                    'newest_date': slot.date
                }
            
            slots_by_game[game_name]['count'] += 1
            if slot.date < slots_by_game[game_name]['oldest_date']:
                slots_by_game[game_name]['oldest_date'] = slot.date
            if slot.date > slots_by_game[game_name]['newest_date']:
                slots_by_game[game_name]['newest_date'] = slot.date
        
        # Display breakdown
        self.stdout.write(f"\n📋 Slots to be deleted by game:")
        for game_name, stats in slots_by_game.items():
            self.stdout.write(
                f"   • {game_name}: {stats['count']} slots "
                f"({stats['oldest_date']} to {stats['newest_date']})"
            )
        
        self.stdout.write(f"\n🔢 Total slots to delete: {total_old_unused}")
        
        # Calculate date range
        if old_unused_slots.exists():
            oldest_slot_date = old_unused_slots.order_by('date').first().date
            newest_slot_date = old_unused_slots.order_by('-date').first().date
            self.stdout.write(f"📅 Date range: {oldest_slot_date} to {newest_slot_date}")
        
        # Check for slots WITH bookings (should NOT be deleted)
        old_slots_with_bookings = GameSlot.objects.filter(
            date__lt=cutoff_date,
            is_active=True
        ).annotate(
            booking_count=Count('bookings')
        ).filter(
            booking_count__gt=0
        ).count()
        
        if old_slots_with_bookings > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {old_slots_with_bookings} old slots WITH bookings will be preserved"
                )
            )
        
        # Dry run - just show what would be deleted
        if dry_run:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS("🧪 DRY RUN COMPLETE - No data was deleted"))
            self.stdout.write("=" * 70)
            self.stdout.write("\nTo actually delete these slots, run without --dry-run flag:")
            self.stdout.write("  python manage.py cleanup_old_slots")
            return
        
        # Confirmation prompt (unless --force is used)
        if not force:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.WARNING("⚠️  CONFIRMATION REQUIRED"))
            self.stdout.write("=" * 70)
            response = input(f"\nDelete {total_old_unused} old unused slots? (yes/no): ")
            
            if response.lower() != 'yes':
                self.stdout.write(self.style.ERROR("\n❌ Deletion cancelled"))
                return
        
        # Perform deletion
        self.stdout.write("\n🗑️  Deleting slots...")
        
        try:
            # Get associated availability records first
            availability_ids = list(
                SlotAvailability.objects.filter(
                    game_slot__in=old_unused_slots
                ).values_list('id', flat=True)
            )
            
            # Delete availability records
            deleted_availabilities = SlotAvailability.objects.filter(
                id__in=availability_ids
            ).delete()
            
            # Delete the slots
            deleted_slots, deleted_details = old_unused_slots.delete()
            
            # Success message
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS("✅ CLEANUP COMPLETED SUCCESSFULLY"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"\n📊 Deletion Summary:")
            self.stdout.write(f"   • Slots deleted: {deleted_details.get('booking.GameSlot', 0)}")
            self.stdout.write(f"   • Availabilities deleted: {deleted_availabilities[0]}")
            self.stdout.write(f"\n✅ Old unused slots cleaned up successfully!")
            self.stdout.write(f"⚠️  Slots with bookings were preserved (not deleted)")
            
            # Log the cleanup
            logger.info(
                f"Cleaned up {deleted_details.get('booking.GameSlot', 0)} old unused slots "
                f"older than {cutoff_date}"
            )
            
        except Exception as e:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.ERROR("❌ ERROR DURING CLEANUP"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"Error: {str(e)}")
            logger.error(f"Error during slot cleanup: {str(e)}")
            raise
        
        self.stdout.write("\n" + "=" * 70)
