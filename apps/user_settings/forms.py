from django import forms

from .models import UserSettings


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["dark_mode", "show_home_tips"]
        labels = {"dark_mode": "Dark mode", "show_home_tips": "Show project prompts"}
        help_texts = {
            "dark_mode": "Use a darker background across your workspace.",
            "show_home_tips": "Show the getting-started prompts on Home.",
        }
