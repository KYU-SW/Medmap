"""기기 간 인계 코드 저장소(메모리 전용, Phase A S1 — spec 2026-10-01 rev2 §0-A).

실행: ~/ai_env/bin/python -m unittest tests.test_handoff_codes
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.handoff_codes import HandoffCapacity, HandoffInvalid, HandoffLocked, HandoffStore

PAYLOAD = {"session": {"schema_version": "medmap-session-v1"}, "cache": [{"evidence_id": "E_53", "status": "POSITIVE"}]}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def store(**kw):
    clock = Clock()
    return HandoffStore(clock=clock, **kw), clock


class HandoffStoreTest(unittest.TestCase):
    def test_code_is_8_digits_and_claim_returns_payload_once(self):
        s, _ = store()
        code = s.create(PAYLOAD)
        self.assertRegex(code, r"^\d{8}$")
        self.assertEqual(s.claim(code), PAYLOAD)
        with self.assertRaises(HandoffInvalid):
            s.claim(code)                                     # 1회용: 열면 삭제
        self.assertEqual(s.pending(), 0)

    def test_expires_after_15_minutes(self):
        s, clock = store()
        code = s.create(PAYLOAD)
        clock.t += 15 * 60 + 1
        with self.assertRaises(HandoffInvalid):
            s.claim(code)
        self.assertEqual(s.pending(), 0)                      # 만료 항목은 정리

    def test_still_valid_just_before_expiry(self):
        s, clock = store()
        code = s.create(PAYLOAD)
        clock.t += 15 * 60 - 1
        self.assertEqual(s.claim(code), PAYLOAD)

    def test_wrong_expired_and_used_codes_are_indistinguishable(self):
        s, clock = store()
        used = s.create(PAYLOAD)
        s.claim(used)
        expired = s.create(PAYLOAD)
        clock.t += 901
        errors = []
        for code in (used, expired, "00000000", "abc"):
            with self.assertRaises(HandoffInvalid) as ctx:
                s.claim(code)
            errors.append(str(ctx.exception))
        self.assertEqual(len(set(errors)), 1)

    def test_capacity_limit(self):
        s, _ = store(capacity=3)
        for _ in range(3):
            s.create(PAYLOAD)
        with self.assertRaises(HandoffCapacity):
            s.create(PAYLOAD)

    def test_codes_unique_among_pending(self):
        s, _ = store(capacity=500)
        codes = {s.create(PAYLOAD) for _ in range(500)}
        self.assertEqual(len(codes), 500)

    def test_global_lockout_after_20_failures_then_unlocks_after_5_minutes(self):
        s, clock = store()
        good = s.create(PAYLOAD)
        for _ in range(20):
            with self.assertRaises(HandoffInvalid):
                s.claim("12345678" if good != "12345678" else "87654321")
        with self.assertRaises(HandoffLocked):
            s.claim(good)                                     # 잠금 중에는 맞는 번호도 거부(추측 차단)
        clock.t += 5 * 60 + 1
        self.assertEqual(s.claim(good), PAYLOAD)

    def test_failures_outside_window_do_not_accumulate(self):
        s, clock = store()
        good = s.create(PAYLOAD)
        for _ in range(19):
            with self.assertRaises(HandoffInvalid):
                s.claim("00000000" if good != "00000000" else "11111111")
        clock.t += 5 * 60 + 1                                  # 실패 창(5분) 밖으로
        for _ in range(19):
            with self.assertRaises(HandoffInvalid):
                s.claim("00000000" if good != "00000000" else "11111111")
        self.assertEqual(s.claim(good), PAYLOAD)

    # ---- 기기별 잠금(서비스 방해 완화): 전체 잠금(20회)은 그대로 두고, 한 기기는 5회에서 먼저 잠근다 ----
    def _fail(self, s, client, n, good):
        bad = "12345678" if good != "12345678" else "87654321"
        for _ in range(n):
            with self.assertRaises((HandoffInvalid, HandoffLocked)):
                s.claim(bad, client=client)

    def test_one_client_locked_after_5_failures_others_still_claim(self):
        s, _ = store()
        good = s.create(PAYLOAD)
        self._fail(s, "10.0.0.9", 5, good)
        with self.assertRaises(HandoffLocked):
            s.claim(good, client="10.0.0.9")                  # 그 기기는 맞는 번호도 거부
        self.assertEqual(s.claim(good, client="10.0.0.2"), PAYLOAD)   # 다른 기기(진료실 PC)는 정상

    def test_locked_client_attempts_do_not_feed_global_lockout(self):
        s, _ = store()
        good = s.create(PAYLOAD)
        self._fail(s, "10.0.0.9", 500, good)                  # 한 기기가 계속 두드려도
        self.assertEqual(s.claim(good, client="10.0.0.2"), PAYLOAD)   # 전체 잠금으로 번지지 않는다

    def test_global_lockout_still_applies_across_clients(self):
        s, _ = store()
        good = s.create(PAYLOAD)
        for i in range(4):                                    # 4기기 × 5회 = 20 → 전체 잠금(추측 방어 그대로)
            self._fail(s, f"10.0.1.{i}", 5, good)
        with self.assertRaises(HandoffLocked):
            s.claim(good, client="10.0.0.2")

    def test_each_failure_counted_exactly_once_toward_global(self):
        s, _ = store()
        good = s.create(PAYLOAD)
        for i in range(3):
            self._fail(s, f"10.0.1.{i}", 5, good)
        self._fail(s, "10.0.1.9", 4, good)                    # 전체 19회 → 아직 잠기지 않음
        other = s.create(PAYLOAD)
        self.assertEqual(s.claim(other, client="10.0.0.2"), PAYLOAD)
        self._fail(s, "10.0.1.10", 1, good)                   # 20회째 → 전체 잠금
        with self.assertRaises(HandoffLocked):
            s.claim(good, client="10.0.0.2")

    def test_client_lock_expires_after_5_minutes(self):
        s, clock = store()
        good = s.create(PAYLOAD)
        self._fail(s, "10.0.0.9", 5, good)
        clock.t += 5 * 60 + 1
        self.assertEqual(s.claim(good, client="10.0.0.9"), PAYLOAD)

    def test_client_table_is_purged(self):
        s, clock = store()
        good = s.create(PAYLOAD)
        for i in range(3):
            self._fail(s, f"10.0.2.{i}", 1, good)
        clock.t += 10 * 60 + 1
        self.assertEqual(s.tracked_clients(), 0)              # 메모리에 기기 기록이 쌓이지 않는다

    def test_payload_is_copied_not_shared(self):
        s, _ = store()
        payload = {"session": {"a": 1}, "cache": []}
        code = s.create(payload)
        payload["session"]["a"] = 2
        self.assertEqual(s.claim(code)["session"]["a"], 1)


if __name__ == "__main__":
    unittest.main()
