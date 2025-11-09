from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


class CustomPasswordValidator:
    """Custom password validator for enhanced security"""
    
    @staticmethod
    def validate_password_complexity(password):
        """
        Validate password complexity requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit.")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character.")


class CafeOwnerLoginForm(AuthenticationForm):
    """Custom login form for cafe owners with enhanced styling"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Username or Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Password'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username or Email'
        self.fields['password'].label = 'Password'


class CafeOwnerRegistrationForm(UserCreationForm):
    """Registration form for cafe owners with password complexity validation"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Email Address'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Last Name'
        })
    )
    cafe_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Cafe Name'
        })
    )
    phone = forms.CharField(
        max_length=17,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Phone Number (+1234567890)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Tailwind CSS classes to password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm Password'
        })

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if password1:
            CustomPasswordValidator.validate_password_complexity(password1)
        return password1

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create CafeOwner profile
            from .models import CafeOwner
            CafeOwner.objects.create(
                user=user,
                cafe_name=self.cleaned_data['cafe_name'],
                contact_email=self.cleaned_data['email'],
                phone=self.cleaned_data['phone']
            )
        return user


class CommissionSettingsForm(forms.ModelForm):
    """Form for TapNex superuser to manage commission settings"""
    
    class Meta:
        from .models import TapNexSuperuser
        model = TapNexSuperuser
        fields = ['commission_rate', 'platform_fee', 'platform_fee_type', 'contact_email', 'phone']
        widgets = {
            'commission_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '10.00',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'platform_fee': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'platform_fee_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'admin@tapnex.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '+1234567890'
            })
        }
        labels = {
            'commission_rate': 'Commission Rate (%)',
            'platform_fee': 'Platform Fee',
            'platform_fee_type': 'Platform Fee Type',
            'contact_email': 'TapNex Contact Email',
            'phone': 'TapNex Contact Phone'
        }
        help_texts = {
            'commission_rate': 'Percentage commission taken from each booking (e.g., 10.00 for 10%)',
            'platform_fee': 'Platform fee amount - can be fixed (₹) or percentage (%) based on type selected',
            'platform_fee_type': 'Choose whether platform fee is a fixed amount per booking or a percentage of booking amount',
            'contact_email': 'Primary contact email for TapNex Technologies',
            'phone': 'Contact phone number for TapNex support'
        }
    
    def clean_commission_rate(self):
        rate = self.cleaned_data.get('commission_rate')
        if rate is not None:
            if rate < 0 or rate > 100:
                raise ValidationError("Commission rate must be between 0% and 100%")
        return rate
    
    def clean_platform_fee(self):
        fee = self.cleaned_data.get('platform_fee')
        if fee is not None:
            if fee < 0:
                raise ValidationError("Platform fee cannot be negative")
        return fee
    
    def clean(self):
        """Validate commission settings against Razorpay limits"""
        cleaned_data = super().clean()
        commission_rate = cleaned_data.get('commission_rate')
        platform_fee = cleaned_data.get('platform_fee')
        platform_fee_type = cleaned_data.get('platform_fee_type')
        
        if commission_rate is not None:
            from decimal import Decimal
            
            # Test with common booking amounts to check if owner_payout will be >= ₹1.00
            test_amounts = [Decimal('10.00'), Decimal('40.00'), Decimal('100.00')]
            warnings = []
            
            for amount in test_amounts:
                # Calculate owner payout
                commission = (amount * Decimal(str(commission_rate))) / Decimal('100')
                owner_payout = amount - commission
                
                if owner_payout < Decimal('1.00'):
                    warnings.append(
                        f"⚠️ For ₹{amount} bookings, owner will receive ₹{owner_payout:.2f} "
                        f"(below Razorpay's ₹1.00 minimum transfer limit)"
                    )
            
            if warnings:
                warning_msg = (
                    "WARNING: High commission rate may cause Razorpay transfer failures!\n\n" +
                    "\n".join(warnings) +
                    "\n\nRazorpay requires minimum ₹1.00 for transfers. "
                    "Consider lowering commission rate or increasing minimum booking prices."
                )
                raise ValidationError(warning_msg)
        
        return cleaned_data

class CafeOwnerManagementForm(forms.ModelForm):
    """Form for TapNex superuser to manage cafe owner account"""
    
    # User fields
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Last Name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Email Address'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Username'
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-2 focus:ring-blue-500 cursor-pointer'
        }),
        label='Account Active'
    )
    
    class Meta:
        from .models import CafeOwner
        model = CafeOwner
        fields = ['cafe_name', 'contact_email', 'phone']
        widgets = {
            'cafe_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Gaming Cafe Name'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Business Contact Email'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '+1234567890'
            })
        }
        labels = {
            'cafe_name': 'Gaming Cafe Name',
            'contact_email': 'Business Contact Email',
            'phone': 'Phone Number'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            # Populate user fields
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['username'].initial = self.instance.user.username
            self.fields['is_active'].initial = self.instance.user.is_active
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance and self.instance.user:
            # Check if username is taken by another user
            if User.objects.filter(username=username).exclude(id=self.instance.user.id).exists():
                raise ValidationError("This username is already taken.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance and self.instance.user:
            # Check if email is taken by another user
            if User.objects.filter(email=email).exclude(id=self.instance.user.id).exists():
                raise ValidationError("This email is already taken.")
        return email
    
    def save(self, commit=True):
        cafe_owner = super().save(commit=False)
        
        if commit and cafe_owner.user:
            # Update user fields
            cafe_owner.user.first_name = self.cleaned_data['first_name']
            cafe_owner.user.last_name = self.cleaned_data['last_name']
            cafe_owner.user.email = self.cleaned_data['email']
            cafe_owner.user.username = self.cleaned_data['username']
            cafe_owner.user.is_active = self.cleaned_data['is_active']
            cafe_owner.user.save()
            
            cafe_owner.save()
        
        return cafe_owner