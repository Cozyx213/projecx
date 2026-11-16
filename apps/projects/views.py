from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.home.models import Project, ProjectVersion, SimilarityCheck

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
            messages.error(request, "Archived projects cannot be edited. Restore it first.")
            return redirect("projects:detail", pk=project.pk)
        latest = _latest_version(project)
    form = ProposalForm(
        request.POST if request.method == "POST" else None,
        instance=latest or ProjectVersion(),
    )
    if request.method == "POST" and form.is_valid():
        if latest and not form.has_changed():
            messages.info(request, "No changes to save.")
            return redirect("projects:detail", pk=project.pk)
        version = form.save(commit=False)
        version.pk = None
        version.project = project or Project.objects.create(user=request.user)
        version.version_number = latest.version_number + 1 if latest else 1
        version.created_at = timezone.now()
        version.save(force_insert=True)
        messages.success(
            request, f"Saved version {version.version_number} of “{version.title}”."
        )
        return redirect("projects:detail", pk=version.project_id)
    return render(
        request, "projects/form.html",
        {"form": form, "project": project, "latest": latest},
    )


SECTIONS = [
    ("description", "Short description"),
    ("problem_statement", "Problem statement"),
    ("target_users", "Target users"),
    ("proposed_solution", "Proposed solution"),
    ("objectives", "Objectives"),
    ("scope", "Scope and limitations"),
    ("features", "Key features"),
]
COMPARED_FIELDS = [("title", "Title"), ("category", "Category")] + SECTIONS


def _version_history(versions):
    """Newest first, each with the labels of sections changed since the one before."""
    history = []
    previous = None
    for version in sorted(versions, key=lambda item: item.version_number):
        changed = [
            label for field, label in COMPARED_FIELDS
            if previous is not None
            and (getattr(version, field) or "") != (getattr(previous, field) or "")
        ]
        history.append({"version": version, "changed": changed})
        previous = version
    return history[::-1]


@login_required
@require_http_methods(["GET", "HEAD"])
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    versions = list(project.versions.all())
    history = _version_history(versions)
    latest = history[0]["version"]
    selected = latest
    requested = request.GET.get("version", "")
    if requested.isdigit():
        selected = next(
            (v for v in versions if v.version_number == int(requested)), latest
        )
    sections = [
        {"label": label, "text": getattr(selected, field) or ""}
        for field, label in SECTIONS
    ]
    return render(
        request, "projects/detail.html",
        {
            "project": project, "latest": latest, "selected": selected,
            "history": history, "sections": sections,
            "checks": SimilarityCheck.objects.filter(project_version__project=project)
            .select_related("project_version")
            .annotate(top_score=Max("matches__similarity_score"))
            .order_by("-created_at", "-pk")[:3],
            "missing": [item["label"] for item in sections if not item["text"].strip()],
        },
    )


@login_required
@require_POST
@transaction.atomic
def project_update(request, pk):
    project = get_object_or_404(
        Project.objects.select_for_update(), pk=pk, user=request.user
    )
    action = request.POST.get("action", "")
    archived = project.status == Project.Status.ARCHIVED
    if action == "submit" and project.status == Project.Status.DRAFT:
        latest = _latest_version(project)
        if not (latest.problem_statement or "").strip():
            messages.error(request, "Add a problem statement before submitting.")
        else:
            project.status = Project.Status.SUBMITTED
            messages.success(request, "Project submitted.")
    elif action == "draft" and project.status != Project.Status.DRAFT:
        project.status = Project.Status.DRAFT
        messages.success(
            request, "Project restored as a draft." if archived else "Project returned to draft."
        )
    elif action == "archive" and not archived:
        project.status = Project.Status.ARCHIVED
        project.is_public = False
        messages.success(request, "Project archived and made private.")
    elif action == "publish" and not archived and not project.is_public:
        project.is_public = True
        messages.success(request, "Project is now public. Others can be matched against it.")
    elif action == "unpublish" and project.is_public:
        project.is_public = False
        messages.success(request, "Project is now private.")
    else:
        messages.error(request, "That action is not available for this project.")
    project.save(update_fields=["status", "is_public"])
    return redirect("projects:detail", pk=project.pk)
