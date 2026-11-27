import html

import pytest


@pytest.mark.django_db
def test_anonymous_visitor_sees_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    page = html.unescape(response.content.decode())
    assert "Přihlásit se" in page and 'href="/prihlaseni/"' in page
    assert "https://romanzdk.com" in page
    assert "mailto:romanzdk@gmail.com" in page
    assert 'class="tabbar"' not in page


@pytest.mark.django_db
def test_email_is_not_in_plain_text_in_the_source(client):
    assert "romanzdk@gmail.com" not in client.get("/").content.decode()


@pytest.mark.django_db
def test_logged_in_user_still_gets_today(client, django_user_model):
    client.force_login(django_user_model.objects.create_user(username="l", password="SilneHeslo123"))
    page = client.get("/").content.decode()
    assert "<h1>Dnes</h1>" in page
    assert "romanzdk.com" not in page
