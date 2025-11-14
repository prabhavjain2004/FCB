"""
Cleanup script to remove wrong/old slots
- Deletes slots from old schedule (3 AM - 5 PM)
- Keeps slots with bookings
- Removes empty future slots
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from datetime import date, time

print("🧹 Starting slot cleanup...")
print("=" * 60)

for game in Game.objects.all():
    print(f"\n📋 Game: {game.name}")
    print(f"   Schedule: {game.opening_time} - {game.closing_time}")
    
    # Get all future slots for this game
    future_slots = game.slots.filter(date__gte=date.today())
    
    # Find slots that are OUTSIDE the game's schedule (wrong timing)
    wrong_time_slots = []
    for slot in future_slots:
        # Check if slot is outside the schedule
        # For overnight schedules (closing at 00:00), valid range is opening_time to 23:59
        if game.closing_time == time(0, 0):
            # Overnight: slots should be >= opening_time OR == 00:00 (midnight end)
            if slot.start_time < game.opening_time and slot.end_time != time(0, 0):
                wrong_time_slots.append(slot)
        else:
            # Same day: slots should be between opening and closing
            if slot.start_time < game.opening_time or slot.start_time >= game.closing_time:
                wrong_time_slots.append(slot)
    
    # Separate into with bookings vs without
    wrong_with_bookings = [s for s in wrong_time_slots if s.bookings.exists()]
    wrong_without_bookings = [s for s in wrong_time_slots if not s.bookings.exists()]
    
    # Get empty future slots (within correct schedule)
    correct_time_slots = future_slots.exclude(id__in=[s.id for s in wrong_time_slots])
    empty_correct_slots = correct_time_slots.filter(bookings__isnull=True)
    
    print(f"\n   📊 Analysis:")
    print(f"      Wrong timing slots with bookings: {len(wrong_with_bookings)} (KEEPING)")
    print(f"      Wrong timing slots without bookings: {len(wrong_without_bookings)} (DELETING)")
    print(f"      Correct timing empty slots: {empty_correct_slots.count()} (DELETING)")
    
    # Delete wrong timing slots without bookings
    if wrong_without_bookings:
        print(f"\n   🗑️  Deleting {len(wrong_without_bookings)} wrong timing slots:")
        for slot in wrong_without_bookings[:5]:  # Show first 5
            print(f"      - {slot.date} {slot.start_time}-{slot.end_time}")
        if len(wrong_without_bookings) > 5:
            print(f"      ... and {len(wrong_without_bookings) - 5} more")
        
        deleted_count = 0
        for slot in wrong_without_bookings:
            slot.delete()
            deleted_count += 1
        print(f"   ✅ Deleted {deleted_count} wrong slots")
    
    # Delete empty slots (keep only next 2 days)
    today = date.today()
    from datetime import timedelta
    cutoff_date = today + timedelta(days=2)
    
    empty_beyond_2days = empty_correct_slots.filter(date__gt=cutoff_date)
    if empty_beyond_2days.exists():
        count = empty_beyond_2days.count()
        print(f"\n   🗑️  Deleting {count} empty slots beyond 2 days")
        empty_beyond_2days.delete()
        print(f"   ✅ Deleted {count} slots")

print("\n" + "=" * 60)
print("✅ Cleanup complete!")
print("\nRunning verification...")

# Verify
for game in Game.objects.all():
    today_slots = game.slots.filter(date=date.today()).order_by('start_time')[:5]
    print(f"\n{game.name} - Today's first 5 slots:")
    for slot in today_slots:
        has_booking = "📚" if slot.bookings.exists() else "⭕"
        print(f"  {has_booking} {slot.start_time} - {slot.end_time}")
