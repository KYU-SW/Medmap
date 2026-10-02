"""Natural Intake end-to-end(실제 엔진): extract → 확인(테스트가 사용자 역할) → exact-k3 start → IG 질문.

실행: ~/ai_env/bin/python -m unittest tests.test_natural_intake_e2e
"""
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
BOOTSTRAP = ["E_91", "E_53", "E_66", "E_201", "E_175", "E_88"]


def setUpModule():
    CLIENT.__enter__()


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def candidates(text):
    response = CLIENT.post("/v1/intake/extract", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()["candidates"]


def plan(initial, confirmed):
    """rev3: additional = initial 제외 확인 POSITIVE 발화순 앞 3개. 나머지 POSITIVE → cache.
    확인된 NEGATIVE 는 frozen bootstrap/backup 순서에 있고 walk 가 실제로 그 항목에 도달하면
    다시 묻지 않고 재사용(known 1개로 셈, cache 에서 제외)한다. 도달하기 전에 need 가 채워지거나
    frozen 목록 밖이면 그대로 cache 에 남는다. (여기서는 물어본 질문마다 known 답이 온다고 가정한다 —
    이 e2e 스위트는 UNKNOWN 분기를 다루지 않는다.)
    """
    positives = [c for c in confirmed if c["evidence_id"] != initial and c["status"] == "POSITIVE"]
    additional = positives[:3]
    used = {c["evidence_id"] for c in additional}
    negative_ids = {c["evidence_id"] for c in confirmed if c["status"] == "NEGATIVE"}
    positive_ids = {c["evidence_id"] for c in confirmed if c["status"] == "POSITIVE"}
    excluded = {initial, *positive_ids}
    sequence = [e for e in BOOTSTRAP if e not in excluded]
    need = 3 - len(additional)
    boot = []       # 실제로 물어본(ASKED) 질문
    reused = []     # 재사용된 확인 NEGATIVE
    known = 0
    for evidence_id in sequence:
        if known >= need:
            break
        if evidence_id in negative_ids:
            reused.append(evidence_id)
        else:
            boot.append(evidence_id)
        known += 1
    cached = [c for c in confirmed if c["evidence_id"] != initial and c["evidence_id"] not in used and c["evidence_id"] not in reused]
    return additional, boot, cached, reused


def start(initial, answers):
    body = {"age": 45, "sex": "M", "model_context": "k3", "initial_evidence": initial, "answers": answers}
    response = CLIENT.post("/v1/session/start", json=body)
    assert response.status_code == 200, response.text
    return response.json()


class NaturalIntakeEndToEnd(unittest.TestCase):
    def assert_ig_started(self, turn, submitted):
        self.assertIsNone(turn.get("stop_reason"))
        self.assertTrue(turn["model_context_match"])
        self.assertEqual(turn["questions_asked_in_session"], 0)
        self.assertIsNotNone(turn["next_question"])
        self.assertNotIn(turn["next_question"]["question_id"], submitted)

    def test_A_two_candidates_initial_one_bootstrap_two(self):
        found = candidates("기침이 나고 열이 나요")
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        self.assertEqual(len(confirmed), 2)
        additional, boot, cached, reused = plan("E_201", confirmed)     # 사용자가 "기침"을 가장 불편한 증상으로 선택
        self.assertEqual(reused, [])
        self.assertEqual([c["evidence_id"] for c in additional], ["E_91"])
        self.assertEqual(boot, ["E_53", "E_66"])
        self.assertEqual(cached, [])
        answers = [{"question_id": c["evidence_id"], "kind": c["status"], "value": None} for c in additional]
        answers += [{"question_id": "E_53", "kind": "NEGATIVE", "value": None},
                    {"question_id": "E_66", "kind": "POSITIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_91", "E_53", "E_66"})

    def test_B_zero_candidates_manual_initial_bootstrap_three(self):
        self.assertEqual(candidates("그냥 몸이 좀 이상해요"), [])
        additional, boot, _, reused = plan("E_201", [])                 # 검색으로 "기침" 선택
        self.assertEqual(reused, [])
        self.assertEqual(boot, ["E_91", "E_53", "E_66"])
        answers = [{"question_id": "E_91", "kind": "NEGATIVE", "value": None},     # known 답만(UNKNOWN 은 start 에 넣지 않음)
                   {"question_id": "E_53", "kind": "NEGATIVE", "value": None},
                   {"question_id": "E_66", "kind": "POSITIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_91", "E_53", "E_66"})

    def test_C_and_D_many_candidates_cache_rest_and_server_guard(self):
        found = candidates("기침이 나고 열도 있고 숨이 차요. 가래도 누렇게 나오고 식은땀도 나요. 목소리도 쉬었어요.")
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        additional, boot, cached, reused = plan("E_66", confirmed)      # "숨이 참" 선택
        self.assertEqual([c["evidence_id"] for c in additional], ["E_201", "E_91", "E_77"])
        self.assertEqual(boot, [])
        self.assertEqual(reused, [])
        self.assertEqual([c["evidence_id"] for c in cached], ["E_50", "E_212"])
        answers = [{"question_id": c["evidence_id"], "kind": c["status"], "value": None} for c in additional]
        turn = start("E_66", answers)
        self.assert_ig_started(turn, {"E_66", "E_201", "E_91", "E_77"})
        # D(서버 측): 엔진이 제안하지 않은 cached evidence 를 미리 제출하면 409 로 막힌다.
        proposed = turn["next_question"]["question_id"]
        for entry in cached:
            submission = {"question_id": entry["evidence_id"], "answer": {"kind": entry["status"], "value": None}}
            response = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": submission})
            if entry["evidence_id"] == proposed:
                self.assertEqual(response.status_code, 200, response.text)
            else:
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNEXPECTED_ANSWER")

    def test_E_negative_candidate_reused_as_bootstrap_answer(self):
        found = candidates("기침은 나는데 열은 없어요")
        eligible = [c["evidence_id"] for c in found if c["initial_eligible"]]
        self.assertEqual(eligible, ["E_201"])                   # E_91 NEGATIVE 는 initial 후보 아님
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        additional, boot, cached, reused = plan("E_201", confirmed)
        self.assertEqual(additional, [])                        # NEGATIVE 는 additional 에 넣지 않음(STEP17A 범위)
        self.assertEqual(reused, ["E_91"])                      # frozen 목록에 있고 walk 가 도달 → 재사용(rev3)
        self.assertEqual(boot, ["E_53", "E_66"])                # E_91 은 다시 묻지 않는다
        self.assertEqual(cached, [])
        answers = [{"question_id": "E_91", "kind": "NEGATIVE", "value": None},   # 재사용된 확인 NEGATIVE, start 본문에 포함
                   {"question_id": "E_53", "kind": "POSITIVE", "value": None},
                   {"question_id": "E_66", "kind": "NEGATIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_91", "E_53", "E_66"})
        # cache 가 빈 상태이므로, 이 세션에 없던 임의의 binary evidence(E_214)를 미리 제출하면
        # 엔진이 실제로 그것을 다음 질문으로 제안한 경우가 아닌 한 409 로 막힌다.
        proposed = turn["next_question"]["question_id"]
        submission = {"question_id": "E_214", "answer": {"kind": "NEGATIVE", "value": None}}
        response = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": submission})
        expected = 200 if proposed == "E_214" else 409
        self.assertEqual(response.status_code, expected, response.text)
        if expected == 409:
            self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNEXPECTED_ANSWER")


if __name__ == "__main__":
    unittest.main()
