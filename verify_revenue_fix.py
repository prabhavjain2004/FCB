"""
Verification script for revenue page fix
Run this to verify the revenue calculations are working correctly
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from authentication.models import TapNexSuperuser
from django.db.models import Sum, Count
from datetime import date, timedelta
from decimal import Decimal

print("=" * 60)
print("REVENUE PAGE FIX VERIFICATION")
print("=" * 60)

# Check TapNex settings
print("\n1. Checking TapNex Commission Settings...")
try:
    tapnex_user = TapNexSuperuser.objects.first()
    if tapnex_user:
        print(f"   ✓ Commission Rate: {tapnex_user.commission_rate}%")
        print(f"   ✓ Platform Fee: {tapnex_user.platform_fee} ({tapnex_user.platform_fee_type})")
    else:
        print("   ✗ No TapNex superuser found!")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Check total bookings
print("\n2. Checking Booking Data...")
total_bookings = Booking.objects.count()
paid_bookings = Booking.objects.filter(payment_status='PAID').count()
print(f"   ✓ Total Bookings: {total_bookings}")
print(f"   ✓ Paid Bookings: {paid_bookings}")

# Check revenue calculations
print("\n3. Checking Revenue Calculations...")
today = date.today()
month_start = today.replace(day=1)

# This month's data (using payment date - created_at)
this_month_bookings = Booking.objects.filter(
    created_at__date__gte=month_start,
    created_at__date__lte=today,
    payment_status='PAID'
)

total_revenue = this_month_bookings.aggregate(
    total=Sum('owner_payout')
)['total'] or Decimal('0.00')

total_bookings_count = this_month_bookings.count()

print(f"   ✓ This Month's Revenue (Owner): ₹{total_revenue}")
print(f"   ✓ This Month's Bookings: {total_bookings_count}")

# Booking type breakdown
private_count = this_month_bookings.filter(booking_type='PRIVATE').count()
shared_count = this_month_bookings.filter(booking_type='SHARED').count()
print(f"   ✓ Private Bookings: {private_count}")
print(f"   ✓ Shared Bookings: {shared_count}")

# Revenue by game
print("\n4. Checking Revenue by Game...")
revenue_by_game = this_month_bookings.values('game__name').annotate(
    total=Sum('owner_payout'),
    count=Count('id')
).order_by('-total')[:5]

for game in revenue_by_game:
    print(f"   ✓ {game['game__name']}: ₹{game['total']} ({game['count']} bookings)")

# All-time data
print("\n5. Checking All-Time Data...")
all_paid = Booking.objects.filter(payment_status='PAID')
all_time_revenue = all_paid.aggregate(total=Sum('owner_payout'))['total'] or Decimal('0.00')
print(f"   ✓ All-Time Revenue (Owner): ₹{all_time_revenue}")
print(f"   ✓ All-Time Paid Bookings: {all_paid.count()}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
print("\nNext Steps:")
print("1. Start the development server: python manage.py runserver")
print("2. Login as cafe owner")
print("3. Navigate to: http://localhost:8000/owner/revenue/")
print("4. Verify the revenue page shows correct data")
print("\nExpected Results:")
print(f"- Total Revenue should show: ₹{total_revenue} (for this month)")
print(f"- Total Bookings should show: {total_bookings_count}")
print(f"- Commission rate should display correctly")
print(f"- Revenue trend chart should display")
print(f"- Game breakdown table should show data")
