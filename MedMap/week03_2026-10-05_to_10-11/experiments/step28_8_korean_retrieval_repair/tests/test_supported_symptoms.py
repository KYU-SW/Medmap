"""지원 증상 짧은 표현(지시문 §6) — 잘못된 canonical 자동 연결 금지(필수) + 기대 canonical 연결 여부(기록)."""
import json
import unittest
from pathlib import Path

import _engine
from evaluate_policies import SUPPORTED12

OUT = Path(__file__).resolve().parents[1] / "outputs/supported12_detail.json"


class TestSupported(unittest.TestCase):
    def test_no_wrong_auto(self):
        detail = {}
        for t, g in SUPPORTED12:
            a = _engine.autos(t, "P5")
            detail[t] = {"expected": g, "auto": a, "hit": g in a}
            with self.subTest(t=t, auto=a):
                self.assertTrue(not a or g in a)
        OUT.write_text(json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")

    def test_headache_is_pain_composite(self):
        rs = _engine.run("두통", "P5")
        self.assertTrue(any(o["status"] == "EXISTING_COMPOSITE" and o["canonical_id"] == "pain" for o in rs))


if __name__ == "__main__":
    unittest.main()
