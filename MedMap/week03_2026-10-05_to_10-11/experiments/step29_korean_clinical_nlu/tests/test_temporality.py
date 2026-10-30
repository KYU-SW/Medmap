import unittest

from _nlu import find


class TestTemporality(unittest.TestCase):
    def test_onset_ongoing(self):
        m = find("3일 전부터 기침해요", "기침")
        self.assertEqual(m["onset_text"], "3일 전부터")
        self.assertEqual(m["temporality"], "ONGOING")

    def test_past_and_resolved(self):
        self.assertIn(find("지난주에는 열이 났어요", "열")["temporality"], ("PAST", "RESOLVED"))
        self.assertEqual(find("어제는 숨이 찼는데 오늘은 괜찮아요", "숨")["temporality"], "RESOLVED")

    def test_scope_not_copied(self):
        m = find("어제부터 코피가 나고 머리가 아파요", "머리")
        self.assertEqual(m["time_scope"], "UNCERTAIN")
        self.assertIsNone(m["onset_text"])

    def test_frequency(self):
        self.assertEqual(find("가끔 숨이 차요", "숨")["frequency_text"], "가끔")


if __name__ == "__main__":
    unittest.main()
