from django import forms

from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["full_name", "bio"]
        labels = {"full_name": "Full name", "bio": "About you"}
        help_texts = {"bio": "Share your interests and the kinds of projects you want to work on."}
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "bio": forms.Textarea(attrs={"rows": 5}),
        }
