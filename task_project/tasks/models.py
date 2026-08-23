from ast import mod
from django.db import models


# Create your models here.
class User(models.Model):

    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, null=False)


class Task(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")

    # T -> U
    # user = User.objects.get(id=1)
    # user.tasks
    title = models.CharField(max_length=255)
    description = models.TextField()
    completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    due_date = models.DateField()
