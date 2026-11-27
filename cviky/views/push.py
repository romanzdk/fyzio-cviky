import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from cviky.models import PushSubscription

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# The reminder scheduler POSTs to every stored endpoint, so only real push services are accepted (no SSRF).
PUSH_SERVICE_DOMAINS = ("push.apple.com", "fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com")


def _is_push_service(endpoint: str) -> bool:
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError:
        return False
    host = url.hostname or ""
    return (
        url.scheme == "https"
        and port in (None, 443)
        and any(host == domain or host.endswith("." + domain) for domain in PUSH_SERVICE_DOMAINS)
    )


def service_worker(request):
    content = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def manifest(request):
    content = (STATIC_DIR / "manifest.webmanifest").read_text(encoding="utf-8")
    return HttpResponse(content, content_type="application/manifest+json")


@login_required
@ensure_csrf_cookie
def install(request):
    return render(request, "cviky/install.html", {"vapid_public_key": settings.VAPID_PUBLIC_KEY})


@login_required
@require_POST
def subscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        keys = data["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"error": "invalid"}, status=400)
    if not isinstance(endpoint, str) or not _is_push_service(endpoint) or not p256dh or not auth:
        return JsonResponse({"error": "invalid"}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
    )
    return HttpResponse(status=204)
