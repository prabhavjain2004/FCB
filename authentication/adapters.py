from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .models import Customer


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter for handling Google OAuth authentication"""
    
    def pre_social_login(self, request, sociallogin):
        """Handle pre-login logic for social accounts"""
        if sociallogin.account.provider == 'google':
            # Check if user already exists with this email
            email = sociallogin.account.extra_data.get('email')
            if email:
                try:
                    from django.contrib.auth.models import User
                    existing_user = User.objects.get(email=email)
                    
                    # If user exists but doesn't have a social account, connect them
                    if not sociallogin.is_existing:
                        sociallogin.connect(request, existing_user)
                        
                except User.DoesNotExist:
                    pass
    
    def save_user(self, request, sociallogin, form=None):
        """Save user data from Google OAuth"""
        user = super().save_user(request, sociallogin, form)
        
        # Update user information from Google data
        extra_data = sociallogin.account.extra_data
        
        if not user.first_name and extra_data.get('given_name'):
            user.first_name = extra_data.get('given_name')
        
        if not user.last_name and extra_data.get('family_name'):
            user.last_name = extra_data.get('family_name')
            
        user.save()
        
        # Create customer profile for Google OAuth users
        Customer.objects.get_or_create(user=user)
        
        return user
    
    def get_login_redirect_url(self, request):
        """Redirect users to appropriate dashboard after Google login"""
        # Check for 'next' parameter first
        next_url = request.GET.get('next') or request.POST.get('next')
        
        if request.user.is_authenticated:
            # Ensure customer profile exists for Google OAuth users
            if not hasattr(request.user, 'customer_profile') and not hasattr(request.user, 'cafe_owner_profile') and not request.user.is_superuser:
                Customer.objects.get_or_create(user=request.user)
            
            # Check user role and redirect accordingly
            if request.user.is_superuser:
                return '/accounts/tapnex/dashboard/'
            elif hasattr(request.user, 'cafe_owner_profile'):
                return '/accounts/owner/dashboard/'
            elif hasattr(request.user, 'customer_profile'):
                # If there's a next URL, use it, otherwise go to dashboard
                return next_url if next_url else '/accounts/customer/dashboard/'
            else:
                # Fallback - create customer profile and redirect to dashboard
                Customer.objects.get_or_create(user=request.user)
                return next_url if next_url else '/accounts/customer/dashboard/'
        
        return '/accounts/customer/dashboard/'
    
    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """Handle authentication errors - redirect without showing messages"""
        # Don't show any error messages - the custom error page will handle it
        return redirect(reverse('authentication:customer_login'))


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter for account management"""
    
    def get_login_redirect_url(self, request):
        """Redirect users based on their role after manual login"""
        # Check for 'next' parameter first
        next_url = request.GET.get('next') or request.POST.get('next')
        
        if request.user.is_authenticated:
            # Check user role and redirect accordingly
            if request.user.is_superuser:
                return '/accounts/tapnex/dashboard/'
            elif hasattr(request.user, 'cafe_owner_profile'):
                return '/accounts/owner/dashboard/'
            elif hasattr(request.user, 'customer_profile'):
                # If there's a next URL, use it, otherwise go to dashboard
                return next_url if next_url else '/accounts/customer/dashboard/'
            else:
                # Fallback - create customer profile and redirect to dashboard
                Customer.objects.get_or_create(user=request.user)
                return next_url if next_url else '/accounts/customer/dashboard/'
        
        return '/accounts/customer/dashboard/'
    
    def add_message(self, request, level, message_tag, message, extra_tags=''):
        """Customize message display - ensure message is a string"""
        # Don't add login success messages from allauth - we'll handle them ourselves
        if message_tag == 'account/messages/logged_in.txt':
            return
        
        # Convert message to string if it's not already
        if not isinstance(message, str):
            # If it's a dict, skip it (likely a context dict from allauth)
            if isinstance(message, dict):
                return
            message = str(message)
        
        messages.add_message(request, level, message, extra_tags=extra_tags)