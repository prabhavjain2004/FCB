"""
URL configuration for gaming_cafe project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# Django admin is disabled - using custom TapNex superuser dashboard instead
# from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from authentication.views import home_view
from authentication.policy_views import (
    privacy_policy_view,
    terms_conditions_view,
    refund_policy_view,
    contact_view,
    about_view,
    shipping_policy_view
)
from django.views.generic import TemplateView, RedirectView
from .sitemaps import StaticViewSitemap, GamesSitemap
from .views import robots_txt

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
    'games': GamesSitemap,
}

urlpatterns = [
    # Django Admin is disabled - use /accounts/tapnex/dashboard/ instead
    # path('admin/', admin.site.urls),
    
    # URL Redirects for common paths (without /accounts/ prefix)
    path('customer/dashboard/', RedirectView.as_view(pattern_name='authentication:customer_dashboard', permanent=True)),
    path('owner/dashboard/', RedirectView.as_view(pattern_name='authentication:cafe_owner_dashboard', permanent=True)),
    
    # Redirect signup to login since Google OAuth handles both
    path('accounts/signup/', RedirectView.as_view(pattern_name='authentication:customer_login', permanent=False)),
    
    path('accounts/', include('authentication.urls')),
    path('accounts/', include('allauth.urls')),
    path('booking/', include('booking.urls')),
    path('api/', include('booking.api_urls')),  # REST API endpoints
    path('', home_view, name='home'),
    
    # Policy pages
    path('privacy/', privacy_policy_view, name='privacy'),
    path('terms/', terms_conditions_view, name='terms'),
    path('refund-policy/', refund_policy_view, name='refund_policy'),
    path('shipping-policy/', shipping_policy_view, name='shipping_policy'),
    path('contact/', contact_view, name='contact'),
    path('about/', about_view, name='about'),
    
    # SEO files
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
]

# Custom error handlers
handler404 = 'gaming_cafe.views.custom_404'
handler500 = 'gaming_cafe.views.custom_500'
handler403 = 'gaming_cafe.views.custom_403'

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)