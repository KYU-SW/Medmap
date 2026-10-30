import dataclasses
import unittest

from _base import S, SIM, packet
import blind_workflow_simulator as BW


class NoProductionMutation(unittest.TestCase):
    def files(self):
        P = S.PRODUCT
        fs = [P / "medmap/patient_state.py", P / "medmap/doctor_view.py", P / "medmap/evidence.py", P / "medmap/diagnosis.py",
              P / "data/ddxplus/en/release_evidences.json", P / "exp/step16b_next_information_validation/model_k3.pkl",
              P / "medmap-web/src/doctor/DoctorApp.jsx"]
        return {str(f): S.sha256(f) for f in fs}

    def test_product_files_unchanged_after_full_flow(self):
        before = self.files()
        p = packet("엄마는 기침하고 저는 머리가 아파요.")
        after, _ = SIM.apply_decisions(p, SIM.policy_confirm_stage_a(p))
        SIM.validate_candidate(after["model_input"]["patient_state_delta"])
        BW.simulate(p)
        self.assertEqual(before, self.files())

    def test_patient_state_frozen_and_not_persisted(self):
        S.product()
        from medmap.patient_state import PatientState
        st = PatientState.new(40, "F")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            st.age = 41
        r = SIM.validate_candidate({"E_66": {}})
        self.assertFalse(r["persisted"])
        self.assertTrue(r["valid"])

    def test_product_root_is_master_checkout(self):
        import subprocess
        b = subprocess.run(["git", "-C", str(S.PRODUCT), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(b, "master")


if __name__ == "__main__":
    unittest.main()
