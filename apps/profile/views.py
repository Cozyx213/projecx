from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ProfileForm
from .models import Profile


@login_required
@require_http_methods(["GET", "POST", "HEAD"])
def profile(request):
    account_profile = Profile.objects.filter(user=request.user).first()
    form = ProfileForm(
        request.POST if request.method == "POST" else None,
        instance=account_profile or Profile(user=request.user),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("profile:profile")
    return render(request, "profile/profile.html", {"form": form, "profile": account_profile})
