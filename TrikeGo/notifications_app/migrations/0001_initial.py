from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=512)),
                ('auth', models.CharField(max_length=128)),
                ('p256dh', models.CharField(max_length=128)),
                ('user_agent', models.CharField(blank=True, max_length=256)),
                ('topics', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'endpoint')},
            },
        ),
        migrations.AddIndex(
            model_name='pushsubscription',
            index=models.Index(fields=['user', 'is_active'], name='notif_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='pushsubscription',
            index=models.Index(fields=['is_active'], name='notif_active_idx'),
        ),
    ]
