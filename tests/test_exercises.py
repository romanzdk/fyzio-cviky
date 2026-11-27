import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.urls import reverse

from cviky.choices import AREAS, POSITIONS
from cviky.llm import ExerciseDraft
from cviky.models import Exercise
from cviky.views import exercises as exercises_views

User = get_user_model()

DRAFT = ExerciseDraft(
    title="Uvolnění krku",
    area="krk",
    position="sed",
    tags=["krční páteř", "šíje"],
    steps="Pomalu otáčej hlavu.",
    cautions="Nepřekračuj bolest.",
    reps="10× na každou stranu",
)


@pytest.fixture
def user(db):
    return User.objects.create_user(username="a", password="SilneHeslo123")


@pytest.fixture
def other(db):
    return User.objects.create_user(username="b", password="SilneHeslo123")


@pytest.fixture
def logged_in(client, user):
    client.force_login(user)
    return client


def _mock_draft(monkeypatch, draft):
    monkeypatch.setattr(exercises_views, "structure_exercise", lambda text: draft)


@pytest.mark.django_db
def test_dictate_shows_prefilled_form(logged_in, monkeypatch):
    _mock_draft(monkeypatch, DRAFT)
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "nějaký diktát"})
    assert response.status_code == 200
    assert "Uvolnění krku" in response.content.decode()
    assert Exercise.objects.count() == 0


@pytest.mark.django_db
def test_save_keeps_original_text(logged_in, monkeypatch):
    _mock_draft(monkeypatch, DRAFT)
    response = logged_in.post(
        reverse("exercise_create"),
        {
            "step": "save",
            "title": DRAFT.title,
            "area": DRAFT.area,
            "position": DRAFT.position,
            "tags": ", ".join(DRAFT.tags),
            "steps": DRAFT.steps,
            "cautions": DRAFT.cautions,
            "reps": DRAFT.reps,
            "original_text": "původní diktovaný text",
        },
    )
    assert response.status_code == 302
    exercise = Exercise.objects.get()
    assert exercise.original_text == "původní diktovaný text"
    assert exercise.tags == DRAFT.tags
    assert response.url == reverse("exercise_detail", args=[exercise.pk])


@pytest.mark.django_db
def test_llm_failure_still_allows_save(logged_in, monkeypatch):
    _mock_draft(monkeypatch, ExerciseDraft())
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "můj diktát"})
    assert response.status_code == 200
    assert "můj diktát" in response.content.decode()
    response = logged_in.post(
        reverse("exercise_create"),
        {"step": "save", "title": "Ručně pojmenovaný cvik", "original_text": "můj diktát"},
    )
    assert response.status_code == 302
    exercise = Exercise.objects.get()
    assert exercise.title == "Ručně pojmenovaný cvik"
    assert exercise.original_text == "můj diktát"


@pytest.mark.django_db
def test_empty_text_rejected(logged_in):
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "   "})
    assert response.status_code == 200
    assert Exercise.objects.count() == 0
    assert "Zadej" in response.content.decode()


@pytest.mark.django_db
def test_text_over_5000_chars_rejected(logged_in):
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "x" * 5001})
    assert response.status_code == 200
    assert Exercise.objects.count() == 0
    assert "5000" in response.content.decode()


@pytest.mark.django_db
def test_search_ignores_diacritics(logged_in, user):
    Exercise.objects.create(user=user, title="Uvolnění krční páteře")
    response = logged_in.get(reverse("exercise_list"), {"q": "pater"})
    assert "Uvolnění krční páteře" in response.content.decode()


@pytest.mark.django_db
def test_search_matches_tags(logged_in, user):
    Exercise.objects.create(user=user, title="Cvik", tags=["šíje"])
    response = logged_in.get(reverse("exercise_list"), {"q": "sije"})
    assert "Cvik" in response.content.decode()


@pytest.mark.django_db
def test_search_requires_all_words(logged_in, user):
    Exercise.objects.create(user=user, title="Uvolnění krku vsedě")
    Exercise.objects.create(user=user, title="Uvolnění krku vleže")
    response = logged_in.get(reverse("exercise_list"), {"q": "uvolneni vleze"})
    content = response.content.decode()
    assert "Uvolnění krku vleže" in content
    assert "vsedě" not in content


@pytest.mark.django_db
def test_filters_area_and_position(logged_in, user):
    Exercise.objects.create(user=user, title="Sedící krk", area="krk", position="sed")
    Exercise.objects.create(user=user, title="Stojící bedra", area="bederni", position="stoj")
    content = logged_in.get(reverse("exercise_list"), {"area": "krk", "position": "sed"}).content.decode()
    assert "Sedící krk" in content
    assert "Stojící bedra" not in content


@pytest.mark.django_db
def test_search_does_not_leak_other_users(logged_in, user, other):
    Exercise.objects.create(user=other, title="Cizí tajný cvik")
    content = logged_in.get(reverse("exercise_list")).content.decode()
    assert "Cizí tajný cvik" not in content


@pytest.mark.django_db
def test_other_users_exercise_404(logged_in, other):
    exercise = Exercise.objects.create(user=other, title="Cizí")
    for name in ("exercise_detail", "exercise_edit", "exercise_delete"):
        response = logged_in.get(reverse(name, args=[exercise.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
def test_add_another_button_after_save(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Cvik")
    content = logged_in.get(reverse("exercise_detail", args=[exercise.pk])).content.decode()
    assert "Přidat další cvik" in content
    assert reverse("exercise_create") in content


@pytest.mark.django_db
def test_edit_updates_exercise(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Starý")
    response = logged_in.post(
        reverse("exercise_edit", args=[exercise.pk]),
        {"title": "Nový", "original_text": ""},
    )
    assert response.status_code == 302
    exercise.refresh_from_db()
    assert exercise.title == "Nový"


@pytest.mark.django_db
def test_delete_requires_post_and_removes(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Zmizík")
    assert logged_in.get(reverse("exercise_delete", args=[exercise.pk])).status_code == 200
    response = logged_in.post(reverse("exercise_delete", args=[exercise.pk]))
    assert response.status_code == 302
    assert not Exercise.objects.filter(pk=exercise.pk).exists()


def test_every_area_and_position_has_an_svg():
    for key, _ in AREAS:
        assert finders.find(f"cviky/body/{key}.svg"), key
    for key, _ in POSITIONS:
        assert finders.find(f"cviky/poloha/{key}.svg"), key


def test_illustration_renders_for_every_area_and_position():
    for key, label in AREAS:
        html = render_to_string("cviky/ilustrace.html", {"area": key, "position": ""})
        assert f"cviky/body/{key}.svg" in html
        assert f'alt="{label}"' in html
    for key, label in POSITIONS:
        html = render_to_string("cviky/ilustrace.html", {"area": "", "position": key})
        assert f"cviky/poloha/{key}.svg" in html
        assert f'alt="{label}"' in html
    empty = render_to_string("cviky/ilustrace.html", {"area": "", "position": ""})
    assert "<img" not in empty
