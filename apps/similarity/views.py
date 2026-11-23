import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.home.models import (
    Project, ProjectVersion, Recommendation, SimilarityCheck, SimilarityMatch,
)

from . import engine, llm

logger = logging.getLogger(__name__)
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
    candidates = list(_candidates(user, project))

    used_llm = False
    if llm.is_configured():
        try:
            analysis = llm.analyze_similarity(
                proposal,
                [(candidate.pk, _sections(candidate)) for candidate in candidates],
                max_matches=MAX_MATCHES,
            )
        except llm.OpenAIError:
            logger.warning(
                "OpenAI similarity check failed; falling back to local text engine.",
                exc_info=True,
            )
        else:
            used_llm = True
            by_pk = {candidate.pk: candidate for candidate in candidates}
            SimilarityMatch.objects.bulk_create(
                SimilarityMatch(
                    similarity_check=check,
                    matched_version=by_pk[match.candidate_id],
                    similarity_score=match.score,
                    explanation=match.explanation,
                )
                for match in analysis.matches
                if match.candidate_id in by_pk
            )
            Recommendation.objects.bulk_create(
                Recommendation(similarity_check=check, suggestion=suggestion)
                for suggestion in analysis.recommendations
            )

    if not used_llm:
        results = []
        for candidate in candidates:
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
    check.used_llm = used_llm
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
    if getattr(check, "used_llm", False):
        messages.success(request, "Similarity check completed with AI analysis.")
    else:
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


def check_history(user):
    """JOIN: each of the user's checks with its project version and match totals."""
    # Only my checks (follows check → version → project → user)
    checks = SimilarityCheck.objects.filter(project_version__project__user=user)

    # JOIN: get each check's project version (title, version number) in the same query
    checks = checks.select_related("project_version")
    
    # Count the matches and get the highest score
    checks = checks.annotate(
        match_count=Count("matches"),
        top_score=Max("matches__similarity_score"),
    )

    # Newest first
    return checks.order_by("-created_at", "-pk")


def checked_project_ids():
    """Inner query: the project of every version that has a similarity check."""
    return SimilarityCheck.objects.values("project_version__project_id")


def runnable_projects(user):
    return (
        Project.objects.filter(user=user)
        .exclude(status=Project.Status.ARCHIVED)
        .prefetch_related(
            Prefetch("versions", queryset=ProjectVersion.objects.order_by("-version_number"))
        )
        .order_by("-created_at", "-pk")
    )


def projects_not_checked(user):
    """SUBQUERY: the user's projects whose id is NOT IN the inner query."""
    return runnable_projects(user).exclude(id__in=Subquery(checked_project_ids()))


def projects_checked(user):
    """SUBQUERY: the user's projects whose id is IN the inner query."""
    return runnable_projects(user).filter(id__in=Subquery(checked_project_ids()))


def _choices(projects):
    return [
        {"project": project, "latest": versions[0]}
        for project in projects
        if (versions := list(project.versions.all()))
    ]


@login_required
@require_http_methods(["GET", "HEAD"])
def check_list(request):
    history = check_history(request.user)
    unchecked = projects_not_checked(request.user)
  
    rows = []
    for check in history:
        level, label = _level(check.top_score) if check.top_score is not None else ("none", "No matches")
        rows.append({"check": check, "level": level, "label": label})
    return render(
        request, "similarity/checks.html",
        {
            "rows": rows,
            "unchecked": _choices(unchecked),
            "checked": _choices(projects_checked(request.user)),
        },
    )
