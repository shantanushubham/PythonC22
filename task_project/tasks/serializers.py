from rest_framework import serializers

from tasks.models import Task, User


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "username", "email", "name"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)


class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "id",
            "user",
            "title",
            "description",
            "completed",
            "created_at",
            "updated_at",
            "due_date",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
