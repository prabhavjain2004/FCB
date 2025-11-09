"""
Commission calculation and revenue tracking service for TapNex superuser management.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta, date
from .models import TapNexSuperuser
from booking.models import Booking


class CommissionCalculator:
    """Service for calculating commissions and revenue analytics"""
    
    @staticmethod
    def calculate_commission(booking_amount, commission_rate, platform_fee, platform_fee_type='PERCENT'):
        """Calculate commission from a booking amount"""
        booking_amount = Decimal(str(booking_amount))
        commission_rate = Decimal(str(commission_rate))
        platform_fee = Decimal(str(platform_fee))
        
        commission = (booking_amount * commission_rate) / 100
        
        # Calculate platform fee based on type
        if platform_fee_type == 'PERCENT':
            platform_fee_amount = (booking_amount * platform_fee) / 100
        else:  # FIXED
            platform_fee_amount = platform_fee
        
        total_commission = commission + platform_fee_amount
        net_payout = booking_amount - total_commission
        
        return {
            'gross_revenue': booking_amount,
            'commission_amount': commission,
            'platform_fee': platform_fee_amount,
            'platform_fee_type': platform_fee_type,
            'total_commission': total_commission,
            'net_payout': net_payout
        }
    
    @staticmethod
    def get_tapnex_revenue_analytics(start_date=None, end_date=None):
        """Get TapNex earnings analytics (commission + platform fee only)"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get TapNex superuser settings
        try:
            tapnex_user = TapNexSuperuser.objects.first()
            if not tapnex_user or tapnex_user.commission_rate is None or tapnex_user.platform_fee is None:
                raise ValueError("Commission rate and platform fee must be configured in superuser settings")
            
            current_commission_rate = tapnex_user.commission_rate
            current_platform_fee = tapnex_user.platform_fee
            platform_fee_type = tapnex_user.platform_fee_type
        except TapNexSuperuser.DoesNotExist:
            raise ValueError("TapNex superuser not found. Commission rates must be configured.")
        
        # Get confirmed bookings in date range
        bookings = Booking.objects.filter(
            status='CONFIRMED',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).exclude(commission_amount__isnull=True, platform_fee__isnull=True)
        
        # Calculate TapNex earnings from stored values (historical rates preserved)
        total_bookings = bookings.count()
        
        # Sum actual commission and platform fees from bookings
        totals = bookings.aggregate(
            total_commission=Sum('commission_amount'),
            total_platform_fee=Sum('platform_fee'),
            total_booking_amount=Sum('subtotal')
        )
        
        total_commission = totals['total_commission'] or Decimal('0.00')
        total_platform_fee = totals['total_platform_fee'] or Decimal('0.00')
        total_booking_amount = totals['total_booking_amount'] or Decimal('0.00')
        
        # TapNex total revenue (commission + platform fee)
        tapnex_total_revenue = total_commission + total_platform_fee
        
        # Average revenue per booking
        avg_revenue_per_booking = tapnex_total_revenue / total_bookings if total_bookings > 0 else Decimal('0.00')
        
        # Booking type breakdown
        private_bookings = bookings.filter(booking_type='PRIVATE')
        shared_bookings = bookings.filter(booking_type='SHARED')
        
        private_totals = private_bookings.aggregate(
            commission=Sum('commission_amount'),
            platform_fee=Sum('platform_fee')
        )
        shared_totals = shared_bookings.aggregate(
            commission=Sum('commission_amount'),
            platform_fee=Sum('platform_fee')
        )
        
        private_tapnex_revenue = (private_totals['commission'] or Decimal('0.00')) + (private_totals['platform_fee'] or Decimal('0.00'))
        shared_tapnex_revenue = (shared_totals['commission'] or Decimal('0.00')) + (shared_totals['platform_fee'] or Decimal('0.00'))
        
        # Daily revenue trend
        daily_revenue = []
        current_date = start_date
        while current_date <= end_date:
            day_bookings = bookings.filter(created_at__date=current_date)
            day_totals = day_bookings.aggregate(
                commission=Sum('commission_amount'),
                platform_fee=Sum('platform_fee')
            )
            
            day_commission = day_totals['commission'] or Decimal('0.00')
            day_platform_fee = day_totals['platform_fee'] or Decimal('0.00')
            day_tapnex_revenue = day_commission + day_platform_fee
            
            daily_revenue.append({
                'date': current_date,
                'tapnex_revenue': day_tapnex_revenue,
                'commission': day_commission,
                'platform_fee': day_platform_fee,
                'bookings': day_bookings.count()
            })
            
            current_date += timedelta(days=1)
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'totals': {
                'tapnex_total_revenue': tapnex_total_revenue,
                'total_commission': total_commission,
                'total_platform_fee': total_platform_fee,
                'total_bookings': total_bookings,
                'total_booking_amount': total_booking_amount,
                'avg_revenue_per_booking': avg_revenue_per_booking
            },
            'booking_breakdown': {
                'private_bookings': private_bookings.count(),
                'shared_bookings': shared_bookings.count(),
                'private_tapnex_revenue': private_tapnex_revenue,
                'shared_tapnex_revenue': shared_tapnex_revenue
            },
            'settings': {
                'current_commission_rate': current_commission_rate,
                'current_platform_fee': current_platform_fee,
                'platform_fee_type': platform_fee_type
            },
            'daily_trend': daily_revenue
        }
    
    @staticmethod
    def get_revenue_analytics(start_date=None, end_date=None):
        """Get comprehensive revenue analytics for TapNex dashboard (DEPRECATED - use get_tapnex_revenue_analytics)"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get TapNex superuser settings - REQUIRED, no defaults
        try:
            tapnex_user = TapNexSuperuser.objects.first()
            if not tapnex_user or tapnex_user.commission_rate is None or tapnex_user.platform_fee is None:
                raise ValueError("Commission rate and platform fee must be configured in superuser settings")
            
            commission_rate = tapnex_user.commission_rate
            platform_fee = tapnex_user.platform_fee
            platform_fee_type = tapnex_user.platform_fee_type
        except TapNexSuperuser.DoesNotExist:
            raise ValueError("TapNex superuser not found. Commission rates must be configured.")
        
        # Get confirmed bookings in date range
        bookings = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).exclude(total_amount__isnull=True)
        
        # Calculate totals
        total_bookings = bookings.count()
        gross_revenue = bookings.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # Calculate commission breakdown
        commission_amount = (gross_revenue * commission_rate) / 100
        
        # Calculate platform fees based on type
        if platform_fee_type == 'PERCENT':
            total_platform_fees = (gross_revenue * platform_fee) / 100
        else:  # FIXED
            total_platform_fees = platform_fee * total_bookings
        
        total_commission = commission_amount + total_platform_fees
        net_payout = gross_revenue - total_commission
        
        # Booking type breakdown
        private_bookings = bookings.filter(booking_type='PRIVATE')
        shared_bookings = bookings.filter(booking_type='SHARED')
        
        private_revenue = private_bookings.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        shared_revenue = shared_bookings.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # Daily revenue trend (last 7 days)
        daily_revenue = []
        for i in range(7):
            day = end_date - timedelta(days=i)
            day_bookings = bookings.filter(created_at__date=day)
            day_revenue = day_bookings.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            daily_revenue.append({
                'date': day,
                'revenue': day_revenue,
                'bookings': day_bookings.count()
            })
        
        daily_revenue.reverse()  # Chronological order
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'totals': {
                'gross_revenue': gross_revenue,
                'commission_amount': commission_amount,
                'platform_fees': total_platform_fees,
                'total_commission': total_commission,
                'net_payout': net_payout,
                'total_bookings': total_bookings
            },
            'booking_breakdown': {
                'private_bookings': private_bookings.count(),
                'shared_bookings': shared_bookings.count(),
                'private_revenue': private_revenue,
                'shared_revenue': shared_revenue
            },
            'settings': {
                'commission_rate': commission_rate,
                'platform_fee': platform_fee
            },
            'daily_trend': daily_revenue
        }
    
    @staticmethod
    def get_monthly_revenue_report(year=None, month=None):
        """Get detailed monthly revenue report"""
        if not year:
            year = date.today().year
        if not month:
            month = date.today().month
        
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        return CommissionCalculator.get_revenue_analytics(start_date, end_date)
    
    @staticmethod
    def get_tapnex_game_revenue_breakdown(start_date=None, end_date=None):
        """Get TapNex revenue breakdown by game (commission + platform fee per game)"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get bookings with game information
        bookings = Booking.objects.filter(
            status='CONFIRMED',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            game__isnull=False
        ).select_related('game')
        
        # Group by game
        game_stats = {}
        for booking in bookings:
            game_name = booking.game.name
            if game_name not in game_stats:
                game_stats[game_name] = {
                    'bookings': 0,
                    'tapnex_revenue': Decimal('0.00'),
                    'commission': Decimal('0.00'),
                    'platform_fee': Decimal('0.00'),
                    'private_bookings': 0,
                    'shared_bookings': 0,
                    'private_tapnex_revenue': Decimal('0.00'),
                    'shared_tapnex_revenue': Decimal('0.00')
                }
            
            stats = game_stats[game_name]
            commission = booking.commission_amount or Decimal('0.00')
            platform_fee = booking.platform_fee or Decimal('0.00')
            tapnex_revenue = commission + platform_fee
            
            stats['bookings'] += 1
            stats['tapnex_revenue'] += tapnex_revenue
            stats['commission'] += commission
            stats['platform_fee'] += platform_fee
            
            if booking.booking_type == 'PRIVATE':
                stats['private_bookings'] += 1
                stats['private_tapnex_revenue'] += tapnex_revenue
            else:
                stats['shared_bookings'] += 1
                stats['shared_tapnex_revenue'] += tapnex_revenue
        
        # Sort by TapNex revenue
        sorted_games = sorted(
            game_stats.items(),
            key=lambda x: x[1]['tapnex_revenue'],
            reverse=True
        )
        
        return sorted_games
    
    @staticmethod
    def get_game_revenue_breakdown(start_date=None, end_date=None):
        """Get revenue breakdown by game type (DEPRECATED - use get_tapnex_game_revenue_breakdown)"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Get bookings with game information
        bookings = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            game__isnull=False
        ).select_related('game')
        
        # Group by game
        game_stats = {}
        for booking in bookings:
            game_name = booking.game.name
            if game_name not in game_stats:
                game_stats[game_name] = {
                    'bookings': 0,
                    'revenue': Decimal('0.00'),
                    'private_bookings': 0,
                    'shared_bookings': 0,
                    'private_revenue': Decimal('0.00'),
                    'shared_revenue': Decimal('0.00')
                }
            
            stats = game_stats[game_name]
            stats['bookings'] += 1
            stats['revenue'] += booking.total_amount or Decimal('0.00')
            
            if booking.booking_type == 'PRIVATE':
                stats['private_bookings'] += 1
                stats['private_revenue'] += booking.total_amount or Decimal('0.00')
            else:
                stats['shared_bookings'] += 1
                stats['shared_revenue'] += booking.total_amount or Decimal('0.00')
        
        # Sort by revenue
        sorted_games = sorted(
            game_stats.items(),
            key=lambda x: x[1]['revenue'],
            reverse=True
        )
        
        return sorted_games


class RevenueTracker:
    """Service for tracking and monitoring revenue metrics"""
    
    @staticmethod
    def get_real_time_metrics():
        """Get real-time dashboard metrics"""
        today = date.today()
        
        # Today's metrics
        today_bookings = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date=today
        )
        
        today_revenue = today_bookings.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # This month's metrics
        month_start = today.replace(day=1)
        month_bookings = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date__gte=month_start,
            created_at__date__lte=today
        )
        
        month_revenue = month_bookings.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # Active bookings (currently in progress)
        active_bookings = Booking.objects.filter(
            status='IN_PROGRESS'
        ).count()
        
        # Pending payments
        pending_payments = Booking.objects.filter(
            status='PENDING'
        ).count()
        
        # Get commission settings - REQUIRED, no defaults
        try:
            tapnex_user = TapNexSuperuser.objects.first()
            if not tapnex_user or tapnex_user.commission_rate is None or tapnex_user.platform_fee is None:
                raise ValueError("Commission rate and platform fee must be configured in superuser settings")
            
            commission_rate = tapnex_user.commission_rate
            platform_fee = tapnex_user.platform_fee
        except TapNexSuperuser.DoesNotExist:
            raise ValueError("TapNex superuser not found. Commission rates must be configured.")
        
        # Calculate today's commission
        today_commission = CommissionCalculator.calculate_commission(
            today_revenue, commission_rate, platform_fee
        )
        
        return {
            'today': {
                'bookings': today_bookings.count(),
                'revenue': today_revenue,
                'commission': today_commission['total_commission']
            },
            'month': {
                'bookings': month_bookings.count(),
                'revenue': month_revenue
            },
            'active': {
                'in_progress': active_bookings,
                'pending_payments': pending_payments
            },
            'settings': {
                'commission_rate': commission_rate,
                'platform_fee': platform_fee
            }
        }
    
    @staticmethod
    def get_growth_metrics():
        """Get growth metrics comparing current vs previous periods"""
        today = date.today()
        
        # Current month vs previous month
        current_month_start = today.replace(day=1)
        if current_month_start.month == 1:
            prev_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
            prev_month_end = current_month_start - timedelta(days=1)
        else:
            prev_month_start = current_month_start.replace(month=current_month_start.month - 1)
            prev_month_end = current_month_start - timedelta(days=1)
        
        # Current month revenue
        current_revenue = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date__gte=current_month_start,
            created_at__date__lte=today
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Previous month revenue
        prev_revenue = Booking.objects.filter(
            status__in=['CONFIRMED', 'IN_PROGRESS', 'COMPLETED'],
            created_at__date__gte=prev_month_start,
            created_at__date__lte=prev_month_end
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Calculate growth percentage
        if prev_revenue > 0:
            growth_rate = ((current_revenue - prev_revenue) / prev_revenue) * 100
        else:
            growth_rate = 100 if current_revenue > 0 else 0
        
        return {
            'current_month_revenue': current_revenue,
            'previous_month_revenue': prev_revenue,
            'growth_rate': growth_rate,
            'growth_amount': current_revenue - prev_revenue
        }