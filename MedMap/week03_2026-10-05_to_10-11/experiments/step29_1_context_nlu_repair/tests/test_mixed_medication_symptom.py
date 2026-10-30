import unittest

from _v2 import autos, find


class T(unittest.TestCase):
    def test_drug_then_symptom(self):
        self.assertIn("cough", autos("기침약을 먹었는데 기침이 계속 나요"))

    def test_drug_only(self):
        for t in ("기침약을 먹었어요", "기침 억제제", "약을 먹었어요"):
            with self.subTest(t=t):
                self.assertNotIn("cough", autos(t))

    def test_fever_not_absent_when_not_going_down(self):
        m = find("해열제를 먹었는데 열이 안 내려요", "열")
        if m is not None:
            self.assertNotEqual(m["assertion"], "ABSENT")


if __name__ == "__main__":
    unittest.main()
