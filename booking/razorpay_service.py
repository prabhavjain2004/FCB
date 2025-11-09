"""
Razorpay Payment Service
Handles all Razorpay payment operations including order creation, verification, and webhooks
"""

import razorpay
import hmac
import hashlib
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class RazorpayService:
    """Service class for Razorpay payment integration"""
    
    def __init__(self):
        """Initialize Razorpay client"""
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        # Disable signature verification in SDK as we'll verify manually
        self.client.set_app_details({
            "title": "NEXGEN FC - Gaming Cafe Booking",
            "version": "1.0.0"
        })
    
    def create_order(self, booking):
        """
        Create a Razorpay order for a booking
        
        Args:
            booking: Booking instance
            
        Returns:
            dict: Order data from Razorpay
        """
        try:
            # Convert amount to paise (smallest currency unit)
            amount_paise = int(booking.total_amount * 100)
            
            # Create order data
            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': str(booking.id),
                'notes': {
                    'booking_id': str(booking.id),
                    'customer_email': booking.customer.user.email,
                    'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
                    'game_name': booking.game.name,
                    'booking_type': booking.booking_type,
                }
            }
            
            # Create order via Razorpay API
            order = self.client.order.create(data=order_data)
            
            logger.info(f"Razorpay order created: {order['id']} for booking {booking.id}")
            
            return {
                'success': True,
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'order_data': order
            }
            
        except Exception as e:
            logger.error(f"Failed to create Razorpay order for booking {booking.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment_signature(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """
        Verify payment signature from Razorpay
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature to verify
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Create signature string
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, razorpay_signature)
            
            if is_valid:
                logger.info(f"Payment signature verified successfully for payment {razorpay_payment_id}")
            else:
                logger.warning(f"Invalid payment signature for payment {razorpay_payment_id}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying payment signature: {str(e)}")
            return False
    
    def verify_webhook_signature(self, webhook_body, webhook_signature):
        """
        Verify webhook signature from Razorpay
        
        Args:
            webhook_body: Raw webhook body (bytes or string)
            webhook_signature: X-Razorpay-Signature header value
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            if not settings.RAZORPAY_WEBHOOK_SECRET:
                logger.warning("Razorpay webhook secret not configured")
                return False
            
            # Convert body to bytes if string
            if isinstance(webhook_body, str):
                webhook_body = webhook_body.encode('utf-8')
            
            # Generate expected signature
            expected_signature = hmac.new(
                settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
                webhook_body,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, webhook_signature)
            
            if is_valid:
                logger.info("Webhook signature verified successfully")
            else:
                logger.warning("Invalid webhook signature")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def fetch_payment(self, payment_id):
        """
        Fetch payment details from Razorpay
        
        Args:
            payment_id: Razorpay payment ID
            
        Returns:
            dict: Payment details
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            logger.info(f"Fetched payment details for {payment_id}")
            return {
                'success': True,
                'payment': payment
            }
        except Exception as e:
            logger.error(f"Failed to fetch payment {payment_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def capture_payment(self, payment_id, amount):
        """
        Capture a payment (for authorized payments)
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount in paise to capture
            
        Returns:
            dict: Capture result
        """
        try:
            result = self.client.payment.capture(payment_id, amount)
            logger.info(f"Payment captured: {payment_id}")
            return {
                'success': True,
                'payment': result
            }
        except Exception as e:
            logger.error(f"Failed to capture payment {payment_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def fetch_order(self, order_id):
        """
        Fetch order details from Razorpay
        
        Args:
            order_id: Razorpay order ID
            
        Returns:
            dict: Order details
        """
        try:
            order = self.client.order.fetch(order_id)
            logger.info(f"Fetched order details for {order_id}")
            return {
                'success': True,
                'order': order
            }
        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_payment_details(self, payment_id):
        """
        Fetch payment details from Razorpay - used for status checks
        
        Args:
            payment_id: Razorpay payment ID
            
        Returns:
            dict: Payment details or None if error
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            logger.info(f"Fetched payment details for {payment_id}: status={payment.get('status')}")
            return payment
        except Exception as e:
            logger.error(f"Failed to fetch payment {payment_id}: {str(e)}")
            return None
    
    def calculate_payment_split(self, booking_amount, commission_rate, platform_fee_rate, platform_fee_type='PERCENT'):
        """
        Calculate payment split with commission and platform fee
        
        Payment Flow:
        - User pays: booking_amount + platform_fee
        - Platform keeps: commission + platform_fee
        - Owner receives: booking_amount - commission
        
        IMPORTANT: Commission is deducted from BASE booking_amount, NOT after adding platform fee
        
        Args:
            booking_amount: Base booking amount (Decimal) - the subtotal before any fees
            commission_rate: Commission percentage (must be set by superuser, no default)
            platform_fee_rate: Platform fee percentage or fixed amount (must be set by superuser)
            platform_fee_type: 'PERCENT' or 'FIXED' (default: 'PERCENT')
            
        Returns:
            dict: {
                'booking_amount': Decimal - Base booking amount
                'platform_fee': Decimal - Platform fee (paid by user)
                'total_charged': Decimal - Total amount user pays
                'commission': Decimal - Commission deducted from owner (from base amount)
                'owner_payout': Decimal - Amount owner receives (base - commission)
            }
        """
        booking_amount = Decimal(str(booking_amount))
        commission_rate = Decimal(str(commission_rate))
        platform_fee_rate = Decimal(str(platform_fee_rate))
        
        # Calculate platform fee (paid by user, added to total)
        if platform_fee_type == 'PERCENT':
            platform_fee = (booking_amount * platform_fee_rate / 100).quantize(Decimal('0.01'))
        else:  # FIXED
            platform_fee = platform_fee_rate.quantize(Decimal('0.01'))
        
        # Calculate commission (deducted from BASE booking_amount, NOT from total with platform fee)
        commission = (booking_amount * commission_rate / 100).quantize(Decimal('0.01'))
        
        # Total amount user pays (base + platform fee)
        total_charged = booking_amount + platform_fee
        
        # Amount owner receives (base - commission)
        # Platform fee is NOT deducted from owner, it's paid by customer
        owner_payout = booking_amount - commission
        
        logger.info(f"Payment Split - Base: ₹{booking_amount}, Platform Fee ({platform_fee_type}): ₹{platform_fee}, "
                   f"Commission ({commission_rate}%): ₹{commission}, Total Charged: ₹{total_charged}, Owner Payout: ₹{owner_payout}")
        
        return {
            'booking_amount': booking_amount,
            'platform_fee': platform_fee,
            'total_charged': total_charged,
            'commission': commission,
            'owner_payout': owner_payout
        }
    
    def create_order_with_transfer(self, booking, owner_account_id=None):
        """
        Create a Razorpay order with optional transfer/route configuration
        
        Note: Razorpay Route requires additional setup. If owner_account_id is not provided,
        creates a normal order. Transfer is created after payment success.
        
        Args:
            booking: Booking instance
            owner_account_id: Razorpay account ID of owner (optional)
            
        Returns:
            dict: Order data from Razorpay
        """
        try:
            # Convert amount to paise (smallest currency unit)
            amount_paise = int(booking.total_amount * 100)
            
            # Create order data
            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': str(booking.id),
                'notes': {
                    'booking_id': str(booking.id),
                    'customer_email': booking.customer.user.email,
                    'customer_name': booking.customer.user.get_full_name() or booking.customer.user.username,
                    'game_name': booking.game.name,
                    'booking_type': booking.booking_type,
                    'owner_payout': str(booking.owner_payout),
                    'commission': str(booking.commission_amount),
                    'platform_fee': str(booking.platform_fee),
                }
            }
            
            # Add transfer configuration if owner account is provided
            # Note: This requires Razorpay Route to be enabled on your account
            if owner_account_id:
                order_data['transfers'] = [{
                    'account': owner_account_id,
                    'amount': int(booking.owner_payout * 100),  # Amount in paise
                    'currency': 'INR',
                    'notes': {
                        'booking_id': str(booking.id),
                        'transfer_type': 'owner_payout'
                    }
                }]
                logger.info(f"Order created with transfer configuration for account {owner_account_id}")
            
            # Create order via Razorpay API
            order = self.client.order.create(data=order_data)
            
            logger.info(f"Razorpay order created: {order['id']} for booking {booking.id}")
            
            return {
                'success': True,
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'order_data': order
            }
            
        except Exception as e:
            logger.error(f"Failed to create Razorpay order for booking {booking.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_transfer(self, payment_id, owner_account_id, amount, booking_id, notes=None):
        """
        Create a transfer to owner's Razorpay account after payment
        
        This is used when transfer is not created during order creation.
        Requires Razorpay Route to be enabled on your account.
        
        Args:
            payment_id: Razorpay payment ID
            owner_account_id: Owner's Razorpay account ID
            amount: Amount to transfer in paise
            booking_id: Reference booking ID
            notes: Optional notes dict
            
        Returns:
            dict: Transfer response
        """
        try:
            transfer_data = {
                'account': owner_account_id,
                'amount': amount,
                'currency': 'INR',
                'notes': notes or {
                    'booking_id': str(booking_id),
                    'transfer_type': 'owner_payout'
                }
            }
            
            # Create transfer from payment
            transfer = self.client.payment.transfer(payment_id, transfer_data)
            
            logger.info(f"Transfer created: {transfer['id']} for payment {payment_id}, "
                       f"amount: ₹{amount/100}, account: {owner_account_id}")
            
            return {
                'success': True,
                'transfer_id': transfer['id'],
                'transfer': transfer
            }
            
        except Exception as e:
            logger.error(f"Failed to create transfer for payment {payment_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def fetch_transfer(self, transfer_id):
        """
        Fetch transfer details and status from Razorpay
        
        Args:
            transfer_id: Razorpay transfer ID
            
        Returns:
            dict: Transfer details or error
        """
        try:
            transfer = self.client.transfer.fetch(transfer_id)
            
            logger.info(f"Fetched transfer {transfer_id}: status={transfer.get('status')}")
            
            return {
                'success': True,
                'transfer': transfer
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch transfer {transfer_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
razorpay_service = RazorpayService()
