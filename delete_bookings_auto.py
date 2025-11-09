"""
Script to automatically delete all bookings from the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking, BookingHistory, Notification

print("=" * 60)
print("DELETING ALL BOOKINGS")
print("=" * 60)

# Count existing bookings
total_bookings = Booking.objects.count()
paid_bookings = Booking.objects.filter(payment_status='PAID').count()
pending_bookings = Booking.objects.filter(payment_status='PENDING').count()

print(f"\nCurrent Database State:")
print(f"  Total Bookings: {total_bookings}")
print(f"  Paid Bookings: {paid_bookings}")
print(f"  Pending Bookings: {pending_bookings}")

if total_bookings == 0:
    print("\n✓ No bookings found. Database is already clean!")
else:
    print("\nDeleting bookings...")
    
    try:
        # Delete booking history
        history_count = BookingHistory.objects.count()
        if history_count > 0:
            BookingHistory.objects.all().delete()
            print(f"  ✓ Deleted {history_count} booking history records")
        
        # Delete notifications related to bookings
        notification_count = Notification.objects.filter(booking__isnull=False).count()
        if notification_count > 0:
            Notification.objects.filter(booking__isnull=False).delete()
            print(f"  ✓ Deleted {notification_count} booking notifications")
        
        # Delete all bookings
        Booking.objects.all().delete()
        print(f"  ✓ Deleted {total_bookings} bookings")
        
        print("\n" + "=" * 60)
        print("✓ ALL BOOKINGS DELETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Verify deletion
        remaining = Booking.objects.count()
        print(f"\nVerification:")
        print(f"  Remaining Bookings: {remaining}")
        
        if remaining == 0:
            print("\n✓ Database is now clean and ready for fresh testing!")
            print("\nRevenue page will now show ₹0.00 until new bookings are made.")
        else:
            print(f"\n⚠ Warning: {remaining} bookings still remain!")
        
    except Exception as e:
        print(f"\n✗ Error during deletion: {e}")
        print("Some data may have been deleted. Please check the database.")

print("\nNext Steps:")
print("1. Start the development server: python manage.py runserver")
print("2. Make new test bookings as a customer")
print("3. Complete payment for the bookings")
print("4. Check the owner's revenue page to see the new data")
