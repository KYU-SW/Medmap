"""/v1/intake/extract 계약 — 후보만 반환, 원문 저장·로그 금지, 기존 session API 무관.

실행: ~/ai_env/bin/python -m unittest tests.test_intake_api
"""
import logging
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import api as api_module

CLIENT = TestClient(api_module.app)
KEYS = {"evidence_id", "status", "label_ko", "matched_text", "initial_eligible"}


def setUpModule():
    CLIENT.__enter__()


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def extract(text):
    return CLIENT.post("/v1/intake/extract", json={"text": text})


class IntakeExtractTests(unittest.TestCase):
    def test_01_two_positive_candidates(self):
        response = extract("기침이 나고 열이 나요")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"candidates", "mapper_version"})
        self.assertEqual(body["mapper_version"], "v1.2")
        got = [(c["evidence_id"], c["status"], c["matched_text"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", "기침", True), ("E_91", "POSITIVE", "열", True)])
        self.assertEqual(body["candidates"][0]["label_ko"], "기침이 있나요?")
        for c in body["candidates"]:
            self.assertEqual(set(c), KEYS)          # confidence·alias_id·source 비노출

    def test_02_zero_candidates_is_normal(self):
        response = extract("그냥 몸이 좀 이상해요")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"], [])

    def test_03_negative_is_never_initial_eligible(self):
        body = extract("기침은 나는데 열은 없어요").json()
        got = [(c["evidence_id"], c["status"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", True), ("E_91", "NEGATIVE", False)])

    def test_04_past_history_positive_is_not_initial_eligible(self):
        body = extract("기침이 나고 당뇨가 있어요").json()
        got = [(c["evidence_id"], c["status"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", True), ("E_69", "POSITIVE", False)])

    def test_05_mention_order_preserved_for_many(self):
        body = extract("기침이 나고 열도 있고 숨이 차요. 가래도 누렇게 나오고 식은땀도 나요. 목소리도 쉬었어요.").json()
        self.assertEqual([c["evidence_id"] for c in body["candidates"]],
                         ["E_201", "E_91", "E_66", "E_77", "E_50", "E_212"])

    def test_06_validation_errors_do_not_echo_text(self):
        secret = "비밀문장가나다" * 150             # 1,050자 > 1,000
        response = extract(secret)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")
        self.assertNotIn("비밀문장", response.text)
        self.assertEqual(extract("").status_code, 422)
        extra = CLIENT.post("/v1/intake/extract", json={"text": "기침", "session": {}})
        self.assertEqual(extra.status_code, 422)

    def test_07_text_is_never_logged_even_with_payload_logging(self):
        marker = "로그금지표식문장 기침이 나요"
        previous = api_module.LOG_PAYLOAD
        api_module.LOG_PAYLOAD = True
        try:
            with self.assertLogs("medmap", level=logging.DEBUG) as captured:
                self.assertEqual(extract(marker).status_code, 200)
        finally:
            api_module.LOG_PAYLOAD = previous
        joined = "\n".join(record.getMessage() for record in captured.records)
        self.assertNotIn("로그금지표식", joined)
        self.assertNotIn("기침이 나요", joined)

    def test_08_response_has_no_session(self):
        body = extract("기침이 나요").json()
        self.assertNotIn("session", body)
        self.assertNotIn("text", body)


if __name__ == "__main__":
    unittest.main()
