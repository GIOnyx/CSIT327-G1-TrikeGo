from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0006_booking_booking_boo_status_e01616_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='passengers',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
