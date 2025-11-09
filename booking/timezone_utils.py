"""
Timezone utility functions for consistent IST handling
"""
from django.utils import timezone
from django.conf import settings
import pytz


def get_local_now():
    """Get current datetime in local timezone (IST)"""
    local_tz = pytz.timezone(settings.TIME_ZONE)
    return timezone.now().astimezone(local_tz)


def get_local_today():
    """Get current date in local timezone (IST)"""
    return get_local_now().date()


def get_local_time():
    """Get current time in local timezone (IST)"""
    return get_local_now().time()
