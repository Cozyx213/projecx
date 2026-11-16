from decimal import Decimal
from importlib import import_module

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase, TransactionTestCase

from .models import Project, ProjectVersion, Recommendation, SimilarityCheck, SimilarityMatch


class ProjectDraftTest(TestCase):
    def test_draft_validation_versions_and_account_isolation(self):
        owner = get_user_model().objects.create_user("owner")
        other = get_user_model().objects.create_user("other")
        self.client.force_login(owner)
        self.assertContains(self.client.get("/"), "New idea")
        self.assertFalse(Project.objects.exists())
        data = {
            "title": "Study space finder",
            "problem_statement": "Finding a quiet room takes too long.",
            "target_users": "Students",
        }
        invalid = self.client.post("/", {**data, "title": ""})
        self.assertIn("title", invalid.context["form"].errors)
        self.assertFalse(Project.objects.exists())
        self.assertRedirects(self.client.post("/", {**data, "user": other.pk}), "/")
        project = Project.objects.get(user=owner)
        original = project.versions.get(version_number=1)
        self.assertEqual(original.problem_statement, data["problem_statement"])
        original.description = "Keep sections not edited by the home form."
        original.save()
        self.assertRedirects(
            self.client.post("/", {**data, "title": "Campus study spaces"}), "/"
        )
        original.refresh_from_db()
        self.assertEqual(original.title, data["title"])
        revised = project.versions.get(version_number=2)
        self.assertEqual(revised.title, "Campus study spaces")
        self.assertEqual(revised.description, original.description)
        self.assertEqual(Project.objects.count(), 1)
        self.assertContains(self.client.get("/"), "Campus study spaces")
        self.client.force_login(other)
        self.assertNotContains(self.client.get("/"), "Campus study spaces")
        self.assertRedirects(self.client.post("/", {**data, "user": owner.pk}), "/")
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(project.versions.count(), 2)


class ERDRelationshipsTest(TestCase):
    def test_relationships_and_database_constraints(self):
        user = get_user_model().objects.create_user("student")
        project = Project.objects.create(user=user)
        other_project = Project.objects.create(user=user)
        version = ProjectVersion.objects.create(project=project, version_number=1, title="A")
        other_version = ProjectVersion.objects.create(
            project=other_project, version_number=1, title="B"
        )
        check = SimilarityCheck.objects.create(project_version=version)
        match = SimilarityMatch.objects.create(
            similarity_check=check, matched_version=other_version,
            similarity_score=Decimal("75.50"), explanation="Same target users.",
        )
        recommendation = Recommendation.objects.create(
            similarity_check=check, suggestion="Focus on students with accessibility needs."
        )
        self.assertEqual(user.projects.count(), 2)
        self.assertEqual(version.similarity_checks.get(), check)
        self.assertEqual(check.matches.get(), match)
        self.assertEqual(other_version.matched_by.get(), match)
        self.assertEqual(check.recommendations.get(), recommendation)
        self.assertFalse(project.is_public)
        self.assertEqual(project.status, "draft")
        self.assertIsNone(version.description)
        self.assertIsNone(check.completed_at)

        invalid_rows = [
            (Project, {"user": user, "status": "invalid"}),
            (ProjectVersion, {"project": project, "version_number": 1, "title": "Duplicate"}),
            (ProjectVersion, {"project": project, "version_number": 0, "title": "Invalid"}),
            (SimilarityCheck, {"project_version": version, "status": "invalid"}),
            (SimilarityMatch, {"similarity_check": check, "matched_version": other_version,
                               "similarity_score": 50, "explanation": "Duplicate"}),
        ]
        for score in (Decimal("-0.01"), Decimal("100.01")):
            another_check = SimilarityCheck.objects.create(project_version=version)
            invalid_rows.append((SimilarityMatch, {
                "similarity_check": another_check, "matched_version": other_version,
                "similarity_score": score, "explanation": "Out of range",
            }))
        for model, values in invalid_rows:
            with self.subTest(model=model.__name__, values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.create(**values)

        project.delete()
        self.assertFalse(SimilarityCheck.objects.exists())
        self.assertFalse(SimilarityMatch.objects.exists())
        self.assertFalse(Recommendation.objects.exists())
        self.assertTrue(ProjectVersion.objects.filter(pk=other_version.pk).exists())


class LegacyDraftMigrationTest(TransactionTestCase):
    def test_existing_draft_content_and_timestamp_are_preserved(self):
        migration = import_module("apps.home.migrations.0002_approved_erd")
        state = MigrationLoader(connection).project_state([("home", "0001_initial")])
        # The data migration sees both the legacy model and the new ERD models.
        for operation in migration.Migration.operations[:5]:
            operation.state_forwards("home", state)
        Draft = state.apps.get_model("home", "ProjectDraft")
        with connection.schema_editor() as editor:
            editor.create_model(Draft)
        try:
            user = get_user_model().objects.create_user("legacy")
            draft = Draft.objects.create(
                user_id=user.pk, title="Original title", problem="Original problem",
                audience="Original audience",
            )
            with connection.schema_editor() as editor:
                migration.migrate_drafts(state.apps, editor)
            project = Project.objects.get(user=user)
            version = project.versions.get(version_number=1)
            self.assertEqual(version.title, draft.title)
            self.assertEqual(version.problem_statement, draft.problem)
            self.assertEqual(version.target_users, draft.audience)
            self.assertEqual(version.created_at, draft.updated_at)
            self.assertEqual(project.created_at, draft.updated_at)
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(Draft)
