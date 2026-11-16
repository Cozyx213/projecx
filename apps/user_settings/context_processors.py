from .models import UserSettings


def preferences(request):
    # The shared layout reads preferences here, so views need no cross-feature imports.
    saved = None
    if request.user.is_authenticated:
        saved = UserSettings.objects.filter(user=request.user).first()
    return {"preferences": saved or {"dark_mode": False, "show_home_tips": True}}
