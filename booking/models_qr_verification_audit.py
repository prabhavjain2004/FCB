"""
QR Verification Audit Trail Model
Tracks all verification attempts for security monitoring
"""

from django.db import models
from django.conf import settings


class QRVerificationAttempt(models.Model):
    """Track all QR verification attempts (successful and failed)"""
    
    ATTEMPT_TYPES = [
        ('SUCCESS', 'Successful Verification'),
        ('FAILED_INVALID_TOKEN', 'Invalid Token'),
        ('FAILED_EXPIRED_TOKEN', 'Expired Token'),
        ('FAILED_WRONG_DATE', 'Wrong Date'),
        ('FAILED_WRONG_TIME', 'Wrong Time'),
        ('FAILED_UNPAID', 'Unpaid Booking'),
        ('FAILED_CANCELLED', 'Cancelled Booking'),
        ('FAILED_COMPLETED', 'Already Completed'),
        ('FAILED_ALREADY_VERIFIED', 'Already Verified'),
        ('FAILED_RATE_LIMIT', 'Rate Limit Exceeded'),
    ]
    
    booking = models.ForeignKey(
        'booking.Booking',  # Use string reference to avoid circular import
        on_delete=models.CASCADE,
        related_name='verification_attempts_log',
        null=True,
        blank=True,
        help_text='Booking being verified (null if token not found)'
    )
    token_used = models.CharField(
        max_length=100,
        help_text='Token that was attempted (first 20 chars for security)'
    )
    attempt_type = models.CharField(
        max_length=30,
        choices=ATTEMPT_TYPES,
        help_text='Type of verification attempt'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Use settings reference instead of direct import
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_verification_attempts',
        help_text='Owner/staff who attempted verification'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of verification attempt'
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text='User agent of verification attempt'
    )
    failure_reason = models.TextField(
        blank=True,
        help_text='Detailed reason for failure'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When the attempt was made'
    )
    
    class Meta:
        verbose_name = "QR Verification Attempt"
        verbose_name_plural = "QR Verification Attempts"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['booking', '-timestamp'], name='qr_attempt_booking_idx'),
            models.Index(fields=['attempt_type', '-timestamp'], name='qr_attempt_type_idx'),
            models.Index(fields=['verified_by', '-timestamp'], name='qr_attempt_user_idx'),
            models.Index(fields=['-timestamp'], name='qr_attempt_time_idx'),
        ]
    
    def __str__(self):
        return f"{self.get_attempt_type_display()} - {self.timestamp}"
    
    @classmethod
    def log_attempt(cls, booking, token, attempt_type, verified_by=None, 
                    ip_address=None, user_agent=None, failure_reason=''):
        """
        Log a verification attempt
        
        Args:
            booking: Booking instance (can be None if token not found)
            token: Verification token used
            attempt_type: Type of attempt (from ATTEMPT_TYPES)
            verified_by: User who attempted verification
            ip_address: IP address of request
            user_agent: User agent string
            failure_reason: Detailed failure reason
        """
        # Store only first 20 chars of token for security
        token_truncated = token[:20] if token else ''
        
        return cls.objects.create(
            booking=booking,
            token_used=token_truncated,
            attempt_type=attempt_type,
            verified_by=verified_by,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason
        )
    
    @classmethod
    def get_recent_failures(cls, booking, minutes=10):
        """Get recent failed attempts for a booking"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        
        return cls.objects.filter(
            booking=booking,
            timestamp__gte=cutoff_time,
            attempt_type__startswith='FAILED_'
        ).count()
    
    @classmethod
    def get_user_recent_attempts(cls, user, minutes=5):
        """Get recent attempts by a user (for rate limiting)"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        
        return cls.objects.filter(
            verified_by=user,
            timestamp__gte=cutoff_time
        ).count()
