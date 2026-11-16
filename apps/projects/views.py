from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.home.models import Project, ProjectVersion

from .forms import ProposalForm


def _latest_version(project):
    return project.versions.order_by("-version_number").first()


@login_required
@require_http_methods(["GET", "HEAD"])
def project_list(request):
    status = request.GET.get("status", "")
    if status not in Project.Status.values:
        status = ""
    owned = Project.objects.filter(user=request.user)
    counts = dict(owned.values_list("status").annotate(total=Count("pk")))
    projects = (
        owned.filter(status=status) if status else owned
    ).annotate(
        version_count=Count("versions"), last_saved=Max("versions__created_at")
    ).prefetch_related(
        Prefetch("versions", queryset=ProjectVersion.objects.order_by("-version_number"))
    ).order_by("-last_saved", "-pk")
    rows = []
    for project in projects:
        versions = list(project.versions.all())
        if versions:
            rows.append({"project": project, "latest": versions[0]})
    filters = [{"value": "", "label": "All", "count": sum(counts.values())}] + [
        {"value": value, "label": label, "count": counts.get(value, 0)}
        for value, label in Project.Status.choices
    ]
    return render(
        request, "projects/projects.html",
        {"rows": rows, "filters": filters, "active_status": status},
    )


@login_required
@require_http_methods(["GET", "POST", "HEAD"])
@transaction.atomic
def project_form(request, pk=None):
    project = None
    latest = None
    if pk is not None:
        project = get_object_or_404(
            Project.objects.select_for_update(), pk=pk, user=request.user
        )
        if project.status == Project.Status.ARCHIVED:
            messages.error(request, "Archived projects cannot be edited.")
            return redirect("projects:list")
        latest = _latest_version(project)
    form = ProposalForm(
        request.POST if request.method == "POST" else None,
        instance=latest or ProjectVersion(),
    )
    if request.method == "POST" and form.is_valid():
        if latest and not form.has_changed():
            messages.info(request, "No changes to save.")
            return redirect("projects:list")
        version = form.save(commit=False)
        version.pk = None
        version.project = project or Project.objects.create(user=request.user)
        version.version_number = latest.version_number + 1 if latest else 1
        version.created_at = timezone.now()
        version.save(force_insert=True)
        messages.success(
            request, f"Saved version {version.version_number} of “{version.title}”."
        )
        return redirect("projects:list")
    return render(
        request, "projects/form.html",
        {"form": form, "project": project, "latest": latest},
    )
