from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from cviky.forms import SeriesForm
from cviky.models import Exercise, Series, SeriesExercise


def _exercise_rows(user, series=None):
    selected = {}
    if series is not None:
        selected = {item.exercise_id: item.order for item in series.items.all()}
    return [
        {
            "exercise": exercise,
            "checked": exercise.pk in selected,
            "order": selected.get(exercise.pk, ""),
        }
        for exercise in Exercise.objects.filter(user=user)
    ]


def _selected_exercise_ids(request, user):
    posted = {int(value) for value in request.POST.getlist("exercises") if value.isdigit()}
    own = Exercise.objects.filter(user=user, pk__in=posted).values_list("pk", flat=True)
    return set(own)


def _order(request, exercise_id):
    value = request.POST.get(f"order_{exercise_id}", "")
    return int(value) if value.isdigit() else 0


def _sync_items(request, series):
    selected = _selected_exercise_ids(request, series.user)
    existing = {item.exercise_id: item for item in series.items.all()}
    for exercise_id, item in existing.items():
        if exercise_id not in selected:
            item.delete()
    for exercise_id in selected:
        if exercise_id in existing:
            item = existing[exercise_id]
            item.order = _order(request, exercise_id)
            item.save(update_fields=["order"])
        else:
            SeriesExercise.objects.create(
                series=series,
                exercise_id=exercise_id,
                order=_order(request, exercise_id),
            )


def _form(request, series=None):
    if request.method == "POST":
        form = SeriesForm(request.POST, instance=series)
        if form.is_valid():
            series = form.save(commit=False)
            series.user = request.user
            series.save()
            _sync_items(request, series)
            return redirect("series_list")
    else:
        form = SeriesForm(instance=series)
    return render(
        request,
        "cviky/series_form.html",
        {"form": form, "series": series, "rows": _exercise_rows(request.user, series)},
    )


@login_required
def index(request):
    series = Series.objects.filter(user=request.user).annotate(exercise_count=Count("items"))
    return render(request, "cviky/series_list.html", {"series": series})


@login_required
def create(request):
    return _form(request)


@login_required
def edit(request, pk):
    series = get_object_or_404(Series, pk=pk, user=request.user)
    return _form(request, series)


@login_required
def delete(request, pk):
    series = get_object_or_404(Series, pk=pk, user=request.user)
    if request.method == "POST":
        series.delete()
        return redirect("series_list")
    return render(request, "cviky/series_delete.html", {"series": series})
