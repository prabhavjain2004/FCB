"""
Payment Views for Razorpay Integration
Handles order creation, payment verification, and webhooks
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from authentication.decorators import customer_required
from .models import Booking
from .razorpay_service import razorpay_service
from .booking_service import BookingService
from .qr_service_enhanced import QRCodeServiceEnhanced as QRCodeService  # Use enhanced version
import json
import logging

logger = logging.getLogger(__name__)


@customer_required
@require_http_methods(["POST"])
def create_razorpay_order(request, booking_id):
    """
    Create a Razorpay order for a booking with payment split configuration
    
    POST /booking/payment/create-order/<booking_id>/
    """
    try:
        from authentication.models import TapNexSuperuser, CafeOwner
        
        # Get booking
        booking = get_object_or_404(
            Booking, 
            id=booking_id, 
            customer=request.user.customer_profile
        )
        
        # Verify booking is pending
        if booking.status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': 'Booking is not in pending status'
            }, status=400)
        
        # Get TapNex settings for commission/platform fee rates
        tapnex_user = TapNexSuperuser.objects.first()
        if not tapnex_user:
            logger.error("TapNex superuser not found - commission and platform fee must be configured")
            return JsonResponse({
                'success': False,
                'error': 'System configuration error: Commission rates not configured. Please contact administrator.'
            }, status=500)
        
        # Get commission and platform fee rates from superuser settings
        commission_rate = float(tapnex_user.commission_rate)
        
        if tapnex_user.platform_fee_type == 'PERCENT':
            platform_fee_rate = float(tapnex_user.platform_fee)
        else:
            # For FIXED type, pass the fixed amount directly
            platform_fee_rate = float(tapnex_user.platform_fee)
        
        # Calculate payment split
        split = razorpay_service.calculate_payment_split(
            booking.subtotal,  # Base booking amount
            commission_rate=commission_rate,  # From superuser settings
            platform_fee_rate=platform_fee_rate,  # From superuser settings
            platform_fee_type=tapnex_user.platform_fee_type
        )
        
        # Update booking with calculated amounts
        booking.platform_fee = split['platform_fee']
        booking.total_amount = split['total_charged']  # What user pays
        booking.commission_amount = split['commission']  # Commission deducted
        booking.owner_payout = split['owner_payout']  # What owner receives
        booking.save(update_fields=['platform_fee', 'total_amount', 'commission_amount', 'owner_payout'])
        
        # Get cafe owner's Razorpay account (if configured)
        cafe_owner = CafeOwner.objects.first()
        owner_account_id = None
        if cafe_owner and cafe_owner.razorpay_account_id:
            owner_account_id = cafe_owner.razorpay_account_id
            logger.info(f"Using Razorpay account {owner_account_id} for transfer")
        
        # Create Razorpay order (with transfer if account configured)
        order_result = razorpay_service.create_order_with_transfer(booking, owner_account_id)
        
        if not order_result['success']:
            return JsonResponse({
                'success': False,
                'error': order_result.get('error', 'Failed to create order')
            }, status=500)
        
        # Save order ID to booking
        booking.razorpay_order_id = order_result['order_id']
        booking.save(update_fields=['razorpay_order_id'])
        
        # Return order details for frontend
        return JsonResponse({
            'success': True,
            'order_id': order_result['order_id'],
            'amount': order_result['amount'],
            'currency': order_result['currency'],
            'key': settings.RAZORPAY_KEY_ID,
            'booking_id': str(booking.id),
            'customer_name': request.user.get_full_name() or request.user.username,
            'customer_email': request.user.email,
            'customer_phone': request.user.customer_profile.phone if hasattr(request.user, 'customer_profile') and request.user.customer_profile.phone else '',
        })
        
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


@customer_required
@require_http_methods(["POST"])
def verify_razorpay_payment(request):
    """
    Verify Razorpay payment after successful payment
    
    POST /booking/payment/verify/
    Body: {
        "razorpay_order_id": "order_xxx",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_signature": "signature_xxx",
        "booking_id": "uuid"
    }
    """
    try:
        data = json.loads(request.body)
        
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        booking_id = data.get('booking_id')
        
        # Validate inputs
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, booking_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required payment details'
            }, status=400)
        
        # Get booking
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile
        )
        
        # Verify signature
        is_valid = razorpay_service.verify_payment_signature(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        )
        
        if not is_valid:
            logger.warning(f"Invalid payment signature for booking {booking_id}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid payment signature'
            }, status=400)
        
        # Update booking with payment details (with database lock)
        from django.db import transaction
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking_id)
            
            booking.razorpay_payment_id = razorpay_payment_id
            booking.razorpay_signature = razorpay_signature
            booking.payment_status = 'PAID'
            booking.status = 'CONFIRMED'
            
            # Check if this is first verification (for notifications)
            should_notify = not booking.owner_notified
            
            booking.save(update_fields=[
                'razorpay_payment_id',
                'razorpay_signature',
                'payment_status',
                'status'
            ])
        
        logger.info(f"Payment verified successfully for booking {booking_id}")
        
        # Ensure verification token exists (no file generation)
        QRCodeService.generate_qr_code(booking)
        logger.info(f"Verification token ensured for booking {booking_id}")
        logger.info(f"Verification token ensured for booking {booking_id}")
        
        # Create transfer to owner if not done during order creation
        # (This happens if transfer was not included in order due to account not configured)
        from authentication.models import CafeOwner
        cafe_owner = CafeOwner.objects.first()
        
        if cafe_owner and cafe_owner.razorpay_account_id and not booking.razorpay_transfer_id:
            try:
                # Create transfer to owner
                transfer_result = razorpay_service.create_transfer(
                    razorpay_payment_id,
                    cafe_owner.razorpay_account_id,
                    int(booking.owner_payout * 100),  # Convert to paise
                    str(booking.id),
                    notes={
                        'booking_id': str(booking.id),
                        'transfer_type': 'owner_payout',
                        'commission': str(booking.commission_amount),
                        'owner_payout': str(booking.owner_payout)
                    }
                )
                
                if transfer_result['success']:
                    booking.transfer_status = 'PROCESSED'
                    booking.razorpay_transfer_id = transfer_result['transfer_id']
                    booking.transfer_processed_at = timezone.now()
                    booking.save(update_fields=['transfer_status', 'razorpay_transfer_id', 'transfer_processed_at'])
                    logger.info(f"Transfer created successfully: {transfer_result['transfer_id']} for booking {booking_id}")
                else:
                    booking.transfer_status = 'FAILED'
                    booking.save(update_fields=['transfer_status'])
                    logger.error(f"Transfer creation failed for booking {booking_id}: {transfer_result.get('error')}")
            except Exception as e:
                logger.error(f"Error creating transfer for booking {booking_id}: {str(e)}")
                booking.transfer_status = 'FAILED'
                booking.save(update_fields=['transfer_status'])
        
        # Send Telegram notification (only if flag was just set)
        if should_notify:
            try:
                from booking.telegram_service import telegram_service
                notification_sent = telegram_service.send_new_booking_notification(booking)
                
                if notification_sent:
                    # Only mark as notified if actually sent successfully
                    booking.owner_notified = True
                    booking.save(update_fields=['owner_notified'])
                    logger.info(f"Telegram notification sent successfully for booking {booking_id}")
                else:
                    logger.warning(f"Telegram notification failed for booking {booking_id} - will retry on next verification attempt")
                    
            except Exception as e:
                logger.error(f"Exception sending Telegram notification for booking {booking_id}: {e}", exc_info=True)
                # Don't set owner_notified flag so it can retry later
        else:
            logger.info(f"Telegram notification already sent for booking {booking_id}")
        
        # Send confirmation email and create in-app notification
        try:
            from booking.notifications import NotificationService, InAppNotification
            NotificationService.send_booking_confirmation_email(booking)
            InAppNotification.notify_booking_confirmed(booking)
            logger.info(f"Confirmation email and notification sent for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to send confirmation email/notification for booking {booking_id}: {e}")
            # Don't fail the payment if notification fails
        
        return JsonResponse({
            'success': True,
            'message': 'Payment verified successfully',
            'booking_id': str(booking.id),
            'status': booking.status,
            'transfer_status': booking.transfer_status
        })
        
    except Exception as e:
        logger.error(f"Error verifying payment for booking {booking_id if 'booking_id' in locals() else 'unknown'}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def razorpay_webhook(request):
    """
    Handle Razorpay webhooks
    
    POST /booking/payment/webhook/
    
    Events handled:
    - payment.authorized - Payment authorized by bank
    - payment.captured - Payment successfully captured
    - payment.failed - Payment attempt failed
    - order.paid - Order fully paid
    
    NOTE: Refunds are not supported - All sales are final
    """
    try:
        # Get webhook signature
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        
        if not webhook_signature:
            logger.warning("Webhook received without signature")
            return HttpResponse(status=400)
        
        # Verify webhook signature (if webhook secret is configured)
        if settings.RAZORPAY_WEBHOOK_SECRET:
            is_valid = razorpay_service.verify_webhook_signature(
                request.body,
                webhook_signature
            )
            
            if not is_valid:
                logger.warning("Invalid webhook signature")
                return HttpResponse(status=400)
        else:
            logger.warning("Webhook secret not configured - skipping signature verification")
        
        # Parse webhook data
        webhook_data = json.loads(request.body)
        event = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        payment_entity = payload.get('payment', {}).get('entity', {})
        order_entity = payload.get('order', {}).get('entity', {})
        
        logger.info(f"Received Razorpay webhook: {event}")
        
        # Handle payment events only (no refunds)
        if event == 'payment.authorized':
            handle_payment_authorized(payment_entity)
        elif event == 'payment.captured':
            handle_payment_captured(payment_entity)
        elif event == 'payment.failed':
            handle_payment_failed(payment_entity)
        elif event == 'order.paid':
            handle_order_paid(order_entity)
        elif event == 'transfer.processed':
            handle_transfer_processed(payload.get('transfer', {}).get('entity', {}))
        elif event == 'transfer.failed':
            handle_transfer_failed(payload.get('transfer', {}).get('entity', {}))
        elif event == 'transfer.reversed':
            handle_transfer_reversed(payload.get('transfer', {}).get('entity', {}))
        else:
            logger.info(f"Unhandled webhook event: {event}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)


def handle_payment_authorized(payment_entity):
    """Handle payment.authorized event"""
    try:
        order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')
        amount = payment_entity.get('amount')
        
        # Find booking by order ID
        booking = Booking.objects.filter(razorpay_order_id=order_id).first()
        
        if not booking:
            logger.warning(f"Booking not found for order {order_id}")
            return
        
        # Update booking - payment authorized but not captured yet
        booking.razorpay_payment_id = payment_id
        booking.payment_status = 'PENDING'  # Keep as PENDING until captured
        booking.notes = f"{booking.notes}\nPayment authorized: ₹{amount/100}"
        booking.save(update_fields=['razorpay_payment_id', 'payment_status', 'notes'])
        
        logger.info(f"Payment authorized for booking {booking.id}")
        
    except Exception as e:
        logger.error(f"Error handling payment.authorized: {str(e)}")


def handle_payment_captured(payment_entity):
    """Handle payment.captured event"""
    try:
        order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')
        amount = payment_entity.get('amount')
        
        # Find booking by order ID with database lock
        from django.db import transaction
        with transaction.atomic():
            booking = Booking.objects.select_for_update().filter(razorpay_order_id=order_id).first()
            
            if not booking:
                logger.warning(f"Booking not found for order {order_id}")
                return
            
            # Check if notification should be sent (before updating)
            should_notify = not booking.owner_notified
            
            # Update booking
            booking.razorpay_payment_id = payment_id
            booking.payment_status = 'PAID'
            booking.status = 'CONFIRMED'
            
            booking.save(update_fields=[
                'razorpay_payment_id',
                'payment_status',
                'status'
            ])
                
        logger.info(f"Payment captured for booking {booking.id} via webhook")
        
        # Ensure verification token exists
        if not booking.verification_token:
            QRCodeService.generate_qr_code(booking)
            logger.info(f"Verification token ensured for booking {booking.id} via webhook")
        
        # Send notification (outside transaction to avoid blocking)
        if should_notify:
            try:
                from booking.telegram_service import telegram_service
                notification_sent = telegram_service.send_new_booking_notification(booking)
                
                if notification_sent:
                    # Only mark as notified if actually sent successfully
                    booking.owner_notified = True
                    booking.save(update_fields=['owner_notified'])
                    logger.info(f"Telegram notification sent successfully for booking {booking.id} via webhook")
                else:
                    logger.warning(f"Telegram notification failed for booking {booking.id} via webhook - will retry later")
                    
            except Exception as e:
                logger.error(f"Exception sending Telegram notification for booking {booking.id} via webhook: {e}", exc_info=True)
        else:
            logger.info(f"Telegram notification already sent for booking {booking.id}")
        
    except Exception as e:
        logger.error(f"Error handling payment.captured: {str(e)}")


def handle_payment_failed(payment_entity):
    """Handle payment.failed event"""
    try:
        order_id = payment_entity.get('order_id')
        error_code = payment_entity.get('error_code')
        error_description = payment_entity.get('error_description')
        
        # Find booking by order ID
        booking = Booking.objects.filter(razorpay_order_id=order_id).first()
        
        if not booking:
            logger.warning(f"Booking not found for order {order_id}")
            return
        
        # Update booking
        booking.payment_status = 'FAILED'
        booking.notes = f"{booking.notes}\nPayment failed: {error_description} ({error_code})"
        booking.save(update_fields=['payment_status', 'notes'])
        
        logger.info(f"Payment failed for booking {booking.id}: {error_description}")
        
        # TODO: Send failure notification to customer
        
    except Exception as e:
        logger.error(f"Error handling payment.failed: {str(e)}")


def handle_order_paid(order_entity):
    """Handle order.paid event"""
    try:
        order_id = order_entity.get('id')
        amount_paid = order_entity.get('amount_paid')
        
        # Find booking by order ID with database lock
        from django.db import transaction
        with transaction.atomic():
            booking = Booking.objects.select_for_update().filter(razorpay_order_id=order_id).first()
            
            if not booking:
                logger.warning(f"Booking not found for order {order_id}")
                return
            
            # Update booking
            booking.payment_status = 'PAID'
            booking.status = 'CONFIRMED'
            
            # Check and send notification (atomically)
            if not booking.owner_notified:
                booking.owner_notified = True  # Set BEFORE save to prevent race
                booking.save(update_fields=[
                    'payment_status',
                    'status',
                    'owner_notified'
                ])
                
                logger.info(f"Order paid for booking {booking.id}")
                
                # Ensure verification token exists
                if not booking.verification_token:
                    QRCodeService.generate_qr_code(booking)
                    logger.info(f"Verification token ensured for booking {booking.id} via order.paid webhook")
                
                # Send notification AFTER database lock is released
                try:
                    from booking.telegram_service import telegram_service
                    telegram_service.send_new_booking_notification(booking)
                    logger.info(f"Telegram notification sent for booking {booking.id}")
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification for booking {booking.id}: {e}")
            else:
                booking.save(update_fields=[
                    'payment_status',
                    'status'
                ])
                logger.info(f"Order paid for booking {booking.id} - notification already sent")
        
    except Exception as e:
        logger.error(f"Error handling order.paid: {str(e)}")


def handle_transfer_processed(transfer_entity):
    """Handle transfer.processed event - Transfer to owner account successful"""
    try:
        transfer_id = transfer_entity.get('id')
        amount = transfer_entity.get('amount')
        recipient = transfer_entity.get('recipient')
        notes = transfer_entity.get('notes', {})
        booking_id = notes.get('booking_id')
        
        if not booking_id:
            logger.warning(f"Transfer {transfer_id} has no booking_id in notes")
            return
        
        # Find booking
        booking = Booking.objects.filter(id=booking_id).first()
        
        if not booking:
            logger.warning(f"Booking {booking_id} not found for transfer {transfer_id}")
            return
        
        # Update booking with transfer success
        booking.razorpay_transfer_id = transfer_id
        booking.transfer_status = 'PROCESSED'
        booking.transfer_processed_at = timezone.now()
        booking.save(update_fields=['razorpay_transfer_id', 'transfer_status', 'transfer_processed_at'])
        
        logger.info(f"Transfer processed successfully for booking {booking_id}: ₹{amount/100} to {recipient}")
        
    except Exception as e:
        logger.error(f"Error handling transfer.processed: {str(e)}")


def handle_transfer_failed(transfer_entity):
    """Handle transfer.failed event - Transfer to owner account failed"""
    try:
        transfer_id = transfer_entity.get('id')
        error_code = transfer_entity.get('error_code')
        error_description = transfer_entity.get('error_description')
        notes = transfer_entity.get('notes', {})
        booking_id = notes.get('booking_id')
        
        if not booking_id:
            logger.warning(f"Transfer {transfer_id} has no booking_id in notes")
            return
        
        # Find booking
        booking = Booking.objects.filter(id=booking_id).first()
        
        if not booking:
            logger.warning(f"Booking {booking_id} not found for transfer {transfer_id}")
            return
        
        # Update booking with transfer failure
        booking.razorpay_transfer_id = transfer_id
        booking.transfer_status = 'FAILED'
        booking.notes = f"{booking.notes}\nTransfer failed: {error_description} ({error_code})"
        booking.save(update_fields=['razorpay_transfer_id', 'transfer_status', 'notes'])
        
        logger.error(f"Transfer failed for booking {booking_id}: {error_description}")
        
        # TODO: Alert admin about failed transfer for manual processing
        
    except Exception as e:
        logger.error(f"Error handling transfer.failed: {str(e)}")


def handle_transfer_reversed(transfer_entity):
    """Handle transfer.reversed event - Transfer was reversed"""
    try:
        transfer_id = transfer_entity.get('id')
        notes = transfer_entity.get('notes', {})
        booking_id = notes.get('booking_id')
        
        if not booking_id:
            logger.warning(f"Transfer {transfer_id} has no booking_id in notes")
            return
        
        # Find booking
        booking = Booking.objects.filter(id=booking_id).first()
        
        if not booking:
            logger.warning(f"Booking {booking_id} not found for transfer {transfer_id}")
            return
        
        # Update booking with transfer reversal
        booking.transfer_status = 'FAILED'
        booking.notes = f"{booking.notes}\nTransfer reversed: {transfer_id}"
        booking.save(update_fields=['transfer_status', 'notes'])
        
        logger.warning(f"Transfer reversed for booking {booking_id}: {transfer_id}")
        
        # TODO: Alert admin about reversed transfer
        
    except Exception as e:
        logger.error(f"Error handling transfer.reversed: {str(e)}")


@customer_required
def payment_cancelled(request, booking_id):
    """
    Payment cancelled page - shown when user cancels payment
    Also automatically cancels the pending booking
    """
    try:
        # Get booking - must be owned by current user
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile
        )
        
        # Cancel the booking if it's still pending
        if booking.status == 'PENDING':
            booking.status = 'CANCELLED'
            booking.payment_status = 'CANCELLED'
            booking.notes = f"{booking.notes}\nPayment cancelled by user at {timezone.now()}"
            booking.save(update_fields=['status', 'payment_status', 'notes'])
            
            logger.info(f"Booking {booking_id} cancelled due to payment cancellation")
        
        context = {
            'booking': booking,
        }
        
        return render(request, 'booking/payment_cancelled.html', context)
        
    except Exception as e:
        logger.error(f"Error in payment_cancelled view: {str(e)}")
        messages.error(request, 'Unable to process cancellation')
        return redirect('booking:my_bookings')


@customer_required
def payment_success(request, booking_id):
    """
    Secure payment success page - ONLY accessible after verified payment
    Prevents direct URL access without payment verification
    """
    try:
        # Get booking - must be owned by current user
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile
        )
        
        # SECURITY CHECK: Only allow access if payment is verified
        if booking.status != 'CONFIRMED' or not booking.razorpay_payment_id:
            logger.warning(f"Unauthorized access to success page for booking {booking_id} - Status: {booking.status}, Payment ID: {booking.razorpay_payment_id}")
            messages.error(request, 'Payment verification required. Please complete the payment first.')
            return redirect('booking:hybrid_booking_confirm', booking_id=booking_id)
        
        # ADDITIONAL SECURITY: Check if payment was verified within last 30 minutes
        # Increased from 10 to 30 minutes to handle network delays and slow verification
        # This prevents old confirmed bookings from being accessed via this URL
        if booking.updated_at and (timezone.now() - booking.updated_at).total_seconds() > 1800:
            logger.info(f"Success page access for old booking {booking_id} - redirecting to my bookings")
            # If updated more than 30 minutes ago, redirect to my bookings
            return redirect('booking:my_bookings')
        
        # Ensure verification token exists
        if not booking.verification_token:
            logger.info(f"Ensuring verification token for booking {booking_id} on success page")
            QRCodeService.generate_qr_code(booking)
            booking.refresh_from_db()
            logger.info(f"Verification token ensured for booking {booking_id}")
        
        logger.info(f"User successfully reached payment success page for booking {booking_id}")
        
        context = {
            'booking': booking,
        }
        
        return render(request, 'booking/success.html', context)
        
    except Exception as e:
        logger.error(f"Error in payment_success view for booking {booking_id}: {str(e)}", exc_info=True)
        messages.error(request, 'Unable to display booking confirmation')
        return redirect('booking:my_bookings')


@customer_required
@require_http_methods(["GET"])
def check_payment_status(request, booking_id):
    """
    API endpoint to check payment status - used as fallback when webhook verification fails
    
    GET /booking/payment/status/<booking_id>/
    """
    try:
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user.customer_profile
        )
        
        # If already confirmed, return success
        if booking.status == 'CONFIRMED' and booking.payment_status == 'PAID':
            return JsonResponse({
                'success': True,
                'payment_status': booking.payment_status,
                'booking_status': booking.status,
                'needs_action': False,
                'message': 'Payment confirmed successfully'
            })
        
        # Check with Razorpay if we have payment ID
        if booking.razorpay_payment_id and booking.payment_status != 'PAID':
            payment_details = razorpay_service.get_payment_details(booking.razorpay_payment_id)
            
            if payment_details and payment_details.get('status') == 'captured':
                booking.payment_status = 'PAID'
                booking.status = 'CONFIRMED'
                booking.save(update_fields=['payment_status', 'status'])
                
                logger.info(f"Payment status updated via API fallback for booking {booking_id}")
                
                return JsonResponse({
                    'success': True,
                    'payment_status': 'PAID',
                    'booking_status': 'CONFIRMED',
                    'needs_action': False,
                    'message': 'Payment confirmed successfully'
                })
        
        return JsonResponse({
            'success': True,
            'payment_status': booking.payment_status,
            'booking_status': booking.status,
            'needs_action': booking.status == 'PENDING',
            'message': 'Payment still processing' if booking.status == 'PENDING' else 'Payment completed'
        })
        
    except Exception as e:
        logger.error(f"Error checking payment status for booking {booking_id if 'booking_id' in locals() else 'unknown'}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)
