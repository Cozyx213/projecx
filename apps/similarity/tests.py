import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.home.models import Project, ProjectVersion, SimilarityCheck

from . import engine, llm, views

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

    def test_run_list_splits_projects_by_subquery(self):
        checked = make_project(self.owner, {**CLINIC, "title": "Already checked"})
        SimilarityCheck.objects.create(project_version=checked.versions.get())
        make_project(self.owner, {**CLINIC, "title": "Archived idea"}, status=Project.Status.ARCHIVED)
        other_checked = make_project(self.other, {**CLINIC, "title": "Other's project"})
        SimilarityCheck.objects.create(project_version=other_checked.versions.get())

        sql = str(views.projects_not_checked(self.owner).query)
        self.assertIn("NOT (", sql)
        self.assertIn('IN (SELECT U1."project_id"', sql)
        self.assertEqual(list(views.projects_not_checked(self.owner)), [self.project])
        self.assertEqual(list(views.projects_checked(self.owner)), [checked])

        self.client.force_login(self.owner)
        page = self.client.get("/checks/")
        self.assertEqual(
            [c["project"] for c in page.context["unchecked"]], [self.project]
        )
        self.assertEqual([c["project"] for c in page.context["checked"]], [checked])
        self.assertContains(page, "Not checked yet")
        self.assertNotContains(page, "Archived idea")
        self.assertNotContains(page, "Other&#x27;s project")

    def test_check_history_joins_versions_and_projects(self):
        check = SimilarityCheck.objects.create(project_version=self.project.versions.get())
        sql = str(views.check_history(self.owner).query)
        self.assertIn('INNER JOIN "project_versions"', sql)
        self.assertIn('INNER JOIN "projects"', sql)
        with self.assertNumQueries(1):
            row = views.check_history(self.owner).get()
            self.assertEqual(row.project_version.title, STUDY["title"])
            self.assertEqual(row.project_version.project_id, self.project.pk)
        self.assertEqual(row, check)


@override_settings(OPENAI_API_KEY="sk-test-key", OPENAI_MODEL="gpt-6-luna")
class OpenAISimilarityTest(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user("owner")
        self.other = users.create_user("other")
        self.project = make_project(self.owner, STUDY)
        self.run_url = f"/checks/run/{self.project.pk}/"

    def test_uses_openai_embeddings_and_chat_for_semantic_matches(self):
        paraphrase = make_project(
            self.other,
            {
                "title": "University library seat availability tracker",
                "problem_statement": "Undergraduates spend too much time searching for open desks.",
                "proposed_solution": "Live floorplan showing free library seats.",
                "target_users": "University learners",
            },
            is_public=True,
        )
        paraphrase_version = paraphrase.versions.get()
        clinic = make_project(self.other, CLINIC, is_public=True)
        clinic_version = clinic.versions.get()

        def fake_post(path, payload):
            if path == "embeddings":
                # target=[1,0], paraphrase=[0.95,0.05], clinic=[0,1]
                return {
                    "data": [
                        {"index": 0, "embedding": [1.0, 0.0]},
                        {"index": 1, "embedding": [0.95, 0.05]},
                        {"index": 2, "embedding": [0.0, 1.0]},
                    ]
                }
            self.assertEqual(path, "chat/completions")
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "matches": [
                                        {
                                            "candidate_id": paraphrase_version.pk,
                                            "similarity_score": 84.5,
                                            "explanation": "Both proposals track live study space availability for college students.",
                                        },
                                        {
                                            "candidate_id": clinic_version.pk,
                                            "similarity_score": 4.0,
                                            "explanation": "Unrelated domain.",
                                        },
                                        {
                                            "candidate_id": 999999,
                                            "similarity_score": 99,
                                            "explanation": "Invented id",
                                        },
                                    ],
                                    "recommendations": [
                                        "Differentiate by adding group study room reservations and noise sensors.",
                                        "Specify the scope and key features for your campus rollout.",
                                    ],
                                }
                            )
                        }
                    }
                ]
            }

        self.client.force_login(self.owner)
        with patch("apps.similarity.llm._post_json", side_effect=fake_post) as mocked:
            response = self.client.post(self.run_url, follow=True)
        self.assertEqual(mocked.call_count, 2)
        self.assertContains(response, "AI analysis")

        check = SimilarityCheck.objects.get()
        matches = list(check.matches.all())
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_version, paraphrase_version)
        self.assertEqual(matches[0].similarity_score, Decimal("84.50"))
        self.assertIn("live study space availability", matches[0].explanation)
        recs = list(check.recommendations.order_by("pk").values_list("suggestion", flat=True))
        self.assertEqual(len(recs), 2)
        self.assertIn("noise sensors", recs[0])

    def test_falls_back_to_local_engine_when_openai_fails(self):
        public = make_project(self.other, STUDY_COPY, is_public=True)
        self.client.force_login(self.owner)
        with patch("apps.similarity.llm._post_json", side_effect=llm.OpenAIError("timeout")):
            with self.assertLogs("apps.similarity.views", level="WARNING"):
                response = self.client.post(self.run_url, follow=True)
        self.assertContains(response, "Similarity check completed.")
        check = SimilarityCheck.objects.get()
        self.assertEqual(check.status, "completed")
        self.assertEqual(
            list(check.matches.values_list("matched_version__project", flat=True)),
            [public.pk],
        )
