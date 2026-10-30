import unittest

from _base import AD, S, packet
import validate_schema as VS

TEXTS = ["어제부터 코피가 나고 머리가 아파요.", "기침은 없는데 숨이 차요.", "기침약을 먹었는데 기침이 계속 나요.", "심장 부분이요.", "그제부터 열이 나고 배가 아파요."]


class AdapterContract(unittest.TestCase):
    def test_schema_no_violation(self):
        A = S.nlu()
        for t in TEXTS:
            out = A.analyze(t, S.NLU_POLICY)
            p = AD.build_packet(t, out)
            self.assertEqual(VS.check(t, out, p), [], t)

    def test_required_fields_and_banner(self):
        p = packet(TEXTS[0])
        self.assertEqual(p["schema_version"], S.SCHEMA_VERSION)
        self.assertTrue(p["research_simulation"])
        self.assertEqual(p["clinical_validation"], "NONE")
        for it in p["items"]:
            for f in AD.REQUIRED_FIELDS:
                self.assertIn(f, it)
            self.assertEqual(it["confirmation"]["status"], "UNCONFIRMED")
            self.assertTrue(it["requires_confirmation"])

    def test_model_input_not_applied(self):
        for t in TEXTS:
            mi = packet(t)["model_input"]
            self.assertFalse(mi["applied"])
            self.assertEqual(mi["auto_input_count"], 0)
            self.assertEqual(mi["stage_b_clinician_confirmed"], [])
            self.assertEqual(mi["patient_state_delta"], {})

    def test_validator_catches_broken_offset(self):
        A = S.nlu()
        t = TEXTS[1]
        out = A.analyze(t, S.NLU_POLICY)
        p = AD.build_packet(t, out)
        p["items"][0]["span_end"] += 1
        self.assertTrue(any(v.startswith("G1") or v.startswith("G2") for v in VS.check(t, out, p)))


if __name__ == "__main__":
    unittest.main()
