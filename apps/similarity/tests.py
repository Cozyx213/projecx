from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.home.models import Project, ProjectVersion, SimilarityCheck

from . import engine

STUDY = {
    "title": "Campus study space finder",
    "problem_statement": "Students waste time looking for a quiet study room on campus.",
    "proposed_solution": "A map that shows available study rooms in real time.",
    "target_users": "College students",
}
STUDY_COPY = {
    "title": "Study room locator",
    "problem_statement": "Finding a quiet room to study on campus takes students too long.",
    "proposed_solution": "Show available study rooms on a campus map in real time.",
    "target_users": "Students",
}
CLINIC = {
    "title": "Barangay clinic queue",
    "problem_statement": "Patients wait for hours without knowing their place in line.",
    "proposed_solution": "Text message updates for each patient number.",
    "target_users": "Clinic patients and nurses",
}


class EngineTest(SimpleTestCase):
    def test_tokenize_drops_stop_words_and_stems(self):
        self.assertEqual(engine.tokenize("The students are finding rooms!"), ["student", "find", "room"])
        self.assertEqual(engine.tokenize("Classes on campus, studies"), ["class", "campus", "study"])
        self.assertEqual(engine.tokenize(None), [])

    def test_scores_are_ordered_and_bounded(self):
        same = engine.compare(STUDY, STUDY)
        close = engine.compare(STUDY, STUDY_COPY)
        far = engine.compare(STUDY, CLINIC)
        self.assertEqual(same.score, Decimal("100.00"))
        self.assertGreater(close.score, engine.MODERATE_SCORE)
        self.assertLess(far.score, engine.MIN_SCORE)
        self.assertGreater(close.score, far.score)
        self.assertEqual(close.score, engine.compare(STUDY_COPY, STUDY).score)
        self.assertEqual(engine.compare(STUDY, {}).score, Decimal("0.00"))
        self.assertEqual(engine.compare({}, {}).score, Decimal("0.00"))
        self.assertIn("study", close.shared_terms)
        self.assertIn("room", close.shared_terms)
        self.assertIn("campus", close.shared_terms)

    def test_explanations_and_recommendations(self):
        close = engine.compare(STUDY, STUDY_COPY)
        text = engine.explain(close)
        self.assertIn("Strongest overlap", text)
        self.assertIn("Shared terms:", text)
        self.assertIn("general wording", engine.explain(engine.compare(STUDY, {})))

        none = engine.recommend(STUDY, [])
        self.assertIn("No similar projects", none[0])
        self.assertIn("short description", none[-1])
        self.assertNotIn("problem statement", none[-1])

        identical = engine.recommend(STUDY, [("Twin", engine.compare(STUDY, STUDY))])
        self.assertIn("very close to “Twin”", identical[0])
        moderate = engine.Comparison(score=Decimal("55.00"), section_scores={"scope": 0.6})
        self.assertIn("in the scope and limitations", engine.recommend(STUDY, [("Mid", moderate)])[0])
        category_only = engine.Comparison(score=Decimal("20.00"), section_scores={"category": 1.0})
        self.assertIsNone(category_only.strongest_section)
        self.assertIn("(73%)", engine.recommend(STUDY, [("T", engine.Comparison(score=Decimal("73.20")))])[0])
        low = engine.Comparison(score=Decimal("15.00"))
        self.assertIn("reasonably distinct", engine.recommend(STUDY, [("Low", low)])[0])
        repeated = engine.recommend(STUDY, [("A", close), ("B", close)])
        self.assertTrue(any("Several similar projects" in item for item in repeated))


def make_project(user, fields, **project_fields):
    project = Project.objects.create(user=user, **project_fields)
    ProjectVersion.objects.create(project=project, version_number=1, **fields)
    return project


class SimilarityCheckViewTest(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user("owner")
        self.other = users.create_user("other")
        self.project = make_project(self.owner, STUDY)
        self.run_url = f"/checks/run/{self.project.pk}/"

    def test_run_compares_only_permitted_projects(self):
        public = make_project(self.other, STUDY_COPY, is_public=True)
        make_project(self.other, {**STUDY_COPY, "title": "Hidden private twin"})
        make_project(
            self.other, {**STUDY_COPY, "title": "Archived twin"},
            is_public=True, status=Project.Status.ARCHIVED,
        )
        make_project(self.other, CLINIC, is_public=True)
        mine = make_project(self.owner, {**STUDY, "title": "My earlier study idea"})
        self.client.force_login(self.owner)
        response = self.client.post(self.run_url)
        check = SimilarityCheck.objects.get()
        self.assertRedirects(response, f"/checks/{check.pk}/")
        self.assertEqual(check.status, "completed")
        self.assertIsNotNone(check.completed_at)
        self.assertEqual(check.project_version, self.project.versions.get())
        matched = list(check.matches.order_by("-similarity_score").values_list("matched_version__project", flat=True))
        self.assertEqual(matched, [mine.pk, public.pk])
        self.assertTrue(check.recommendations.exists())

        page = self.client.get(f"/checks/{check.pk}/")
        self.assertContains(page, "My earlier study idea")
        self.assertContains(page, "Public project by @other")
        self.assertContains(page, "High similarity")
        top_score = check.matches.order_by("-similarity_score").first().similarity_score
        self.assertContains(page, f'style="width: {top_score:.0f}%"')
        self.assertNotContains(page, "Hidden private twin")
        self.assertNotContains(page, "Archived twin")
        self.assertNotContains(page, "Barangay clinic queue")
        self.assertNotContains(page, f"/projects/{public.pk}/")
        self.assertContains(self.client.get("/checks/"), "Campus study space finder")
        self.assertContains(self.client.get(f"/projects/{self.project.pk}/"), f"/checks/{check.pk}/")

    def test_no_matches_and_latest_version_is_checked(self):
        ProjectVersion.objects.create(
            project=self.project, version_number=2, title="<i>Renamed</i> finder"
        )
        self.client.force_login(self.owner)
        self.client.post(self.run_url)
        check = SimilarityCheck.objects.get()
        self.assertEqual(check.project_version.version_number, 2)
        self.assertFalse(check.matches.exists())
        page = self.client.get(f"/checks/{check.pk}/")
        self.assertContains(page, "No similar projects were found")
        self.assertContains(page, "&lt;i&gt;Renamed&lt;/i&gt; finder")
        self.assertNotContains(page, "earlier version")
        ProjectVersion.objects.create(project=self.project, version_number=3, title="Third")
        self.assertContains(self.client.get(f"/checks/{check.pk}/"), "earlier version")

    def test_checks_are_private_and_archived_projects_are_refused(self):
        self.assertRedirects(self.client.get("/checks/"), "/login/?next=/checks/")
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.run_url).status_code, 405)
        self.client.post(self.run_url)
        check = SimilarityCheck.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.run_url).status_code, 404)
        self.assertEqual(self.client.get(f"/checks/{check.pk}/").status_code, 404)
        self.assertNotContains(self.client.get("/checks/"), "Campus study space finder")
        self.assertContains(self.client.get("/checks/"), "You need a project")
        self.assertEqual(SimilarityCheck.objects.count(), 1)
        self.client.force_login(self.owner)
        self.project.status = Project.Status.ARCHIVED
        self.project.save()
        self.assertRedirects(self.client.post(self.run_url), f"/projects/{self.project.pk}/")
        self.assertEqual(SimilarityCheck.objects.count(), 1)
