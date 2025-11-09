"""
Enhanced QR Code Verification Service with Security Features
- Token expiration
- Date/time validation
- Payment verification
- Rate limiting
- Audit trail
"""

import secrets
from django.utils import timezone
from datetime import timedelta, time
import logging

logger = logging.getLogger(__name__)


class QRCodeServiceEnhanced:
    """Enhanced service for generating and managing booking QR codes with security"""
    
    # Security constants
    MAX_VERIFICATION_ATTEMPTS = 5  # Max failed attempts before blocking
    RATE_LIMIT_WINDOW_MINUTES = 5  # Rate limit window
    MAX_ATTEMPTS_PER_WINDOW = 10  # Max attempts per user in window
    TOKEN_EXPIRY_HOURS = 24  # Token expires 24 hours after slot end
    VERIFICATION_TIME_WINDOW_MINUTES = 30  # Can verify 30 min before slot start
    
    @staticmethod
    def generate_verification_token():
        """Generate a cryptographically secure unique verification token"""
        return secrets.token_urlsafe(32)  # Generates ~43 character string
    
    @staticmethod
    def generate_qr_data(booking):
        """
        Generate QR code data string for a booking with token expiration
        
        Args:
            booking: Booking model instance
            
        Returns:
            str: QR code data string in format "booking_id|token|booking"
        """
        try:
            # Generate verification token if not exists or expired
            if not booking.verification_token or (
                booking.token_expires_at and timezone.now() >= booking.token_expires_at
            ):
                booking.verification_token = QRCodeServiceEnhanced.generate_verification_token()
                # Token expires 24 hours after booking slot ends
                booking.token_expires_at = booking.game_slot.end_datetime + timedelta(
                    hours=QRCodeServiceEnhanced.TOKEN_EXPIRY_HOURS
                )
                booking.save(update_fields=['verification_token', 'token_expires_at'])
            
            # Create QR code data string
            qr_data = f"{booking.id}|{booking.verification_token}|booking"
            
            logger.info(f"QR data generated for booking {booking.id}")
            return qr_data
            
        except Exception as e:
            logger.error(f"Error generating QR data for booking {booking.id}: {str(e)}")
            return None
    
    @staticmethod
    def verify_token(token, verified_by_user=None, request=None):
        """
        Verify a booking token with comprehensive security checks
        
        Args:
            token: Verification token from QR code
            verified_by_user: User attempting verification
            request: HTTP request object (for IP/user agent logging)
            
        Returns:
            tuple: (success: bool, booking: Booking or None, message: str, error_code: str)
        """
        from .models import Booking
        from .models_qr_verification_audit import QRVerificationAttempt
        
        # Extract IP and user agent for audit
        ip_address = None
        user_agent = ''
        if request:
            ip_address = QRCodeServiceEnhanced._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        try:
            # SECURITY CHECK 1: Rate limiting per user
            if verified_by_user:
                recent_attempts = QRVerificationAttempt.get_user_recent_attempts(
                    verified_by_user, 
                    minutes=QRCodeServiceEnhanced.RATE_LIMIT_WINDOW_MINUTES
                )
                
                if recent_attempts >= QRCodeServiceEnhanced.MAX_ATTEMPTS_PER_WINDOW:
                    QRVerificationAttempt.log_attempt(
                        booking=None,
                        token=token,
                        attempt_type='FAILED_RATE_LIMIT',
                        verified_by=verified_by_user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        failure_reason=f'Rate limit exceeded: {recent_attempts} attempts in {QRCodeServiceEnhanced.RATE_LIMIT_WINDOW_MINUTES} minutes'
                    )
                    logger.warning(f"Rate limit exceeded for user {verified_by_user.username}")
                    return False, None, "Too many verification attempts. Please wait a few minutes.", 'RATE_LIMIT'
            
            # SECURITY CHECK 2: Token lookup
            try:
                booking = Booking.objects.select_related(
                    'customer', 
                    'customer__user', 
                    'game', 
                    'game_slot'
                ).get(verification_token=token)
            except Booking.DoesNotExist:
                QRVerificationAttempt.log_attempt(
                    booking=None,
                    token=token,
                    attempt_type='FAILED_INVALID_TOKEN',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason='Token not found in database'
                )
                logger.warning(f"Invalid verification token attempted: {token[:10]}...")
                return False, None, "Invalid QR code or booking not found", 'INVALID_TOKEN'
            
            # Update last attempt timestamp
            booking.last_verification_attempt = timezone.now()
            
            # SECURITY CHECK 3: Token expiration
            if booking.token_expires_at and timezone.now() >= booking.token_expires_at:
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_EXPIRED_TOKEN',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Token expired at {booking.token_expires_at}'
                )
                return False, booking, "QR code has expired. Please contact support.", 'EXPIRED_TOKEN'
            
            # SECURITY CHECK 4: Payment verification
            if booking.payment_status != 'PAID' and booking.status != 'CONFIRMED':
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_UNPAID',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Payment status: {booking.payment_status}, Booking status: {booking.status}'
                )
                return False, booking, "Payment not completed for this booking", 'UNPAID'
            
            # SECURITY CHECK 5: Booking status validation
            if booking.status == 'CANCELLED':
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_CANCELLED',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason='Booking is cancelled'
                )
                return False, booking, "This booking has been cancelled", 'CANCELLED'
            
            if booking.status == 'COMPLETED':
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_COMPLETED',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason='Booking already completed'
                )
                return False, booking, "This booking has already been completed", 'COMPLETED'
            
            if booking.status not in ['CONFIRMED', 'IN_PROGRESS']:
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_INVALID_TOKEN',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Invalid booking status: {booking.status}'
                )
                return False, booking, f"Booking status is {booking.get_status_display()}", 'INVALID_STATUS'
            
            # SECURITY CHECK 6: Date validation (booking must be for today)
            booking_date = booking.game_slot.date
            today = timezone.localtime(timezone.now()).date()
            
            if booking_date != today:
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_WRONG_DATE',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Booking date: {booking_date}, Today: {today}'
                )
                
                if booking_date < today:
                    return False, booking, "This booking was for a past date", 'PAST_DATE'
                else:
                    return False, booking, f"This booking is for {booking_date.strftime('%B %d, %Y')}, not today", 'FUTURE_DATE'
            
            # SECURITY CHECK 7: Time validation (can verify 30 min before slot start)
            now_local = timezone.localtime(timezone.now())
            slot_start = booking.game_slot.start_datetime
            slot_start_local = timezone.localtime(slot_start)
            
            # Allow verification 30 minutes before slot start
            earliest_verification_time = slot_start_local - timedelta(
                minutes=QRCodeServiceEnhanced.VERIFICATION_TIME_WINDOW_MINUTES
            )
            
            if now_local < earliest_verification_time:
                booking.verification_attempts += 1
                booking.save(update_fields=['verification_attempts', 'last_verification_attempt'])
                
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_WRONG_TIME',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Too early. Slot starts at {slot_start_local}, can verify from {earliest_verification_time}'
                )
                
                time_until_slot = slot_start_local - now_local
                hours = int(time_until_slot.total_seconds() // 3600)
                minutes = int((time_until_slot.total_seconds() % 3600) // 60)
                
                return False, booking, f"Too early. Slot starts in {hours}h {minutes}m. You can verify 30 minutes before.", 'TOO_EARLY'
            
            # SECURITY CHECK 8: Already verified check
            if booking.is_verified:
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_ALREADY_VERIFIED',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Already verified at {booking.verified_at} by {booking.verified_by}'
                )
                return False, booking, "This booking has already been verified", 'ALREADY_VERIFIED'
            
            # SECURITY CHECK 9: Max failed attempts check
            if booking.verification_attempts >= QRCodeServiceEnhanced.MAX_VERIFICATION_ATTEMPTS:
                QRVerificationAttempt.log_attempt(
                    booking=booking,
                    token=token,
                    attempt_type='FAILED_RATE_LIMIT',
                    verified_by=verified_by_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    failure_reason=f'Max attempts exceeded: {booking.verification_attempts} attempts'
                )
                return False, booking, "Too many failed attempts. Please contact support.", 'MAX_ATTEMPTS'
            
            # All checks passed - log success
            QRVerificationAttempt.log_attempt(
                booking=booking,
                token=token,
                attempt_type='SUCCESS',
                verified_by=verified_by_user,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason=''
            )
            
            # Save last attempt timestamp
            booking.save(update_fields=['last_verification_attempt'])
            
            return True, booking, "Valid booking - ready for verification", 'SUCCESS'
            
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return False, None, "Verification error occurred", 'SYSTEM_ERROR'
    
    @staticmethod
    def mark_as_verified(booking, verified_by_user=None):
        """
        Mark booking as verified after successful QR scan
        
        Args:
            booking: Booking instance
            verified_by_user: User who verified (owner/staff)
            
        Returns:
            bool: True if successful
        """
        try:
            booking.is_verified = True
            booking.verified_at = timezone.now()
            booking.verified_by = verified_by_user
            
            # Update status to IN_PROGRESS if currently CONFIRMED
            if booking.status == 'CONFIRMED':
                booking.status = 'IN_PROGRESS'
            
            booking.save(update_fields=['is_verified', 'verified_at', 'verified_by', 'status'])
            
            logger.info(f"Booking {booking.id} marked as verified by {verified_by_user}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking booking as verified: {str(e)}")
            return False
    
    @staticmethod
    def regenerate_token(booking):
        """
        Regenerate verification token for a booking
        
        Args:
            booking: Booking instance
            
        Returns:
            bool: True if successful
        """
        try:
            # Generate new verification token
            booking.verification_token = QRCodeServiceEnhanced.generate_verification_token()
            booking.token_expires_at = booking.game_slot.end_datetime + timedelta(
                hours=QRCodeServiceEnhanced.TOKEN_EXPIRY_HOURS
            )
            booking.verification_attempts = 0  # Reset attempts
            booking.save(update_fields=['verification_token', 'token_expires_at', 'verification_attempts'])
            
            logger.info(f"Verification token regenerated for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error regenerating verification token: {str(e)}")
            return False
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
