import unittest

from _v3 import find


class T(unittest.TestCase):
    def test_past_event_preserved_and_resolved(self):
        for t in ("열이 났어요 오늘은 괜찮아요", "어제는 배가 아팠어요 오늘은 괜찮아요."):
            m = find(t, "열" if "열" in t else "배")
            self.assertEqual(m["assertion"], "PRESENT", t)
            self.assertEqual(m["temporality"], "PAST", t)
            self.assertEqual(m["current_status"], "RESOLVED", t)
            self.assertFalse(m["model_input"]["eligible"] and m["model_input"]["polarity"] == "POSITIVE")

    def test_improvement_is_not_resolution(self):
        self.assertEqual(find("어제 열이 났어요 지금은 많이 좋아졌어요", "열")["current_status"], "IMPROVING")

    def test_unrelated_normal_state_not_resolution(self):
        self.assertEqual(find("기침이 나요 배는 괜찮아요", "기침")["current_status"], "UNSPECIFIED")

    def test_negated_improvement_persists(self):
        m = find("해열제를 먹었는데 열이 안 내려요", "열")
        self.assertEqual(m["assertion"], "PRESENT")
        self.assertEqual(m["current_status"], "PERSISTING")

    def test_strength_recorded(self):
        self.assertEqual(find("어제 기침이 났어요 지금은 증상이 없어요", "기침")["resolution"]["strength"], "STRONG")


if __name__ == "__main__":
    unittest.main()
