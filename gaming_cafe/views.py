"""
Custom error handlers and utility views
"""
from django.shortcuts import render
from django.http import HttpResponse


def custom_404(request, exception):
    """Custom 404 error page"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 error page"""
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """Custom 403 error page"""
    return render(request, '403.html', status=403)


def robots_txt(request):
    """Serve robots.txt file"""
    return render(request, 'robots.txt', content_type='text/plain')
