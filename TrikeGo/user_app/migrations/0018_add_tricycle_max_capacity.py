from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0017_alter_driver_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='tricycle',
            name='max_capacity',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
