import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from django.db.models import Sum
from datetime import date
from django.utils import timezone

print("=" * 60)
print("DEBUGGING DATE FILTER")
print("=" * 60)

today = date.today()
month_start = today.replace(day=1)

print(f"\nFilter parameters:")
print(f"  month_start: {month_start} (type: {type(month_start)})")
print(f"  today: {today} (type: {type(today)})")

# Try different filter approaches
print("\n" + "-" * 60)
print("Test 1: Using created_at__date__gte and created_at__date__lte")
test1 = Booking.objects.filter(
    created_at__date__gte=month_start,
    created_at__date__lte=today,
    payment_status='PAID'
)
print(f"Results: {test1.count()}")

print("\n" + "-" * 60)
print("Test 2: Using created_at__gte and created_at__lte with datetime")
from datetime import datetime
month_start_dt = datetime.combine(month_start, datetime.min.time())
today_dt = datetime.combine(today, datetime.max.time())
month_start_dt = timezone.make_aware(month_start_dt)
today_dt = timezone.make_aware(today_dt)

test2 = Booking.objects.filter(
    created_at__gte=month_start_dt,
    created_at__lte=today_dt,
    payment_status='PAID'
)
print(f"Results: {test2.count()}")
if test2.count() > 0:
    total = test2.aggregate(total=Sum('owner_payout'))['total']
    print(f"Total Revenue: ₹{total}")

print("\n" + "-" * 60)
print("Test 3: Just payment_status='PAID'")
test3 = Booking.objects.filter(payment_status='PAID')
print(f"Results: {test3.count()}")
for b in test3:
    print(f"  Booking: {b.id}, Created: {b.created_at}, Payout: ₹{b.owner_payout}")

print("\n" + "-" * 60)
print("Test 4: Using date() method in Python")
all_paid = Booking.objects.filter(payment_status='PAID')
filtered_in_python = [b for b in all_paid if month_start <= b.created_at.date() <= today]
print(f"Results: {len(filtered_in_python)}")
if filtered_in_python:
    total = sum(b.owner_payout for b in filtered_in_python)
    print(f"Total Revenue: ₹{total}")
