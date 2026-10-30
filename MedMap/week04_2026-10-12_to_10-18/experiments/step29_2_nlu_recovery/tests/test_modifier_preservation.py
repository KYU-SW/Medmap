import unittest

from _v3 import analyze, autos, SEL
from evaluator_v6 import evaluate


class T(unittest.TestCase):
    def test_quality_modifier_concept(self):
        self.assertIn("pain", autos("박동성 두통이 있어요"))
        self.assertIn("dizziness", autos("회전성 어지럼증이 심해요"))

    def test_no_v6_violation_for_modifiers(self):
        for t in ("박동성 두통이 있어요", "회전성 어지럼증이 심해요"):
            self.assertEqual(evaluate(analyze(t, SEL)), [], t)

    def test_ideophone_kept_in_attributes(self):
        o = analyze("머리가 지끈지끈 아파요", SEL)
        self.assertTrue(any("지끈지끈" in a for m in o["mentions"] for a in m.get("attributes") or []))


if __name__ == "__main__":
    unittest.main()
