"""
Regenerate slots for all games to ensure midnight slots are created
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game
from datetime import date, timedelta

print("🔄 Regenerating slots for next 2 days...")
print("=" * 60)

for game in Game.objects.filter(is_active=True):
    print(f"\n🎮 {game.name}")
    # Regenerate using the model's method (which will use days_ahead=2)
    game.generate_slots(days_ahead=2)
    
    # Count slots
    today = date.today()
    for i in range(3):
        check_date = today + timedelta(days=i)
        count = game.slots.filter(date=check_date).count()
        print(f"   {check_date}: {count} slots")

print("\n" + "=" * 60)
print("✅ Regeneration complete!")
