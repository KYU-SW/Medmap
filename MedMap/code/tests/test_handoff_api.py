"""/v1/handoff/* (Phase A S1 기기 간 인계, 메모리 전용) 회귀 — spec 2026-10-01 rev2 §0-A.

실행: ~/ai_env/bin/python -m unittest tests.test_handoff_api
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
from medmap import api_handoff
from medmap.handoff_codes import HandoffStore

CLIENT = TestClient(api_module.app)
START_BODY = {"age": 45, "sex": "M", "model_context": "k3", "initial_evidence": "E_53",
              "answers": [{"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
                          {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
                          {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}]}


def setUpModule():
    CLIENT.__enter__()


def tearDownModule():
    CLIENT.__exit__(None, None, None)


class HandoffApiTest(unittest.TestCase):
    def setUp(self):
        api_handoff.ENABLED = True
        api_handoff.set_store_for_tests(HandoffStore())
        self.session = CLIENT.post("/v1/session/start", json=START_BODY).json()["session"]

    def tearDown(self):
        api_handoff.ENABLED = False
        api_handoff.set_store_for_tests(None)

    def create(self, **body):
        return CLIENT.post("/v1/handoff/codes", json={"session": self.session, "cache": [], **body})

    def test_status_reports_enabled_and_ttl(self):
        self.assertEqual(CLIENT.get("/v1/handoff/status").json(), {"enabled": True, "ttl_s": 900})

    def test_create_then_claim_once_and_doctor_view_opens(self):
        created = self.create(cache=[{"evidence_id": "E_91", "status": "NEGATIVE"}])
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertRegex(body["code"], r"^\d{8}$")
        self.assertEqual(body["expires_in_s"], 900)
        claimed = CLIENT.post("/v1/handoff/claim", json={"code": body["code"]})
        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(claimed.json(), {"session": self.session, "cache": [{"evidence_id": "E_91", "status": "NEGATIVE"}]})
        again = CLIENT.post("/v1/handoff/claim", json={"code": body["code"]})
        self.assertEqual((again.status_code, again.json()["error"]["code"]), (404, "HANDOFF_CODE_INVALID"))
        view = CLIENT.post("/v1/doctor/view", json={"session": claimed.json()["session"], "working_diagnosis": {"state": "PENDING"}})
        self.assertEqual(view.status_code, 200)                          # 받은 세션이 기존 Doctor 경로로 그대로 열린다

    def test_hyphen_and_spaces_in_code_are_accepted(self):
        code = self.create().json()["code"]
        claimed = CLIENT.post("/v1/handoff/claim", json={"code": f" {code[:4]}-{code[4:]} "})
        self.assertEqual(claimed.status_code, 200)

    def test_cache_is_sanitized_server_side(self):
        dirty = [{"evidence_id": "E_91", "status": "NEGATIVE", "matched_text": "열은 없어요"},
                 {"evidence_id": "E_91", "status": "POSITIVE"}, {"evidence_id": "X_1", "status": "POSITIVE"},
                 {"evidence_id": "E_53", "status": "VALUE"}]
        code = self.create(cache=dirty).json()["code"]
        self.assertEqual(CLIENT.post("/v1/handoff/claim", json={"code": code}).json()["cache"],
                         [{"evidence_id": "E_91", "status": "NEGATIVE"}])

    def test_invalid_session_rejected_and_nothing_stored(self):
        bad = CLIENT.post("/v1/handoff/codes", json={"session": {"schema_version": "nope"}, "cache": []})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(api_handoff.store().pending(), 0)

    def test_unknown_fields_and_oversized_body_rejected(self):
        self.assertEqual(self.create(text="원문").status_code, 422)          # 원문 필드 없음(extra forbid)
        big = [{"evidence_id": f"E_{i}", "status": "POSITIVE"} for i in range(500)]
        self.assertEqual(self.create(cache=big).status_code, 422)

    def test_wrong_code_same_response_and_lockout_429(self):
        responses = {CLIENT.post("/v1/handoff/claim", json={"code": c}).text for c in ("00000000", "12", "abcdefgh")}
        self.assertEqual(len(responses), 1)
        for _ in range(20):
            CLIENT.post("/v1/handoff/claim", json={"code": "00000001"})
        locked = CLIENT.post("/v1/handoff/claim", json={"code": self.create().json()["code"]})
        self.assertEqual((locked.status_code, locked.json()["error"]["code"]), (429, "HANDOFF_LOCKED"))

    def test_one_device_lockout_does_not_block_other_devices(self):
        attacker = TestClient(api_module.app, client=("10.0.0.9", 50000))
        doctor = TestClient(api_module.app, client=("10.0.0.2", 50000))
        for _ in range(30):
            attacker.post("/v1/handoff/claim", json={"code": "00000001"})
        code = self.create().json()["code"]
        locked = attacker.post("/v1/handoff/claim", json={"code": code})
        self.assertEqual((locked.status_code, locked.json()["error"]["code"]), (429, "HANDOFF_LOCKED"))
        self.assertEqual(doctor.post("/v1/handoff/claim", json={"code": code}).status_code, 200)

    def test_global_lockout_across_devices(self):
        for i in range(4):
            device = TestClient(api_module.app, client=(f"10.0.1.{i}", 50000))
            for _ in range(5):
                device.post("/v1/handoff/claim", json={"code": "00000001"})
        doctor = TestClient(api_module.app, client=("10.0.0.2", 50000))
        self.assertEqual(doctor.post("/v1/handoff/claim", json={"code": self.create().json()["code"]}).status_code, 429)

    def test_oversized_session_rejected_before_retention(self):
        big = dict(self.session)
        big["padding"] = "x" * (api_handoff.SESSION_MAX_BYTES + 1)             # 메모리에 15분 보관되므로 크기 상한
        r = CLIENT.post("/v1/handoff/codes", json={"session": big, "cache": []})
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (413, "HANDOFF_TOO_LARGE"))
        self.assertEqual(api_handoff.store().pending(), 0)

    def test_store_singleton_is_created_once_under_concurrency(self):
        import threading
        import time as _time
        api_handoff.set_store_for_tests(None)
        original = api_handoff.HandoffStore

        class SlowStore(original):                                         # 생성 구간을 넓혀 경합을 실제로 만든다
            def __init__(self, *a, **k):
                _time.sleep(0.05)
                super().__init__(*a, **k)
        api_handoff.HandoffStore = SlowStore
        self.addCleanup(setattr, api_handoff, "HandoffStore", original)
        seen, barrier = [], threading.Barrier(16)

        def grab():
            barrier.wait()
            seen.append(id(api_handoff.store()))
        threads = [threading.Thread(target=grab) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(seen)), 1)

    def test_capacity_503(self):
        api_handoff.set_store_for_tests(HandoffStore(capacity=1))
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual((self.create().status_code, self.create().json()["error"]["code"]), (503, "HANDOFF_CAPACITY"))

    def test_code_and_session_never_logged(self):
        with self.assertLogs(level="DEBUG") as logs:
            code = self.create(cache=[{"evidence_id": "E_91", "status": "NEGATIVE"}]).json()["code"]
            CLIENT.post("/v1/handoff/claim", json={"code": code})
            CLIENT.post("/v1/handoff/claim", json={"code": "99999999"})
            logging.getLogger("medmap.handoff").info("probe")
        joined = "\n".join(logs.output)
        self.assertNotIn(code, joined)
        self.assertNotIn("99999999", joined)
        self.assertNotIn("E_91", joined)
        self.assertNotIn("V_89", joined)


class HandoffFlagOffTest(unittest.TestCase):
    def test_disabled_by_default_404(self):
        api_handoff.ENABLED = False
        self.assertEqual(CLIENT.get("/v1/handoff/status").json(), {"enabled": False, "ttl_s": 900})
        self.assertEqual(CLIENT.post("/v1/handoff/codes", json={"session": {}, "cache": []}).status_code, 404)
        self.assertEqual(CLIENT.post("/v1/handoff/claim", json={"code": "00000000"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
