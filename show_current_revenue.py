"""
Quick script to show current revenue status
Run this anytime to see what the revenue SHOULD be showing
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Booking
from django.db.models import Sum, Count, Q
from datetime import date
from decimal import Decimal

def format_currency(amount):
    """Format amount as currency"""
    return f"₹{amount:,.2f}"

print("\n" + "="*70)
print("CURRENT REVENUE STATUS")
print("="*70)

today = date.today()
print(f"\n📅 Date: {today.strftime('%B %d, %Y')}")

# Overview Page Stats
print("\n" + "-"*70)
print("OVERVIEW PAGE (Today's Stats)")
print("-"*70)

overview_stats = Booking.objects.filter(
    game_slot__date=today
).aggregate(
    revenue=Sum('owner_payout', filter=Q(payment_status='PAID')),
    total_bookings=Count('id', filter=Q(payment_status='PAID')),
    active_sessions=Count('id', filter=Q(status='IN_PROGRESS')),
    pending=Count('id', filter=Q(payment_status='PENDING'))
)

revenue = overview_stats['revenue'] or Decimal('0.00')
bookings = overview_stats['total_bookings'] or 0
active = overview_stats['active_sessions'] or 0
pending = overview_stats['pending'] or 0

print(f"\n💰 Today's Revenue:     {format_currency(revenue)}")
print(f"📊 Total Bookings:      {bookings}")
print(f"🎮 Active Sessions:     {active}")
print(f"⏳ Pending Payments:    {pending}")

# Revenue Page Stats (This Month)
print("\n" + "-"*70)
print("REVENUE PAGE (This Month)")
print("-"*70)

month_start = today.replace(day=1)
month_stats = Booking.objects.filter(
    created_at__date__gte=month_start,
    created_at__date__lte=today,
    payment_status='PAID'
).aggregate(
    revenue=Sum('owner_payout'),
    bookings=Count('id'),
    private=Count('id', filter=Q(booking_type='PRIVATE')),
    shared=Count('id', filter=Q(booking_type='SHARED'))
)

month_revenue = month_stats['revenue'] or Decimal('0.00')
month_bookings = month_stats['bookings'] or 0
private_count = month_stats['private'] or 0
shared_count = month_stats['shared'] or 0

print(f"\n💰 Total Revenue:       {format_currency(month_revenue)}")
print(f"📊 Total Bookings:      {month_bookings}")
print(f"🔒 Private Bookings:    {private_count}")
print(f"👥 Shared Bookings:     {shared_count}")

if month_bookings > 0:
    avg_value = month_revenue / month_bookings
    print(f"📈 Avg. Booking Value:  {format_currency(avg_value)}")

# Recent Bookings
print("\n" + "-"*70)
print("RECENT PAID BOOKINGS")
print("-"*70)

recent = Booking.objects.filter(
    payment_status='PAID'
).select_related('game', 'game_slot', 'customer__user').order_by('-created_at')[:5]

if recent.exists():
    for i, booking in enumerate(recent, 1):
        print(f"\n{i}. Booking #{str(booking.id)[:8]}...")
        print(f"   Game: {booking.game.name if booking.game else 'N/A'}")
        print(f"   Customer: {booking.customer.user.get_full_name() or booking.customer.user.username}")
        print(f"   Slot Date: {booking.game_slot.date if booking.game_slot else 'N/A'}")
        print(f"   Payment Date: {booking.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Status: {booking.status}")
        print(f"   Owner Payout: {format_currency(booking.owner_payout)}")
else:
    print("\n   No paid bookings found")

# Summary
print("\n" + "="*70)
print("WHAT YOU SHOULD SEE ON THE WEBSITE")
print("="*70)

print(f"\n✅ Overview Page → Today's Revenue: {format_currency(revenue)}")
print(f"✅ Overview Page → Total Bookings: {bookings}")
print(f"✅ Revenue Page → This Month: {format_currency(month_revenue)}")
print(f"✅ Revenue Page → Total Bookings: {month_bookings}")

if revenue == 0 and month_revenue == 0:
    print("\n⚠️  WARNING: No revenue to display!")
    print("   Possible reasons:")
    print("   - No bookings have been paid yet")
    print("   - All bookings are PENDING or EXPIRED")
    print("   - Bookings are for different dates")
else:
    print(f"\n✅ Revenue is being calculated correctly!")
    print(f"   If you see ₹0.00 on the website, it's a browser cache issue.")
    print(f"\n   Quick Fix:")
    print(f"   1. Press Ctrl+Shift+R to hard refresh")
    print(f"   2. Or clear browser cache completely")
    print(f"   3. Or try incognito mode")

print("\n" + "="*70 + "\n")
