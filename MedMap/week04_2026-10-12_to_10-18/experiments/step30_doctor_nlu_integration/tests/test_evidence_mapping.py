import json
import unittest

from _base import ELIG, S


class EvidenceMapping(unittest.TestCase):
    def test_targets_valid_and_unique(self):
        S.product()
        from medmap import config
        raw = json.loads(config.EVIDENCES_JSON.read_text())
        seen = {}
        for cid, r in ELIG.mapping().items():
            e = r["ddxplus_evidence_id"]
            self.assertIn(e, raw)
            self.assertEqual(raw[e]["data_type"], "B", e)
            self.assertEqual(raw[e]["code_question"], e, e)
            self.assertNotIn(e, config.EXCLUDED_QUESTIONS)
            self.assertNotIn(e, seen, f"{e} 충돌 {seen.get(e)} {cid}")
            seen[e] = cid

    def test_specific_rules(self):
        m = ELIG.mapping()
        self.assertEqual(m["pain"]["ddxplus_evidence_id"], "E_53")
        self.assertEqual(m["cough"]["ddxplus_evidence_id"], "E_201")
        self.assertEqual(m["dyspnea"]["ddxplus_evidence_id"], "E_66")
        for cid in ("vomiting", "fatigue", "limb_weakness", "decreased_appetite"):
            self.assertNotIn(cid, m)
        self.assertNotIn("E_55", {r["ddxplus_evidence_id"] for r in m.values()})

    def test_csv_columns(self):
        rows = S.read_csv(S.DATA / "evidence_mapping_candidates.csv")
        for col in ("nlu_concept_id", "ddxplus_evidence_id", "relation_type", "model_compatibility", "mapping_confidence", "validation_status",
                    "conversion_allowed", "conversion_reason"):
            self.assertIn(col, rows[0])
        self.assertFalse(any("snomed" in k.lower() or "umls" in k.lower() for k in rows[0]))


if __name__ == "__main__":
    unittest.main()
