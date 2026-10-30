import unittest

from _v4 import NEW, autos


class T(unittest.TestCase):
    def test_two_symptoms(self):
        for P in NEW:
            a = autos("기침하고 열이 나요", P)
            self.assertIn("cough", a)
            self.assertIn("fever", a)
            self.assertIn("dyspnea", autos("목이 아프고 숨이 차요", P))
