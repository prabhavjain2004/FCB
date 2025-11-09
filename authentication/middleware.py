import time
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware to handle session timeout for security.
    Logs out users after a period of inactivity.
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Get session timeout setting (default: 30 minutes)
            timeout = getattr(settings, 'SESSION_TIMEOUT', 1800)  # 30 minutes in seconds
            
            # Get last activity time from session
            last_activity = request.session.get('last_activity')
            current_time = time.time()
            
            if last_activity:
                # Check if session has timed out
                if current_time - last_activity > timeout:
                    # Session has timed out
                    logout(request)
                    messages.warning(request, 'Your session has expired due to inactivity. Please log in again.')
                    
                    # Redirect to appropriate login page
                    if request.path.startswith('/owner/') or request.path.startswith('/accounts/cafe-owner/'):
                        return redirect('authentication:cafe_owner_login')
                    else:
                        return redirect('authentication:customer_login')
            
            # Update last activity time
            request.session['last_activity'] = current_time
        
        return None


class AdminAccessMiddleware(MiddlewareMixin):
    """
    Middleware to block Django admin access completely.
    All users (including superusers) are redirected to custom dashboard.
    """
    
    def process_request(self, request):
        # Check if this is an admin URL - block completely
        if request.path.startswith('/admin/'):
            messages.warning(request, 'Django admin is disabled. Please use the TapNex custom dashboard.')
            
            # Redirect authenticated superusers to custom dashboard
            if request.user.is_authenticated and request.user.is_superuser:
                return redirect('authentication:tapnex_dashboard')
            
            # Redirect to appropriate area based on user role
            if request.user.is_authenticated:
                if hasattr(request.user, 'cafe_owner_profile'):
                    return redirect('authentication:cafe_owner_dashboard')
                elif hasattr(request.user, 'customer_profile'):
                    return redirect('authentication:customer_dashboard')
            
            # Not authenticated - redirect to staff login
            return redirect('authentication:cafe_owner_login')
        
        return None


class RoleBasedRedirectMiddleware(MiddlewareMixin):
    """
    Middleware to handle automatic role-based redirects for authenticated users
    accessing inappropriate areas.
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Define role-based URL patterns
            customer_urls = ['/customer/', '/accounts/login/']
            owner_urls = ['/owner/', '/accounts/cafe-owner/']
            
            # Check if customer is trying to access owner areas
            if any(request.path.startswith(url) for url in owner_urls):
                if hasattr(request.user, 'customer_profile') and not hasattr(request.user, 'cafe_owner_profile'):
                    if not request.user.is_superuser:
                        messages.info(request, 'Redirected to customer area.')
                        return redirect('authentication:customer_dashboard')
            
            # Check if owner is trying to access customer-specific areas
            elif any(request.path.startswith(url) for url in customer_urls):
                if hasattr(request.user, 'cafe_owner_profile') and not hasattr(request.user, 'customer_profile'):
                    if request.path == '/accounts/login/':  # Customer login page
                        messages.info(request, 'Redirected to owner dashboard.')
                        return redirect('authentication:cafe_owner_dashboard')
        
        return None