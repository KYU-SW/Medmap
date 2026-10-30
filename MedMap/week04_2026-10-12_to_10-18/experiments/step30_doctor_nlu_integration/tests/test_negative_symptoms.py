import unittest

from _base import ELIG, SIM, item_at, item_from, packet, supported_mention


class Negative(unittest.TestCase):
    def test_regression_case(self):
        p = packet("기침은 없는데 숨이 차요.")
        c = item_at(p, "기침")
        self.assertEqual(c["category"], "C")
        self.assertFalse(c["eligibility"]["eligible"])
        self.assertEqual(item_at(p, "숨이 차")["category"], "A")

    def test_forced_absent_blocks_stage_a(self):
        m = supported_mention()
        m["assertion"] = "ABSENT"
        it = item_from(m)
        self.assertEqual(it["category"], "C")
        self.assertFalse(it["eligibility"]["eligible"])
        self.assertIn("ASSERTION:ABSENT", it["eligibility"]["blocking_reasons"])
        self.assertEqual(it["eligibility"]["negative_evidence"]["allowed"], False)

    def test_confirm_absent_never_negative_evidence(self):
        p = packet("기침은 없는데 숨이 차요.")
        c = item_at(p, "기침")
        r = ELIG.stage_b(c, {"decision": "CONFIRM_ABSENT", "confirmer": "DUMMY_SIMULATOR", "source": {"x": 1}})
        self.assertFalse(r["eligible"])
        self.assertFalse(r["negative_evidence"]["allowed"])

    def test_confirm_present_on_negated_requires_override(self):
        p = packet("기침은 없는데 숨이 차요.")
        after, _ = SIM.apply_decisions(p, SIM.policy_confirm_everything(p))
        evs = {r["evidence_id"] for r in after["model_input"]["stage_b_clinician_confirmed"]}
        self.assertNotIn("E_201", evs)
        c = item_at(p, "기침")
        r = ELIG.stage_b(c, {"decision": "CONFIRM_PRESENT", "confirmer": "DUMMY_SIMULATOR", "source": {"x": 1}, "override_reason": "환자 재문진에서 기침 있음"})
        self.assertTrue(r["eligible"])          # 의사의 명시적 재분류 사유가 있을 때만


if __name__ == "__main__":
    unittest.main()
