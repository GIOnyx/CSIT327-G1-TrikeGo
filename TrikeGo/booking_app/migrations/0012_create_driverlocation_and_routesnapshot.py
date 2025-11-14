"""Database-only migration to create DriverLocation and RouteSnapshot tables.

These models' state is already recorded in earlier migrations, but the database
tables were missing (likely due to a previous faked migration). This migration
creates the missing tables without changing Django's migration state.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0005_add_tracking'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
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
                            related_name='current_location',
                            to='user.customuser',
                            on_delete=django.db.models.deletion.CASCADE,
                            limit_choices_to={'trikego_user': 'D'},
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
                        ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routes', to='booking.booking')),
                    ],
                    options={
                        'ordering': ['-created_at'],
                    },
                ),
            ],
        ),
    ]
