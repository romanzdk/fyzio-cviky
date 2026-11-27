from datetime import date, datetime, time, timedelta

from django.db.models import Max, Min
from django.utils import timezone

from cviky.models import Completion, Exercise, Series, SeriesExercise


def local_date(dt: datetime) -> date:
    return timezone.localtime(dt).date()


def local_day_range(today: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(today, time.min), tz)
    end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
    return start, end


def todays_series(user, today: date) -> list[Series]:
    return list(
        Series.objects.filter(user=user, weekdays__contains=[today.weekday()]).order_by("name")
    )


def done_today(user, series: Series, today: date) -> set[int]:
    start, end = local_day_range(today)
    return set(
        Completion.objects.filter(
            user=user, series=series, done_at__gte=start, done_at__lt=end
        ).values_list("exercise_id", flat=True)
    )


def neglected(user, now: datetime) -> list[tuple[Exercise, int]]:
    exercises = list(Exercise.objects.filter(user=user, series_items__isnull=False).distinct())
    if not exercises:
        return []

    last_done = {
        row["exercise_id"]: row["last"]
        for row in Completion.objects.filter(user=user, exercise__in=exercises)
        .values("exercise_id")
        .annotate(last=Max("done_at"))
    }
    added = {
        row["exercise_id"]: row["first"]
        for row in SeriesExercise.objects.filter(series__user=user, exercise__in=exercises)
        .values("exercise_id")
        .annotate(first=Min("added_at"))
    }

    today = local_date(now)
    result = []
    for exercise in exercises:
        reference = last_done.get(exercise.pk) or added.get(exercise.pk)
        if reference is None:
            continue
        days = (today - local_date(reference)).days
        if days >= user.neglect_days:
            result.append((exercise, days))
    result.sort(key=lambda item: item[1], reverse=True)
    return result
