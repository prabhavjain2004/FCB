"""
Django management command to delete all bookings
Usage: python manage.py delete_all_bookings
"""
from django.core.management.base import BaseCommand
from booking.models import Booking, BookingHistory, Notification


class Command(BaseCommand):
    help = 'Delete all bookings from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        # Count existing bookings
        total_bookings = Booking.objects.count()
        paid_bookings = Booking.objects.filter(payment_status='PAID').count()
        pending_bookings = Booking.objects.filter(payment_status='PENDING').count()
        
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.WARNING("DELETE ALL BOOKINGS"))
        self.stdout.write("=" * 60)
        
        self.stdout.write(f"\nCurrent Database State:")
        self.stdout.write(f"  Total Bookings: {total_bookings}")
        self.stdout.write(f"  Paid Bookings: {paid_bookings}")
        self.stdout.write(f"  Pending Bookings: {pending_bookings}")
        
        if total_bookings == 0:
            self.stdout.write(self.style.SUCCESS("\n✓ No bookings found. Database is already clean!"))
            return
        
        # Confirm deletion
        if not options['confirm']:
            self.stdout.write("\n" + "!" * 60)
            self.stdout.write(self.style.ERROR("WARNING: This will DELETE ALL bookings permanently!"))
            self.stdout.write("!" * 60)
            confirm = input("\nType 'yes' to confirm: ")
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING("\n✗ Deletion cancelled. No changes made."))
                return
        
        self.stdout.write("\nDeleting bookings...")
        
        try:
            # Delete booking history
            history_count = BookingHistory.objects.count()
            if history_count > 0:
                BookingHistory.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {history_count} booking history records"))
            
            # Delete notifications related to bookings
            notification_count = Notification.objects.filter(booking__isnull=False).count()
            if notification_count > 0:
                Notification.objects.filter(booking__isnull=False).delete()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {notification_count} booking notifications"))
            
            # Delete all bookings
            Booking.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {total_bookings} bookings"))
            
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✓ ALL BOOKINGS DELETED SUCCESSFULLY!"))
            self.stdout.write("=" * 60)
            
            # Verify deletion
            remaining = Booking.objects.count()
            self.stdout.write(f"\nVerification:")
            self.stdout.write(f"  Remaining Bookings: {remaining}")
            
            if remaining == 0:
                self.stdout.write(self.style.SUCCESS("\n✓ Database is now clean and ready for fresh testing!"))
                self.stdout.write("\nRevenue page will now show ₹0.00 until new bookings are made.")
            else:
                self.stdout.write(self.style.WARNING(f"\n⚠ Warning: {remaining} bookings still remain!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error during deletion: {e}"))
            self.stdout.write("Some data may have been deleted. Please check the database.")
        
        self.stdout.write("\nNext Steps:")
        self.stdout.write("1. Start the development server: python manage.py runserver")
        self.stdout.write("2. Make new test bookings as a customer")
        self.stdout.write("3. Complete payment for the bookings")
        self.stdout.write("4. Check the owner's revenue page to see the new data")
