import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.cache import cache
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
def test_search_matches_area_and_position_labels(user):
    hrudni = Exercise.objects.create(user=user, title="Rotace", area="hrudni", position="sed")
    bederni = Exercise.objects.create(user=user, title="Most", area="bederni", position="leh_zada")
    Exercise.objects.create(user=user, title="Kolena", area="kolena", position="stoj")
    panev = Exercise.objects.create(user=user, title="Pánev", area="panev", position="leh_bricho")

    assert set(exercises_views.search_exercises(user, "páteř")) == {hrudni, bederni}
    assert set(exercises_views.search_exercises(user, "pater zadech")) == {bederni}
    assert set(exercises_views.search_exercises(user, "SED")) == {hrudni}
    assert set(exercises_views.search_exercises(user, "kycle")) == {panev}
    assert set(exercises_views.search_exercises(user, "xyz")) == set()


@pytest.mark.django_db
def test_search_matches_other_word_forms_of_labels(user):
    hrudni = Exercise.objects.create(user=user, title="Rotace", area="hrudni", position="sed")
    bederni = Exercise.objects.create(user=user, title="Most", area="bederni", position="leh_zada")
    bricho = Exercise.objects.create(user=user, title="Plavec", area="cele_telo", position="leh_bricho")

    assert set(exercises_views.search_exercises(user, "páteře")) == {hrudni, bederni}
    assert set(exercises_views.search_exercises(user, "záda")) == {bederni}
    assert set(exercises_views.search_exercises(user, "břicho")) == {bricho}
    assert set(exercises_views.search_exercises(user, "na")) == set()


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


LONG_TEXT = "Pomalu otáčej hlavu do strany a drž ramena uvolněná po celou dobu cvičení, dýchej klidně"
PREFILLED_TITLE = "Pomalu otáčej hlavu do strany a drž ramena uvolněná po celou…"
AUTOFILL_NOTE = "Automatické zpracování se nepovedlo, doplň kartu ručně."


@pytest.mark.django_db
def test_empty_draft_shows_original_text_prefilled_title_and_note(logged_in, monkeypatch):
    _mock_draft(monkeypatch, ExerciseDraft())
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": LONG_TEXT})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Původní text" in content
    assert LONG_TEXT in content
    assert PREFILLED_TITLE in content
    assert AUTOFILL_NOTE in content


@pytest.mark.django_db
def test_empty_draft_saves_without_retyping(logged_in, monkeypatch):
    _mock_draft(monkeypatch, ExerciseDraft())
    logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": LONG_TEXT})
    response = logged_in.post(
        reverse("exercise_create"),
        {"step": "save", "title": PREFILLED_TITLE, "original_text": LONG_TEXT},
    )
    assert response.status_code == 302
    exercise = Exercise.objects.get()
    assert exercise.title == PREFILLED_TITLE
    assert exercise.original_text == LONG_TEXT


@pytest.mark.django_db
def test_successful_draft_has_no_autofill_note(logged_in, monkeypatch):
    _mock_draft(monkeypatch, DRAFT)
    response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "nějaký diktát"})
    assert AUTOFILL_NOTE not in response.content.decode()


@pytest.mark.django_db
def test_detail_shows_original_text(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Cvik", original_text="původní diktát")
    content = logged_in.get(reverse("exercise_detail", args=[exercise.pk])).content.decode()
    assert "Původní text" in content
    assert "původní diktát" in content
    assert "umělá inteligence" in content


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Krátký popis", "Krátký popis"),
        ("x" * 100, "x" * 60 + "…"),
        (
            "Pomalu otáčej hlavu do strany a drž ramena uvolněná po celou dobu cvičení",
            "Pomalu otáčej hlavu do strany a drž ramena uvolněná po celou…",
        ),
        ("cvik " * 12 + "dlouhy", "cvik cvik cvik cvik cvik cvik cvik cvik cvik cvik cvik cvik…"),
    ],
)
def test_prefill_title_cuts_at_word_boundary(text, expected):
    assert exercises_views._prefill_title(text) == expected


def test_every_area_and_position_has_an_svg():
    for key, _ in AREAS:
        assert finders.find(f"cviky/body/{key}.svg"), key
    for key, _ in POSITIONS:
        assert finders.find(f"cviky/poloha/{key}.svg"), key


@pytest.mark.django_db
def test_detail_shows_illustrations_for_every_area_and_position(client, django_user_model):
    user = django_user_model.objects.create_user(username="ilu", password="SilneHeslo123")
    client.force_login(user)
    for (area, area_label), (position, position_label) in zip(AREAS, POSITIONS * 2, strict=False):
        exercise = Exercise.objects.create(user=user, title="Cvik", area=area, position=position)
        html = client.get(reverse("exercise_detail", args=[exercise.pk])).content.decode()
        assert f"cviky/body/{area}.svg" in html
        assert f'alt="{area_label}"' in html
        assert f"cviky/poloha/{position}.svg" in html
        assert f'alt="{position_label}"' in html
    bare = Exercise.objects.create(user=user, title="Bez ikon")
    assert "<figure>" not in client.get(reverse("exercise_detail", args=[bare.pk])).content.decode()


@pytest.mark.django_db
def test_llm_calls_capped_per_user_per_day(logged_in, monkeypatch):
    calls = []
    monkeypatch.setattr(exercises_views, "structure_exercise", lambda text: calls.append(text) or DRAFT)
    monkeypatch.setattr(exercises_views, "DAILY_LLM_LIMIT", 2)
    cache.clear()
    for _ in range(3):
        response = logged_in.post(reverse("exercise_create"), {"step": "dictate", "text": "diktát"})
    assert len(calls) == 2
    assert "Automatické zpracování se nepovedlo" in response.content.decode()
    cache.clear()


@pytest.mark.django_db
def test_empty_list_offers_first_exercise(logged_in):
    assert "Nadiktovat první cvik" in logged_in.get(reverse("exercise_list")).content.decode()
    assert "Přidat další cvik" in logged_in.get(reverse("exercise_list") + "?q=nic").content.decode()
