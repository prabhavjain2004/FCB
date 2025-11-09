"""
Django Admin configuration for QR Verification Audit
"""

from django.contrib import admin
from .models_qr_verification_audit import QRVerificationAttempt


@admin.register(QRVerificationAttempt)
class QRVerificationAttemptAdmin(admin.ModelAdmin):
    """Admin interface for QR verification audit trail"""
    
    list_display = [
        'timestamp',
        'booking',
        'attempt_type',
        'verified_by',
        'ip_address',
        'token_preview'
    ]
    
    list_filter = [
        'attempt_type',
        'timestamp',
        'verified_by'
    ]
    
    search_fields = [
        'booking__id',
        'token_used',
        'verified_by__username',
        'ip_address',
        'failure_reason'
    ]
    
    readonly_fields = [
        'booking',
        'token_used',
        'attempt_type',
        'verified_by',
        'ip_address',
        'user_agent',
        'failure_reason',
        'timestamp'
    ]
    
    date_hierarchy = 'timestamp'
    
    ordering = ['-timestamp']
    
    def token_preview(self, obj):
        """Show first 10 chars of token"""
        return f"{obj.token_used[:10]}..." if obj.token_used else "N/A"
    token_preview.short_description = 'Token'
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit records"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit records"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit records"""
        return False
