from typing import Any, Dict

from rest_framework import serializers

from .models import PushSubscription


class PushSubscriptionSerializer(serializers.ModelSerializer):
    endpoint = serializers.URLField(max_length=512)
    keys = serializers.DictField(child=serializers.CharField(), write_only=True)
    topics = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
        default=list,
    )

    class Meta:
        model = PushSubscription
        fields = (
            'id',
            'endpoint',
            'keys',
            'topics',
            'user_agent',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'is_active', 'created_at', 'updated_at')

    def validate_keys(self, value: Dict[str, Any]) -> Dict[str, Any]:
        if 'auth' not in value or 'p256dh' not in value:
            raise serializers.ValidationError('Both auth and p256dh keys are required.')
        return value

    def create(self, validated_data: Dict[str, Any]) -> PushSubscription:
        keys = validated_data.pop('keys', {})
        instance, _created = PushSubscription.objects.update_or_create(
            user=validated_data['user'],
            endpoint=validated_data['endpoint'],
            defaults={
                'auth': keys.get('auth', ''),
                'p256dh': keys.get('p256dh', ''),
                'topics': validated_data.get('topics', []),
                'user_agent': validated_data.get('user_agent', ''),
                'is_active': True,
            },
        )
        return instance

    def update(self, instance: PushSubscription, validated_data: Dict[str, Any]) -> PushSubscription:
        keys = validated_data.pop('keys', None) or {}
        instance.auth = keys.get('auth', instance.auth)
        instance.p256dh = keys.get('p256dh', instance.p256dh)
        instance.topics = validated_data.get('topics', instance.topics)
        instance.user_agent = validated_data.get('user_agent', instance.user_agent)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save(update_fields=['auth', 'p256dh', 'topics', 'user_agent', 'is_active', 'updated_at'])
        return instance
