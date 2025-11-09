"""
Sitemap configuration for customer-facing pages
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static customer-facing pages"""
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        """Return list of customer-facing URL names"""
        return [
            'home',
            'about',
            'contact',
            'privacy',
            'terms',
            'refund_policy',
            'shipping_policy',
            'authentication:customer_login',
        ]

    def location(self, item):
        """Return the URL for each item"""
        return reverse(item)


class GamesSitemap(Sitemap):
    """Sitemap for games/booking pages"""
    priority = 0.9
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        """Return list of booking-related URL names"""
        return [
            'booking:game_selection',
        ]

    def location(self, item):
        """Return the URL for each item"""
        return reverse(item)
