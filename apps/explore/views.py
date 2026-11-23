from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Prefetch
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.home.models import Project, ProjectVersion

SECTIONS = [
    ("description", "Short description"),
    ("problem_statement", "Problem statement"),
    ("target_users", "Target users"),
    ("proposed_solution", "Proposed solution"),
    ("objectives", "Objectives"),
    ("scope", "Scope and limitations"),
    ("features", "Key features"),
]


def _public_projects():
    return (
        Project.objects.filter(is_public=True)
        .exclude(status=Project.Status.ARCHIVED)
        .select_related("user")
        .annotate(
            version_count=Count("versions"),
            last_saved=Max("versions__created_at"),
        )
        .prefetch_related(
            Prefetch("versions", queryset=ProjectVersion.objects.order_by("-version_number"))
        )
        .order_by("-last_saved", "-pk")
    )


@login_required
@require_http_methods(["GET", "HEAD"])
def explore_list(request):
    selected_category = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()
    query_lower = query.lower()

    all_rows = []
    category_counts = Counter()
    for project in _public_projects():
        versions = list(project.versions.all())
        if not versions:
            continue
        latest = versions[0]
        category = (latest.category or "").strip()
        if category:
            category_counts[category] += 1
        all_rows.append(
            {
                "project": project,
                "latest": latest,
                "category": category,
                "own": project.user_id == request.user.pk,
            }
        )

    categories = [{"value": "", "label": "All", "count": len(all_rows)}] + [
        {"value": cat, "label": cat, "count": count}
        for cat, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    ]

    rows = all_rows
    if selected_category:
        rows = [row for row in rows if row["category"].lower() == selected_category.lower()]
    if query_lower:
        def _matches(row):
            latest = row["latest"]
            haystack = " ".join(
                [
                    latest.title or "",
                    latest.category or "",
                    latest.description or "",
                    latest.problem_statement or "",
                    latest.target_users or "",
                    row["project"].user.username or "",
                ]
            ).lower()
            return query_lower in haystack

        rows = [row for row in rows if _matches(row)]

    return render(
        request,
        "explore/explore.html",
        {
            "rows": rows,
            "categories": categories,
            "active_category": selected_category,
            "query": query,
            "total_public": len(all_rows),
        },
    )


@login_required
@require_http_methods(["GET", "HEAD"])
def explore_detail(request, pk):
    project = get_object_or_404(
        Project.objects.filter(is_public=True)
        .exclude(status=Project.Status.ARCHIVED)
        .select_related("user"),
        pk=pk,
    )
    latest = project.versions.order_by("-version_number").first()
    if latest is None:
        get_object_or_404(ProjectVersion, pk=-1)
    sections = [
        {"label": label, "text": getattr(latest, field) or ""}
        for field, label in SECTIONS
    ]
    return render(
        request,
        "explore/detail.html",
        {
            "project": project,
            "latest": latest,
            "sections": sections,
            "version_count": project.versions.count(),
            "own": project.user_id == request.user.pk,
        },
    )
