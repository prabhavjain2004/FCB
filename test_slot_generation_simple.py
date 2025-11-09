"""
Simple and quick test for slot generation
Tests basic functionality without complex setup
"""
import os
import django
from datetime import date, time, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from booking.models import Game, GameSlot
from booking.slot_generator import SlotGenerator


def test_slot_generation():
    """Quick test to check if slot generation is working"""
    
    print("=" * 70)
    print("QUICK SLOT GENERATION TEST")
    print("=" * 70)
    
    # Find an active game
    games = Game.objects.filter(is_active=True)
    
    if not games.exists():
        print("❌ No active games found in database!")
        print("ℹ️  Please create a game first")
        return
    
    game = games.first()
    print(f"\n✅ Found game: {game.name}")
    print(f"   - Opening: {game.opening_time}")
    print(f"   - Closing: {game.closing_time}")
    print(f"   - Slot Duration: {game.slot_duration_minutes} min")
    print(f"   - Available Days: {len(game.available_days)} days")
    print(f"   - Capacity: {game.capacity}")
    
    # Check existing slots
    existing_slots = GameSlot.objects.filter(game=game).count()
    print(f"\n📊 Existing slots in database: {existing_slots}")
    
    # Test generation for a far future date (30 days ahead)
    test_date = date.today() + timedelta(days=30)
    
    print(f"\n🧪 Testing slot generation for: {test_date}")
    
    # Check if slots already exist for this date
    existing_for_date = GameSlot.objects.filter(
        game=game,
        date=test_date
    ).count()
    
    if existing_for_date > 0:
        print(f"⚠️  {existing_for_date} slots already exist for {test_date}")
        print("   Deleting existing slots for clean test...")
        GameSlot.objects.filter(game=game, date=test_date).delete()
    
    # Generate slots
    print("\n⏳ Generating slots...")
    
    try:
        result = SlotGenerator.generate_slots_for_game(
            game,
            test_date,
            test_date
        )
        
        print(f"\n📈 RESULTS:")
        print(f"   - Slots Created: {result['created']}")
        print(f"   - Slots Skipped: {result['skipped']}")
        print(f"   - Errors: {len(result['errors'])}")
        
        if result['errors']:
            print("\n❌ Errors found:")
            for error in result['errors']:
                print(f"   - {error}")
        
        # Verify in database
        db_count = GameSlot.objects.filter(
            game=game,
            date=test_date
        ).count()
        
        print(f"\n✅ Verification: {db_count} slots in database")
        
        if result['created'] > 0:
            print("\n✅ SLOT GENERATION IS WORKING!")
            
            # Show sample slots
            sample_slots = GameSlot.objects.filter(
                game=game,
                date=test_date
            ).order_by('start_time')[:5]
            
            print("\n📋 Sample slots:")
            for slot in sample_slots:
                print(f"   - {slot.start_time} to {slot.end_time}")
                
        else:
            print("\n❌ NO SLOTS WERE CREATED!")
            print("   Check the errors above for details")
            
    except Exception as e:
        print(f"\n❌ EXCEPTION OCCURRED: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_slot_generation()
