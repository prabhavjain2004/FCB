from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.signals import pre_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from .models import Customer


@receiver(pre_social_login)
def create_customer_profile(sender, request, sociallogin, **kwargs):
    """
    Create Customer profile automatically when user signs in with Google OAuth
    """
    if sociallogin.account.provider == 'google':
        user = sociallogin.user
        
        # If user already exists, ensure they have a customer profile
        if user.pk:
            customer, created = Customer.objects.get_or_create(
                user=user,
                defaults={
                    'google_id': sociallogin.account.uid,
                    'avatar_url': sociallogin.account.extra_data.get('picture', ''),
                }
            )
            if not created and not customer.google_id:
                # Update existing customer with Google data
                customer.google_id = sociallogin.account.uid
                customer.avatar_url = sociallogin.account.extra_data.get('picture', '')
                customer.save()


@receiver(post_save, sender=User)
def create_customer_profile_post_save(sender, instance, created, **kwargs):
    """
    Create Customer profile for new users created via Google OAuth
    """
    if created:
        # Check if this user was created via Google OAuth
        social_accounts = SocialAccount.objects.filter(user=instance, provider='google')
        if social_accounts.exists():
            social_account = social_accounts.first()
            Customer.objects.get_or_create(
                user=instance,
                defaults={
                    'google_id': social_account.uid,
                    'avatar_url': social_account.extra_data.get('picture', ''),
                }
            )