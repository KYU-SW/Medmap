import unittest

from _v3 import find, ms


class T(unittest.TestCase):
    def test_negation_not_propagated(self):
        self.assertEqual(find("기침은 없어요 숨은 차요", "숨")["assertion"], "PRESENT")
        self.assertEqual(find("기침은 없어요 숨은 차요", "기침")["assertion"], "ABSENT")

    def test_evaluative_scope_same_clause(self):
        self.assertEqual(find("머리는 괜찮은데 배가 아파요.", "배")["assertion"], "PRESENT")
        m = find("머리는 괜찮은데 배가 아파요.", "머리")
        self.assertTrue(m is None or m["assertion"] != "PRESENT")

    def test_eval_non_symptom_no_negation(self):
        self.assertFalse([m for m in ms("검사 결과는 괜찮아요.") if m.get("is_symptom") and m["assertion"] == "ABSENT"])

    def test_unsure_eval_not_certain_absent(self):
        m = find("머리는 괜찮은지 모르겠어요.", "머리")
        self.assertTrue(m is None or not (m["assertion"] == "ABSENT" and m.get("assertion_certainty") != "LOW"))

    def test_appetite_eval_not_present(self):
        m = find("입맛은 괜찮아요.", "입맛")
        self.assertTrue(m is None or m["assertion"] != "PRESENT")


if __name__ == "__main__":
    unittest.main()
