"""
Clean and regenerate ALL slots for next 2 days
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from booking.slot_generator import SlotGenerator
from datetime import date, timedelta

print("🧹 Cleaning and regenerating ALL slots...")
print("=" * 60)

today = date.today()
end_date = today + timedelta(days=2)

for game in Game.objects.filter(is_active=True):
    print(f"\n🎮 {game.name}")
    
    # Delete all empty slots for next 3 days
    deleted = GameSlot.objects.filter(
        game=game,
        date__range=[today, end_date],
        bookings__isnull=True
    ).delete()[0]
    print(f"   Deleted {deleted} empty slots")
    
    # Regenerate
    result = SlotGenerator.generate_slots_for_game(game, today, end_date)
    print(f"   Created {result['created']} new slots")
    
    # Verify
    for i in range(3):
        check_date = today + timedelta(days=i)
        count = game.slots.filter(date=check_date).count()
        slots = game.slots.filter(date=check_date).order_by('start_time')
        if slots.exists():
            first = slots.first()
            last = slots.last()
            print(f"   {check_date}: {count} slots ({first.start_time}-{last.end_time})")

print("\n" + "=" * 60)
print("✅ Complete! All games should now have 7 slots per day (17:00-00:00)")
