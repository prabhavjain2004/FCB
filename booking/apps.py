from django.apps import AppConfig


class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booking'
    verbose_name = 'Gaming Cafe Booking System'
    
    def ready(self):
        # Import signals
        import booking.signals
        
        # Import audit model so Django discovers it
        # This is the correct place to import models (after apps are ready)
        from . import models_qr_verification_audit
