from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "email", "first_name", "last_name", "is_staff")
        read_only_fields = (
            "id",
            "email",
            "is_staff",
        )

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "email", "first_name", "last_name", "password", "is_staff")
        read_only_fields = (
            "id",
            "is_staff",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
            }
        }

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)
