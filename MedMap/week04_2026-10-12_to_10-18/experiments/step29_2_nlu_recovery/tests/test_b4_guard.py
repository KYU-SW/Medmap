import unittest

from _v3 import find


class T(unittest.TestCase):
    def test_b1_blocks_model_only(self):
        self.assertEqual(find("몸이 펄펄 끓어요", "몸", "V3_B1")["status"], "UNCERTAIN")

    def test_b2_allows_symptom_evidence(self):
        self.assertEqual(find("몸이 펄펄 끓어요", "몸", "V3_B2")["canonical_id"], "fever")

    def test_b3_holds_conflict(self):
        m = find("정신이 아찔해요", "정신", "V3_B3")
        self.assertEqual(m["status"], "UNCERTAIN")
        self.assertEqual(m["guard_blocked_concept"], "confusion")
        self.assertIn("B4_SEMANTIC_CONFLICT", m["guard_reasons"])

    def test_blocked_keeps_raw_and_reason(self):
        m = find("정신이 아찔해요", "정신", "V3_B3")
        self.assertTrue(m["raw_span"] and m["requires_confirmation"] and not m["model_input"]["eligible"])

    def test_b0_no_b4_block(self):
        self.assertEqual(find("몸이 펄펄 끓어요", "몸", "V3_B0")["canonical_id"], "fever")


if __name__ == "__main__":
    unittest.main()
