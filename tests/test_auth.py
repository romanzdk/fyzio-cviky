import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from cviky.backends import MAX_FAILURES
from cviky.models import Invite

User = get_user_model()


@pytest.mark.django_db
def test_register_with_valid_invite_creates_user_and_marks_used(client):
    invite = Invite.objects.create()
    response = client.post(
        reverse("register", args=[invite.token]),
        {"username": "novak", "password1": "SilneHeslo123", "password2": "SilneHeslo123"},
    )
    assert response.status_code == 302
    user = User.objects.get(username="novak")
    invite.refresh_from_db()
    assert invite.used_by == user
    assert invite.used_at is not None
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_used_invite_returns_404(client):
    user = User.objects.create_user(username="a", password="SilneHeslo123")
    invite = Invite.objects.create(used_by=user, used_at=timezone.now())
    response = client.get(reverse("register", args=[invite.token]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_unknown_token_returns_404(client):
    response = client.get(reverse("register", args=["00000000-0000-0000-0000-000000000000"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_no_open_registration(client):
    response = client.post(
        "/registrace/",
        {"username": "x", "password1": "SilneHeslo123", "password2": "SilneHeslo123"},
    )
    assert response.status_code == 404
    assert not User.objects.filter(username="x").exists()


@pytest.mark.django_db
def test_anonymous_redirected_to_login(client):
    response = client.get("/cviky/")
    assert response.status_code == 302
    assert response.url == "/prihlaseni/?next=/cviky/"


@pytest.mark.django_db
def test_invite_stays_used_after_user_deleted(client):
    user = User.objects.create_user(username="a", password="SilneHeslo123")
    invite = Invite.objects.create(used_by=user, used_at=timezone.now())
    user.delete()
    response = client.get(reverse("register", args=[invite.token]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_logout_via_post_redirects_to_login(client):
    user = User.objects.create_user(username="a", password="SilneHeslo123")
    client.force_login(user)
    response = client.post(reverse("logout"))
    assert response.status_code == 302
    assert response.url == reverse("login")
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_profile_has_logout_button(client):
    user = User.objects.create_user(username="a", password="SilneHeslo123")
    client.force_login(user)
    content = client.get(reverse("profile")).content.decode()
    assert "Odhlásit se" in content
    assert 'action="/odhlaseni/"' in content
    assert "csrfmiddlewaretoken" in content


@pytest.mark.django_db
def test_login_blocked_after_too_many_failures(client):
    cache.clear()
    User.objects.create_user(username="a", password="SilneHeslo123")
    for _ in range(MAX_FAILURES):
        client.post(reverse("login"), {"username": "a", "password": "spatne"})
    response = client.post(reverse("login"), {"username": "a", "password": "SilneHeslo123"})
    assert "_auth_user_id" not in client.session
    assert response.status_code == 200

    other_ip = client.post(
        reverse("login"), {"username": "a", "password": "SilneHeslo123"}, HTTP_X_FORWARDED_FOR="203.0.113.9"
    )
    assert other_ip.status_code == 302
    cache.clear()


@pytest.mark.django_db
def test_admin_login_shares_the_throttle(client):
    cache.clear()
    User.objects.create_superuser(username="admin", password="SilneHeslo123")
    for _ in range(MAX_FAILURES):
        client.post(reverse("login"), {"username": "admin", "password": "spatne"})
    client.post("/sprava/login/", {"username": "admin", "password": "SilneHeslo123"})
    assert "_auth_user_id" not in client.session
    cache.clear()
