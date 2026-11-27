from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cviky.models import Completion, Exercise, Series
from cviky.today import done_today, local_date, local_day_range, neglected, todays_series


@login_required
def home(request):
    now = timezone.now()
    today = local_date(now)
    rows = []
    for series in todays_series(request.user, today):
        done = done_today(request.user, series, today)
        items = [
            {"exercise": item.exercise, "checked": item.exercise_id in done}
            for item in series.items.select_related("exercise")
        ]
        rows.append(
            {
                "series": series,
                "items": items,
                "done_count": sum(1 for item in items if item["checked"]),
                "total": len(items),
            }
        )
    return render(
        request,
        "cviky/today.html",
        {"today": today, "rows": rows, "neglected": neglected(request.user, now)},
    )


@login_required
@require_POST
def toggle(request):
    exercise = get_object_or_404(Exercise, pk=request.POST.get("exercise"), user=request.user)
    series = None
    series_id = request.POST.get("series")
    if series_id:
        series = get_object_or_404(Series, pk=series_id, user=request.user)

    start, end = local_day_range(local_date(timezone.now()))
    existing = Completion.objects.filter(
        user=request.user, exercise=exercise, series=series, done_at__gte=start, done_at__lt=end
    )
    if existing.exists():
        existing.delete()
    else:
        Completion.objects.create(user=request.user, exercise=exercise, series=series)
    return redirect("home")
