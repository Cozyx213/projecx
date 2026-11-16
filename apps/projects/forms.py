from django import forms

from apps.home.models import ProjectVersion


class ProposalForm(forms.ModelForm):
    """Every proposal section of a project version."""

    class Meta:
        model = ProjectVersion
        fields = [
            "title", "category", "description", "problem_statement", "target_users",
            "proposed_solution", "objectives", "scope", "features",
        ]
        labels = {
            "title": "Project title",
            "category": "Category",
            "description": "Short description",
            "problem_statement": "Problem statement",
            "target_users": "Target users",
            "proposed_solution": "Proposed solution",
            "objectives": "Objectives",
            "scope": "Scope and limitations",
            "features": "Key features",
        }
        help_texts = {
            "category": "For example: Education, Health, Campus services.",
            "objectives": "One objective per line.",
            "features": "One feature per line.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Give your idea a name"}),
            "category": forms.TextInput(attrs={"placeholder": "Education"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "problem_statement": forms.Textarea(attrs={"rows": 4}),
            "target_users": forms.TextInput(),
            "proposed_solution": forms.Textarea(attrs={"rows": 4}),
            "objectives": forms.Textarea(attrs={"rows": 4}),
            "scope": forms.Textarea(attrs={"rows": 3}),
            "features": forms.Textarea(attrs={"rows": 4}),
        }
