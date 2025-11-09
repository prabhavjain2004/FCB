"""
Automatic slot generation without cron jobs
Generates slots in the background without blocking users
"""
from datetime import date, timedelta
from django.core.cache import cache
from django.db.models import Max
from .models import Game, GameSlot
from .slot_generator import SlotGenerator
import logging
import threading

logger = logging.getLogger(__name__)


class AutoSlotGenerator:
    """Automatically generate slots in the background"""
    
    CACHE_KEY_PREFIX = 'last_slot_check_'
    DAYS_TO_MAINTAIN = 7  # Always maintain 7 days of slots ahead
    CHECK_INTERVAL = 3600  # Check once per hour (in seconds)
    
    @classmethod
    def ensure_slots_available(cls, game=None, async_mode=True):
        """
        Ensure slots are available for all active games or a specific game
        
        Args:
            game: Optional Game instance to check. If None, checks all active games.
            async_mode: If True, runs in background thread (non-blocking)
        """
        if async_mode:
            # Run in background thread - doesn't block the request
            thread = threading.Thread(
                target=cls._check_and_generate_slots,
                args=(game,),
                daemon=True
            )
            thread.start()
        else:
            # Run synchronously (for testing or manual triggers)
            cls._check_and_generate_slots(game)
    
    @classmethod
    def _check_and_generate_slots(cls, game=None):
        """Internal method to check and generate slots"""
        if game:
            games = [game]
        else:
            games = Game.objects.filter(is_active=True)
        
        for game_instance in games:
            cls._ensure_game_slots(game_instance)
    
    @classmethod
    def _ensure_game_slots(cls, game):
        """
        Ensure a specific game has slots for the next N days
        Uses caching ONLY to prevent slot generation overhead (once per hour)
        NOTE: This cache does NOT affect real-time data display - it only controls
        when new slots are generated in the background
        """
        cache_key = f"{cls.CACHE_KEY_PREFIX}{game.id}"
        last_check = cache.get(cache_key)
        
        # Only check once per hour to avoid overhead (doesn't affect real-time updates)
        if last_check:
            return
        
        try:
            # Find the furthest date we have slots for
            latest_slot = GameSlot.objects.filter(
                game=game,
                is_active=True
            ).aggregate(max_date=Max('date'))['max_date']
            
            target_date = date.today() + timedelta(days=cls.DAYS_TO_MAINTAIN)
            
            # If we don't have slots far enough, generate them
            if not latest_slot or latest_slot < target_date:
                start_date = latest_slot + timedelta(days=1) if latest_slot else date.today()
                end_date = target_date
                
                logger.info(f"🔄 Auto-generating slots for {game.name} from {start_date} to {end_date}")
                
                result = SlotGenerator.generate_slots_for_game(game, start_date, end_date)
                logger.info(f"✅ Created {result['created']} slots for {game.name}")
            
            # Cache for specified interval
            cache.set(cache_key, True, cls.CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Error auto-generating slots for {game.name}: {str(e)}")
    
    @classmethod
    def check_daily_generation(cls):
        """
        Check if we need to generate slots for today
        Call this in middleware on first request of the day
        NOTE: This cache does NOT affect real-time data display
        """
        today_key = f"daily_slot_check_{date.today()}"
        
        # Check if we've already run today (doesn't affect real-time updates)
        if cache.get(today_key):
            return False
        
        # Mark as checked for today (lasts 24 hours - doesn't affect real-time updates)
        cache.set(today_key, True, 86400)
        
        # Generate slots in background
        cls.ensure_slots_available(async_mode=True)
        
        return True
    
    @classmethod
    def force_generate_all(cls):
        """
        Force slot generation for all games (synchronous)
        Use for manual triggers or management commands
        """
        cls.ensure_slots_available(game=None, async_mode=False)


# Convenience functions
def auto_generate_slots_for_game(game, async_mode=True):
    """
    Auto-generate slots for a specific game
    
    Args:
        game: Game instance
        async_mode: If True, runs in background (default)
    """
    AutoSlotGenerator.ensure_slots_available(game, async_mode=async_mode)


def auto_generate_slots_all_games(async_mode=True):
    """
    Auto-generate slots for all active games
    
    Args:
        async_mode: If True, runs in background (default)
    """
    AutoSlotGenerator.ensure_slots_available(game=None, async_mode=async_mode)


def check_and_generate_daily_slots():
    """
    Check and generate slots once per day
    Call this in middleware or views
    """
    return AutoSlotGenerator.check_daily_generation()
