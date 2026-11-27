import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

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


class Series(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="series")
    name = models.CharField(max_length=200)
    weekdays = ArrayField(models.PositiveSmallIntegerField(), default=list, blank=True)
    remind_at = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SeriesExercise(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="series_items")
    order = models.PositiveSmallIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["series", "exercise"], name="unique_series_exercise")
        ]

    def __str__(self):
        return f"{self.series} – {self.exercise}"


class Completion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="completions")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="completions")
    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, null=True, blank=True, related_name="completions"
    )
    done_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-done_at"]

    def __str__(self):
        return f"{self.exercise} – {self.done_at:%Y-%m-%d}"


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.endpoint


class ReminderSent(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name="reminders_sent")
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["series", "date"], name="unique_reminder_sent")
        ]

    def __str__(self):
        return f"{self.series} – {self.date}"


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
