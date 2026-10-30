import unittest

import _nlu  # noqa: F401
from p5_normalizer_adapter import engine, p5


class TestAdapter(unittest.TestCase):
    def test_same_as_policy_engine_p5(self):
        for t in ("기침해요", "코피가 나요", "머리가 아파요", "외 음 부 근", "무기력"):
            a = [(r["status"], r["canonical_id"], r["ontology_id"], r["span_start"], r["span_end"]) for r in p5(t)]
            b = [(r["status"], r["canonical_id"], r["ontology_id"], r["span_start"], r["span_end"]) for r in engine().run_all(t)["P5"]]
            with self.subTest(t=t):
                self.assertEqual(a, b)

    def test_schema_keys(self):
        for k in ("status", "canonical_id", "ontology_id", "evidence_level", "usable_by_disease_model", "display", "span_start", "span_end", "span_text", "ko_evidence"):
            self.assertIn(k, p5("기침해요")[0])


if __name__ == "__main__":
    unittest.main()
