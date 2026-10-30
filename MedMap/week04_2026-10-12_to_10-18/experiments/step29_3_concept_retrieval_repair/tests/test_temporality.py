import unittest

from _v4 import find


class T(unittest.TestCase):
    def test_past_vs_now(self):
        self.assertEqual(find("어제 열이 났어요", "열")["temporality"], "PAST")
        self.assertIn(find("지금 열이 나요", "열")["temporality"], ("CURRENT", "ONGOING"))

    def test_masked_time_restored(self):
        self.assertEqual(find("지난주에 숨이 찼어요", "숨", "R2")["onset_text"], "지난주에")
