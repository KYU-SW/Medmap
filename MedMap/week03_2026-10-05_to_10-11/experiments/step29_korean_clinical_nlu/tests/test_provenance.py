import unittest

from _nlu import ms


class TestProvenance(unittest.TestCase):
    def test_silver_new_not_model_input(self):
        for t in ("코피가 나고 기침도 해요", "입냄새가 나요", "코골이가 심해요", "손이 떨려요"):
            for m in ms(t):
                if m["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or m.get("silver"):
                    with self.subTest(t=t, span=m["raw_span"]):
                        self.assertFalse(m["model_input"]["eligible"])
                        self.assertFalse(m["model_supported"] and m["status"] != "EXISTING_CANONICAL")
                        self.assertTrue(m.get("evidence_level"))

    def test_uncertain_has_reason(self):
        for t in ("심장 부분", "속이 화끈화끈해요", "무기력", "토하지 않았어요"):
            for m in ms(t):
                if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM"):
                    with self.subTest(t=t):
                        self.assertTrue(m.get("reason") or m.get("guard_reasons"))
                        self.assertTrue(m["raw_span"])


if __name__ == "__main__":
    unittest.main()
