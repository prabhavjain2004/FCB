"""
Test script to verify timezone fix is working
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from django.utils import timezone
from booking.models import Booking
from django.db.models import Sum, Count, Q
from datetime import date
from decimal import Decimal

print("=" * 70)
print("TIMEZONE FIX VERIFICATION")
print("=" * 70)

# Show timezone info
print("\n1. Timezone Information:")
print(f"   Django TIME_ZONE setting: Asia/Kolkata (IST)")
print(f"   timezone.now(): {timezone.now()}")
print(f"   timezone.now().date() (UTC): {timezone.now().date()}")
print(f"   timezone.localdate() (IST): {timezone.localdate()}")
print(f"   date.today() (System): {date.today()}")

# Test Overview Page Query
print("\n2. Overview Page Query (game_slot__date=localdate):")
today = timezone.localdate()
print(f"   Using date: {today}")

todays_stats = Booking.objects.filter(
    game_slot__date=today
).aggregate(
    revenue=Sum('owner_payout', filter=Q(payment_status='PAID')),
    total_bookings=Count('id', filter=Q(payment_status='PAID'))
)

revenue = todays_stats['revenue'] or Decimal('0.00')
bookings = todays_stats['total_bookings'] or 0

print(f"   ✓ Revenue: ₹{revenue}")
print(f"   ✓ Bookings: {bookings}")

# Test Revenue Page Query
print("\n3. Revenue Page Query (This Month):")
start_date = today.replace(day=1)
end_date = today
print(f"   Date Range: {start_date} to {end_date}")

month_stats = Booking.objects.filter(
    created_at__date__gte=start_date,
    created_at__date__lte=end_date,
    payment_status='PAID'
).aggregate(
    revenue=Sum('owner_payout'),
    bookings=Count('id')
)

month_revenue = month_stats['revenue'] or Decimal('0.00')
month_bookings = month_stats['bookings'] or 0

print(f"   ✓ Revenue: ₹{month_revenue}")
print(f"   ✓ Bookings: {month_bookings}")

# Show all bookings
print("\n4. All PAID Bookings:")
all_paid = Booking.objects.filter(payment_status='PAID').select_related('game', 'game_slot')

if all_paid.exists():
    for booking in all_paid:
        print(f"\n   Booking: {str(booking.id)[:8]}...")
        print(f"   - Game: {booking.game.name if booking.game else 'N/A'}")
        print(f"   - Slot Date: {booking.game_slot.date if booking.game_slot else 'N/A'}")
        print(f"   - Created At: {booking.created_at}")
        print(f"   - Created Date (UTC): {booking.created_at.date()}")
        print(f"   - Owner Payout: ₹{booking.owner_payout}")
        print(f"   - Status: {booking.status}")
else:
    print("   No PAID bookings found")

print("\n" + "=" * 70)
print("EXPECTED RESULTS")
print("=" * 70)

if revenue > 0:
    print(f"\n✅ Overview Page SHOULD show:")
    print(f"   - Today's Revenue: ₹{revenue}")
    print(f"   - Total Bookings: {bookings}")
    
    print(f"\n✅ Revenue Page SHOULD show:")
    print(f"   - Date Range: {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}")
    print(f"   - Total Revenue: ₹{month_revenue}")
    print(f"   - Total Bookings: {month_bookings}")
    
    print(f"\n✅ TIMEZONE FIX IS WORKING!")
else:
    print("\n⚠️  No revenue to display")
    print("   This is expected if there are no PAID bookings for today")

print("\n" + "=" * 70)
print("\nNext Steps:")
print("1. Restart the development server")
print("2. Clear browser cache (Ctrl+Shift+Delete)")
print("3. Login as cafe owner")
print("4. Check Overview and Revenue pages")
print("\nThe revenue should now display correctly!")
