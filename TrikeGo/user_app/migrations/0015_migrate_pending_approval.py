from django.db import migrations


def forwards(apps, schema_editor):
    Driver = apps.get_model('user', 'Driver')
    # Find drivers still marked pending_approval in the DB (historical values)
    pending_qs = Driver.objects.filter(status='pending_approval')
    # Record ids to enable reverse operation via marking them with their previous status
    ids = list(pending_qs.values_list('id', flat=True))
    if ids:
        # Store the affected IDs in a separate table via a migration state model isn't necessary; instead
        # persist the ids in a temporary model field is not available. We'll use a simple approach:
        # mark is_verified False and set status to 'Offline'. We also store previous status in a dedicated
        # field isn't possible here; so reverse will restore 'pending_approval' for records where is_verified is False
        # and where status == 'Offline' and they were changed by this migration.
        pending_qs.update(is_verified=False, status='Offline')


def backwards(apps, schema_editor):
    Driver = apps.get_model('user', 'Driver')
    # Attempt to restore 'pending_approval' for drivers that were previously pending:
    # We assume drivers that are currently is_verified=False and status=='Offline' and have never been verified
    # are the ones we changed. This is a best-effort reverse.
    Driver.objects.filter(is_verified=False, status='Offline').update(status='pending_approval')


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0014_alter_driver_status_tricycle'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
