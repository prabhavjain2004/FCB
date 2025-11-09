"""
Middleware to automatically maintain slot availability
Runs background checks without blocking requests
"""
from .auto_slot_generator import check_and_generate_daily_slots
import logging

logger = logging.getLogger(__name__)


class AutoSlotMaintenanceMiddleware:
    """
    Middleware that ensures slots are automatically generated
    Checks once per day on first request
    Runs in background - doesn't slow down user requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check and generate slots in background (once per day)
        # This doesn't block the request - runs in a separate thread
        try:
            check_and_generate_daily_slots()
        except Exception as e:
            # Don't let slot generation errors break the site
            logger.error(f"Error in auto slot maintenance: {str(e)}")
        
        # Process the request normally
        response = self.get_response(request)
        
        return response


class NoCacheMiddleware:
    """
    Middleware to disable all caching on owner and admin pages for real-time updates.
    Ensures that all data is always fresh and up-to-date.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Apply no-cache headers to owner, admin, and management pages
        owner_paths = [
            '/owner/',
            '/accounts/owner/',
            '/accounts/cafe-owner/',
            '/accounts/tapnex/',
            '/game-management/',
            '/booking/game-management/',
        ]
        
        # Check if current path matches any owner/admin paths
        if any(request.path.startswith(path) for path in owner_paths):
            # Disable all caching for real-time updates
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            # Additional headers to prevent caching
            response['X-Accel-Expires'] = '0'
            
            logger.debug(f"Applied no-cache headers to: {request.path}")
        
        return response
