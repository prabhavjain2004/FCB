from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse


def customer_required(view_func):
    """
    Decorator that requires the user to be a customer.
    Redirects to appropriate login if not authenticated or not a customer.
    Preserves the 'next' parameter for redirect after login.
    """
    @wraps(view_func)
    @login_required(login_url='/accounts/login/')
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'customer_profile'):
            # If user is authenticated but not a customer, show access denied
            if request.user.is_authenticated:
                messages.error(request, 'Access denied. This area is for customers only.')
                if hasattr(request.user, 'cafe_owner_profile'):
                    return redirect('authentication:cafe_owner_dashboard')
                elif request.user.is_superuser:
                    return redirect('authentication:tapnex_dashboard')
                else:
                    # Redirect to customer login with next parameter
                    from django.http import QueryDict
                    next_url = request.get_full_path()
                    return redirect(f'/accounts/login/?next={next_url}')
            else:
                # User not authenticated - redirect to login with next parameter
                from django.http import QueryDict
                next_url = request.get_full_path()
                return redirect(f'/accounts/login/?next={next_url}')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def cafe_owner_required(view_func):
    """
    Decorator that requires the user to be a cafe owner.
    Redirects to appropriate login if not authenticated or not a cafe owner.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'cafe_owner_profile'):
            # If user is authenticated but not a cafe owner, show access denied
            if request.user.is_authenticated:
                messages.error(request, 'Access denied. This area is for cafe owners only.')
                if hasattr(request.user, 'customer_profile'):
                    return redirect('authentication:customer_dashboard')
                elif request.user.is_superuser:
                    return redirect('authentication:tapnex_dashboard')
                else:
                    return redirect('authentication:cafe_owner_login')
            else:
                return redirect('authentication:cafe_owner_login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator that requires the user to be a superuser.
    Shows 403 Forbidden if not a superuser.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'Access denied. Superuser privileges required.')
            # Redirect based on user type
            if hasattr(request.user, 'cafe_owner_profile'):
                return redirect('authentication:cafe_owner_dashboard')
            elif hasattr(request.user, 'customer_profile'):
                return redirect('authentication:customer_dashboard')
            else:
                return redirect('authentication:customer_login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_access_required(view_func):
    """
    Decorator that restricts Django admin access to superusers only.
    Redirects non-superusers to their appropriate dashboards.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authentication:cafe_owner_login')
        
        if not request.user.is_superuser:
            messages.warning(request, 'Django admin access is restricted to system administrators.')
            # Redirect to appropriate dashboard based on user role
            if hasattr(request.user, 'cafe_owner_profile'):
                return redirect('authentication:cafe_owner_dashboard')
            elif hasattr(request.user, 'customer_profile'):
                return redirect('authentication:customer_dashboard')
            else:
                return redirect('authentication:customer_login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class RoleBasedAccessMixin:
    """
    Mixin for class-based views to handle role-based access control.
    Preserves the 'next' parameter for redirect after login.
    """
    required_role = None  # 'customer', 'cafe_owner', or 'superuser'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Redirect to login with next parameter
            next_url = request.get_full_path()
            return redirect(f'/accounts/login/?next={next_url}')
        
        if self.required_role == 'customer':
            if not hasattr(request.user, 'customer_profile'):
                messages.error(request, 'Access denied. This area is for customers only.')
                return self._redirect_based_on_role(request)
        
        elif self.required_role == 'cafe_owner':
            if not hasattr(request.user, 'cafe_owner_profile'):
                messages.error(request, 'Access denied. This area is for cafe owners only.')
                return self._redirect_based_on_role(request)
        
        elif self.required_role == 'superuser':
            if not request.user.is_superuser:
                messages.error(request, 'Access denied. Superuser privileges required.')
                return self._redirect_based_on_role(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _redirect_based_on_role(self, request):
        """Redirect user to appropriate dashboard based on their role"""
        if request.user.is_superuser:
            return redirect('authentication:tapnex_dashboard')
        elif hasattr(request.user, 'cafe_owner_profile'):
            return redirect('authentication:cafe_owner_dashboard')
        elif hasattr(request.user, 'customer_profile'):
            return redirect('authentication:customer_dashboard')
        else:
            # Redirect to login with next parameter
            next_url = request.get_full_path()
            return redirect(f'/accounts/login/?next={next_url}')


def tapnex_superuser_required(view_func):
    """
    Decorator that requires the user to be a TapNex superuser.
    Checks for Django superuser status or TapNex superuser profile.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is Django superuser or has TapNex superuser profile
        if request.user.is_superuser or hasattr(request.user, 'tapnex_superuser_profile'):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, 'Access denied. TapNex administrator access required.')
            # Redirect based on user type
            if hasattr(request.user, 'cafe_owner_profile'):
                return redirect('authentication:cafe_owner_dashboard')
            elif hasattr(request.user, 'customer_profile'):
                return redirect('authentication:customer_dashboard')
            else:
                return redirect('/')
    return _wrapped_view


def cafe_staff_required(view_func):
    """
    Decorator that requires the user to be an active cafe staff member.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'cafe_staff_profile') and request.user.cafe_staff_profile.is_active:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, 'Access denied. This area is for cafe staff only.')
            # Redirect based on user type
            if hasattr(request.user, 'cafe_owner_profile'):
                return redirect('authentication:cafe_owner_dashboard')
            elif hasattr(request.user, 'customer_profile'):
                return redirect('authentication:customer_dashboard')
            elif request.user.is_superuser:
                return redirect('authentication:tapnex_dashboard')
            else:
                return redirect('authentication:cafe_owner_login')
    return _wrapped_view


def cafe_owner_or_staff_required(view_func):
    """
    Decorator that requires the user to be either a cafe owner or an active staff member.
    Used for QR scanning and booking verification.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is cafe owner
        if hasattr(request.user, 'cafe_owner_profile'):
            return view_func(request, *args, **kwargs)
        # Check if user is active staff
        elif hasattr(request.user, 'cafe_staff_profile') and request.user.cafe_staff_profile.is_active:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, 'Access denied. This area is for cafe owners and staff only.')
            # Redirect based on user type
            if hasattr(request.user, 'customer_profile'):
                return redirect('authentication:customer_dashboard')
            elif request.user.is_superuser:
                return redirect('authentication:tapnex_dashboard')
            else:
                return redirect('authentication:cafe_owner_login')
    return _wrapped_view