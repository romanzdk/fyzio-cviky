import pytest
from django.urls import reverse

from cviky.models import Exercise, Series
from cviky.templatetags.cviky_extras import exercises_label, step_lines


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "0 cviků"), (1, "1 cvik"), (2, "2 cviky"), (4, "4 cviky"), (5, "5 cviků")],
)
def test_exercises_label_plural(count, expected):
    assert exercises_label(count) == expected


@pytest.fixture
def logged_in(client, django_user_model):
    user = django_user_model.objects.create_user(username="design", password="SilneHeslo123")
    client.force_login(user)
    return client


def _active_tab(html):
    nav = html[html.index('<nav class="tabbar"'):]
    assert nav.count('aria-current="page"') == 1
    return nav[: nav.index('aria-current="page"')].rsplit("<a ", 1)[1]


@pytest.mark.django_db
def test_pages_load_stylesheet_and_mark_active_tab(logged_in):
    html = logged_in.get(reverse("home")).content.decode()
    assert "cviky/app.css" in html
    assert 'aria-label="Hlavní navigace"' in html
    assert 'href="/"' in _active_tab(html)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "href"),
    [
        ("/cviky/", "/cviky/"),
        ("/cviky/novy/", "/cviky/"),
        ("/serie/", "/serie/"),
        ("/serie/nova/", "/serie/"),
        ("/profil/", "/profil/"),
        ("/instalace/", "/profil/"),
    ],
)
def test_each_section_marks_one_tab_active(logged_in, url, href):
    assert f'href="{href}"' in _active_tab(logged_in.get(url).content.decode())


@pytest.mark.django_db
def test_login_page_has_no_tabbar(client):
    html = client.get(reverse("login")).content.decode()
    assert "cviky/app.css" in html
    assert 'class="tabbar"' not in html


@pytest.mark.django_db
def test_dictate_button_shown_on_home_but_not_on_create(logged_in):
    assert 'class="fab"' in logged_in.get(reverse("home")).content.decode()
    assert 'class="fab"' not in logged_in.get(reverse("exercise_create")).content.decode()


@pytest.mark.django_db
def test_login_is_czech_even_for_english_browser(client):
    html = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9").content.decode()
    assert "Uživatelské jméno" in html


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sedni si.\nOtoč hlavu.", ["Sedni si.", "Otoč hlavu."]),
        ("1. Sedni si.\n2) Otoč hlavu.\n\n  3 . Vydrž", ["Sedni si.", "Otoč hlavu.", "Vydrž"]),
        ("10× opakuj", ["10× opakuj"]),
        ("", []),
    ],
)
def test_step_lines_strip_numbering_and_blank_lines(text, expected):
    assert step_lines(text) == expected


@pytest.mark.django_db
def test_check_button_exposes_pressed_state(logged_in, django_user_model):
    user = django_user_model.objects.get(username="design")
    exercise = Exercise.objects.create(user=user, title="Krk")
    series = Series.objects.create(user=user, name="S", weekdays=list(range(7)))
    series.items.create(exercise=exercise, order=0)
    assert 'aria-pressed="false"' in logged_in.get("/").content.decode()
    logged_in.post("/hotovo/", {"exercise": exercise.pk, "series": series.pk})
    assert 'aria-pressed="true"' in logged_in.get("/").content.decode()


@pytest.mark.django_db
def test_filters_say_all_when_empty(logged_in):
    html = logged_in.get("/cviky/").content.decode()
    for name in ("Oblast", "Poloha", "Série"):
        assert f'<option value="">{name}: vše</option>' in html


@pytest.mark.django_db
def test_series_delete_warns_about_history(logged_in, django_user_model):
    user = django_user_model.objects.get(username="design")
    series = Series.objects.create(user=user, name="S")
    html = logged_in.get(f"/serie/{series.pk}/smazat/").content.decode()
    assert "historie odkliknutí" in html
