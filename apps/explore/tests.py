from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.home.models import Project, ProjectVersion


def make_project(user, title, *, category="", problem="", is_public=True, status=Project.Status.DRAFT):
    project = Project.objects.create(user=user, is_public=is_public, status=status)
    ProjectVersion.objects.create(
        project=project,
        version_number=1,
        title=title,
        category=category,
        problem_statement=problem,
    )
    return project


class ExploreViewTest(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user("owner")
        self.other = users.create_user("other")

    def test_explore_requires_login_and_shows_only_public_non_archived_projects(self):
        self.assertRedirects(self.client.get("/explore/"), "/login/?next=/explore/")

        pub_other = make_project(
            self.other,
            "Campus shuttle tracker",
            category="Campus services",
            problem="Students cannot see when the next shuttle arrives.",
            is_public=True,
        )
        pub_own = make_project(
            self.owner,
            "Library seat finder",
            category="Education",
            problem="Quiet desks fill up before exams.",
            is_public=True,
        )
        make_project(self.other, "Secret private idea", is_public=False)
        make_project(
            self.other,
            "Archived public idea",
            is_public=True,
            status=Project.Status.ARCHIVED,
        )

        self.client.force_login(self.owner)
        page = self.client.get("/explore/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Campus shuttle tracker")
        self.assertContains(page, "@other")
        self.assertContains(page, "Library seat finder")
        self.assertContains(page, "Your project")
        self.assertNotContains(page, "Secret private idea")
        self.assertNotContains(page, "Archived public idea")

        # Filter by category
        filtered = self.client.get("/explore/?category=Education")
        self.assertContains(filtered, "Library seat finder")
        self.assertNotContains(filtered, "Campus shuttle tracker")

        # Search by keyword and author
        searched = self.client.get("/explore/?q=shuttle")
        self.assertContains(searched, "Campus shuttle tracker")
        self.assertNotContains(searched, "Library seat finder")

        # Public detail page works and escapes HTML
        ProjectVersion.objects.create(
            project=pub_other,
            version_number=2,
            title="<b>Shuttle</b> v2",
            category="Campus services",
            problem_statement="Updated problem statement.",
        )
        detail = self.client.get(f"/explore/{pub_other.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "&lt;b&gt;Shuttle&lt;/b&gt; v2")
        self.assertContains(detail, "Updated problem statement.")
        self.assertContains(detail, "Shared by @other")

        own_detail = self.client.get(f"/explore/{pub_own.pk}/")
        self.assertContains(own_detail, f"/projects/{pub_own.pk}/")

    def test_explore_detail_blocks_private_and_archived_projects(self):
        private_project = make_project(self.other, "Private draft", is_public=False)
        archived_project = make_project(
            self.other,
            "Archived project",
            is_public=True,
            status=Project.Status.ARCHIVED,
        )
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f"/explore/{private_project.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/explore/{archived_project.pk}/").status_code, 404)
