"""
QR Code Generation Service for Booking Verification
Dynamic QR code generation - no file storage needed
"""

import secrets
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class QRCodeService:
    """Service for generating and managing booking QR codes"""
    
    @staticmethod
    def generate_verification_token():
        """Generate a secure unique verification token"""
        # Use secrets for cryptographically strong random token
        return secrets.token_urlsafe(32)  # Generates ~43 character string
    
    @staticmethod
    def generate_qr_data(booking):
        """
        Generate QR code data string for a booking (no file generation)
        
        Args:
            booking: Booking model instance
            
        Returns:
            str: QR code data string in format "booking_id|token|booking"
        """
        try:
            from datetime import timedelta
            
            # Generate verification token if not exists or expired
            if not booking.verification_token or (booking.token_expires_at and timezone.now() >= booking.token_expires_at):
                booking.verification_token = QRCodeService.generate_verification_token()
                # Token expires 24 hours after booking slot ends
                booking.token_expires_at = booking.game_slot.end_datetime + timedelta(hours=24)
                booking.save(update_fields=['verification_token', 'token_expires_at'])
            
            # Create QR code data string
            # Format: booking_id|verification_token|booking
            qr_data = f"{booking.id}|{booking.verification_token}|booking"
            
            logger.info(f"QR data generated for booking {booking.id}")
            return qr_data
            
        except Exception as e:
            logger.error(f"Error generating QR data for booking {booking.id}: {str(e)}")
            return None
    
    @staticmethod
    def generate_qr_code(booking):
        """
        Generate verification token for booking (backward compatibility)
        No longer generates actual QR code file - just ensures token exists
        
        Args:
            booking: Booking model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate verification token if not exists
            if not booking.verification_token:
                booking.verification_token = QRCodeService.generate_verification_token()
                booking.save(update_fields=['verification_token'])
            
            logger.info(f"Verification token ensured for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating verification token for booking {booking.id}: {str(e)}")
            return False
    
    @staticmethod
    def verify_token(token):
        """
        Verify a booking token from QR code scan
        
        Args:
            token: Verification token from QR code
            
        Returns:
            tuple: (success: bool, booking: Booking or None, message: str)
        """
        from .models import Booking
        
        try:
            # Fast database lookup using indexed field
            booking = Booking.objects.select_related(
                'customer', 
                'customer__user', 
                'game', 
                'game_slot'
            ).get(verification_token=token)
            
            # Check if booking is valid for verification
            if booking.status == 'CANCELLED':
                return False, booking, "This booking has been cancelled"
            
            if booking.status == 'COMPLETED':
                return False, booking, "This booking has already been completed"
            
            if booking.status != 'CONFIRMED' and booking.status != 'IN_PROGRESS':
                return False, booking, f"Booking status is {booking.get_status_display()}"
            
            # Check if already verified
            if booking.is_verified and booking.status == 'IN_PROGRESS':
                return True, booking, "Booking already verified and in progress"
            
            return True, booking, "Valid booking"
            
        except Booking.DoesNotExist:
            logger.warning(f"Invalid verification token attempted: {token[:10]}...")
            return False, None, "Invalid QR code or booking not found"
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return False, None, "Verification error occurred"
    
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
    def regenerate_qr_code(booking):
        """
        Regenerate verification token for a booking
        
        Args:
            booking: Booking instance
            
        Returns:
            bool: True if successful
        """
        try:
            # Generate new verification token
            booking.verification_token = QRCodeService.generate_verification_token()
            booking.save(update_fields=['verification_token'])
            
            logger.info(f"Verification token regenerated for booking {booking.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error regenerating verification token: {str(e)}")
            return False
