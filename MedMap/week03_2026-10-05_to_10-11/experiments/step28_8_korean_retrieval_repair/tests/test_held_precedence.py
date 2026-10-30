"""보류 우선(P4·P5): 보류 행 표현은 기존 자동 연결보다 우선해 UNCERTAIN, 부정 구문은 같은 차단 대신 확인 경로, 다른 구문은 영향 없음."""
import unittest

import _engine


class TestHeld(unittest.TestCase):
    def test_held_blocks_auto(self):
        for t in ("무기력", "묽은변"):
            for p in ("P4", "P5"):
                rs = _engine.run(t, p)
                with self.subTest(t=t, p=p):
                    self.assertTrue(all(o["status"] not in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") for o in rs))
                    self.assertTrue(any(o["reason"] == "AMBIGUOUS_CONCEPT_RELATION" and o["canonical_id"] is None for o in rs))
                    self.assertTrue(all(o["raw_preserved"] and o["source_text"] == t for o in rs))

    def test_negated_not_blanket_blocked(self):
        rs = _engine.run("무기력하지 않아요", "P5")
        self.assertFalse(any(o["reason"] == "AMBIGUOUS_CONCEPT_RELATION" for o in rs))

    def test_other_span_unaffected(self):
        self.assertIn("pain", _engine.autos("머리가 아파요", "P5"))

    def test_all_held_rows_not_auto(self):
        E = _engine.engine()
        bad = []
        for r in E.clean.rows:
            if r["mapping_decision"] in ("HOLD_CONCEPT_UNCERTAIN", "HOLD_AUDIT_NOT_EXACT") and _engine.autos(r["korean_expression"], "P5"):
                bad.append(r["korean_expression"])
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
