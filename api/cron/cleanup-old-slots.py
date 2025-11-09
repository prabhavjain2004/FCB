"""
Vercel Cron API endpoint for cleaning up old slots
Called automatically every Tuesday at 2:00 AM by Vercel cron
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from django.core.management import call_command
from django.http import JsonResponse
from io import StringIO
import logging

logger = logging.getLogger(__name__)


def handler(request):
    """
    Vercel cron handler for cleanup_old_slots command
    
    Security:
    - Vercel cron jobs include a secret token in headers
    - Only POST requests from Vercel cron system
    """
    
    # Verify request is from Vercel cron (optional but recommended)
    cron_secret = request.headers.get('Authorization', '')
    expected_secret = os.getenv('CRON_SECRET', '')
    
    # If CRON_SECRET is set, verify it
    if expected_secret and cron_secret != f'Bearer {expected_secret}':
        logger.warning("Unauthorized cron request attempted")
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        # Capture command output
        output = StringIO()
        
        # Run the cleanup command
        # --force: Skip confirmation
        # --days 7: Delete slots older than 7 days
        call_command(
            'cleanup_old_slots',
            force=True,
            days=7,
            stdout=output,
            stderr=output
        )
        
        output_text = output.getvalue()
        
        logger.info(f"Cron cleanup executed successfully: {output_text[:200]}")
        
        return JsonResponse({
            'success': True,
            'message': 'Old slots cleaned up successfully',
            'timestamp': str(django.utils.timezone.now()),
            'output': output_text[:500]  # Limit output size
        })
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during cron cleanup: {error_msg}")
        
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'timestamp': str(django.utils.timezone.now())
        }, status=500)
