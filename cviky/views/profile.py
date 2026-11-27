from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from cviky.forms import ProfileForm


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            request.user.neglect_days = form.cleaned_data["neglect_days"]
            request.user.save(update_fields=["neglect_days"])
            return redirect("profile")
    else:
        form = ProfileForm(initial={"neglect_days": request.user.neglect_days})
    return render(request, "cviky/profile.html", {"form": form})
