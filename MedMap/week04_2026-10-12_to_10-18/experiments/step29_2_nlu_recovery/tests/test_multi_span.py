import unittest

from _v3 import autos


class T(unittest.TestCase):
    def test_three_symptoms_no_period(self):
        a = autos("기침이 나요 열이 나요 숨이 차요")
        for c in ("cough", "fever", "dyspnea"):
            self.assertIn(c, a)

    def test_second_symptom_keeps_first(self):
        self.assertIn("cough", autos("기침이 나요"))
        self.assertIn("cough", autos("기침이 나요 머리가 아파요"))


if __name__ == "__main__":
    unittest.main()
