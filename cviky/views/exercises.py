import unicodedata

from django.contrib.auth.decorators import login_required
from django.contrib.postgres.lookups import Unaccent
from django.db.models import CharField, F, Func, Q, Value
from django.shortcuts import get_object_or_404, redirect, render

from cviky.choices import AREAS, POSITIONS
from cviky.forms import ExerciseForm
from cviky.llm import structure_exercise
from cviky.models import Exercise, Series

MAX_TEXT_LENGTH = 5000

EMPTY_TEXT_ERROR = "Zadej popis cviku."
TOO_LONG_ERROR = f"Popis je příliš dlouhý (max {MAX_TEXT_LENGTH} znaků)."


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _keys_with_label(choices, word: str) -> list[str]:
    folded = _fold(word)
    if len(folded) < 3:
        return []
    # Czech inflects word endings (páteř/páteře, záda/zádech), so a 3-letter stem is compared too.
    stem = folded[:3]
    return [
        key
        for key, label in choices
        if folded in _fold(label) or any(part.startswith(stem) for part in _fold(label).replace("/", " ").split())
    ]


def search_exercises(user, q: str, area: str = "", position: str = "", series_id: int | None = None):
    queryset = Exercise.objects.filter(user=user)
    if area.strip():
        queryset = queryset.filter(area=area.strip())
    if position.strip():
        queryset = queryset.filter(position=position.strip())
    if series_id is not None:
        queryset = queryset.filter(series_items__series_id=series_id)

    words = q.split()
    if words:
        tags_text = Unaccent(
            Func(F("tags"), Value(" "), function="array_to_string", output_field=CharField())
        )
        queryset = queryset.annotate(tags_text=tags_text)
        # ponytail: icontains scan, per-user data is small; switch to SearchVector + GIN if one user has thousands
        for word in words:
            queryset = queryset.filter(
                Q(title__unaccent__icontains=word)
                | Q(steps__unaccent__icontains=word)
                | Q(original_text__unaccent__icontains=word)
                | Q(tags_text__unaccent__icontains=word)
                | Q(area__in=_keys_with_label(AREAS, word))
                | Q(position__in=_keys_with_label(POSITIONS, word))
            )
    return queryset


@login_required
def index(request):
    q = request.GET.get("q", "")
    area = request.GET.get("area", "")
    position = request.GET.get("position", "")
    serie = request.GET.get("serie", "")
    series_id = None
    if serie.isdigit():
        series_id = (
            Series.objects.filter(user=request.user, pk=int(serie)).values_list("pk", flat=True).first()
        )
    return render(
        request,
        "cviky/exercise_list.html",
        {
            "exercises": search_exercises(request.user, q, area, position, series_id),
            "q": q,
            "area": area,
            "position": position,
            "serie": serie,
            "series": Series.objects.filter(user=request.user),
            "areas": AREAS,
            "positions": POSITIONS,
        },
    )


def _prefill_title(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= 60:
        return normalized
    if normalized[60].isspace():
        return normalized[:60].rstrip() + "…"
    prefix = normalized[:60]
    if " " in prefix:
        prefix = prefix[: prefix.rfind(" ")]
    return prefix.rstrip() + "…"


def _review(request, draft, original_text):
    form = ExerciseForm(
        initial={
            "title": draft.title or _prefill_title(original_text),
            "area": draft.area,
            "position": draft.position,
            "tags": draft.tags,
            "steps": draft.steps,
            "cautions": draft.cautions,
            "reps": draft.reps,
            "original_text": original_text,
        }
    )
    return render(
        request,
        "cviky/exercise_create.html",
        {"step": "review", "form": form, "autofill_failed": not draft.title},
    )


@login_required
def create(request):
    if request.method == "POST":
        step = request.POST.get("step")
        if step == "dictate":
            text = request.POST.get("text", "").strip()
            if not text:
                return render(
                    request,
                    "cviky/exercise_create.html",
                    {"step": "dictate", "error": EMPTY_TEXT_ERROR, "text": text},
                )
            if len(text) > MAX_TEXT_LENGTH:
                return render(
                    request,
                    "cviky/exercise_create.html",
                    {"step": "dictate", "error": TOO_LONG_ERROR, "text": text},
                )
            return _review(request, structure_exercise(text), text)
        if step == "save":
            form = ExerciseForm(request.POST)
            if form.is_valid():
                exercise = form.save(commit=False)
                exercise.user = request.user
                exercise.save()
                return redirect("exercise_detail", pk=exercise.pk)
            return render(request, "cviky/exercise_create.html", {"step": "review", "form": form})
    return render(request, "cviky/exercise_create.html", {"step": "dictate"})


@login_required
def detail(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, user=request.user)
    return render(request, "cviky/exercise_detail.html", {"exercise": exercise})


@login_required
def edit(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, user=request.user)
    if request.method == "POST":
        form = ExerciseForm(request.POST, instance=exercise)
        if form.is_valid():
            form.save()
            return redirect("exercise_detail", pk=exercise.pk)
    else:
        form = ExerciseForm(instance=exercise)
    return render(request, "cviky/exercise_edit.html", {"exercise": exercise, "form": form})


@login_required
def delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk, user=request.user)
    if request.method == "POST":
        exercise.delete()
        return redirect("exercise_list")
    return render(request, "cviky/exercise_delete.html", {"exercise": exercise})
