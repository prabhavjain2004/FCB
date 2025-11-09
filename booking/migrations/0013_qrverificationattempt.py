# Generated migration for QR Verification Audit Trail

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('booking', '0012_add_qr_security_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='QRVerificationAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_used', models.CharField(help_text='Token that was attempted (first 20 chars for security)', max_length=100)),
                ('attempt_type', models.CharField(choices=[('SUCCESS', 'Successful Verification'), ('FAILED_INVALID_TOKEN', 'Invalid Token'), ('FAILED_EXPIRED_TOKEN', 'Expired Token'), ('FAILED_WRONG_DATE', 'Wrong Date'), ('FAILED_WRONG_TIME', 'Wrong Time'), ('FAILED_UNPAID', 'Unpaid Booking'), ('FAILED_CANCELLED', 'Cancelled Booking'), ('FAILED_COMPLETED', 'Already Completed'), ('FAILED_ALREADY_VERIFIED', 'Already Verified'), ('FAILED_RATE_LIMIT', 'Rate Limit Exceeded')], help_text='Type of verification attempt', max_length=30)),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of verification attempt', null=True)),
                ('user_agent', models.CharField(blank=True, help_text='User agent of verification attempt', max_length=500)),
                ('failure_reason', models.TextField(blank=True, help_text='Detailed reason for failure')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When the attempt was made')),
                ('booking', models.ForeignKey(blank=True, help_text='Booking being verified (null if token not found)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='verification_attempts_log', to='booking.booking')),
                ('verified_by', models.ForeignKey(blank=True, help_text='Owner/staff who attempted verification', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qr_verification_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'QR Verification Attempt',
                'verbose_name_plural': 'QR Verification Attempts',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='qrverificationattempt',
            index=models.Index(fields=['booking', '-timestamp'], name='qr_attempt_booking_idx'),
        ),
        migrations.AddIndex(
            model_name='qrverificationattempt',
            index=models.Index(fields=['attempt_type', '-timestamp'], name='qr_attempt_type_idx'),
        ),
        migrations.AddIndex(
            model_name='qrverificationattempt',
            index=models.Index(fields=['verified_by', '-timestamp'], name='qr_attempt_user_idx'),
        ),
        migrations.AddIndex(
            model_name='qrverificationattempt',
            index=models.Index(fields=['-timestamp'], name='qr_attempt_time_idx'),
        ),
    ]
