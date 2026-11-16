from django import forms

from .models import ProjectVersion


class ProjectDraftForm(forms.ModelForm):
    class Meta:
        model = ProjectVersion
        fields = ["title", "problem_statement", "target_users"]
        labels = {
            "title": "Working title",
            "problem_statement": "What problem do you want to solve?",
            "target_users": "Who will use it?",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Give your idea a name"}),
            "problem_statement": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe a real problem you have noticed."}),
            "target_users": forms.TextInput(attrs={"placeholder": "For example, students looking for study spaces"}),
        }
