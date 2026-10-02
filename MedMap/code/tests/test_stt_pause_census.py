"""쉼 전수 기록 분석 스크립트(scripts/stt_pause_census.py) — 로그 파싱·등급별 집계.

실행: ~/ai_env/bin/python -m unittest tests.test_stt_pause_census
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stt_pause_census as census

L = "INFO medmap.stt_stream stt_stream sid=ab event=pause dur_ms={d} resumed={r} censored={c} silence_ms=1500 " \
    "cls_partial={cp}/x cls_cand={cc} stable=1 cand_ready_ms=210.0"


class PauseCensusParseTest(unittest.TestCase):
    def test_groups_by_candidate_class_and_counts_resumes(self):
        rows = census.parse([L.format(d=320, r=1, c=0, cp="continuing", cc="continuing"),
                             L.format(d=900, r=1, c=0, cp="incomplete", cc="incomplete"),
                             L.format(d=1500, r=0, c=1, cp="complete", cc="complete"),
                             L.format(d=200, r=1, c=0, cp="complete", cc="none"),
                             "unrelated line"])
        self.assertEqual(len(rows), 4)
        out = census.table(rows)
        complete = [line for line in out.splitlines() if line.startswith("complete")][0].split("\t")
        self.assertEqual(complete[1:4], ["2", "1", "1"])              # 후보 없으면 partial 등급으로
        incomplete = [line for line in out.splitlines() if line.startswith("incomplete")][0].split("\t")
        self.assertEqual(incomplete[8], "1/1")                         # 900 ms 쉬고 다시 말함 → ≥300 에서 재개 1

    def test_micro_gaps_below_min_are_excluded_but_counted(self):
        rows = census.parse([L.format(d=32, r=1, c=0, cp="incomplete", cc="none"),
                             L.format(d=400, r=1, c=0, cp="continuing", cc="continuing")])
        out = census.table(rows, min_ms=96)
        self.assertIn("excluded_below_96ms=1", out)
        self.assertFalse(any(line.startswith("incomplete") for line in out.splitlines()))


if __name__ == "__main__":
    unittest.main()
