from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import UserSettingsForm
from .models import UserSettings


@login_required
@require_http_methods(["GET", "POST", "HEAD"])
def settings(request):
    preferences = UserSettings.objects.filter(user=request.user).first()
    form = UserSettingsForm(
        request.POST if request.method == "POST" else None,
        instance=preferences or UserSettings(user=request.user),
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": True, "dark_mode": saved.dark_mode, "show_home_tips": saved.show_home_tips}
            )
        messages.success(request, "Settings saved.")
        return redirect("user_settings:settings")
    return render(request, "user_settings/settings.html", {"form": form})


@login_required
@require_POST
def toggle_theme(request):
    preferences, _ = UserSettings.objects.get_or_create(user=request.user)
    preferences.dark_mode = not preferences.dark_mode
    preferences.save(update_fields=["dark_mode"])
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("home:home")
