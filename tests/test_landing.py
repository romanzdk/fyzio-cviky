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


@pytest.mark.django_db
def test_installed_app_goes_straight_to_login_when_logged_out(client):
    response = client.get("/?app")
    assert response.status_code == 302
    assert response.url == "/prihlaseni/"


def test_manifest_starts_installed_app_with_app_flag(client):
    import json

    assert json.loads(client.get("/manifest.webmanifest").content)["start_url"] == "/?app"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/cviky/", "/cviky/novy/", "/serie/", "/profil/", "/instalace/", "/hotovo/"])
def test_private_pages_still_require_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert response.url.startswith("/prihlaseni/")


@pytest.mark.django_db
def test_pages_ask_not_to_be_indexed(client):
    for url in ("/", "/prihlaseni/"):
        assert '<meta name="robots" content="noindex, nofollow">' in client.get(url).content.decode()


@pytest.mark.django_db
def test_login_page_links_back_to_landing(client):
    assert 'href="/"' in client.get("/prihlaseni/").content.decode()


@pytest.mark.django_db
def test_landing_shows_sample_exercise_card_with_illustrations(client):
    page = client.get("/").content.decode()
    assert "cviky/body/krk" in page and "cviky/poloha/sed" in page
    assert "Ukázka karty cviku" in page
    assert "Opakování: 10× na každou stranu" in page
    assert page.count("<li>Sedni si") == 1


@pytest.mark.django_db
def test_pages_send_cookieless_visit_counts_to_goatcounter(client):
    tag = 'data-goatcounter="https://cviky.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'
    assert tag in client.get("/").content.decode()
    assert tag in client.get("/prihlaseni/").content.decode()


@pytest.mark.django_db
def test_pages_send_csp_and_inline_scripts_carry_its_nonce(client):
    response = client.get("/")
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    nonce = csp.split("'nonce-")[1].split("'")[0]
    assert response.content.decode().count(f'nonce="{nonce}"') == 2
    assert 'src="//' not in response.content.decode()
