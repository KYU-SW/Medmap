import unittest

import _v3  # noqa: F401
from evaluator_v6 import mention_violations as v6


def M(t, u, c, **kw):
    s = t.index(u)
    return {"source_text": t, "raw_span": u, "span_start": s, "span_end": s + len(u), "unit_text": u, "source_sentence": t, "status": "EXISTING_CANONICAL",
            "canonical_id": c, **kw}


class T(unittest.TestCase):
    def test_quality_modifiers_ok(self):
        for t, c in [("박동성 두통", "pain"), ("회전성 어지럼증", "dizziness"), ("박동성 두통이 있어요", "pain"), ("회전성 어지럼증이 있어요", "dizziness")]:
            self.assertEqual(v6(M(t, t, c)), [], t)

    def test_disease_modifier_bad(self):
        self.assertIn("DISEASE_TERM", v6(M("알레르기성 비염", "알레르기성 비염", "cough")))
        self.assertIn("DISEASE_TERM", v6(M("혈관성 편두통", "혈관성 편두통", "pain")))

    def test_mixed_sentence_other_span_ok(self):
        self.assertEqual(v6(M("고혈압이 있고 머리가 아파요", "머리가 아파요", "pain")), [])
        self.assertEqual(v6(M("기침약을 먹었는데 기침이 계속 나요", "기침이 계속 나요", "cough")), [])
        self.assertIn("DRUG_OR_TREATMENT_TERM", v6(M("기침약을 먹었는데 기침이 계속 나요", "기침약을 먹었는데", "cough")))

    def test_vomit_nausea_blood(self):
        self.assertIn("MODAL_VOMIT_AS_VOMITING", v6(M("토할 것 같아요", "토할 것 같아요", "vomiting")))
        self.assertEqual(v6(M("토할 것 같아요", "토할 것 같아요", "nausea")), [])
        self.assertIn("VOMIT_AS_NAUSEA", v6(M("토했어요", "토했어요", "nausea")))
        self.assertIn("EPISTAXIS_AS_BLEEDING", v6(M("코피가 나요", "코피가 나요", "hemoptysis")))
        self.assertIn("BLOOD_ROUTE_MISMATCH", v6(M("기침하면 피가 같이 나와요", "기침하면 피가 같이 나와요", "hematemesis")))
        self.assertEqual(v6(M("기침하면 피가 같이 나와요", "기침하면 피가 같이 나와요", "hemoptysis")), [])

    def test_assertion_rules(self):
        self.assertIn("NEGATION_MISSED", v6(M("기침은 안 나요", "기침은 안 나요", "cough", assertion="PRESENT")))
        self.assertEqual(v6(M("열이 안 내려요", "열이 안 내려요", "fever", assertion="PRESENT")), [])
        self.assertEqual(v6(M("다리에 힘이 없어요", "다리에 힘이 없어요", "limb_weakness", assertion="PRESENT")), [])
        self.assertIn("SPURIOUS_NEGATION", v6(M("숨은 차요", "숨은 차요", "dyspnea", assertion="ABSENT")))


if __name__ == "__main__":
    unittest.main()
