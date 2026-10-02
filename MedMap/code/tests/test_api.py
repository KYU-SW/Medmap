"""API v1 회귀 테스트 — API 는 엔진을 감싸기만 하며 결과를 바꾸지 않는다.

실행: ~/ai_env/bin/python -m unittest discover -s tests
"""
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import DiagnosisEngine, EvidenceCatalog, NextInformationEngine, PatientState, value
from medmap import api as api_module
from medmap.question_presentation import QuestionPresenter
from medmap.serialization import deserialize_session

CLIENT = TestClient(api_module.app)
CATALOG = EvidenceCatalog()
PRESENTER = QuestionPresenter(CATALOG)

START_BODY = {"age": 45, "sex": "M", "model_context": "k3", "initial_evidence": "E_53",
              "answers": [{"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
                          {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
                          {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}]}


def setUpModule():
    CLIENT.__enter__()          # lifespan 실행(모델 1회 로딩)


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def start():
    response = CLIENT.post("/v1/session/start", json=START_BODY)
    assert response.status_code == 200, response.text
    return response.json()


def answer(turn, values=("V_181",), question_id=None, session=None):
    submission = {"question_id": question_id or turn["next_question"]["question_id"],
                  "answer": {"kind": "VALUE", "value": list(values)}}
    return CLIENT.post("/v1/session/answer", json={"session": session or turn["session"], "submission": submission})


class HealthTests(unittest.TestCase):
    def test_01_health(self):
        body = CLIENT.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["engine_ready"])
        self.assertEqual(body["schema"], {"session": "medmap-session-v1", "turn": "medmap-turn-v1",
                                          "answer": "medmap-answer-v1"})
        self.assertEqual(body["max_questions"], api_module.MAX_QUESTIONS)
        self.assertEqual(body["model_contexts"], ["k3", "k5", "k10"])


class FlowTests(unittest.TestCase):
    def test_02_start(self):
        turn = start()
        self.assertEqual(turn["schema_version"], "medmap-turn-v1")
        self.assertEqual(len(turn["diagnoses"]), 3)
        self.assertIn("question_ko", turn["next_question"])
        self.assertEqual(turn["questions_asked_in_session"], 0)
        self.assertIsNone(turn["stop_reason"])
        self.assertEqual(turn["session"]["schema_version"], "medmap-session-v1")

    def test_03_answer(self):
        turn = start()
        after = answer(turn).json()
        self.assertEqual(after["diagnoses_before"], turn["diagnoses"])
        self.assertEqual(after["n_asked"], turn["n_asked"] + 1)
        self.assertEqual(after["questions_asked_in_session"], 1)
        self.assertNotEqual(after["next_question"]["question_id"], turn["next_question"]["question_id"])

    def test_04_resume(self):
        turn = start()
        after = answer(turn).json()
        resumed = CLIENT.post("/v1/session/resume", json={"session": after["session"]}).json()
        self.assertEqual(resumed["diagnoses"], after["diagnoses"])
        self.assertEqual(resumed["next_question"]["question_id"], after["next_question"]["question_id"])
        self.assertEqual(resumed["next_question"]["information_gain"], after["next_question"]["information_gain"])
        self.assertEqual(resumed["questions_asked_in_session"], after["questions_asked_in_session"])

    def test_05_start_answer_resume_chain_and_max_questions(self):
        turn = start()
        for expected in (1, 2, 3):
            question_id = turn["next_question"]["question_id"]
            choice = CATALOG.question(question_id).possible_values
            payload = {"question_id": question_id,
                       "answer": {"kind": "VALUE", "value": [choice[0]]} if choice else
                                 {"kind": "NEGATIVE", "value": None}}
            turn = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": payload}).json()
            self.assertEqual(turn["questions_asked_in_session"], expected)
        self.assertIsNone(turn["next_question"])
        self.assertEqual(turn["stop_reason"], "MAX_QUESTIONS")
        resumed = CLIENT.post("/v1/session/resume", json={"session": turn["session"]}).json()
        self.assertEqual(resumed["stop_reason"], "MAX_QUESTIONS")     # 질문 수는 세션 상태에서 계산된다


class ErrorTests(unittest.TestCase):
    def submit(self, submission, session=None):
        return CLIENT.post("/v1/session/answer", json={"session": session or start()["session"],
                                                       "submission": submission})

    def test_06_unknown_evidence_id(self):
        response = self.submit({"question_id": "E_9999", "answer": {"kind": "POSITIVE", "value": None}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNKNOWN_EVIDENCE_ID")

    def test_07_invalid_value_id(self):
        response = self.submit({"question_id": "E_130", "answer": {"kind": "VALUE", "value": ["V_NOPE"]}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_INVALID_ANSWER_VALUE")

    def test_08_parent_gate_violation(self):
        response = self.submit({"question_id": "E_130", "answer": {"kind": "VALUE", "value": ["V_156"]}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_PARENT_GATE_VIOLATION")

    def test_09_excluded_questions(self):
        for excluded in ("E_134", "E_152"):
            response = self.submit({"question_id": excluded, "answer": {"kind": "VALUE", "value": ["0"]}})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"]["code"], "MEDMAP_EXCLUDED_QUESTION")

    def test_10_duplicate_answer(self):
        response = self.submit({"question_id": "E_55", "answer": {"kind": "VALUE", "value": ["V_89"]}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_ALREADY_ASKED")

    def test_11_unsupported_schema_version(self):
        session = start()["session"]
        session["schema_version"] = "medmap-session-v2"
        response = CLIENT.post("/v1/session/resume", json={"session": session})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNSUPPORTED_SCHEMA_VERSION")

    def test_12_invalid_model_context(self):
        body = dict(START_BODY, model_context="k7")
        response = CLIENT.post("/v1/session/start", json=body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_INVALID_MODEL_CONTEXT")
        session = start()["session"]
        session["patient_state"]["model_context"] = "k7"
        self.assertEqual(CLIENT.post("/v1/session/resume", json={"session": session}).status_code, 400)

    def test_19_answering_a_question_that_was_not_proposed(self):
        turn = start()
        other = next(q for q in ("E_91", "E_201", "E_181")
                     if q != turn["next_question"]["question_id"])
        response = self.submit({"question_id": other, "answer": {"kind": "POSITIVE", "value": None}},
                               session=turn["session"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNEXPECTED_ANSWER")

    def test_20_identifying_fields_are_rejected(self):
        for extra in ({"name": "홍길동"}, {"phone": "010-0000-0000"}, {"email": "a@b.c"}, {"max_questions": 100}):
            response = CLIENT.post("/v1/session/start", json=dict(START_BODY, **extra))
            self.assertEqual(response.status_code, 422, extra)
            self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_20b_invalid_age_and_sex(self):
        self.assertEqual(CLIENT.post("/v1/session/start", json=dict(START_BODY, age=-1)).status_code, 400)
        self.assertEqual(CLIENT.post("/v1/session/start", json=dict(START_BODY, sex="X")).status_code, 400)


class RegressionTests(unittest.TestCase):
    def test_13_public_response_has_no_full_posterior(self):
        turn = start()
        self.assertNotIn("debug", turn)
        self.assertEqual(len(turn["diagnoses"]), 3)
        self.assertNotIn("posterior", str(turn))

    def test_14_api_matches_direct_engine_call(self):
        engine = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"), presenter=PRESENTER, max_questions=3)
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"),
                                                   "E_204": value("V_10")})
        direct = engine.start(state)
        turn = start()
        self.assertEqual([d["name"] for d in turn["diagnoses"]], [d for d, _ in direct.diagnoses.top3])
        self.assertEqual([d["probability"] for d in turn["diagnoses"]], [p for _, p in direct.diagnoses.top3])
        self.assertEqual(turn["next_question"]["question_id"], direct.next_question.evidence_id)
        self.assertEqual(turn["next_question"]["information_gain"], direct.next_question.information_gain)

        direct_after = engine.answer(direct, direct.next_question.evidence_id, PRESENTER.to_answer(
            direct.next_question.evidence_id, "V_181"))
        api_after = answer(turn).json()
        self.assertEqual([d["name"] for d in api_after["diagnoses"]], [d for d, _ in direct_after.diagnoses.top3])
        self.assertEqual(api_after["next_question"]["question_id"], direct_after.next_question.evidence_id)
        self.assertEqual(api_after["next_question"]["information_gain"], direct_after.next_question.information_gain)
        self.assertEqual(deserialize_session(api_after["session"], CATALOG).state, direct_after.state)

    def test_15_repeated_request_is_identical(self):
        self.assertEqual(start(), start())
        turn = start()
        self.assertEqual(answer(turn).json(), answer(turn).json())

    def test_16_no_fit_call_during_api_flow(self):
        model_cls = type(api_module.REGISTRY.diagnosis["k3"].model)
        original = model_cls.fit
        def explode(*args, **kwargs):
            raise AssertionError("MEDMAP_RUNTIME_FIT_FORBIDDEN")
        model_cls.fit = explode
        try:
            turn = start()
            after = answer(turn).json()
            CLIENT.post("/v1/session/resume", json={"session": after["session"]})
        finally:
            model_cls.fit = original

    def test_17_no_research_split_access_in_api_layer(self):
        source = (ROOT / "medmap" / "api.py").read_text()
        for forbidden in ["release_validate_patients", "release_test_patients", "release_conditions.json",
                          "PATHOLOGY", ".fit(", "train("]:
            self.assertNotIn(forbidden, source)
        self.assertEqual(api_module.REGISTRY.catalog.excluded, {"E_134", "E_152"})

    def test_18_model_context_is_never_auto_switched(self):
        turn = start()
        self.assertEqual(turn["model_context"], "k3")
        after = answer(turn).json()
        self.assertEqual(after["model_context"], "k3")
        resumed = CLIENT.post("/v1/session/resume", json={"session": after["session"]}).json()
        self.assertEqual(resumed["model_context"], "k3")
        self.assertEqual(resumed["model_context_match"], after["model_context_match"])   # 경로가 달라도 같은 판정
        k5 = CLIENT.post("/v1/session/start", json=dict(START_BODY, model_context="k5")).json()
        self.assertEqual(k5["model_context"], "k5")                # 다른 모델로 바꾸지 않는다
        self.assertFalse(k5["model_context_match"])


def observations(n):
    """추가 관측 n 개를 가진 start 본문(부모 gate 를 건드리지 않는 binary 질문만 사용)."""
    pool = ["E_55", "E_56", "E_204", "E_91", "E_201", "E_181", "E_0", "E_9", "E_45", "E_50", "E_66", "E_69"]
    typed = {"E_55": ["V_89"], "E_56": ["2"], "E_204": ["V_10"]}
    answers = []
    for evidence_id in pool[:n]:
        if evidence_id in typed:
            answers.append({"question_id": evidence_id, "kind": "VALUE", "value": typed[evidence_id]})
        else:
            answers.append({"question_id": evidence_id, "kind": "POSITIVE", "value": None})
    return answers


class ModelContextMatchTests(unittest.TestCase):
    """model_context_match = (추가 관측 수 == k). 질문이 늘어도 자동으로 true 가 유지되지 않는다."""

    def match_for(self, context, n):
        body = {"age": 45, "sex": "M", "model_context": context, "initial_evidence": "E_53",
                "answers": observations(n)}
        return CLIENT.post("/v1/session/start", json=body).json()

    def test_21_exact_k_is_true_and_off_by_one_is_false(self):
        for context, k in (("k3", 3), ("k5", 5), ("k10", 10)):
            with self.subTest(context=context):
                self.assertTrue(self.match_for(context, k)["model_context_match"])
                self.assertFalse(self.match_for(context, k + 1)["model_context_match"])
        self.assertFalse(self.match_for("k3", 6)["model_context_match"])

    def test_22_match_becomes_false_after_each_engine_question(self):
        turn = start()
        self.assertTrue(turn["model_context_match"])               # k3 + 3
        after = answer(turn).json()
        self.assertFalse(after["model_context_match"])             # k3 + 4
        again = CLIENT.post("/v1/session/answer", json={
            "session": after["session"],
            "submission": {"question_id": after["next_question"]["question_id"],
                           "answer": {"kind": "VALUE", "value": ["V_123"]}}}).json()
        self.assertFalse(again["model_context_match"])             # k3 + 5


class StoppingBudgetTests(unittest.TestCase):
    def test_23_questions_used_counts_only_engine_questions(self):
        turn = start()
        self.assertEqual(turn["questions_asked_in_session"], 0)
        expected = 0
        while turn["next_question"] is not None:
            question_id = turn["next_question"]["question_id"]
            choices = CATALOG.question(question_id).possible_values
            payload = {"question_id": question_id,
                       "answer": {"kind": "VALUE", "value": [choices[0]]} if choices
                                 else {"kind": "NEGATIVE", "value": None}}
            turn = CLIENT.post("/v1/session/answer",
                               json={"session": turn["session"], "submission": payload}).json()
            expected += 1
            self.assertEqual(turn["questions_asked_in_session"], expected)
        self.assertEqual(expected, 3)
        self.assertEqual(turn["stop_reason"], "MAX_QUESTIONS")

    def test_24_irregular_start_is_not_treated_as_a_normal_session(self):
        for context, n in (("k3", 4), ("k3", 1), ("k5", 3), ("k10", 3)):
            with self.subTest(context=context, n=n):
                body = {"age": 45, "sex": "M", "model_context": context, "initial_evidence": "E_53",
                        "answers": observations(n)}
                turn = CLIENT.post("/v1/session/start", json=body).json()
                self.assertFalse(turn["model_context_match"])
                self.assertIsNone(turn["questions_asked_in_session"])   # 질문 수를 추정하지 않는다
                self.assertIsNone(turn["next_question"])                # 질문도 제안하지 않는다
                self.assertEqual(turn["stop_reason"], "UNSUPPORTED_SESSION_SHAPE")
                self.assertEqual(len(turn["diagnoses"]), 3)             # 진단은 돌려준다

    def test_25_state_below_the_model_view_cannot_be_resumed_as_a_session(self):
        body = {"age": 45, "sex": "M", "model_context": "k5", "initial_evidence": "E_53",
                "answers": observations(2)}
        turn = CLIENT.post("/v1/session/start", json=body).json()
        resumed = CLIENT.post("/v1/session/resume", json={"session": turn["session"]}).json()
        self.assertEqual(resumed["stop_reason"], "UNSUPPORTED_SESSION_SHAPE")
        self.assertIsNone(resumed["questions_asked_in_session"])
        response = CLIENT.post("/v1/session/answer", json={
            "session": turn["session"],
            "submission": {"question_id": "E_201", "answer": {"kind": "POSITIVE", "value": None}}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNSUPPORTED_SESSION_SHAPE")

    def test_26_diagnosis_and_ig_are_unchanged_by_this_fix(self):
        engine = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"), presenter=PRESENTER, max_questions=3)
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"),
                                                   "E_204": value("V_10")})
        direct = engine.start(state)
        turn = start()
        self.assertEqual(turn["next_question"]["question_id"], direct.next_question.evidence_id)
        self.assertEqual(turn["next_question"]["information_gain"], direct.next_question.information_gain)
        self.assertEqual([d["probability"] for d in turn["diagnoses"]], [p for _, p in direct.diagnoses.top3])


if __name__ == "__main__":
    unittest.main()
