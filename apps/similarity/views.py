from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.home.models import (
    Project, ProjectVersion, Recommendation, SimilarityCheck, SimilarityMatch,
)

from . import engine

MAX_MATCHES = 5


def _sections(version):
    return {name: getattr(version, name) for name in engine.SECTIONS}


def _candidates(user, project):
    """Latest versions the user may be compared with.

    Their own other projects, plus public projects of other accounts.
    Archived projects and the project being checked are left out.
    """
    projects = (
        Project.objects.exclude(pk=project.pk)
        .exclude(status=Project.Status.ARCHIVED)
        .filter(Q(user=user) | Q(is_public=True))
        .prefetch_related(
            Prefetch("versions", queryset=ProjectVersion.objects.order_by("-version_number"))
        )
    )
    for candidate in projects:
        versions = list(candidate.versions.all())
        if versions:
            yield versions[0]


def run_check(user, project):
    """Compare the project's latest version and store the results."""
    version = project.versions.order_by("-version_number").first()
    check = SimilarityCheck.objects.create(project_version=version)
    proposal = _sections(version)
    results = []
    for candidate in _candidates(user, project):
        comparison = engine.compare(proposal, _sections(candidate))
        if comparison.score >= engine.MIN_SCORE:
            results.append((candidate, comparison))
    results.sort(key=lambda item: (-item[1].score, item[0].pk))
    results = results[:MAX_MATCHES]
    SimilarityMatch.objects.bulk_create(
        SimilarityMatch(
            similarity_check=check, matched_version=candidate,
            similarity_score=comparison.score, explanation=engine.explain(comparison),
        )
        for candidate, comparison in results
    )
    Recommendation.objects.bulk_create(
        Recommendation(similarity_check=check, suggestion=suggestion)
        for suggestion in engine.recommend(
            proposal, [(candidate.title, comparison) for candidate, comparison in results]
        )
    )
    check.status = SimilarityCheck.Status.COMPLETED
    check.completed_at = timezone.now()
    check.save(update_fields=["status", "completed_at"])
    return check


def _level(score):
    if score >= engine.HIGH_SCORE:
        return "high", "High similarity"
    if score >= engine.MODERATE_SCORE:
        return "moderate", "Moderate similarity"
    return "low", "Low similarity"


@login_required
@require_POST
@transaction.atomic
def run(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, user=request.user)
    if project.status == Project.Status.ARCHIVED:
        messages.error(request, "Restore this project before checking it.")
        return redirect("projects:detail", pk=project.pk)
    check = run_check(request.user, project)
    messages.success(request, "Similarity check completed.")
    return redirect("similarity:detail", pk=check.pk)


@login_required
@require_http_methods(["GET", "HEAD"])
def check_detail(request, pk):
    check = get_object_or_404(
        SimilarityCheck.objects.select_related("project_version__project"),
        pk=pk, project_version__project__user=request.user,
    )
    matches = []
    for match in check.matches.select_related(
        "matched_version__project__user"
    ).order_by("-similarity_score", "pk"):
        level, label = _level(match.similarity_score)
        matched_project = match.matched_version.project
        matches.append({
            "match": match, "level": level, "label": label,
            "own": matched_project.user_id == request.user.pk,
            "project": matched_project,
        })
    top = matches[0] if matches else None
    return render(
        request, "similarity/detail.html",
        {
            "check": check, "version": check.project_version,
            "project": check.project_version.project, "matches": matches, "top": top,
            "recommendations": check.recommendations.order_by("pk"),
            "is_latest": not check.project_version.project.versions.filter(
                version_number__gt=check.project_version.version_number
            ).exists(),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD"])
def check_list(request):
    checks = (
        SimilarityCheck.objects.filter(project_version__project__user=request.user)
        .select_related("project_version__project")
        .annotate(match_count=Count("matches"), top_score=Max("matches__similarity_score"))
        .order_by("-created_at", "-pk")
    )
    rows = []
    for check in checks:
        level, label = _level(check.top_score) if check.top_score is not None else ("none", "No matches")
        rows.append({"check": check, "level": level, "label": label})
    projects = (
        Project.objects.filter(user=request.user)
        .exclude(status=Project.Status.ARCHIVED)
        .prefetch_related(
            Prefetch("versions", queryset=ProjectVersion.objects.order_by("-version_number"))
        )
        .order_by("-created_at", "-pk")
    )
    choices = [
        {"project": project, "latest": versions[0]}
        for project in projects
        if (versions := list(project.versions.all()))
    ]
    return render(request, "similarity/checks.html", {"rows": rows, "choices": choices})
