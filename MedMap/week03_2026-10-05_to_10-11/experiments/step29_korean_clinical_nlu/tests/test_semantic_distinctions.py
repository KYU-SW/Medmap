import unittest

from _nlu import concept_of, ms
from evaluator_v4 import violations

CASES = ["토했어요", "토할 것 같아요", "손이 떨려요", "추워서 몸이 덜덜 떨려요", "코피가 나요", "심장 부분", "가슴이 두근거려요", "속이 화끈화끈해요",
         "숨 쉴 때마다 옆구리가 찌르듯이 아파요", "기침 억제제", "고혈압"]


class TestDistinctions(unittest.TestCase):
    def test_no_v4_violation(self):
        for t in CASES:
            m = ms(t)
            cs = [x["canonical_id"] for x in m if x["status"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")] + [c for x in m for c in (x.get("display") or [])]
            with self.subTest(t=t, cs=cs):
                self.assertEqual(violations(t, cs), [])

    def test_body_part_only_no_concept(self):
        self.assertFalse([concept_of(x) for x in ms("심장 부분") if concept_of(x)])

    def test_pain_with_breath_not_dyspnea(self):
        self.assertNotIn("dyspnea", [concept_of(x) for x in ms("숨 쉴 때마다 옆구리가 찌르듯이 아파요")])


if __name__ == "__main__":
    unittest.main()
