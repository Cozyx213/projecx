from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.home.models import Project, ProjectVersion


def make_project(user, title, **fields):
    status = fields.pop("status", Project.Status.DRAFT)
    project = Project.objects.create(user=user, status=status)
    ProjectVersion.objects.create(project=project, version_number=1, title=title, **fields)
    return project


class ProjectListTest(TestCase):
    def test_list_requires_login_and_shows_only_own_projects(self):
        self.assertRedirects(self.client.get("/projects/"), "/login/?next=/projects/")
        owner = get_user_model().objects.create_user("owner")
        other = get_user_model().objects.create_user("other")
        self.client.force_login(owner)
        self.assertContains(self.client.get("/projects/"), "No projects yet")
        make_project(owner, "Study space finder", category="Education")
        make_project(owner, "Old idea", status=Project.Status.ARCHIVED)
        make_project(other, "Secret rival idea")
        response = self.client.get("/projects/")
        self.assertContains(response, "Study space finder")
        self.assertContains(response, "Old idea")
        self.assertNotContains(response, "Secret rival idea")
        archived = self.client.get("/projects/?status=archived")
        self.assertContains(archived, "Old idea")
        self.assertNotContains(archived, "Study space finder")
        self.assertContains(self.client.get("/projects/?status=submitted"), "No submitted projects")
        self.assertContains(self.client.get("/projects/?status=bogus"), "Study space finder")

    def test_list_shows_latest_version_and_escapes_titles(self):
        owner = get_user_model().objects.create_user("owner")
        project = make_project(owner, "<script>alert(1)</script>")
        ProjectVersion.objects.create(project=project, version_number=2, title="Renamed idea")
        self.client.force_login(owner)
        response = self.client.get("/projects/")
        self.assertContains(response, "Renamed idea")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertEqual(response.context["rows"][0]["project"].version_count, 2)


class ProposalFormTest(TestCase):
    data = {
        "title": "Campus lost and found",
        "category": "Campus services",
        "description": "A shared board for lost items.",
        "problem_statement": "Lost items are reported in scattered group chats.",
        "target_users": "Students and guards",
        "proposed_solution": "One searchable list with photos.",
        "objectives": "Reduce unclaimed items",
        "scope": "Main campus only",
        "features": "Photo upload\nClaim requests",
    }

    def test_create_edit_and_versioning(self):
        owner = get_user_model().objects.create_user("owner")
        self.client.force_login(owner)
        invalid = self.client.post("/projects/new/", {**self.data, "title": ""})
        self.assertIn("title", invalid.context["form"].errors)
        self.assertFalse(Project.objects.exists())
        self.assertRedirects(self.client.post("/projects/new/", self.data), "/projects/")
        project = Project.objects.get(user=owner)
        first = project.versions.get()
        self.assertEqual(first.version_number, 1)
        self.assertEqual(first.features, self.data["features"])
        edit_url = f"/projects/{project.pk}/edit/"
        self.assertContains(self.client.get(edit_url), "Campus lost and found")
        self.assertRedirects(self.client.post(edit_url, self.data), "/projects/")
        self.assertEqual(project.versions.count(), 1)
        self.assertRedirects(
            self.client.post(edit_url, {**self.data, "scope": "All campuses"}), "/projects/"
        )
        self.assertEqual(project.versions.count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.scope, "Main campus only")
        self.assertEqual(project.versions.get(version_number=2).scope, "All campuses")

    def test_other_accounts_and_archived_projects_cannot_be_edited(self):
        owner = get_user_model().objects.create_user("owner")
        other = get_user_model().objects.create_user("other")
        project = make_project(owner, "Mine")
        archived = make_project(owner, "Shelved", status=Project.Status.ARCHIVED)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/projects/{project.pk}/edit/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/projects/{project.pk}/edit/", self.data).status_code, 404
        )
        self.client.force_login(owner)
        self.assertRedirects(
            self.client.post(f"/projects/{archived.pk}/edit/", self.data), "/projects/"
        )
        self.assertEqual(archived.versions.count(), 1)
        self.assertEqual(project.versions.count(), 1)
