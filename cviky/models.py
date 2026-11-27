from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    neglect_days = models.PositiveSmallIntegerField(default=7)
