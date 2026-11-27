import pytest
from django.urls import reverse

from cviky.templatetags.cviky_extras import exercises_label


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


@pytest.mark.django_db
def test_pages_load_stylesheet_and_mark_active_tab(logged_in):
    html = logged_in.get(reverse("home")).content.decode()
    assert "cviky/app.css" in html
    nav = html[html.index('class="tabbar"'):]
    assert nav.index('aria-current="page"') < nav.index("Dnes") < nav.index("Cviky")


@pytest.mark.django_db
def test_exercise_pages_mark_cviky_tab_active(logged_in):
    html = logged_in.get(reverse("exercise_list")).content.decode()
    nav = html[html.index('class="tabbar"'):]
    assert nav.index('aria-current="page"') < nav.index("Cviky") < nav.index("Série")


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
