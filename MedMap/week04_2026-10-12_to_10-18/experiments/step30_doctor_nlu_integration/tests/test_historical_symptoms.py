import unittest

from _base import item_at, item_from, packet, supported_mention


class Historical(unittest.TestCase):
    def test_regression_case(self):
        p = packet("어제 열이 났어요 오늘은 괜찮아요.")
        it = item_at(p, "열")
        self.assertEqual(it["category"], "D")
        self.assertFalse(it["eligibility"]["eligible"])
        self.assertEqual(it["raw_span"], p["source_text"][it["span_start"]:it["span_end"]])

    def test_forced_past_and_resolved(self):
        for k, v in (("temporality", "PAST"), ("current_status", "RESOLVED")):
            m = supported_mention()
            m[k] = v
            it = item_from(m)
            self.assertEqual(it["category"], "D", (k, v))
            self.assertFalse(it["eligibility"]["eligible"])

    def test_improving_is_uncertain(self):
        m = supported_mention()
        m["current_status"] = "IMPROVING"
        it = item_from(m)
        self.assertEqual(it["category"], "F")
        self.assertFalse(it["eligibility"]["eligible"])

    def test_dev_past(self):
        it = item_at(packet("지난달에 기침을 했었어요."), "기침")
        self.assertEqual(it["category"], "D")
        self.assertFalse(it["eligibility"]["eligible"])


if __name__ == "__main__":
    unittest.main()
