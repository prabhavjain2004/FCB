"""
Check for potential Vercel deployment issues
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game

print("=" * 70)
print("VERCEL DEPLOYMENT READINESS CHECK")
print("=" * 70)

# Check all games for potential issues
games = Game.objects.filter(is_active=True)

print(f"\n📊 Found {games.count()} active games\n")

issues_found = []

for game in games:
    print(f"🎮 {game.name}")
    print(f"   Opening: {game.opening_time}")
    print(f"   Closing: {game.closing_time}")
    print(f"   Slot Duration: {game.slot_duration_minutes} min")
    
    # Calculate expected slots per day
    from datetime import datetime, timedelta, time as dt_time
    
    current = game.opening_time
    slot_count = 0
    max_iterations = 50  # Safety limit
    
    while current < game.closing_time and slot_count < max_iterations:
        start_dt = datetime.combine(datetime.today(), current)
        end_dt = start_dt + timedelta(minutes=game.slot_duration_minutes)
        end_time = end_dt.time()
        
        if end_time > game.closing_time:
            break
        
        # Check for wraparound
        if end_time < current:
            issues_found.append(f"{game.name}: Wraparound detected at {current}")
            print(f"   ⚠️  WRAPAROUND: Slot at {current} ends at {end_time} (next day)")
            break
        
        slot_count += 1
        current = end_time
    
    print(f"   Slots per day: {slot_count}")
    
    # Calculate generation time estimate
    days_to_generate = 2  # As configured
    total_slots = slot_count * days_to_generate
    estimated_time = total_slots * 0.05  # ~0.05 seconds per slot with overhead
    
    print(f"   Initial generation: {total_slots} slots (~{estimated_time:.1f}s)")
    
    if estimated_time > 8:
        issues_found.append(f"{game.name}: May timeout on Vercel ({estimated_time:.1f}s)")
        print(f"   ⚠️  WARNING: May timeout on Vercel!")
    else:
        print(f"   ✅ Should work on Vercel")
    
    print()

print("=" * 70)

if issues_found:
    print("⚠️  ISSUES FOUND:")
    for issue in issues_found:
        print(f"   - {issue}")
else:
    print("✅ NO ISSUES FOUND - READY FOR DEPLOYMENT!")

print("=" * 70)
