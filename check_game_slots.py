import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from datetime import date

game = Game.objects.first()
if game:
    print(f'Game: {game.name}')
    print(f'Opening: {game.opening_time}')
    print(f'Closing: {game.closing_time}')
    print(f'Duration: {game.slot_duration_minutes} minutes')
    print(f'\nSlots for today and tomorrow:')
    for slot in game.slots.filter(date__gte=date.today()).order_by('date', 'start_time')[:15]:
        print(f'  {slot.date} {slot.start_time} - {slot.end_time}')
else:
    print('No games found')
