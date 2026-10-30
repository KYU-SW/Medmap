import unittest
from unittest import mock

from _base import AD, S, packet
import blind_workflow_simulator as BW


class BlindWorkflow(unittest.TestCase):
    def test_simulation_no_violation(self):
        for t in ("기침은 없는데 숨이 차요.", "어제부터 코피가 나고 머리가 아파요."):
            r = BW.simulate(packet(t))
            self.assertEqual(r["violations"], [], t)
            self.assertEqual(r["stage2_pending_assessment"], "LOCKED")

    def test_packet_build_never_calls_disease_model(self):
        S.product()
        from medmap.diagnosis import DiagnosisEngine
        A = S.nlu()
        out = A.analyze("목이 아프고 숨이 차요.", S.NLU_POLICY)
        with mock.patch.object(DiagnosisEngine, "diagnose", side_effect=AssertionError("diagnose called")), \
             mock.patch.object(DiagnosisEngine, "posterior", side_effect=AssertionError("posterior called")):
            p = AD.build_packet("목이 아프고 숨이 차요.", out)
        self.assertEqual(BW.leak_scan(p, BW.reg().classes), [])

    def test_leak_scan_detects(self):
        cls = BW.reg().classes
        self.assertTrue(BW.leak_scan({"x": cls[0]}, cls))
        self.assertTrue(BW.leak_scan({"ranking": []}, cls))


if __name__ == "__main__":
    unittest.main()
