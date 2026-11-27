import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    neglect_days = models.PositiveSmallIntegerField(default=7)


class Invite(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_by = models.ForeignKey(
        "cviky.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invites",
    )
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return str(self.token)
