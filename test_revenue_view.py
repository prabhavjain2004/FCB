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
print("SIMULATING OWNER REVENUE VIEW")
print("=" * 60)

# Simulate the view logic
today = date.today()
period = 'month'  # Default period

if period == 'month':
    start_date = today.replace(day=1)
    end_date = today

print(f"\nPeriod: {period}")
print(f"Start Date: {start_date}")
print(f"End Date: {end_date}")

# Get commission settings
try:
    tapnex_user = TapNexSuperuser.objects.first()
    commission_rate = tapnex_user.commission_rate if tapnex_user and tapnex_user.commission_rate else Decimal('0.00')
    platform_fee = tapnex_user.platform_fee if tapnex_user and tapnex_user.platform_fee else Decimal('0.00')
    platform_fee_type = tapnex_user.platform_fee_type if tapnex_user else 'PERCENT'
    print(f"\nCommission Rate: {commission_rate}%")
    print(f"Platform Fee: {platform_fee} ({platform_fee_type})")
except:
    commission_rate = Decimal('0.00')
    platform_fee = Decimal('0.00')
    platform_fee_type = 'PERCENT'

# Base queryset
paid_bookings = Booking.objects.filter(
    created_at__date__gte=start_date,
    created_at__date__lte=end_date,
    payment_status='PAID'
)

print(f"\nPAID Bookings Found: {paid_bookings.count()}")

# Total revenue
total_revenue = paid_bookings.aggregate(
    total=Sum('owner_payout')
)['total'] or Decimal('0.00')

# Total bookings count
total_bookings = paid_bookings.count()

# Booking type breakdown
private_bookings = paid_bookings.filter(booking_type='PRIVATE')
shared_bookings = paid_bookings.filter(booking_type='SHARED')

private_revenue = private_bookings.aggregate(
    total=Sum('owner_payout')
)['total'] or Decimal('0.00')

shared_revenue = shared_bookings.aggregate(
    total=Sum('owner_payout')
)['total'] or Decimal('0.00')

print("\n" + "=" * 60)
print("REVENUE PAGE SHOULD SHOW:")
print("=" * 60)
print(f"\n✅ Total Revenue: ₹{total_revenue}")
print(f"✅ Total Bookings: {total_bookings}")
print(f"✅ Private Bookings: {private_bookings.count()} (₹{private_revenue})")
print(f"✅ Shared Bookings: {shared_bookings.count()} (₹{shared_revenue})")
print(f"✅ Commission Rate: {commission_rate}%")
print(f"✅ Platform Fee: {platform_fee} ({platform_fee_type})")

if total_bookings > 0:
    avg_value = total_revenue / total_bookings
    print(f"✅ Avg Booking Value: ₹{avg_value:.2f}")

print("\n" + "=" * 60)
if total_revenue > 0:
    print("✅ SUCCESS! Revenue page should display data correctly!")
else:
    print("❌ WARNING! Revenue is still ₹0.00")
print("=" * 60)
