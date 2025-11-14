# Generated migration file
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0004_alter_booking_destination_latitude_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='estimated_distance',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='estimated_duration',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='estimated_arrival',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Driver Assignment'),
                    ('accepted', 'Driver Accepted'),
                    ('on_the_way', 'Driver On The Way'),
                    ('started', 'Trip Started'),
                    ('completed', 'Completed'),
                    ('cancelled_by_rider', 'Cancelled by Rider'),
                    ('cancelled_by_driver', 'Cancelled by Driver'),
                    ('no_driver_found', 'No Driver Found')
                ],
                default='pending',
                max_length=20
            ),
        ),
        migrations.CreateModel(
            name='DriverLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latitude', models.DecimalField(decimal_places=15, max_digits=18)),
                ('longitude', models.DecimalField(decimal_places=15, max_digits=18)),
                ('heading', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('speed', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('accuracy', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('timestamp', models.DateTimeField(auto_now=True)),
                ('driver', models.OneToOneField(
                    limit_choices_to={'trikego_user': 'D'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='current_location',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Driver Location',
                'verbose_name_plural': 'Driver Locations',
            },
        ),
        migrations.CreateModel(
            name='RouteSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('route_data', models.JSONField()),
                ('distance', models.DecimalField(decimal_places=2, max_digits=10)),
                ('duration', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('booking', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='routes',
                    to='booking.booking'
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]