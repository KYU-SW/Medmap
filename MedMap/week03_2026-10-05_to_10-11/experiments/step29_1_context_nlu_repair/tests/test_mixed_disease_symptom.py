import unittest

from _v2 import autos


class T(unittest.TestCase):
    def test_disease_and_symptom(self):
        self.assertIn("pain", autos("고혈압이 있고 머리가 아파요"))
        self.assertIn("dyspnea", autos("천식이 있어서 숨이 차요"))

    def test_disease_only(self):
        for t in ("당뇨가 있어요", "고혈압", "혈관성 편두통"):
            with self.subTest(t=t):
                self.assertEqual([c for c in autos(t) if c], [])


if __name__ == "__main__":
    unittest.main()
