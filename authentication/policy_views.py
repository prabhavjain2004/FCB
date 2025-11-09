"""Views for policy pages - Privacy, Terms, Refund, Contact, About"""
from django.shortcuts import render
from django.views.generic import TemplateView


class PrivacyPolicyView(TemplateView):
    """Privacy Policy page"""
    template_name = 'pages/privacy.html'


class TermsConditionsView(TemplateView):
    """Terms & Conditions page"""
    template_name = 'pages/terms.html'


class RefundPolicyView(TemplateView):
    """Refund & Cancellation Policy page"""
    template_name = 'pages/refund_policy.html'


class ContactView(TemplateView):
    """Contact Us page"""
    template_name = 'pages/contact.html'


class AboutView(TemplateView):
    """About Us page"""
    template_name = 'pages/about.html'


def privacy_policy_view(request):
    """Privacy policy view"""
    return render(request, 'pages/privacy.html')


def terms_conditions_view(request):
    """Terms and conditions view"""
    return render(request, 'pages/terms.html')


def refund_policy_view(request):
    """Refund policy view"""
    return render(request, 'pages/refund_policy.html')


def contact_view(request):
    """Contact us view"""
    return render(request, 'pages/contact.html')


def about_view(request):
    """About us view"""
    return render(request, 'pages/about.html')


def shipping_policy_view(request):
    """Shipping & Delivery policy view"""
    return render(request, 'pages/shipping_policy.html')
