import unittest

from _v2 import autos, ms


class T(unittest.TestCase):
    def test_no_forced_concept(self):
        self.assertNotIn("limb_weakness", autos("양쪽 팔을 들어요"))
        self.assertNotIn("palpitations", autos("심장 부분"))
        self.assertNotIn("fever", autos("온몸에 힘이 없어요"))

    def test_question_not_report(self):
        for t in ("열이 나면 어떻게 해야 하나요", "기침이 나면 병원에 와야 하나요?"):
            with self.subTest(t=t):
                self.assertFalse(any(m["model_input"]["polarity"] == "POSITIVE" for m in ms(t)))


if __name__ == "__main__":
    unittest.main()
