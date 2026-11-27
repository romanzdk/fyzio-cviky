from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.core.exceptions import PermissionDenied

MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60


def client_ip(request) -> str:
    # Caddy replaces any client-sent X-Forwarded-For, so its last entry is the real visitor.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.rsplit(",", 1)[-1].strip() or request.META.get("REMOTE_ADDR", "")


class ThrottledModelBackend(ModelBackend):
    """Blocks an IP for a while after too many failed logins (app login and /sprava/ both go through here)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is None:
            return super().authenticate(request, username, password, **kwargs)
        # ponytail: per-process LocMemCache, so each gunicorn worker counts on its own; shared cache if workers grow
        key = f"login-failures:{client_ip(request)}"
        if cache.get(key, 0) >= MAX_FAILURES:
            raise PermissionDenied
        user = super().authenticate(request, username, password, **kwargs)
        if user is None:
            cache.add(key, 0, WINDOW_SECONDS)
            cache.incr(key)
        return user
