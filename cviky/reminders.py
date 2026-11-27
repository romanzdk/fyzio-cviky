import json
import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pywebpush import WebPushException, webpush

from cviky.models import PushSubscription, ReminderSent, Series
from cviky.today import done_today, local_date, neglected

logger = logging.getLogger(__name__)

WINDOW = timedelta(minutes=60)


def _window(series: Series, today):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(today, series.remind_at), tz)
    end = start + WINDOW
    midnight = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
    return start, min(end, midnight)


def _is_due(series: Series, now: datetime, today) -> bool:
    if series.remind_at is None or today.weekday() not in (series.weekdays or []):
        return False
    start, end = _window(series, today)
    return start <= timezone.localtime(now) < end


def due_series(now: datetime) -> list[Series]:
    today = local_date(now)
    due = []
    for series in Series.objects.filter(remind_at__isnull=False).select_related("user"):
        if not _is_due(series, now, today):
            continue
        exercise_ids = set(series.items.values_list("exercise_id", flat=True))
        if not exercise_ids:
            continue
        if exercise_ids <= done_today(series.user, series, today):
            continue
        if ReminderSent.objects.filter(series=series, date=today).exists():
            continue
        due.append(series)
    return due


def _plural(count: int, one: str, few: str, many: str) -> str:
    if count == 1:
        form = one
    elif 2 <= count <= 4:
        form = few
    else:
        form = many
    return f"{count} {form}"


def reminder_text(series: Series, neglected_count: int) -> tuple[str, str]:
    body = _plural(series.items.count(), "cvik", "cviky", "cviků")
    if neglected_count > 0:
        body += " + " + _plural(
            neglected_count, "dlouho nedělaný", "dlouho nedělané", "dlouho nedělaných"
        )
    return series.name, body


def _neglected_count(series: Series, now: datetime) -> int:
    exercise_ids = set(series.items.values_list("exercise_id", flat=True))
    return sum(1 for exercise, _ in neglected(series.user, now) if exercise.pk in exercise_ids)


def _send(series: Series, now: datetime) -> None:
    title, body = reminder_text(series, _neglected_count(series, now))
    payload = json.dumps({"title": title, "body": body, "url": "/"})
    for subscription in PushSubscription.objects.filter(user=series.user):
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=3600,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                subscription.delete()
            else:
                logger.warning("Push failed for %s: %s", subscription.endpoint, exc)


def send_due(now: datetime) -> int:
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY is not set, skipping reminders")
        return 0
    count = 0
    for series in due_series(now):
        today = local_date(now)
        with transaction.atomic():
            _, created = ReminderSent.objects.get_or_create(series=series, date=today)
        if not created:
            continue
        count += 1
        _send(series, now)
    return count
