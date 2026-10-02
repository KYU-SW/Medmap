"""POST /v1/session/summary 회귀 테스트 (medmap-clinical-summary-v1).

실행: ~/ai_env/bin/python -m unittest tests.test_summary_api
API 는 medmap/clinical_summary.py 를 감싸기만 한다: 로직을 복제하지 않고, 세션 검증/진단 재계산은
기존 공식 경로(/session/resume 과 같은 _restore + _run)를 그대로 쓴다.
"""
import copy
import json
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import EvidenceCatalog
from medmap import api as api_module
from medmap.clinical_summary import SUMMARY_KEYS

CLIENT = TestClient(api_module.app)
CATALOG = EvidenceCatalog()

START_BODY = {"age": 45, "sex": "M", "model_context": "k3", "initial_evidence": "E_53",
              "answers": [{"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
                          {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
                          {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}]}


def setUpModule():
    CLIENT.__enter__()          # lifespan 실행(모델 1회 로딩)


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def start(body=None):
    response = CLIENT.post("/v1/session/start", json=body or START_BODY)
    assert response.status_code == 200, response.text
    return response.json()


def answer_step(turn):
    """test_api.py test_05 와 같은 규칙: YES_NO(possible_values 없음) → NEGATIVE, 그 외 → 첫 선택지."""
    question_id = turn["next_question"]["question_id"]
    choice = CATALOG.question(question_id).possible_values
    payload = {"question_id": question_id,
               "answer": {"kind": "VALUE", "value": [choice[0]]} if choice else
                         {"kind": "NEGATIVE", "value": None}}
    response = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": payload})
    assert response.status_code == 200, response.text
    return response.json()


def run_to_completion(body=None):
    """next_question 이 null 이 될 때까지 진행한 최종 turn(=/session/answer 응답)을 반환한다."""
    turn = start(body)
    while turn["next_question"] is not None:
        turn = answer_step(turn)
    return turn


def summary(session):
    return CLIENT.post("/v1/session/summary", json={"session": session})


class SummaryEndpointTests(unittest.TestCase):
    def test_01_valid_session_returns_summary_schema(self):
        turn = run_to_completion()
        response = summary(turn["session"])
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(tuple(body.keys()), SUMMARY_KEYS)
        self.assertEqual(body["schema_version"], "medmap-clinical-summary-v1")

    def test_02_repeated_call_is_identical(self):
        turn = run_to_completion()
        first = summary(turn["session"]).json()
        second = summary(turn["session"]).json()
        self.assertEqual(first, second)

    def test_03_malformed_session_field_missing(self):
        response = CLIENT.post("/v1/session/summary", json={})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_03b_malformed_session_field_is_string(self):
        response = CLIENT.post("/v1/session/summary", json={"session": "not-a-dict"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_04_invalid_session_matches_resume_error_contract(self):
        session = start()["session"]
        session["schema_version"] = "medmap-session-v2"
        resume_response = CLIENT.post("/v1/session/resume", json={"session": session})
        summary_response = summary(session)
        self.assertEqual(resume_response.status_code, 400)
        self.assertEqual(resume_response.json()["error"]["code"], "MEDMAP_UNSUPPORTED_SCHEMA_VERSION")
        self.assertEqual(summary_response.status_code, resume_response.status_code)
        self.assertEqual(summary_response.json()["error"]["code"], resume_response.json()["error"]["code"])

    def test_05_no_transcript_or_matched_text_leak(self):
        turn = run_to_completion()
        body_text = json.dumps(summary(turn["session"]).json(), ensure_ascii=False)
        for forbidden in ("transcript", "matched_text"):
            self.assertNotIn(forbidden, body_text)

    def test_06_unpersisted_intake_negative_not_in_summary(self):
        """세션에 한 번도 들어가지 않은 evidence(intake cache 전용이라 가정)는 summary 어디에도 없다."""
        turn = run_to_completion()
        asked_ids = {item["question_id"] for item in summary(turn["session"]).json()["answered_questions"]}
        unpersisted = next(eid for eid in CATALOG.ids if eid not in asked_ids)
        body_text = json.dumps(summary(turn["session"]).json(), ensure_ascii=False)
        self.assertNotIn(unpersisted, body_text)

    def test_07_unknown_not_guessed_when_absent_from_session(self):
        turn = run_to_completion()          # START_BODY 는 UNKNOWN 답을 만들지 않음
        body = summary(turn["session"]).json()
        has_unknown_answer = any(a["status"] == "UNKNOWN" for a in body["answered_questions"])
        if not has_unknown_answer:
            self.assertEqual(body["unknown"], [])

    def test_08_diagnosis_candidates_match_resume_top3(self):
        turn = run_to_completion()
        resumed = CLIENT.post("/v1/session/resume", json={"session": turn["session"]}).json()
        body = summary(turn["session"]).json()
        expected = [{"name": d["name"], "probability": d["probability"]} for d in resumed["diagnoses"][:3]]
        actual = [{"name": c["name"], "probability": c["probability"]} for c in body["diagnosis_candidates"]]
        self.assertEqual(actual, expected)

    def test_09_session_unchanged_before_and_after(self):
        turn = run_to_completion()
        before = copy.deepcopy(turn["session"])
        summary(turn["session"])
        self.assertEqual(turn["session"], before)


class ExistingRegressionTests(unittest.TestCase):
    """기존 6 endpoint 는 이 변경으로 영향받지 않는다(요약 파일은 추가만)."""

    def test_10_start_answer_resume_still_work(self):
        turn = start()
        self.assertEqual(turn["schema_version"], "medmap-turn-v1")
        after = answer_step(turn)
        self.assertEqual(after["questions_asked_in_session"], 1)
        resumed = CLIENT.post("/v1/session/resume", json={"session": after["session"]}).json()
        self.assertEqual(resumed["diagnoses"], after["diagnoses"])



class SummaryKoreanTerminologyTests(unittest.TestCase):
    """C: 요약 응답의 질환 표시명·질문 문구가 한국어 정본에서 온다(응답 형태·키는 그대로, 내부 name 은 영문 ID 유지)."""

    def test_40_summary_display_names_and_questions_are_korean(self):
        from medmap.terminology import Terminology
        terms = Terminology()
        body = summary(run_to_completion()["session"]).json()
        self.assertEqual(tuple(body.keys()), SUMMARY_KEYS)
        for candidate in body["diagnosis_candidates"]:
            self.assertFalse(candidate["is_fallback"], candidate)
            self.assertEqual(candidate["display_name"], terms.disease(candidate["name"]).label)
            self.assertNotEqual(candidate["display_name"], candidate["name"])       # name 은 내부 ID 그대로
        for item in body["answered_questions"]:
            self.assertRegex(item["question_ko"], r"[가-힣]", item)


if __name__ == "__main__":
    unittest.main()
