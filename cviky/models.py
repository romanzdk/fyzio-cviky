import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models

from cviky.choices import AREAS, POSITIONS


class User(AbstractUser):
    neglect_days = models.PositiveSmallIntegerField(default=7)


class Exercise(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exercises")
    title = models.CharField(max_length=200)
    area = models.CharField(max_length=32, choices=AREAS, blank=True)
    position = models.CharField(max_length=32, choices=POSITIONS, blank=True)
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    steps = models.TextField(blank=True)
    cautions = models.TextField(blank=True)
    reps = models.CharField(max_length=100, blank=True)
    original_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


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
