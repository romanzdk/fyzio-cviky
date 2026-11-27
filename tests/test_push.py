import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from config import settings as config_settings
from cviky.models import PushSubscription

User = get_user_model()

ENDPOINT = "https://push.example.com/sub/abc"
KEYS = {"p256dh": "BPabc", "auth": "auth123"}


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


def _subscribe(client, endpoint=ENDPOINT, keys=None):
    payload = {"endpoint": endpoint, "keys": KEYS if keys is None else keys}
    return client.post(
        reverse("push_subscribe"),
        data=json.dumps(payload),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_subscribe_saves_subscription(logged_in, user):
    response = _subscribe(logged_in)
    assert response.status_code == 204
    subscription = PushSubscription.objects.get()
    assert subscription.user == user
    assert subscription.endpoint == ENDPOINT
    assert subscription.p256dh == KEYS["p256dh"]
    assert subscription.auth == KEYS["auth"]


@pytest.mark.django_db
def test_same_endpoint_updates_keys_without_duplicate(logged_in):
    _subscribe(logged_in)
    new_keys = {"p256dh": "BPnew", "auth": "authnew"}
    response = _subscribe(logged_in, keys=new_keys)
    assert response.status_code == 204
    assert PushSubscription.objects.count() == 1
    subscription = PushSubscription.objects.get()
    assert subscription.p256dh == new_keys["p256dh"]
    assert subscription.auth == new_keys["auth"]


@pytest.mark.django_db
def test_same_endpoint_reassigns_user(logged_in, other, user, client):
    _subscribe(logged_in)
    client.force_login(other)
    response = _subscribe(client)
    assert response.status_code == 204
    assert PushSubscription.objects.count() == 1
    assert PushSubscription.objects.get().user == other


@pytest.mark.django_db
def test_anonymous_redirects_and_saves_nothing(client):
    response = _subscribe(client)
    assert response.status_code == 302
    assert PushSubscription.objects.count() == 0


@pytest.mark.django_db
def test_invalid_json_returns_400(logged_in):
    response = logged_in.post(
        reverse("push_subscribe"), data="not json", content_type="application/json"
    )
    assert response.status_code == 400
    assert PushSubscription.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"endpoint": ENDPOINT},
        {"endpoint": ENDPOINT, "keys": {"p256dh": "x"}},
        {"keys": KEYS},
        {"endpoint": "", "keys": KEYS},
    ],
)
def test_missing_keys_return_400(logged_in, payload):
    response = logged_in.post(
        reverse("push_subscribe"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert PushSubscription.objects.count() == 0


@pytest.mark.django_db
def test_get_not_allowed(logged_in):
    assert logged_in.get(reverse("push_subscribe")).status_code == 405


def test_service_worker_public_with_headers(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert response["Service-Worker-Allowed"] == "/"
    assert "no-cache" in response["Cache-Control"]


def test_service_worker_handles_push_and_click(client):
    body = client.get("/sw.js").content.decode()
    assert "addEventListener('push'" in body
    assert "showNotification" in body
    assert "addEventListener('notificationclick'" in body
    assert "openWindow" in body


def test_manifest_public_with_content_type(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/manifest+json")


def test_manifest_fields(client):
    manifest = json.loads(client.get("/manifest.webmanifest").content)
    assert manifest["name"] == "Cviky"
    assert manifest["short_name"] == "Cviky"
    assert manifest["lang"] == "cs"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["background_color"] == "#f4f6f5"
    assert manifest["theme_color"] == "#2e7d32"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert all(icon["type"] == "image/png" for icon in manifest["icons"])


def test_vapid_subject_default(settings):
    assert settings.VAPID_SUBJECT == "mailto:admin@localhost"
    assert hasattr(settings, "VAPID_PUBLIC_KEY")
    assert hasattr(settings, "VAPID_PRIVATE_KEY")


def test_session_cookie_age_is_one_year(settings):
    assert settings.SESSION_COOKIE_AGE == 60 * 60 * 24 * 365


def test_service_worker_resolves_notification_url(client):
    body = client.get("/sw.js").content.decode()
    assert "new URL(url, self.location.origin).href" in body


def test_vapid_subject_default_only_with_debug(monkeypatch):
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)
    assert config_settings._vapid_subject(True) == "mailto:admin@localhost"


def test_vapid_subject_required_in_production(monkeypatch):
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)
    with pytest.raises(RuntimeError):
        config_settings._vapid_subject(False)


def test_vapid_subject_rejects_localhost_default_in_production(monkeypatch):
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:admin@localhost")
    with pytest.raises(RuntimeError):
        config_settings._vapid_subject(False)


def test_vapid_subject_accepts_real_address_in_production(monkeypatch):
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:provoz@example.com")
    assert config_settings._vapid_subject(False) == "mailto:provoz@example.com"


@pytest.mark.django_db
def test_install_requires_login(client):
    assert client.get(reverse("install")).status_code == 302


@pytest.mark.django_db
def test_install_shows_czech_steps(logged_in):
    content = logged_in.get(reverse("install")).content.decode()
    assert "1. Klepni na Sdílet (čtvereček se šipkou)" in content
    assert "2. Vyber Přidat na plochu" in content
    assert "3. Otevři appku z plochy a vrať se sem" in content


@pytest.mark.django_db
def test_install_without_vapid_key_shows_message(logged_in, settings):
    settings.VAPID_PUBLIC_KEY = ""
    content = logged_in.get(reverse("install")).content.decode()
    assert "Upozornění nejsou na serveru nastavená." in content
    assert "Zapnout upozornění" not in content


@pytest.mark.django_db
def test_install_with_vapid_key_shows_button(logged_in, settings):
    settings.VAPID_PUBLIC_KEY = "BPpublic-key"
    content = logged_in.get(reverse("install")).content.decode()
    assert "Zapnout upozornění" in content
    assert 'data-vapid-public-key="BPpublic-key"' in content
    assert "push.js" in content


@pytest.mark.django_db
def test_base_registers_service_worker_and_links(logged_in):
    content = logged_in.get(reverse("home")).content.decode()
    assert "navigator.serviceWorker.register('/sw.js')" in content
    assert 'href="/manifest.webmanifest"' in content
    assert "apple-touch-icon" in content
    assert 'name="theme-color" content="#2e7d32"' in content
    assert 'name="apple-mobile-web-app-capable" content="yes"' in content


@pytest.mark.django_db
def test_profile_links_to_notification_setup(logged_in):
    content = logged_in.get(reverse("profile")).content.decode()
    assert 'href="/instalace/"' in content
    assert "Upozornění" in content


@pytest.mark.django_db
def test_install_page_sets_csrf_cookie_for_push_js(client, django_user_model):
    user = django_user_model.objects.create_user(username="csrf", password="SilneHeslo123")
    client.force_login(user)
    response = client.get("/instalace/")
    assert "csrftoken" in response.cookies
