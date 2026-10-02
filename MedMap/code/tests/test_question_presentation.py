"""질문 표현 계층 회귀 테스트 — 표현만 바뀌고 선택·IG·posterior 는 불변이어야 한다."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import (AnswerStatus, DiagnosisEngine, EvidenceCatalog, NextInformationEngine, PatientState,
                    config, negative, positive, value)
from medmap.question_presentation import MULTI_CHOICE, SCALE, SINGLE_CHOICE, YES_NO, QuestionPresenter

CATALOG = EvidenceCatalog()
PRESENTER = QuestionPresenter(CATALOG)
PLAIN_ENGINE = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"))
PRESENTED_ENGINE = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"), presenter=PRESENTER)


def base_state():
    return PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"), "E_204": value("V_10")})


class PresentationTests(unittest.TestCase):
    def test_01_binary_question_is_shown_in_korean_with_three_choices(self):
        view = PRESENTER.present("E_155").to_dict()
        self.assertEqual(view["answer_type"], YES_NO)
        self.assertIn("두근거림", view["question_ko"])
        self.assertNotEqual(view["question_ko"], view["question_original"])
        self.assertFalse(view["is_fallback"])
        self.assertEqual([c["value"] for c in view["choices"]], [True, False, None])
        self.assertEqual([c["label"] for c in view["choices"]], ["예", "아니요", "잘 모르겠어요"])

    def test_02_categorical_question_lists_its_defined_values_only(self):
        view = PRESENTER.present("E_130").to_dict()
        self.assertEqual(view["answer_type"], SINGLE_CHOICE)
        codes = [c["value"] for c in view["choices"] if c["value"] is not None]
        self.assertEqual(codes, list(CATALOG.question("E_130").possible_values))   # 값 추가·삭제 없음
        self.assertIn("분홍색", [c["label"] for c in view["choices"]])

    def test_02b_numeric_scale_question_keeps_its_defined_scale(self):
        view = PRESENTER.present("E_56").to_dict()
        self.assertEqual(view["answer_type"], SCALE)
        self.assertEqual([c["value"] for c in view["choices"] if c["value"] is not None],
                         list(CATALOG.question("E_56").possible_values))

    def test_03_multi_question_accepts_multiple_selections(self):
        view = PRESENTER.present("E_57").to_dict()
        self.assertEqual(view["answer_type"], MULTI_CHOICE)
        answer = PRESENTER.to_answer("E_57", ["V_89", "V_92"])
        self.assertIs(answer.status, AnswerStatus.VALUE)
        self.assertEqual(set(answer.values), {"V_89", "V_92"})

    def test_04_yes_maps_to_positive(self):
        self.assertIs(PRESENTER.to_answer("E_155", "예").status, AnswerStatus.POSITIVE)
        self.assertIs(PRESENTER.to_answer("E_155", True).status, AnswerStatus.POSITIVE)

    def test_05_no_maps_to_negative(self):
        self.assertIs(PRESENTER.to_answer("E_155", "아니요").status, AnswerStatus.NEGATIVE)
        self.assertIs(PRESENTER.to_answer("E_155", False).status, AnswerStatus.NEGATIVE)

    def test_06_unknown_maps_to_unknown(self):
        self.assertIs(PRESENTER.to_answer("E_155", "잘 모르겠어요").status, AnswerStatus.UNKNOWN)
        self.assertIs(PRESENTER.to_answer("E_155", None).status, AnswerStatus.UNKNOWN)
        self.assertIs(PRESENTER.to_answer("E_130", None).status, AnswerStatus.UNKNOWN)

    def test_07_korean_label_resolves_to_the_original_value_id(self):
        self.assertEqual(PRESENTER.to_answer("E_130", "분홍색").values, ("V_156",))
        self.assertEqual(PRESENTER.to_answer("E_55", "이마").values, ("V_89",))
        self.assertEqual(PRESENTER.to_answer("E_54", ["타는 듯한", "묵직한"]).values, ("V_181", "V_183"))
        with self.assertRaises(ValueError):
            PRESENTER.to_answer("E_130", "존재하지 않는 색")

    def test_08_unmapped_question_falls_back_to_the_original_text(self):
        unmapped = next(e for e in CATALOG.ids if e not in PRESENTER.questions_ko)
        view = PRESENTER.present(unmapped).to_dict()
        self.assertTrue(view["is_fallback"])
        self.assertEqual(view["question_ko"], view["question_original"])
        self.assertEqual(view["question_ko"], CATALOG.question(unmapped).text)

    def test_08b_coverage_counts_are_consistent(self):
        coverage = PRESENTER.coverage()
        self.assertEqual(coverage["total_evidence"], len(CATALOG.ids))
        self.assertEqual(coverage["korean_mapped"] + coverage["fallback"], coverage["total_evidence"])
        self.assertEqual(coverage["parent_questions_mapped"], coverage["parent_questions"])
        for evidence_id in PRESENTER.questions_ko:
            self.assertIn(evidence_id, CATALOG.questions)


class InvarianceTests(unittest.TestCase):
    """9~13: 표현 계층을 붙여도 엔진 동작이 그대로인지."""

    def test_09_10_11_selection_ig_and_posterior_are_unchanged(self):
        state = base_state()
        plain, presented = PLAIN_ENGINE.start(state), PRESENTED_ENGINE.start(state)
        self.assertEqual(plain.next_question.evidence_id, presented.next_question.evidence_id)
        self.assertEqual(plain.next_question.information_gain, presented.next_question.information_gain)
        self.assertEqual(plain.diagnoses.probabilities, presented.diagnoses.probabilities)
        self.assertEqual(plain.candidates, presented.candidates)

        qid = plain.next_question.evidence_id
        answer = PRESENTER.to_answer(qid, "타는 듯한")
        after_plain = PLAIN_ENGINE.answer(plain, qid, answer)
        after_presented = PRESENTED_ENGINE.answer(presented, qid, answer)
        self.assertEqual(after_plain.next_question.evidence_id, after_presented.next_question.evidence_id)
        self.assertEqual(after_plain.next_question.information_gain, after_presented.next_question.information_gain)
        self.assertEqual(after_plain.diagnoses.probabilities, after_presented.diagnoses.probabilities)

    def test_09b_existing_output_keys_are_preserved(self):
        view = PRESENTED_ENGINE.start(base_state()).next_question.to_dict()
        for key in ["question_id", "question_text", "answer_type_raw", "possible_values", "information_gain",
                    "explanation", "question_ko", "question_original", "choices", "is_fallback"]:
            self.assertIn(key, view)
        self.assertIsNone(view["explanation"])

    def test_12_excluded_questions_stay_out_with_the_presenter(self):
        for state in (base_state(), PatientState.new(45, "M", "E_129"), PatientState.new(45, "M", "E_151")):
            pool = PRESENTED_ENGINE.eligibility.eligible_questions(state)
            for excluded in config.EXCLUDED_QUESTIONS:
                self.assertNotIn(excluded, pool)
            turn = PRESENTED_ENGINE.start(state)
            if turn.next_question is not None:
                self.assertNotIn(turn.next_question.evidence_id, config.EXCLUDED_QUESTIONS)

    def test_13_parent_gate_rule_is_unchanged_with_the_presenter(self):
        opened = PatientState.new(45, "M", "E_129")
        self.assertIn("E_130", PRESENTED_ENGINE.eligibility.eligible_questions(opened))
        closed = PatientState.new(45, "M", None, {"E_129": negative()})
        self.assertNotIn("E_130", PRESENTED_ENGINE.eligibility.eligible_questions(closed))
        unasked_parent = PatientState.new(45, "M", "E_53")
        self.assertNotIn("E_130", PRESENTED_ENGINE.eligibility.eligible_questions(unasked_parent))


if __name__ == "__main__":
    unittest.main()
