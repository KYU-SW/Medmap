import unittest

from _v2 import autos, ms


class T(unittest.TestCase):
    def test_two(self):
        a = autos("가슴이 아프고 숨이 차요")
        self.assertIn("pain", a)
        self.assertIn("dyspnea", a)

    def test_no_over_split(self):
        pos = [m for m in ms("머리가 지끈지끈 아파요") if m["status"].startswith("EXISTING")]
        self.assertLessEqual(len(pos), 1)


if __name__ == "__main__":
    unittest.main()
