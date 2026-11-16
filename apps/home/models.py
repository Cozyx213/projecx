"""Models mapped to BAJENTING_ERD 1.pdf.

auth_user is Django's existing django.contrib.auth.models.User, referenced
through AUTH_USER_MODEL. Its fields and table are supplied by Django's auth
migrations; declaring another User model would duplicate the ERD entity.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Now
from django.utils import timezone


class Project(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ARCHIVED = "archived", "Archived"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_default="draft"
    )
    is_public = models.BooleanField(default=False, db_default=False)
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "projects"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "submitted", "archived"]),
                name="projects_valid_status",
            ),
        ]

    def __str__(self):
        return f"Project {self.pk}"


class ProjectVersion(models.Model):
    id = models.BigAutoField(primary_key=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.IntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    problem_statement = models.TextField(null=True, blank=True)
    proposed_solution = models.TextField(null=True, blank=True)
    target_users = models.TextField(null=True, blank=True)
    objectives = models.TextField(null=True, blank=True)
    scope = models.TextField(null=True, blank=True)
    features = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "project_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version_number"], name="unique_project_version"
            ),
            models.CheckConstraint(
                condition=models.Q(version_number__gt=0),
                name="project_versions_positive_number",
            ),
        ]

    def __str__(self):
        return f"{self.title} (v{self.version_number})"


class SimilarityCheck(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.BigAutoField(primary_key=True)
    project_version = models.ForeignKey(
        ProjectVersion, on_delete=models.CASCADE, related_name="similarity_checks"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
        db_default="pending",
    )
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "similarity_checks"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "completed", "failed"]),
                name="similarity_checks_valid_status",
            ),
        ]

    def __str__(self):
        return f"Check {self.pk} ({self.status})"


class SimilarityMatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    similarity_check = models.ForeignKey(
        SimilarityCheck, on_delete=models.CASCADE, related_name="matches"
    )
    matched_version = models.ForeignKey(
        ProjectVersion, on_delete=models.CASCADE, related_name="matched_by"
    )
    similarity_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    explanation = models.TextField()

    class Meta:
        db_table = "similarity_matches"
        constraints = [
            models.UniqueConstraint(
                fields=["similarity_check", "matched_version"],
                name="unique_similarity_match",
            ),
            models.CheckConstraint(
                condition=models.Q(similarity_score__gte=0, similarity_score__lte=100),
                name="similarity_score_in_range",
            ),
        ]

    def __str__(self):
        return f"Match {self.pk}: {self.similarity_score}%"


class Recommendation(models.Model):
    id = models.BigAutoField(primary_key=True)
    similarity_check = models.ForeignKey(
        SimilarityCheck, on_delete=models.CASCADE, related_name="recommendations"
    )
    suggestion = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "recommendations"

    def __str__(self):
        return self.suggestion[:80]
