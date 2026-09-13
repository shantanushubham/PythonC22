from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSignUpSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "phone_number", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """Used for PUT / PATCH on an existing user. Password is optional; when
    provided it is always hashed via set_password."""

    class Meta:
        model = User
        fields = ["id", "phone_number", "password", "first_name", "last_name", "email"]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "phone_number": {"required": False},
        }

    # Model present in DB is instance
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone_number = attrs["phone_number"]
        password = attrs["password"]

        user = authenticate(username=phone_number, password=password)

        if user is None:
            raise serializers.ValidationError("Invalid Credentials")

        refresh_token = RefreshToken.for_user(user)

        return {
            "access": str(refresh_token.access_token),
            "refresh": str(refresh_token),
        }
