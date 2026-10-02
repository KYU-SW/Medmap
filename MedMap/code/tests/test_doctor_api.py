"""/v1/doctor/* 회귀 테스트 (medmap-doctor-view-v1).

실행: ~/ai_env/bin/python -m unittest tests.test_doctor_api
핵심: Doctor 경로는 새 알고리즘이 아니다 — 같은 입력이면 /v1/session/answer·/resume 과 같은 session·다음 질문·stop_reason.
표시용 후보(상위 8)는 IG 선택에 관여하지 않는다(다음 질문 = 기존 경로의 다음 질문).
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
from medmap import doctor_view

CLIENT = TestClient(api_module.app)
CATALOG = EvidenceCatalog()
SKIPPED = {"state": "SKIPPED"}

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


def submission_for(question, choice_index):
    """질문 유형별 답 하나. choice_index 로 분기해 서로 다른 상태를 만든다."""
    choices = CATALOG.question(question["question_id"]).possible_values
    if choices:
        return {"question_id": question["question_id"],
                "answer": {"kind": "VALUE", "value": [choices[choice_index % len(choices)]]}}
    kind = ("NEGATIVE", "POSITIVE", "UNKNOWN")[choice_index % 3]
    return {"question_id": question["question_id"], "answer": {"kind": kind, "value": None}}


def doctor(path, body):
    return CLIENT.post(f"/v1/doctor/{path}", json=body)


class DoctorApiTest(unittest.TestCase):
    def test_diagnoses_list(self):
        body = CLIENT.get("/v1/doctor/diagnoses").json()
        self.assertEqual(body["schema_version"], "medmap-doctor-diagnoses-v1")
        codes = [d["code"] for d in body["diagnoses"]]
        self.assertEqual(len(codes), 49)
        self.assertEqual(set(codes), set(api_module.registry().diagnosis["k3"].classes))
        for item in body["diagnoses"]:
            self.assertEqual(set(item), {"code", "label_ko"})

    def test_answer_path_equals_session_answer(self):
        """3개 분기 × 3턴: /doctor/answer 의 session·다음 질문·stop 이 /session/answer 와 동일."""
        for branch in range(3):
            turn = start()
            session = turn["session"]
            view = doctor("view", {"session": session, "working_diagnosis": SKIPPED}).json()
            self.assertEqual(view["next_information"]["question"]["question_id"], turn["next_question"]["question_id"])
            for step in range(3):
                with self.subTest(branch=branch, step=step):
                    sub = submission_for(turn["next_question"], branch + step)
                    plain = CLIENT.post("/v1/session/answer", json={"session": session, "submission": sub}).json()
                    doc = doctor("answer", {"session": session, "working_diagnosis": SKIPPED, "submission": sub})
                    self.assertEqual(doc.status_code, 200, doc.text)
                    doc = doc.json()
                    self.assertEqual(doc["session"], plain["session"])
                    info = doc["next_information"]
                    if plain["next_question"] is None:
                        self.assertIsNone(info["question"])
                        self.assertEqual(plain["stop_reason"], "MAX_QUESTIONS")
                        self.assertEqual(info["status"], "BUDGET_REACHED")
                    else:
                        self.assertEqual(info["question"]["question_id"], plain["next_question"]["question_id"])
                    self.assertEqual(info["questions_used"], plain["questions_asked_in_session"])
                    self.assertEqual(info["max_questions"], 3)
                    # 표시 후보 상위 3 = 기존 경로 diagnoses(같은 posterior), 이후 최대 8까지
                    cands = [c["code"] for c in doc["independent_assessment"]["candidates"]]
                    self.assertEqual(cands[:3], [d["name"] for d in plain["diagnoses"]])
                    self.assertEqual(len(cands), doctor_view.DOCTOR_CANDIDATES_MAX)
                    turn, session = plain, plain["session"]
                    if plain["next_question"] is None:
                        break

    def test_view_equals_resume(self):
        turn = start()
        sub = submission_for(turn["next_question"], 1)
        turn = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": sub}).json()
        resumed = CLIENT.post("/v1/session/resume", json={"session": turn["session"]}).json()
        view = doctor("view", {"session": turn["session"], "working_diagnosis": SKIPPED}).json()
        self.assertEqual(view["session"], resumed["session"])
        self.assertEqual(view["next_information"]["question"]["question_id"], resumed["next_question"]["question_id"])
        self.assertEqual([c["code"] for c in view["independent_assessment"]["candidates"]][:3],
                         [d["name"] for d in resumed["diagnoses"]])

    def test_pending_is_blind_and_cannot_answer(self):
        turn = start()
        view = doctor("view", {"session": turn["session"], "working_diagnosis": {"state": "PENDING"}}).json()
        self.assertEqual(view["independent_assessment"], {"status": "LOCKED"})
        self.assertEqual(view["next_information"], {"status": "LOCKED"})
        self.assertEqual(view["patient_summary"]["age"], 45)
        sub = submission_for(turn["next_question"], 0)
        response = doctor("answer", {"session": turn["session"], "working_diagnosis": {"state": "PENDING"},
                                     "submission": sub})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MEDMAP_WORKING_DIAGNOSIS_PENDING")

    def test_no_probability_in_responses(self):
        turn = start()
        for wd in ({"state": "PENDING"}, SKIPPED,
                   {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "급성 충수염"}}):
            text = doctor("view", {"session": turn["session"], "working_diagnosis": wd}).text
            for word in ("probability", "information_gain", "posterior"):
                self.assertNotIn(word, text)

    def test_invalid_working_diagnosis(self):
        turn = start()
        for wd in ({"state": "ENTERED", "value": {"kind": "CATALOG", "code": "Not a disease"}},
                   {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": ""}}, {"state": "X"}):
            response = doctor("view", {"session": turn["session"], "working_diagnosis": wd})
            self.assertEqual(response.status_code, 400, wd)
            error = response.json()["error"]
            self.assertEqual(error["code"], "MEDMAP_INVALID_WORKING_DIAGNOSIS")
            self.assertEqual(error["field"], "working_diagnosis")

    def test_out_of_scope_label_not_in_error_or_logs(self):
        turn = start()
        secret = "비밀진단명" + "x" * 80
        with self.assertLogs("medmap", level="DEBUG") as logs:
            response = doctor("view", {"session": turn["session"], "working_diagnosis":
                                       {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": secret}}})
            api_module.LOG.info("probe")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(secret, response.text)
        self.assertNotIn("비밀진단명", "\n".join(logs.output))

    def test_accepted_out_of_scope_label_not_logged(self):
        """정상(200) 경로에서도 직접 입력 진단명은 로그에 남지 않는다(payload 로그 옵션을 켠 상태 포함)."""
        turn = start()
        label = "로그금지진단명"
        wd = {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": label}}
        original = api_module.LOG_PAYLOAD
        api_module.LOG_PAYLOAD = True
        try:
            with self.assertLogs("medmap", level="DEBUG") as logs:
                view = doctor("view", {"session": turn["session"], "working_diagnosis": wd})
                sub = submission_for(turn["next_question"], 0)
                answer = doctor("answer", {"session": turn["session"], "working_diagnosis": wd, "submission": sub})
        finally:
            api_module.LOG_PAYLOAD = original
        self.assertEqual((view.status_code, answer.status_code), (200, 200))
        self.assertEqual(view.json()["working_diagnosis"]["value"]["label"], label)     # 응답 에코는 한다
        self.assertNotIn(label, "\n".join(logs.output))

    def test_session_errors_reuse_existing_codes(self):
        turn = start()
        broken = copy.deepcopy(turn["session"])
        broken["schema_version"] = "medmap-session-v0"
        a = CLIENT.post("/v1/session/resume", json={"session": broken})
        b = doctor("view", {"session": broken, "working_diagnosis": SKIPPED})
        self.assertEqual(b.status_code, a.status_code)
        self.assertEqual(b.json()["error"]["code"], a.json()["error"]["code"])
        # 제안되지 않은 질문 답 → 기존 409 규칙 그대로
        wrong = {"question_id": "E_91", "answer": {"kind": "NEGATIVE", "value": None}}
        if turn["next_question"]["question_id"] != "E_91":
            a = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": wrong})
            b = doctor("answer", {"session": turn["session"], "working_diagnosis": SKIPPED, "submission": wrong})
            self.assertEqual((b.status_code, b.json()["error"]["code"]), (a.status_code, a.json()["error"]["code"]))

    def test_extra_fields_rejected(self):
        turn = start()
        response = doctor("view", {"session": turn["session"], "working_diagnosis": SKIPPED, "name": "홍길동"})
        self.assertEqual(response.status_code, 422)

    def test_existing_endpoints_keys_unchanged(self):
        turn = start()
        self.assertEqual(set(turn), {"schema_version", "diagnoses", "diagnoses_before", "next_question", "stop_reason",
                                     "n_asked", "questions_asked_in_session", "model_context", "model_context_match",
                                     "session", "max_questions"})
        summary = CLIENT.post("/v1/session/summary", json={"session": turn["session"]}).json()
        self.assertIn("diagnosis_candidates", summary)
        self.assertEqual(CLIENT.get("/health").json()["max_questions"], 3)


if __name__ == "__main__":
    unittest.main()
