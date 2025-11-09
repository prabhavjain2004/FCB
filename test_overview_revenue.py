"""
Test script to verify overview page revenue calculation
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from django.db.models import Sum, Count, Q
from datetime import date
from decimal import Decimal

print("=" * 70)
print("OVERVIEW PAGE REVENUE TEST")
print("=" * 70)

today = date.today()
print(f"\nToday's Date: {today}")

# Test the exact query used in owner_overview view
print("\n1. Testing Overview Page Query (game_slot__date=today)...")
todays_stats = Booking.objects.filter(
    game_slot__date=today
).aggregate(
    revenue=Sum('owner_payout', filter=Q(payment_status='PAID')),
    total_bookings=Count('id', filter=Q(payment_status='PAID')),
    customers_today=Count('customer', distinct=True, filter=Q(payment_status='PAID')),
    cancelled_today=Count('id', filter=Q(status='CANCELLED'))
)

todays_revenue = todays_stats['revenue'] or Decimal('0.00')
total_bookings_today = todays_stats['total_bookings'] or 0

print(f"   ✓ Today's Revenue: ₹{todays_revenue}")
print(f"   ✓ Total Bookings Today: {total_bookings_today}")
print(f"   ✓ Customers Today: {todays_stats['customers_today'] or 0}")
print(f"   ✓ Cancelled Today: {todays_stats['cancelled_today'] or 0}")

# List all bookings for today
print("\n2. All Bookings for Today...")
todays_bookings = Booking.objects.filter(game_slot__date=today)
print(f"   Total bookings (all statuses): {todays_bookings.count()}")

for booking in todays_bookings:
    print(f"\n   Booking ID: {str(booking.id)[:8]}...")
    print(f"   - Game: {booking.game.name if booking.game else 'N/A'}")
    print(f"   - Slot Date: {booking.game_slot.date if booking.game_slot else 'N/A'}")
    print(f"   - Status: {booking.status}")
    print(f"   - Payment Status: {booking.payment_status}")
    print(f"   - Owner Payout: ₹{booking.owner_payout}")
    print(f"   - Subtotal: ₹{booking.subtotal}")
    print(f"   - Total Amount: ₹{booking.total_amount}")
    print(f"   - Created At: {booking.created_at}")

# Check if there are any bookings with NULL owner_payout
print("\n3. Checking for NULL owner_payout values...")
null_payout_bookings = Booking.objects.filter(
    game_slot__date=today,
    payment_status='PAID',
    owner_payout__isnull=True
)
if null_payout_bookings.exists():
    print(f"   ⚠ WARNING: {null_payout_bookings.count()} PAID bookings have NULL owner_payout!")
    for booking in null_payout_bookings:
        print(f"   - Booking {str(booking.id)[:8]}: owner_payout is NULL")
else:
    print("   ✓ All PAID bookings have owner_payout values")

# Check if there are any bookings with 0 owner_payout
print("\n4. Checking for ZERO owner_payout values...")
zero_payout_bookings = Booking.objects.filter(
    game_slot__date=today,
    payment_status='PAID',
    owner_payout=0
)
if zero_payout_bookings.exists():
    print(f"   ⚠ WARNING: {zero_payout_bookings.count()} PAID bookings have ZERO owner_payout!")
    for booking in zero_payout_bookings:
        print(f"   - Booking {str(booking.id)[:8]}: owner_payout is 0")
else:
    print("   ✓ No PAID bookings with zero owner_payout")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)

if todays_revenue > 0:
    print(f"\n✅ SUCCESS: Overview page SHOULD show ₹{todays_revenue}")
    print(f"✅ SUCCESS: Overview page SHOULD show {total_bookings_today} booking(s)")
else:
    print("\n⚠ WARNING: Revenue is ₹0.00")
    print("   Possible reasons:")
    print("   1. No PAID bookings for today")
    print("   2. All bookings have NULL or ZERO owner_payout")
    print("   3. Bookings exist but game_slot__date doesn't match today")

print("\nTo test the overview page:")
print("1. Start server: python manage.py runserver")
print("2. Login as cafe owner")
print("3. Go to: http://localhost:8000/owner/overview/")
print("4. Check if revenue matches the value above")
print("\nIf revenue still shows ₹0.00 on the page:")
print("- Clear browser cache (Ctrl+Shift+Delete)")
print("- Try incognito/private browsing mode")
print("- Check browser console for JavaScript errors (F12)")
