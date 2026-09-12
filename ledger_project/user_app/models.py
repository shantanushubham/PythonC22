from enum import unique
from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):

    # add user_related_fields
    username = None
    phone_number = models.CharField(unique=True, max_length=12, blank=False)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []