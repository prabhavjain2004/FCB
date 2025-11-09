"""
QR Code Verification Views for Owner/Staff
Fast verification endpoints and scanner interface
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from authentication.decorators import cafe_owner_required
from .models import Booking
from .qr_service import QRCodeService
import json
import logging

logger = logging.getLogger(__name__)


def prepare_booking_data(booking):
    """
    Helper function to prepare booking data for JSON response
    Handles timezone conversion and payment status
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
    
    return {
        'id': str(booking.id),
        'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
        'customer_phone': booking.customer.phone if booking.customer.phone else 'N/A',
        'customer_email': booking.customer.user.email,
        'game_name': booking.game.name if booking.game else booking.gaming_station.name if booking.gaming_station else 'Unknown',
        'date': timezone.localtime(booking.start_datetime).strftime('%A, %B %d, %Y') if booking.start_datetime else 'N/A',
        'start_time': timezone.localtime(booking.start_datetime).strftime('%I:%M %p') if booking.start_datetime else 'N/A',
        'end_time': timezone.localtime(booking.end_datetime).strftime('%I:%M %p') if booking.end_datetime else 'N/A',
        'duration_hours': booking.duration_hours if booking.duration_hours else 0,
        'booking_status': booking.get_status_display(),
        'status_code': booking.status,
        'booking_type': booking.get_booking_type_display() if booking.booking_type else 'N/A',
        'spots_booked': booking.spots_booked if booking.spots_booked else 1,
        'total_amount': float(booking.total_amount) if booking.total_amount else 0,
        'payment_status': payment_status,
        'payment_id': payment_id,
        'is_verified': booking.is_verified,
        'verified_at': timezone.localtime(booking.verified_at).strftime('%I:%M %p, %A, %B %d, %Y') if booking.verified_at else None,
        'verified_by': booking.verified_by.get_full_name() if booking.verified_by else None,
    }


@cafe_owner_required
def qr_scanner_view(request):
    """
    QR Scanner interface for owner/staff to verify bookings
    """
    context = {
        'page_title': 'QR Code Scanner - Booking Verification',
    }
    return render(request, 'booking/qr_scanner.html', context)


@cafe_owner_required
@require_http_methods(["POST"])
def verify_booking_manual(request, booking_id):
    """
    Manual verification by booking ID
    
    POST /booking/verify-manual/<booking_id>/
    """
    try:
        booking = Booking.objects.select_related(
            'customer', 
            'customer__user', 
            'game', 
            'game_slot'
        ).get(id=booking_id)
        
        # Check if booking is valid for verification
        if booking.status == 'CANCELLED':
            return JsonResponse({
                'success': False,
                'message': "This booking has been cancelled",
                'booking': None
            })
        
        if booking.status == 'COMPLETED':
            return JsonResponse({
                'success': False,
                'message': "This booking has already been completed",
                'booking': None
            })
        
        if booking.status not in ['CONFIRMED', 'IN_PROGRESS']:
            return JsonResponse({
                'success': False,
                'message': f"Booking status is {booking.get_status_display()}",
                'booking': None
            })
        
        # Check if already verified - prevent duplicate scans
        if booking.is_verified:
            return JsonResponse({
                'success': False,
                'message': 'This booking has already been verified',
                'booking': None,
                'already_verified': True
            })
        
        # Mark booking as verified
        QRCodeService.mark_as_verified(booking, request.user)
        message = "Booking verified successfully!"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'booking': prepare_booking_data(booking)
        })
        
    except Booking.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Booking not found with this ID'
        }, status=404)
    except Exception as e:
        logger.error(f"Error verifying booking manually: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Verification error occurred'
        }, status=500)


@cafe_owner_required
@require_http_methods(["POST"])
def verify_booking_qr(request):
    """
    Fast API endpoint to verify booking via QR code token
    
    POST /booking/verify-qr/
    Body: {
        "token": "verification_token_from_qr"
    }
    
    Returns:
        {
            "success": true/false,
            "message": "...",
            "booking": {
                "id": "...",
                "customer_name": "...",
                "customer_phone": "...",
                "game_name": "...",
                "date": "...",
                "time": "...",
                "status": "...",
                "spots_booked": 1,
                "total_amount": 500,
                "is_verified": true/false,
                "verified_at": "...",
            }
        }
    """
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        
        if not token:
            return JsonResponse({
                'success': False,
                'message': 'No verification token provided'
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
        
        # Verify token using QR service
        is_valid, booking, message = QRCodeService.verify_token(verification_token)
        
        if not is_valid:
            return JsonResponse({
                'success': False,
                'message': message,
                'booking': None
            })
        
        # Prepare booking data for response
        booking_data = prepare_booking_data(booking)
        
        # Check if already verified - prevent duplicate scans but return booking data
        if booking.is_verified:
            return JsonResponse({
                'success': False,
                'message': 'This booking has already been scanned and verified',
                'booking': booking_data,
                'already_verified': True
            })
        
        # Mark booking as verified
        QRCodeService.mark_as_verified(booking, request.user)
        message = "Booking verified successfully!"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'booking': prepare_booking_data(booking)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error verifying QR code: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Verification error occurred'
        }, status=500)


@cafe_owner_required
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
                'message': 'Booking must be verified before completion'
            }, status=400)
        
        if booking.status not in ['CONFIRMED', 'IN_PROGRESS']:
            return JsonResponse({
                'success': False,
                'message': f'Cannot complete booking with status {booking.get_status_display()}'
            }, status=400)
        
        # Mark as completed
        booking.status = 'COMPLETED'
        booking.save(update_fields=['status'])
        
        return JsonResponse({
            'success': True,
            'message': 'Booking marked as completed'
        })
        
    except Booking.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Booking not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error completing booking: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error completing booking'
        }, status=500)


@cafe_owner_required
def active_bookings_view(request):
    """
    View all currently active/verified bookings for the day
    """
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
