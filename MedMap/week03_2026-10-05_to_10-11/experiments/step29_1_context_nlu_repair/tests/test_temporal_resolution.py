import unittest

from _v2 import find


class T(unittest.TestCase):
    def test_cross_sentence(self):
        m = find("어제 열이 났어요. 오늘은 괜찮아요.", "열")
        self.assertEqual(m["temporality"], "RESOLVED")
        self.assertEqual(m["resolution"]["basis"], "PREV_SENTENCE_LAST_CLAUSE")

    def test_control_not_resolved(self):
        self.assertEqual(find("어제 열이 났어요. 오늘은 배가 아파요.", "열")["temporality"], "PAST")

    def test_same_sentence(self):
        self.assertEqual(find("어제는 숨이 찼는데 오늘은 괜찮아요", "숨")["temporality"], "RESOLVED")

    def test_past_kept_not_present_model(self):
        m = find("어제는 머리가 아팠는데 지금은 괜찮아요", "머리")
        self.assertEqual(m["assertion"], "PRESENT")
        self.assertNotEqual(m["model_input"]["polarity"], "POSITIVE")


if __name__ == "__main__":
    unittest.main()
