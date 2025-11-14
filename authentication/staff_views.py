from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from .models import CafeStaff, CafeOwner
from .decorators import cafe_staff_required, cafe_owner_required
from booking.models import Booking
import json


@cafe_staff_required
def staff_dashboard(request):
    """Staff dashboard showing only today's bookings"""
    staff = request.user.cafe_staff_profile
    cafe_owner = staff.cafe_owner
    now = timezone.now()
    today = timezone.localdate()
    
    # Auto-update booking statuses
    from booking.booking_service import auto_update_bookings_status
    bookings_to_check = Booking.objects.filter(
        status__in=['PENDING', 'CONFIRMED', 'IN_PROGRESS'],
        game_slot__date=today
    ).select_related('game_slot')
    auto_update_bookings_status(bookings_to_check)
    
    # Get today's bookings only (current + upcoming)
    todays_bookings = Booking.objects.filter(
        game_slot__date=today,
        payment_status='PAID'
    ).select_related('game', 'customer__user', 'game_slot').order_by('game_slot__start_time')
    
    # Separate current and upcoming
    current_bookings = []
    upcoming_bookings = []
    
    for booking in todays_bookings:
        if booking.status == 'IN_PROGRESS':
            current_bookings.append(booking)
        elif booking.status in ['CONFIRMED']:
            upcoming_bookings.append(booking)
    
    context = {
        'staff': staff,
        'cafe_owner': cafe_owner,
        'current_bookings': current_bookings,
        'upcoming_bookings': upcoming_bookings,
        'now': now,
        'today': today,
    }
    
    response = render(request, 'authentication/staff_dashboard.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@cafe_owner_required
def manage_staff(request):
    """Owner can manage their staff members"""
    cafe_owner = request.user.cafe_owner_profile
    
    # Get all staff members for this owner
    staff_members = CafeStaff.objects.filter(
        cafe_owner=cafe_owner
    ).select_related('user').order_by('-created_at')
    
    context = {
        'cafe_owner': cafe_owner,
        'staff_members': staff_members,
    }
    
    return render(request, 'authentication/manage_staff.html', context)


@cafe_owner_required
def create_staff(request):
    """Create a new staff member"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        # Validate required fields
        if not username:
            messages.error(request, 'Username is required.')
            return redirect('authentication:manage_staff')
        
        if not password:
            messages.error(request, 'Password is required.')
            return redirect('authentication:manage_staff')
        
        # Validate username format
        if len(username) < 3:
            messages.error(request, 'Username must be at least 3 characters long.')
            return redirect('authentication:manage_staff')
        
        # Validate password strength
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
            return redirect('authentication:manage_staff')
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists. Please choose a different username.')
            return redirect('authentication:manage_staff')
        
        # Validate email if provided
        if email and User.objects.filter(email=email).exists():
            messages.warning(request, f'Email "{email}" is already registered to another user.')
            # Continue but warn the user
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email
            )
            
            # Create staff profile
            CafeStaff.objects.create(
                user=user,
                cafe_owner=request.user.cafe_owner_profile
            )
            
            full_name = user.get_full_name() or username
            messages.success(request, f'✓ Staff member "{full_name}" (Username: {username}) created successfully! They can now log in using the staff portal.')
        except Exception as e:
            messages.error(request, f'Error creating staff: {str(e)}')
    
    return redirect('authentication:manage_staff')


@cafe_owner_required
def edit_staff(request, staff_id):
    """Edit staff member details"""
    staff = get_object_or_404(CafeStaff, id=staff_id, cafe_owner=request.user.cafe_owner_profile)
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '')
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            # Validate email if changed
            if email and email != staff.user.email:
                if User.objects.filter(email=email).exclude(id=staff.user.id).exists():
                    messages.error(request, f'Email "{email}" is already registered to another user.')
                    return redirect('authentication:manage_staff')
            
            # Validate password if provided
            if new_password and len(new_password) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
                return redirect('authentication:manage_staff')
            
            # Update user details
            staff.user.first_name = first_name
            staff.user.last_name = last_name
            staff.user.email = email
            
            # Update password if provided
            if new_password:
                staff.user.set_password(new_password)
            
            staff.user.save()
            
            # Update staff status
            staff.is_active = is_active
            staff.save()
            
            status_msg = "active" if is_active else "inactive"
            full_name = staff.user.get_full_name() or staff.user.username
            messages.success(request, f'✓ Staff member "{full_name}" updated successfully! Status: {status_msg.title()}')
        except Exception as e:
            messages.error(request, f'Error updating staff: {str(e)}')
    
    return redirect('authentication:manage_staff')


@cafe_owner_required
def delete_staff(request, staff_id):
    """Delete a staff member"""
    staff = get_object_or_404(CafeStaff, id=staff_id, cafe_owner=request.user.cafe_owner_profile)
    
    if request.method == 'POST':
        try:
            username = staff.user.username
            full_name = staff.user.get_full_name() or username
            user = staff.user
            staff.delete()
            user.delete()
            messages.success(request, f'✓ Staff member "{full_name}" (Username: {username}) has been removed successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting staff: {str(e)}')
    
    return redirect('authentication:manage_staff')
