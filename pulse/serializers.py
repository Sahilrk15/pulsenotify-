from django.contrib.auth.models import User
from rest_framework import serializers

from .models import PriceAlert


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    # NOTE: no "role" field on purpose - role can never come from the request body.

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class PriceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceAlert
        fields = ['id', 'origin', 'destination', 'threshold_price', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']  # user is taken from request.user

    def validate_origin(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError('Origin cannot be blank.')
        return value

    def validate_destination(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError('Destination cannot be blank.')
        return value

    def validate_threshold_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Threshold price must be greater than 0.')
        return value
