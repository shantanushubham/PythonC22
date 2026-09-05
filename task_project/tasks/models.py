from django.db import models


# Create your models here.
class User(models.Model):

    class Role(models.TextChoices):
        ADMIN = "Admin"
        USER = "User"

    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, null=False)
    password = models.CharField(max_length=70)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)


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

    class Meta:
        indexes = [models.Index(fields=["description"])]
