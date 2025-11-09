import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from django.db.models import Sum
from datetime import date, timedelta
from django.utils import timezone

print("=" * 60)
print("CHECKING REVENUE DATE FILTERING")
print("=" * 60)

# Get current date info
now = timezone.now()
today = now.date()
month_start = today.replace(day=1)

print(f"\nCurrent Date: {today}")
print(f"Current Time: {now}")
print(f"Month Start: {month_start}")

# Check all PAID bookings
paid_bookings = Booking.objects.filter(payment_status='PAID')
print(f"\nTotal PAID bookings: {paid_bookings.count()}")

for b in paid_bookings:
    print(f"\nBooking: {b.id}")
    print(f"  Created At: {b.created_at}")
    print(f"  Created Date: {b.created_at.date()}")
    print(f"  Owner Payout: ₹{b.owner_payout}")

# Test the filter used in owner_revenue view
this_month_bookings = Booking.objects.filter(
    created_at__date__gte=month_start,
    created_at__date__lte=today,
    payment_status='PAID'
)

print("\n" + "=" * 60)
print("THIS MONTH'S FILTER RESULTS:")
print("=" * 60)
print(f"Bookings found: {this_month_bookings.count()}")

if this_month_bookings.count() > 0:
    total = this_month_bookings.aggregate(total=Sum('owner_payout'))['total']
    print(f"Total Revenue: ₹{total}")
    print("\n✅ Revenue page SHOULD show: ₹{:.2f}".format(total))
else:
    print("\n❌ No bookings found with current month filter!")
    print("\nChecking if booking date is outside current month...")
    
    for b in paid_bookings:
        booking_date = b.created_at.date()
        print(f"\nBooking date: {booking_date}")
        print(f"Month start: {month_start}")
        print(f"Today: {today}")
        print(f"Is in range? {month_start <= booking_date <= today}")
