"""
Simulate actual game creation flow (what happens in production)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from booking.slot_generator import SlotGenerator
from datetime import date, timedelta, time
import time as time_module

print("=" * 70)
print("SIMULATING PRODUCTION GAME CREATION FLOW")
print("=" * 70)

# Get an existing game to simulate with
games = Game.objects.filter(is_active=True)

if not games.exists():
    print("\n❌ No active games found. Please create a game first.")
    exit(1)

game = games.first()

print(f"\n🎮 Game: {game.name}")
print(f"   Opening: {game.opening_time}")
print(f"   Closing: {game.closing_time}")
print(f"   Slot Duration: {game.slot_duration_minutes} min")

# Clean up existing future slots for clean test
print("\n🧹 Cleaning up old test data...")
test_start_date = date.today() + timedelta(days=60)
test_end_date = test_start_date + timedelta(days=1)

GameSlot.objects.filter(
    game=game,
    date__range=[test_start_date, test_end_date]
).delete()

print("\n" + "=" * 70)
print("STEP 1: Initial Slot Generation (2 days - like game creation)")
print("=" * 70)

start_time = time_module.time()

try:
    result = SlotGenerator.generate_slots_for_game(
        game,
        test_start_date,
        test_end_date
    )
    
    end_time = time_module.time()
    duration = end_time - start_time
    
    print(f"\n✅ Generation completed in {duration:.2f} seconds")
    print(f"   Slots Created: {result['created']}")
    print(f"   Slots Skipped: {result['skipped']}")
    
    if result['errors']:
        print(f"   ⚠️  Errors: {result['errors']}")
    
    # Verify in database
    db_count = GameSlot.objects.filter(
        game=game,
        date__range=[test_start_date, test_end_date]
    ).count()
    
    print(f"   Database Verification: {db_count} slots")
    
    if duration < 5:
        print(f"\n✅ PASS: Generation time ({duration:.2f}s) is under Vercel timeout")
    elif duration < 10:
        print(f"\n⚠️  WARNING: Generation time ({duration:.2f}s) is close to Vercel limit")
    else:
        print(f"\n❌ FAIL: Generation time ({duration:.2f}s) exceeds Vercel timeout")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("STEP 2: Auto-Generation Check (background)")
print("=" * 70)

# Test auto slot generator
from booking.auto_slot_generator import AutoSlotGenerator

print("\n⏳ Triggering auto-generation (async mode)...")

AutoSlotGenerator.ensure_slots_available(game, async_mode=False)

print("✅ Auto-generation triggered")

# Check if more slots were created
future_slots = GameSlot.objects.filter(
    game=game,
    date__gte=date.today()
).count()

print(f"   Total future slots now: {future_slots}")

print("\n" + "=" * 70)
print("SIMULATION RESULTS")
print("=" * 70)

print("\n✅ Game creation flow simulation complete!")
print("\nWhat happens in production:")
print("1. User creates game → Initial 2 days generated (fast!)")
print("2. Progress bar shows completion")
print("3. Background task generates remaining days")
print("4. User can immediately start booking")

print("\n" + "=" * 70)
