from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import ProjectDraftForm
from .models import Project, ProjectVersion


@login_required
@require_http_methods(["GET", "POST", "HEAD"])
@transaction.atomic
def home(request):
    project = (
        Project.objects.select_for_update()
        .filter(user=request.user, status=Project.Status.DRAFT)
        .order_by("-created_at", "-pk")
        .first()
    )
    draft = project.versions.order_by("-version_number").first() if project else None
    form = ProjectDraftForm(
        request.POST if request.method == "POST" else None,
        instance=draft or ProjectVersion(),
    )
    if request.method == "POST" and form.is_valid():
        next_version = draft.version_number + 1 if draft else 1
        version = form.save(commit=False)
        version.pk = None
        version.project = project or Project.objects.create(user=request.user)
        version.version_number = next_version
        version.created_at = timezone.now()
        version.save(force_insert=True)
        messages.success(request, "Project draft saved.")
        return redirect("home:home")
    return render(request, "home/home.html", {"form": form, "draft": draft})
