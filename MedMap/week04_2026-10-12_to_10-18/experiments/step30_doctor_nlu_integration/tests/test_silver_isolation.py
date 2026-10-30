import unittest

from _base import ELIG, S, SIM, item_at, item_from, packet, supported_mention


class SilverIsolation(unittest.TestCase):
    def test_epistaxis_not_merged(self):
        p = packet("어제부터 코피가 나고 머리가 아파요.")
        it = item_at(p, "코피")
        self.assertEqual(it["category"], "B")
        self.assertFalse(it["eligibility"]["eligible"])
        after, _ = SIM.apply_decisions(p, SIM.policy_confirm_everything(p))
        self.assertNotIn("E_178", after["model_input"]["patient_state_delta"])
        self.assertEqual(it["onset_text"], "어제부터")

    def test_tremor_not_chills(self):
        p = packet("손이 떨려요.")
        for it in p["items"]:
            self.assertNotEqual(it.get("canonical_id"), "chills")
            self.assertFalse(it["eligibility"]["eligible"])
        after, _ = SIM.apply_decisions(p, SIM.policy_confirm_everything(p))
        self.assertEqual(after["model_input"]["patient_state_delta"], {})

    def test_forced_silver_statuses(self):
        for st in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
            m = supported_mention()
            m["status"] = st
            it = item_from(m)
            self.assertEqual(it["category"], "B")
            self.assertFalse(it["eligibility"]["eligible"])
        m = supported_mention()
        m["evidence_sources"] = "SILVER"
        self.assertFalse(item_from(m)["eligibility"]["eligible"])

    def test_no_silver_row_allowed(self):
        for r in S.read_csv(S.DATA / "evidence_mapping_candidates.csv"):
            if r["concept_scope"].startswith("SILVER"):
                self.assertEqual(r["conversion_allowed"], "False", r["nlu_concept_id"])
        self.assertTrue(all(cid in S.inventory() for cid in ELIG.mapping()))


if __name__ == "__main__":
    unittest.main()
