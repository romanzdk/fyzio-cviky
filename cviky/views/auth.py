from django import forms
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from cviky.models import Invite, User


class RegisterForm(UserCreationForm):
    consent = forms.BooleanField(
        label="Souhlasím se zpracováním údajů o mém zdraví (popisů cviků) podle zásad ochrany osobních údajů.",
        error_messages={"required": "Bez souhlasu appka nemůže ukládat tvoje cviky."},
    )

    class Meta(UserCreationForm.Meta):
        model = User


def register(request, token):
    invite = get_object_or_404(Invite, token=token)
    if invite.used_at is not None:
        raise Http404

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                invite = Invite.objects.select_for_update().get(pk=invite.pk)
                if invite.used_at is not None:
                    raise Http404
                user = form.save()
                invite.used_by = user
                invite.used_at = timezone.now()
                invite.save()
            login(request, user)
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "cviky/register.html", {"form": form, "invite": invite})
