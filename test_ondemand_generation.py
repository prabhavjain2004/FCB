"""
Test on-demand slot generation
Simulates a user browsing for Nov 20, 2025 slots
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from booking.slot_generator import SlotGenerator
from datetime import date, timedelta

print("🧪 Testing On-Demand Slot Generation")
print("=" * 70)

# Get a game
game = Game.objects.first()
if not game:
    print("❌ No games found!")
    exit(1)

print(f"\n📋 Game: {game.name}")
print(f"   Schedule: {game.opening_time} - {game.closing_time}")

# Test date: 6 days from now (beyond the 2-day auto-generation)
test_date = date.today() + timedelta(days=6)
print(f"\n📅 Test Date: {test_date} (6 days from now)")

# Check if slots exist
existing_count = GameSlot.objects.filter(game=game, date=test_date).count()
print(f"\n📊 Slots before on-demand generation: {existing_count}")

# Simulate user requesting this date
print(f"\n🎯 Simulating user browsing for {test_date}...")
print("   Calling SlotGenerator.ensure_slots_for_date()...")

import time
start_time = time.time()
success = SlotGenerator.ensure_slots_for_date(game, test_date)
end_time = time.time()

generation_time = (end_time - start_time) * 1000  # Convert to milliseconds

if success:
    print(f"✅ On-demand generation successful!")
    print(f"⚡ Generation time: {generation_time:.0f}ms")
else:
    print(f"❌ On-demand generation failed!")

# Check slots after
new_count = GameSlot.objects.filter(game=game, date=test_date).count()
print(f"\n📊 Slots after on-demand generation: {new_count}")

if new_count > existing_count:
    print(f"✨ Created {new_count - existing_count} new slots!")
    
    # Show the created slots
    slots = GameSlot.objects.filter(game=game, date=test_date).order_by('start_time')[:5]
    print(f"\n🎰 Sample slots for {test_date}:")
    for slot in slots:
        print(f"   • {slot.start_time} - {slot.end_time}")

# Test calling it again (should be instant)
print(f"\n🔄 Testing idempotency (calling again)...")
start_time = time.time()
SlotGenerator.ensure_slots_for_date(game, test_date)
end_time = time.time()
second_call_time = (end_time - start_time) * 1000

print(f"⚡ Second call time: {second_call_time:.0f}ms (should be instant)")

print("\n" + "=" * 70)
print("✅ On-demand generation test complete!")
