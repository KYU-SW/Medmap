"""EXP-01 분할 규칙 단위 테스트 — 가상 행만 사용(실데이터 미접근).
실행: ~/ai_env/bin/python -m unittest discover -s exp/main_ai/exp01_symptom_graph/tests -v (worktree 루트)
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import split_rules as sr  # noqa: E402


def fake_rows(n=4000):
    for i in range(n):
        yield (i, 20 + i % 60, "M" if i % 2 else "F", f"D{i % 7}", f"['E_{i % 37}', 'E_{i % 11}']")


class TestSplit(unittest.TestCase):
    def setUp(self):
        self.rows = list(fake_rows())
        self.asg = sr.assign(self.rows)
        self.prof = {r[0]: (r[1], r[2], r[4]) for r in self.rows}

    def test_reuses_step16b_rule_exactly(self):
        c = sr.s16b_core()
        for ri, a, s, p, e in self.rows[:500]:
            k = hashlib.sha256(f"{ri}|{a}|{s}|{p}|{e}".encode()).hexdigest()
            self.assertEqual(c.split_key(ri, a, s, p, e), k)
            self.assertEqual(self.asg[ri] != "TRAIN16", int(k[:8], 16) % 10 < 2)

    def test_disjoint_covering_and_fractions(self):
        rep = sr.verify(self.asg, self.prof)
        n = len(self.rows)
        self.assertEqual(rep["train_rows"] + rep["select_rows"] + rep["final_rows"], n)
        self.assertAlmostEqual((rep["select_rows"] + rep["final_rows"]) / n, 0.2, delta=0.03)
        self.assertAlmostEqual(rep["select_rows"] / (rep["select_rows"] + rep["final_rows"]), 0.5, delta=0.08)

    def test_unassigned_row_detected(self):
        bad = dict(self.asg)
        bad[0] = "UNKNOWN_SPLIT"                               # 어느 집합에도 안 들어간 행
        with self.assertRaises(sr.SplitInvalid):
            sr.verify(bad, self.prof)

    def test_step16b_expected_match_passes(self):
        rep = sr.verify(self.asg, self.prof)
        exp = {"source_rows": len(self.rows), "train_rows": rep["train_rows"],
               "holdout_rows": rep["select_rows"] + rep["final_rows"],
               "holdout_row_index_sha256": rep["holdout_row_index_sha256"]}
        self.assertEqual(sr.verify(self.asg, self.prof, expected=exp)["train_rows"], rep["train_rows"])

    def test_expected_mismatch_raises(self):
        exp = {"source_rows": len(self.rows), "train_rows": -1, "holdout_rows": 0, "holdout_row_index_sha256": "x"}
        with self.assertRaises(sr.SplitInvalid):
            sr.verify(self.asg, self.prof, expected=exp)

    def test_profile_overlap_reported(self):
        prof = {k: (0, "M", "same") for k in self.prof}      # 모든 프로필 동일 → 중복률 1
        rep = sr.verify(self.asg, prof)
        self.assertEqual(rep["final_profile_in_train16_rate"], 1.0)
        self.assertEqual(rep["final_novel_rows"], 0)

    def test_smoke_subset_deterministic_and_from_select(self):
        se = [k for k, v in self.asg.items() if v == "SELECT"]
        s1, s2 = sr.smoke_subset(se, 100), sr.smoke_subset(list(reversed(se)), 100)
        self.assertEqual(s1, s2)
        self.assertTrue(set(s1) <= set(se))

    def test_final_guard_once_and_after_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            g = sr.FinalGuard(f"{d}/lock.json", f"{d}/final_used")
            with self.assertRaises(sr.SplitInvalid):
                g.acquire("abc")                               # 잠금 전 거부
            Path(f"{d}/lock.json").write_text('{"config_sha256": "abc"}')
            with self.assertRaises(sr.SplitInvalid):
                g.acquire("zzz")                               # config 불일치 거부
            g.acquire("abc")
            with self.assertRaises(sr.SplitInvalid):
                g.acquire("abc")                               # 2회째 거부

    def test_final_guard_environmental_retry_rules(self):
        with tempfile.TemporaryDirectory() as d:
            Path(f"{d}/lock.json").write_text('{"config_sha256": "abc"}')
            g = sr.FinalGuard(f"{d}/lock.json", f"{d}/final_used")
            g.acquire("abc")
            with self.assertRaises(sr.SplitInvalid):
                g.acquire("abc", retry_environmental=True, metrics_written=True)   # 지표 쓴 뒤 재시도 거부
            g.acquire("abc", retry_environmental=True, metrics_written=False)      # 환경 실패 재시도 1회 허용
            with self.assertRaises(sr.SplitInvalid):
                g.acquire("abc", retry_environmental=True, metrics_written=False)  # 두 번째 재시도 거부


if __name__ == "__main__":
    unittest.main()
