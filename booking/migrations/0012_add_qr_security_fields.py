# Generated migration for QR verification security enhancements

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0011_remove_qr_code_field'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add token_expires_at field
        migrations.AddField(
            model_name='booking',
            name='token_expires_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                db_index=True,
                help_text='Timestamp when verification token expires'
            ),
        ),
        
        # Make verification_token unique
        migrations.AlterField(
            model_name='booking',
            name='verification_token',
            field=models.CharField(
                max_length=100,
                unique=True,
                db_index=True,
                blank=True,
                null=True,
                help_text='Unique token for QR code verification (dynamically generated, no file storage)'
            ),
        ),
        
        # Add verification_attempts field for audit trail
        migrations.AddField(
            model_name='booking',
            name='verification_attempts',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of failed verification attempts'
            ),
        ),
        
        # Add last_verification_attempt field
        migrations.AddField(
            model_name='booking',
            name='last_verification_attempt',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Timestamp of last verification attempt'
            ),
        ),
    ]
