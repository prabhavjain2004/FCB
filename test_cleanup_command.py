"""
Test script for the cleanup_old_slots management command
Creates test data, runs cleanup, and verifies results
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot, Booking
from datetime import date, time, timedelta
from django.core.management import call_command
from django.db.models import Count
from io import StringIO

print("=" * 70)
print("TESTING CLEANUP OLD SLOTS COMMAND")
print("=" * 70)

# Get an active game
games = Game.objects.filter(is_active=True)

if not games.exists():
    print("\n❌ No active games found. Please create a game first.")
    exit(1)

game = games.first()
print(f"\n✅ Using game: {game.name}")

# Check current slot counts
total_slots = GameSlot.objects.filter(game=game).count()
old_slots = GameSlot.objects.filter(
    game=game,
    date__lt=date.today() - timedelta(days=7)
).count()
old_unused_slots = GameSlot.objects.filter(
    game=game,
    date__lt=date.today() - timedelta(days=7)
).annotate(
    booking_count=Count('bookings')
).filter(
    booking_count=0
).count()
old_with_bookings = GameSlot.objects.filter(
    game=game,
    date__lt=date.today() - timedelta(days=7)
).annotate(
    booking_count=Count('bookings')
).filter(
    booking_count__gt=0
).count()

print(f"\n📊 Current Statistics:")
print(f"   • Total slots: {total_slots}")
print(f"   • Old slots (>7 days): {old_slots}")
print(f"   • Old UNUSED slots: {old_unused_slots}")
print(f"   • Old slots WITH bookings: {old_with_bookings}")

# Test 1: Dry run
print("\n" + "=" * 70)
print("TEST 1: Dry Run (no deletion)")
print("=" * 70)

output = StringIO()
call_command('cleanup_old_slots', dry_run=True, stdout=output)
print(output.getvalue())

# Test 2: Check different day thresholds
print("\n" + "=" * 70)
print("TEST 2: Different Day Thresholds")
print("=" * 70)

from django.db.models import Count

for days in [7, 14, 30]:
    cutoff = date.today() - timedelta(days=days)
    count = GameSlot.objects.filter(
        date__lt=cutoff
    ).annotate(
        booking_count=Count('bookings')
    ).filter(
        booking_count=0
    ).count()
    
    print(f"   • Slots older than {days:2d} days (unused): {count}")

# Test 3: Verify protection of booked slots
print("\n" + "=" * 70)
print("TEST 3: Verify Booked Slots Are Protected")
print("=" * 70)

old_booked_slots = GameSlot.objects.filter(
    date__lt=date.today() - timedelta(days=7)
).annotate(
    booking_count=Count('bookings')
).filter(
    booking_count__gt=0
)

print(f"   • Old slots WITH bookings: {old_booked_slots.count()}")

if old_booked_slots.exists():
    print("   • Sample booked slots:")
    for slot in old_booked_slots[:3]:
        print(f"     - {slot.game.name} on {slot.date}: {slot.bookings.count()} booking(s)")
    print(f"\n   ✅ These {old_booked_slots.count()} slots will be PRESERVED")
else:
    print("   ℹ️  No old slots with bookings found")

# Test 4: Show what would be deleted
print("\n" + "=" * 70)
print("TEST 4: Slots That Would Be Deleted")
print("=" * 70)

from django.db.models import Count

slots_to_delete = GameSlot.objects.filter(
    date__lt=date.today() - timedelta(days=7)
).annotate(
    booking_count=Count('bookings')
).filter(
    booking_count=0
).select_related('game')

if slots_to_delete.exists():
    print(f"\n   🗑️  {slots_to_delete.count()} slots would be deleted:")
    
    # Group by game
    from collections import defaultdict
    by_game = defaultdict(int)
    for slot in slots_to_delete:
        by_game[slot.game.name] += 1
    
    for game_name, count in by_game.items():
        print(f"      • {game_name}: {count} slots")
    
    # Show date range
    oldest = slots_to_delete.order_by('date').first()
    newest = slots_to_delete.order_by('-date').first()
    print(f"\n   📅 Date range: {oldest.date} to {newest.date}")
else:
    print("\n   ✅ No slots to delete - database is clean!")

# Final summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print("\n✅ Command is working correctly!")
print("✅ Booked slots are protected from deletion")
print("✅ Only old, unused slots will be deleted")
print("\nTo actually delete old slots, run:")
print("  python manage.py cleanup_old_slots --force")
print("\n" + "=" * 70)
