"""MedMap 제품 엔진 회귀 테스트 (요구 13항목 + STEP16B 동등성).

실행: ~/ai_env/bin/python -m unittest discover -s tests -v   (repo 루트에서)
연구 산출물은 읽기만 하며, 학습·분할·VALIDATION/TEST 접근은 없다.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import (STOP_MAX_QUESTIONS, STOP_NO_ELIGIBLE_QUESTION, AnswerStatus, DiagnosisEngine, EvidenceCatalog,
                    NextInformationEngine, PatientState, QuestionEligibility, negative, positive, unknown, value)
from medmap import config

CATALOG = EvidenceCatalog()
ENGINE = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"))


def base_state():
    return PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"), "E_204": value("V_10")})


def any_answer(evidence_id):
    if CATALOG.dtype[evidence_id] == "B":
        return positive()
    return value(CATALOG.question(evidence_id).possible_values[0])


class StateRepresentationTests(unittest.TestCase):
    def test_01_unasked_is_not_negative(self):
        unasked = PatientState.new(30, "F", "E_53")
        answered = PatientState.new(30, "F", "E_53", {"E_91": negative()})
        self.assertIsNone(unasked.status("E_91"))
        self.assertIs(answered.status("E_91"), AnswerStatus.NEGATIVE)
        self.assertNotEqual(CATALOG.encode([unasked]).nnz, CATALOG.encode([answered]).nnz)
        self.assertFalse(np.allclose(ENGINE.diagnosis.posterior(unasked), ENGINE.diagnosis.posterior(answered)))

    def test_01b_unknown_activates_no_feature_but_blocks_reasking(self):
        state = PatientState.new(30, "F", "E_53", {"E_91": unknown()})
        self.assertEqual(CATALOG.encode([state]).nnz, CATALOG.encode([PatientState.new(30, "F", "E_53")]).nnz)
        self.assertNotIn("E_91", ENGINE.eligibility.eligible_questions(state))


class EligibilityTests(unittest.TestCase):
    def test_02_asked_question_is_never_selected_again(self):
        turn = ENGINE.start(base_state())
        chosen = turn.next_question.evidence_id
        nxt = ENGINE.answer(turn, chosen, any_answer(chosen))
        self.assertNotEqual(nxt.next_question.evidence_id, chosen)
        self.assertNotIn(chosen, ENGINE.eligibility.eligible_questions(nxt.state))

    def test_03_initial_evidence_is_never_asked_again(self):
        self.assertNotIn("E_53", ENGINE.eligibility.eligible_questions(base_state()))

    def test_04_excluded_questions_never_enter_the_pool(self):
        self.assertEqual(set(config.EXCLUDED_QUESTIONS), {"E_134", "E_152"})
        for state in (base_state(), PatientState.new(45, "M", "E_129"), PatientState.new(45, "M", "E_151")):
            pool = ENGINE.eligibility.eligible_questions(state)
            self.assertNotIn("E_134", pool)
            self.assertNotIn("E_152", pool)
        for excluded in config.EXCLUDED_QUESTIONS:
            self.assertNotIn(excluded, ENGINE.likelihoods.index)

    def test_05_child_opens_only_when_parent_is_positive(self):
        self.assertIn("E_130", ENGINE.eligibility.eligible_questions(PatientState.new(45, "M", "E_129")))

    def test_06_child_is_closed_when_parent_is_negative_unknown_or_unasked(self):
        for parent_answer in (negative(), unknown()):
            closed = PatientState.new(45, "M", None, {"E_129": parent_answer})
            self.assertNotIn("E_130", ENGINE.eligibility.eligible_questions(closed))
        self.assertNotIn("E_130", ENGINE.eligibility.eligible_questions(PatientState.new(45, "M", "E_53")))


class SafetyTests(unittest.TestCase):
    def test_07_no_hidden_answer_or_truth_access_in_product_code(self):
        for name in ["patient_state.py", "diagnosis.py", "eligibility.py", "next_information.py", "evidence.py"]:
            source = (ROOT / "medmap" / name).read_text()
            for forbidden in ["PATHOLOGY", "release_validate_patients", "release_test_patients", "true_diagnosis", "hidden_answer"]:
                self.assertNotIn(forbidden, source, f"{name} references {forbidden}")
        self.assertFalse(hasattr(base_state(), "truth"))

    def test_07b_forbidden_paths_are_blocked(self):
        for path in config.FORBIDDEN_PATHS:
            with self.assertRaises(config.MedMapForbiddenPath):
                config.check_path(path)


class SelectionTests(unittest.TestCase):
    def test_08_same_state_yields_the_same_question(self):
        first, second = ENGINE.start(base_state()), ENGINE.start(base_state())
        self.assertEqual(first.next_question.evidence_id, second.next_question.evidence_id)
        self.assertEqual(first.candidates, second.candidates)

    def test_09_tie_break_prefers_lower_evidence_number(self):
        class _Ties:
            classes = ENGINE.diagnosis.classes
            index = {"E_200": 0, "E_44": 1, "E_91": 2}
            def information_gain(self, posterior):
                return np.array([0.5, 0.5, 0.5])
        original = ENGINE.likelihoods
        ENGINE.likelihoods = _Ties()
        try:
            ranked = ENGINE.rank_questions(ENGINE.diagnosis.diagnose(base_state()), ["E_200", "E_44", "E_91"])
        finally:
            ENGINE.likelihoods = original
        self.assertEqual([e for e, _ in ranked], ["E_44", "E_91", "E_200"])


class RuntimeContractTests(unittest.TestCase):
    def test_10_answering_never_refits_the_model(self):
        model_cls = type(ENGINE.diagnosis.model)
        original_fit = model_cls.fit
        def explode(*args, **kwargs):
            raise AssertionError("MEDMAP_RUNTIME_FIT_FORBIDDEN")
        model_cls.fit = explode
        try:
            turn = ENGINE.start(base_state())
            ENGINE.answer(turn, turn.next_question.evidence_id, any_answer(turn.next_question.evidence_id))
        finally:
            model_cls.fit = original_fit

    def test_11_posterior_is_recomputed_after_an_answer(self):
        turn = ENGINE.start(base_state())
        qid = turn.next_question.evidence_id
        answers = [positive(), negative()] if CATALOG.dtype[qid] == "B" else \
            [value(v) for v in CATALOG.question(qid).possible_values]
        changed = []
        for answer in answers:
            nxt = ENGINE.answer(turn, qid, answer)
            self.assertEqual(nxt.diagnoses_before.ranking, turn.diagnoses.ranking)
            self.assertIsNot(nxt.diagnoses, turn.diagnoses)
            changed.append(nxt.diagnoses.probabilities != turn.diagnoses.probabilities)
        # 학습에서 한 번도 관측되지 않은 값(가중치 0)은 확률을 바꾸지 않을 수 있으나,
        # 적어도 하나의 합법적 답변은 posterior 를 실제로 바꿔야 한다.
        self.assertTrue(any(changed))

    def test_12_stops_at_max_questions(self):
        engine = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"), max_questions=2)
        turn = engine.start(base_state())
        for _ in range(2):
            qid = turn.next_question.evidence_id
            turn = engine.answer(turn, qid, any_answer(qid))
        self.assertIsNone(turn.next_question)
        self.assertEqual(turn.stop_reason, STOP_MAX_QUESTIONS)

    def test_13_stops_when_no_eligible_question_remains(self):
        engine = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"))
        eligibility = QuestionEligibility(CATALOG)
        eligibility.eligible_questions = lambda state: []
        engine.eligibility = eligibility
        turn = engine.start(base_state())
        self.assertIsNone(turn.next_question)
        self.assertEqual(turn.stop_reason, STOP_NO_ELIGIBLE_QUESTION)


class AnswerValidationTests(unittest.TestCase):
    def test_15_invalid_answer_shape_is_rejected_before_encoding(self):
        turn = ENGINE.start(base_state())
        qid = turn.next_question.evidence_id            # MULTI 질문
        with self.assertRaises(ValueError):
            ENGINE.answer(turn, qid, positive())
        with self.assertRaises(ValueError):
            ENGINE.answer(turn, qid, value("V_NOT_A_REAL_VALUE"))
        with self.assertRaises(ValueError):
            ENGINE.answer(turn, "E_91", negative())     # 제안되지 않은 질문


class Step16BEquivalenceTests(unittest.TestCase):
    """합성 fixture 에서 연구 코드(s16b_core)와 제품 엔진의 pool·IG 순위·top question 이 같은지."""

    def test_14_same_pool_and_question_ranking_as_step16b(self):
        sys.path.insert(0, str(ROOT / "exp" / "step16b_next_information_validation"))
        import s16b_core as research

        sem = research.Semantics()
        data = np.load(config.IG_TABLE_NPZ, allow_pickle=True)
        research_table = {e: np.asarray(data[e], dtype=np.float64) for e in sem.qids}
        qs, qpos, matrix, group = research.pack_ig(sem, research_table)

        fixtures = [
            base_state(),
            PatientState.new(22, "F", "E_129", {"E_91": negative(), "E_204": value("V_10")}),
            PatientState.new(70, "M", "E_91", {"E_53": negative(), "E_201": positive(), "E_204": value("V_1")}),
        ]
        for state in fixtures:
            visible = {e: a.tokens() for e, a in state.answers.items() if a.tokens()}
            research_pool = sorted([q for q in sem.qids if sem.currently_eligible(q, visible)], key=research.qnum)
            product_pool = ENGINE.eligibility.eligible_questions(state)
            self.assertEqual(research_pool, product_pool)

            gains = research.ig_all(ENGINE.diagnosis.posterior(state).astype(np.float64), matrix, group, len(qs))
            research_rank = sorted(product_pool, key=lambda q: (-round(float(gains[qpos[q]]), 12), research.qnum(q)))
            product = ENGINE.rank_questions(ENGINE.diagnosis.diagnose(state), product_pool)
            self.assertEqual(research_rank[:10], [e for e, _ in product[:10]])
            for evidence_id, gain in product[:5]:
                self.assertAlmostEqual(float(gains[qpos[evidence_id]]), gain, places=12)


if __name__ == "__main__":
    unittest.main()
