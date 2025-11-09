import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from django.db.models import Sum

print("=" * 60)
print("CHECKING CURRENT BOOKINGS")
print("=" * 60)

bookings = Booking.objects.all().order_by('-created_at')
print(f"\nTotal bookings: {bookings.count()}")

if bookings.count() == 0:
    print("\n❌ No bookings found! Please make a test booking first.")
else:
    print("\nBooking Details:")
    print("-" * 60)
    for b in bookings:
        print(f"\nBooking ID: {b.id}")
        print(f"  Game: {b.game.name if b.game else 'N/A'}")
        print(f"  Status: {b.status}")
        print(f"  Payment Status: {b.payment_status}")
        print(f"  Total Amount: ₹{b.total_amount}")
        print(f"  Owner Payout: ₹{b.owner_payout}")
        print(f"  Created: {b.created_at}")
    
    # Check PAID bookings
    paid_bookings = bookings.filter(payment_status='PAID')
    print("\n" + "=" * 60)
    print(f"PAID Bookings: {paid_bookings.count()}")
    
    if paid_bookings.count() > 0:
        total_revenue = paid_bookings.aggregate(total=Sum('owner_payout'))['total']
        print(f"Total Owner Revenue: ₹{total_revenue}")
        print("\n✅ Revenue page should show this data!")
    else:
        print("\n❌ No PAID bookings found!")
        print("\nPossible reasons:")
        print("1. Payment was not completed")
        print("2. Booking status is still PENDING")
        print("3. Payment failed")
        
        pending = bookings.filter(payment_status='PENDING').count()
        if pending > 0:
            print(f"\n⚠️  You have {pending} PENDING payment(s)")
            print("   Complete the payment to see revenue!")
