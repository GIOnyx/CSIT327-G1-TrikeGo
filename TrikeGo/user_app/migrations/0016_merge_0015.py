from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0015_migrate_pending_approval'),
        ('user', '0015_remove_tricycle_capacity_alter_tricycle_table'),
    ]

    operations = [
        # This is an empty merge migration that joins the two 0015 branches.
    ]
