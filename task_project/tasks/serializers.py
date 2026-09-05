from typing import override
from rest_framework import serializers

from tasks.models import Task, User
from tasks.utils import BCryptUtil


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "password", "role"]
        extra_kwargs = {"password": {"write_only": True}}
        read_only_fields = ["role"]

    @override
    def create(self, validated_data):
        password = validated_data["password"]
        validated_data.pop("password")
        # del validated_data["password"]
        hashed_password = BCryptUtil.hash_password(password)
        return User.objects.create(password=hashed_password, **validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=120)


class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "completed",
            "created_at",
            "updated_at",
            "due_date",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user"]
