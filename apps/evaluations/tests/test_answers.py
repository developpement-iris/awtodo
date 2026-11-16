from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.evaluations.answers import AnswerError, clean_answers, normalize_answer, visible_question_ids


def q(id, answer_type, *, options=(), required=False, condition_on=None, values=()):
    return SimpleNamespace(
        id=id, label=f"Q{id}", answer_type=answer_type, options=list(options), required=required,
        condition_on_id=condition_on, condition_values=list(values),
    )


class NormalizeTests(SimpleTestCase):
    def test_note_bounds(self):
        self.assertEqual(normalize_answer(q("a", "note_5"), 5), 5)
        for bad in (0, 6, "3", True, 2.5):
            with self.assertRaises(AnswerError):
                normalize_answer(q("a", "note_5"), bad)

    def test_nps_bounds(self):
        self.assertEqual(normalize_answer(q("a", "nps_10"), 0), 0)
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "nps_10"), 11)

    def test_yes_no_accepts_bool_and_text(self):
        self.assertEqual(normalize_answer(q("a", "oui_non"), True), "oui")
        self.assertEqual(normalize_answer(q("a", "oui_non"), "non"), "non")
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "oui_non"), "peut-être")

    def test_choices_must_be_known_options(self):
        single = q("a", "choix_unique", options=["A", "B"])
        multi = q("b", "choix_multiple", options=["A", "B"])
        self.assertEqual(normalize_answer(single, "B"), "B")
        self.assertEqual(normalize_answer(multi, ["A", "B"]), ["A", "B"])
        for question, bad in ((single, "C"), (multi, ["A", "A"]), (multi, ["Z"]), (multi, "A")):
            with self.assertRaises(AnswerError):
                normalize_answer(question, bad)

    def test_text_is_trimmed_and_limited(self):
        self.assertEqual(normalize_answer(q("a", "texte_court"), "  ok "), "ok")
        self.assertIsNone(normalize_answer(q("a", "texte_court"), "   "))
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "texte_court"), "x" * 201)
        with self.assertRaises(AnswerError):
            normalize_answer(q("a", "texte_long"), "x" * 5001)

    def test_empty_values_are_none(self):
        for empty in (None, "", []):
            self.assertIsNone(normalize_answer(q("a", "choix_multiple", options=["A"]), empty))

    def test_zero_is_not_empty(self):
        self.assertEqual(normalize_answer(q("a", "nps_10"), 0), 0)


class VisibilityTests(SimpleTestCase):
    def setUp(self):
        self.root = q("r", "choix_unique", options=["Interne", "Presta", "Mixte"])
        self.presta = q("p", "oui_non", condition_on="r", values=["Presta", "Mixte"])
        self.sub = q("s", "note_5", condition_on="p", values=["oui"])
        self.questions = [self.root, self.presta, self.sub]

    def test_condition_met(self):
        self.assertEqual(visible_question_ids([self.root, self.presta], {"r": "Mixte"}), {"r", "p"})

    def test_condition_not_met(self):
        self.assertEqual(visible_question_ids([self.root, self.presta], {"r": "Interne"}), {"r"})

    def test_hidden_parent_hides_child(self):
        self.assertNotIn("s", visible_question_ids(self.questions, {"r": "Interne", "p": "oui"}))

    def test_missing_target_keeps_question_visible(self):
        self.assertEqual(visible_question_ids([self.presta], {}), {"p"})


class CleanAnswersTests(SimpleTestCase):
    def setUp(self):
        self.root = q("r", "oui_non", required=True)
        self.detail = q("d", "texte_long", required=True, condition_on="r", values=["oui"])
        self.questions = [self.root, self.detail]

    def test_hidden_answers_are_dropped(self):
        cleaned = clean_answers(self.questions, {"r": False, "d": "texte"}, enforce_required=True)
        self.assertEqual(cleaned, {"r": "non", "d": None})

    def test_required_visible_question_is_enforced(self):
        with self.assertRaises(AnswerError) as ctx:
            clean_answers(self.questions, {"r": True}, enforce_required=True)
        self.assertEqual(ctx.exception.question_id, "d")

    def test_required_not_enforced_for_drafts(self):
        self.assertEqual(clean_answers(self.questions, {}, enforce_required=False), {"r": None, "d": None})

    def test_unknown_question_is_rejected(self):
        with self.assertRaises(AnswerError):
            clean_answers(self.questions, {"zzz": 1}, enforce_required=False)
