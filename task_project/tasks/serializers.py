from rest_framework import serializers

from tasks.models import User


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "username", "email", "name"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)