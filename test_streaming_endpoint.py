"""
Test the streaming slot generation endpoint
This simulates what happens when you create a game in production
"""
import os
import django
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from django.test import RequestFactory
from booking.models import Game
from booking.game_management_views import generate_slots_with_progress
from authentication.models import CafeOwner
from django.contrib.auth.models import User


def test_streaming_endpoint():
    """Test the streaming slot generation endpoint"""
    
    print("=" * 70)
    print("STREAMING ENDPOINT TEST (EventSource)")
    print("=" * 70)
    
    # Find an active game
    games = Game.objects.filter(is_active=True)
    
    if not games.exists():
        print("❌ No active games found!")
        print("ℹ️  Please create a game first")
        return
    
    game = games.first()
    print(f"\n✅ Testing with game: {game.name} (ID: {game.id})")
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.get(f'/booking/games/manage/api/generate-slots/{game.id}/?days=2')
    
    # Add user to request (required by @cafe_owner_required decorator)
    if game.cafe_owner:
        request.user = game.cafe_owner.user
    else:
        print("❌ Game has no cafe owner!")
        return
    
    print(f"\n⏳ Calling streaming endpoint (days=2)...")
    print("   This simulates what happens when you create a game\n")
    
    try:
        # Call the view
        response = generate_slots_with_progress(request, game.id)
        
        # Check response type
        print(f"✅ Response type: {type(response).__name__}")
        print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")
        
        # Read the streaming response
        print("\n📊 Streaming output:")
        print("-" * 70)
        
        event_count = 0
        last_progress = 0
        total_slots = 0
        
        for chunk in response.streaming_content:
            chunk_str = chunk.decode('utf-8')
            
            # Parse SSE format
            if chunk_str.startswith('data: '):
                event_count += 1
                data_str = chunk_str[6:].strip()
                
                try:
                    import json
                    data = json.loads(data_str)
                    
                    progress = data.get('progress', 0)
                    status = data.get('status', '')
                    slots = data.get('slots_created', 0)
                    
                    # Only print when progress changes significantly
                    if progress > last_progress + 10 or progress == 100:
                        print(f"   [{progress:3d}%] {status}")
                        last_progress = progress
                    
                    if slots > total_slots:
                        total_slots = slots
                    
                    if data.get('complete'):
                        print("\n✅ Generation complete!")
                        break
                        
                except json.JSONDecodeError:
                    print(f"   ⚠️  Could not parse: {data_str[:50]}...")
        
        print("-" * 70)
        print(f"\n📈 RESULTS:")
        print(f"   - Total Events: {event_count}")
        print(f"   - Slots Created: {total_slots}")
        
        if total_slots > 0:
            print("\n✅ STREAMING ENDPOINT IS WORKING!")
        else:
            print("\n⚠️  NO SLOTS WERE CREATED")
            print("   The endpoint works but no slots were generated")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_streaming_endpoint()
