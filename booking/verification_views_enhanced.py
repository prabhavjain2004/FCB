"""
Enhanced QR Code Verification Views with Security Features
- Rate limiting
- Comprehensive validation
- Audit trail
- Minimal data exposure on failures
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from authentication.decorators import cafe_owner_or_staff_required
from .models import Booking
from .qr_service_enhanced import QRCodeServiceEnhanced
from .models_qr_verification_audit import QRVerificationAttempt
import json
import logging

logger = logging.getLogger(__name__)


def prepare_booking_data(booking, include_sensitive=True):
    """
    Helper function to prepare booking data for JSON response
    
    Args:
        booking: Booking instance
        include_sensitive: Whether to include sensitive customer data
    """
    # Determine payment status
    if booking.payment_status:
        payment_status = booking.payment_status.upper()
    elif booking.status == 'CONFIRMED' or booking.status == 'IN_PROGRESS':
        payment_status = 'PAID'
    else:
        payment_status = 'PENDING'
    
    # Get payment ID (prefer razorpay_payment_id, fallback to payment_id)
    payment_id = booking.razorpay_payment_id or booking.payment_id or 'N/A'
    
    # Base data (always included)
    data = {
        'id': str(booking.id),
        'game_name': booking.game.name if booking.game else booking.gaming_station.name if booking.gaming_station else 'Unknown',
        'date': timezone.localtime(booking.start_datetime).strftime('%A, %B %d, %Y') if booking.start_datetime else 'N/A',
        'start_time': timezone.localtime(booking.start_datetime).strftime('%I:%M %p') if booking.start_datetime else 'N/A',
        'end_time': timezone.localtime(booking.end_datetime).strftime('%I:%M %p') if booking.end_datetime else 'N/A',
        'booking_status': booking.get_status_display(),
        'status_code': booking.status,
        'is_verified': booking.is_verified,
    }
    
    # Sensitive data (only included if authorized)
    if include_sensitive:
        data.update({
            'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
            'customer_phone': booking.customer.phone if booking.customer.phone else 'N/A',
            'customer_email': booking.customer.user.email,
            'duration_hours': booking.duration_hours if booking.duration_hours else 0,
            'booking_type': booking.get_booking_type_display() if booking.booking_type else 'N/A',
            'spots_booked': booking.spots_booked if booking.spots_booked else 1,
            'total_amount': float(booking.total_amount) if booking.total_amount else 0,
            'payment_status': payment_status,
            'payment_id': payment_id,
            'verified_at': timezone.localtime(booking.verified_at).strftime('%I:%M %p, %A, %B %d, %Y') if booking.verified_at else None,
            'verified_by': booking.verified_by.get_full_name() if booking.verified_by else None,
        })
    
    return data


@cafe_owner_or_staff_required
def qr_scanner_view(request):
    """QR Scanner interface for owner/staff to verify bookings"""
    context = {
        'page_title': 'QR Code Scanner - Booking Verification',
    }
    return render(request, 'booking/qr_scanner.html', context)


@cafe_owner_or_staff_required
@require_http_methods(["POST"])
def verify_booking_qr(request):
    """
    Enhanced QR verification endpoint with comprehensive security checks
    
    POST /booking/verify-qr/
    Body: {
        "token": "verification_token_from_qr"
    }
    
    Returns:
        {
            "success": true/false,
            "message": "...",
            "error_code": "...",
            "booking": {...} (only on success or specific failures)
        }
    """
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        
        if not token:
            return JsonResponse({
                'success': False,
                'message': 'No verification token provided',
                'error_code': 'MISSING_TOKEN'
            }, status=400)
        
        # Parse token from QR code data (format: "booking_id|token|booking")
        try:
            parts = token.split('|')
            if len(parts) >= 2:
                verification_token = parts[1]
            else:
                verification_token = token  # Fallback if format is different
        except:
            verification_token = token
        
        # Verify token using enhanced service with all security checks
        is_valid, booking, message, error_code = QRCodeServiceEnhanced.verify_token(
            verification_token,
            verified_by_user=request.user,
            request=request
        )
        
        if not is_valid:
            # SECURITY: Don't expose sensitive booking data on failures
            # Only return booking data for specific error types
            booking_data = None
            
            if error_code in ['ALREADY_VERIFIED', 'COMPLETED'] and booking:
                # For already verified/completed, show limited data
                booking_data = prepare_booking_data(booking, include_sensitive=False)
            
            return JsonResponse({
                'success': False,
                'message': message,
                'error_code': error_code,
                'booking': booking_data
            })
        
        # Mark booking as verified
        QRCodeServiceEnhanced.mark_as_verified(booking, request.user)
        
        # Return full booking data on success
        return JsonResponse({
            'success': True,
            'message': 'Booking verified successfully!',
            'error_code': 'SUCCESS',
            'booking': prepare_booking_data(booking, include_sensitive=True)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data',
            'error_code': 'INVALID_JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error verifying QR code: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Verification error occurred',
            'error_code': 'SYSTEM_ERROR'
        }, status=500)


@cafe_owner_or_staff_required
@require_http_methods(["POST"])
def verify_booking_manual(request, booking_id):
    """
    Manual verification by booking ID with same security checks
    
    POST /booking/verify-manual/<booking_id>/
    """
    try:
        booking = Booking.objects.select_related(
            'customer', 
            'customer__user', 
            'game', 
            'game_slot'
        ).get(id=booking_id)
        
        # Use the same verification logic through the token
        if not booking.verification_token:
            return JsonResponse({
                'success': False,
                'message': 'This booking does not have a verification token',
                'error_code': 'NO_TOKEN'
            })
        
        # Verify using enhanced service
        is_valid, booking, message, error_code = QRCodeServiceEnhanced.verify_token(
            booking.verification_token,
            verified_by_user=request.user,
            request=request
        )
        
        if not is_valid:
            booking_data = None
            if error_code in ['ALREADY_VERIFIED', 'COMPLETED']:
                booking_data = prepare_booking_data(booking, include_sensitive=False)
            
            return JsonResponse({
                'success': False,
                'message': message,
                'error_code': error_code,
                'booking': booking_data
            })
        
        # Mark as verified
        QRCodeServiceEnhanced.mark_as_verified(booking, request.user)
        
        return JsonResponse({
            'success': True,
            'message': 'Booking verified successfully!',
            'error_code': 'SUCCESS',
            'booking': prepare_booking_data(booking, include_sensitive=True)
        })
        
    except Booking.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Booking not found with this ID',
            'error_code': 'NOT_FOUND'
        }, status=404)
    except Exception as e:
        logger.error(f"Error verifying booking manually: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Verification error occurred',
            'error_code': 'SYSTEM_ERROR'
        }, status=500)


@cafe_owner_or_staff_required
@require_http_methods(["POST"])
def complete_booking(request, booking_id):
    """
    Mark a verified booking as completed
    
    POST /booking/complete/<booking_id>/
    """
    try:
        booking = Booking.objects.get(id=booking_id)
        
        if not booking.is_verified:
            return JsonResponse({
                'success': False,
                'message': 'Booking must be verified before completion',
                'error_code': 'NOT_VERIFIED'
            }, status=400)
        
        if booking.status not in ['CONFIRMED', 'IN_PROGRESS']:
            return JsonResponse({
                'success': False,
                'message': f'Cannot complete booking with status {booking.get_status_display()}',
                'error_code': 'INVALID_STATUS'
            }, status=400)
        
        # Mark as completed
        booking.status = 'COMPLETED'
        booking.save(update_fields=['status'])
        
        logger.info(f"Booking {booking.id} marked as completed by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': 'Booking marked as completed',
            'error_code': 'SUCCESS'
        })
        
    except Booking.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Booking not found',
            'error_code': 'NOT_FOUND'
        }, status=404)
    except Exception as e:
        logger.error(f"Error completing booking: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error completing booking',
            'error_code': 'SYSTEM_ERROR'
        }, status=500)


@cafe_owner_or_staff_required
def active_bookings_view(request):
    """View all currently active/verified bookings for the day"""
    today = timezone.now().date()
    now = timezone.now()
    
    # Auto-update booking statuses before displaying
    from .booking_service import auto_update_bookings_status
    
    bookings_to_check = Booking.objects.filter(
        Q(game_slot__date=today) | Q(start_time__date=today),
        status__in=['PENDING', 'CONFIRMED', 'IN_PROGRESS']
    ).select_related('game_slot')
    
    auto_update_bookings_status(bookings_to_check)
    
    # Get all bookings for today that are confirmed or in progress
    active_bookings = Booking.objects.filter(
        Q(game_slot__date=today) | Q(start_time__date=today),
        status__in=['CONFIRMED', 'IN_PROGRESS']
    ).select_related(
        'customer', 
        'customer__user', 
        'game',
        'game_slot'
    ).order_by('-is_verified', 'game_slot__start_time')
    
    context = {
        'active_bookings': active_bookings,
        'today': today,
    }
    
    return render(request, 'booking/active_bookings.html', context)


@cafe_owner_or_staff_required
def verification_audit_log(request):
    """View verification audit log for security monitoring"""
    from datetime import timedelta
    
    # Get filter parameters
    days = int(request.GET.get('days', 7))
    attempt_type = request.GET.get('type', 'all')
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Query verification attempts
    attempts = QRVerificationAttempt.objects.filter(
        timestamp__gte=cutoff_date
    ).select_related('booking', 'verified_by')
    
    if attempt_type != 'all':
        attempts = attempts.filter(attempt_type=attempt_type)
    
    attempts = attempts.order_by('-timestamp')[:100]  # Limit to 100 recent
    
    # Get statistics
    total_attempts = attempts.count()
    successful = attempts.filter(attempt_type='SUCCESS').count()
    failed = total_attempts - successful
    
    context = {
        'attempts': attempts,
        'total_attempts': total_attempts,
        'successful': successful,
        'failed': failed,
        'days': days,
        'attempt_type': attempt_type,
    }
    
    return render(request, 'booking/verification_audit_log.html', context)
