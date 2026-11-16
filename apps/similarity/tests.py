from decimal import Decimal

from django.test import SimpleTestCase

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
        low = engine.Comparison(score=Decimal("15.00"))
        self.assertIn("reasonably distinct", engine.recommend(STUDY, [("Low", low)])[0])
        repeated = engine.recommend(STUDY, [("A", close), ("B", close)])
        self.assertTrue(any("Several similar projects" in item for item in repeated))
