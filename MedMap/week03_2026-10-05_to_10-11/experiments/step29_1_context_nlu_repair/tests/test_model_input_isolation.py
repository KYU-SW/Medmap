import unittest

from _v2 import ms

CASES = ["엄마는 기침하고 저는 열이 나요", "열이 없어요", "지난주에 열이 났어요", "어제 열이 났어요. 오늘은 괜찮아요.", "코피가 나고 기침도 해요", "입냄새가 나요",
         "기침하지 않는 건 아니에요", "숨은 괜찮은 것 같아요"]


class T(unittest.TestCase):
    def test_isolation(self):
        for t in CASES:
            for m in ms(t):
                with self.subTest(t=t, span=m["raw_span"]):
                    mi = m["model_input"]
                    self.assertFalse(mi["applied"])
                    if mi["eligible"]:
                        self.assertEqual(m["experiencer"], "PATIENT")
                        self.assertIn(m["status"], ("EXISTING_CANONICAL", "EXISTING_COMPOSITE"))
                        self.assertNotEqual(m.get("evidence_sources"), "SILVER")
                        if mi["polarity"] == "POSITIVE":
                            self.assertEqual(m["assertion"], "PRESENT")
                            self.assertNotIn(m["temporality"], ("PAST", "RESOLVED"))


if __name__ == "__main__":
    unittest.main()
