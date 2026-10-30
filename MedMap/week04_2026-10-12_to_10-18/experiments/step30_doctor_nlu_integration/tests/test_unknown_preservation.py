import unittest

from _base import item_at, item_from, packet, supported_mention


class UnknownPreservation(unittest.TestCase):
    def test_body_part_only(self):
        p = packet("심장 부분이요.")
        self.assertTrue(p["items"])
        for it in p["items"]:
            self.assertNotEqual(it.get("canonical_id"), "palpitations")
            self.assertFalse(it["eligibility"]["eligible"])
            self.assertEqual(it["raw_span"], p["source_text"][it["span_start"]:it["span_end"]])
        self.assertIn(item_at(p, "심장")["category"], ("F", "H", "G"))

    def test_forced_unknown_symptom_and_possible(self):
        m = supported_mention()
        m["status"] = "UNKNOWN_SYMPTOM"
        it = item_from(m)
        self.assertEqual(it["category"], "H")
        self.assertFalse(it["eligibility"]["eligible"])
        for k, v in (("assertion", "POSSIBLE"), ("assertion", "UNKNOWN"), ("assertion_certainty", "LOW"), ("status", "UNCERTAIN"), ("temporality", "UNKNOWN")):
            m = supported_mention()
            m[k] = v
            it = item_from(m)
            self.assertEqual(it["category"], "F", (k, v))
            self.assertFalse(it["eligibility"]["eligible"], (k, v))
            self.assertTrue(it["uncertainty_reason"])

    def test_guard_reason_kept(self):
        m = supported_mention()
        m["guard_reasons"] = ["TEST_GUARD"]
        it = item_from(m)
        self.assertEqual(it["category"], "F")
        self.assertIn("GUARD:TEST_GUARD", it["uncertainty_reason"])


if __name__ == "__main__":
    unittest.main()
