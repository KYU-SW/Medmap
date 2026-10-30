import unittest

from _base import AD, S


class Provenance(unittest.TestCase):
    def test_nlu_original_and_policy_sha(self):
        A = S.nlu()
        sha = S.sha256(S.S293_DIR / "data/policy_freeze.json")
        for t in ("어제부터 코피가 나고 머리가 아파요.", "심장 부분이요.", "피를 토했어요."):
            out = A.analyze(t, S.NLU_POLICY)
            p = AD.build_packet(t, out)
            for i, m in enumerate(out["mentions"]):
                it = p["items"][i]
                self.assertEqual(it["nlu_original"], m)
                self.assertEqual(it["provenance"]["policy_freeze_sha256"], sha)
                self.assertEqual(it["provenance"]["nlu_policy"], "R2")
                for g in m.get("guard_reasons") or []:
                    self.assertIn(f"GUARD:{g}", it["uncertainty_reason"])

    def test_confirmation_diff_traceable(self):
        from _base import SIM, packet
        p = packet("기침은 없는데 숨이 차요.")
        after, diff = SIM.apply_decisions(p, SIM.policy_confirm_stage_a(p))
        self.assertTrue(any(d["field"] == "model_input.patient_state_delta" for d in diff))
        self.assertTrue(all(d["by"] == "DUMMY_SIMULATOR" for d in diff))
        self.assertEqual(p["model_input"]["patient_state_delta"], {})         # 입력 packet 은 그대로


if __name__ == "__main__":
    unittest.main()
