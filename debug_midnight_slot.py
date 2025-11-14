"""
Debug why midnight slot isn't being created
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from booking.slot_generator import SlotGenerator
from datetime import date, timedelta

# Delete today's slots
game = Game.objects.first()
today = date.today()

print(f"Deleting today's slots for {game.name}...")
GameSlot.objects.filter(game=game, date=today).delete()

print(f"\nRegenerating slots...")
created = SlotGenerator._generate_slots_for_date(game, today)
print(f"Created {created} slots")

print(f"\nToday's slots:")
slots = GameSlot.objects.filter(game=game, date=today).order_by('start_time')
for slot in slots:
    print(f"  {slot.start_time} - {slot.end_time}")

print(f"\nTotal: {slots.count()} slots")
print(f"Expected: 7 slots (17:00-18:00, 18:00-19:00, 19:00-20:00, 20:00-21:00, 21:00-22:00, 22:00-23:00, 23:00-00:00)")
