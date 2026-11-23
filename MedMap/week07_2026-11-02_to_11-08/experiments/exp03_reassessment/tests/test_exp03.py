"""EXP-03 합성 테스트: 실험 A(누출) · B(상태 전이) · C(잘못된 알림 방지) · v3b 연결. 실제 환자 자료 없음."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scenarios as SC  # noqa: E402
from ct_bridge import classify  # noqa: E402
from reassess import assess, session  # noqa: E402

SCN = SC.build("v3b")


def observed(tl, cps):
    return [(a["assessment"].summary, frozenset(x["rule"] for x in a["assessment"].alerts)) for a in session(tl, cps)]


class ExpA_Leakage(unittest.TestCase):
    def test_no_future_leakage_all_scenarios(self):
        for name, (tl, cps, _, _) in SCN.items():
            for T in cps + [c + 1 for c in cps]:
                self.assertEqual(assess(tl, T).key(), assess(tl.truncated(T), T).key(), f"{name}@{T}")

    def test_report_observed_but_not_available(self):
        tl, *_ = SCN["A_consistent"]
        a = assess(tl, 120)                                      # 판독 시행 100, 확인 170
        self.assertNotIn("rep1", [r[0] for r in a.relations])
        self.assertEqual(a.summary, "PENDING")


class ExpB_Transitions(unittest.TestCase):
    def test_expected_states_and_alerts(self):
        for name, (tl, cps, exp, _) in SCN.items():
            self.assertEqual(observed(tl, cps), exp, name)

    def test_extra_expectations(self):
        for name, (tl, cps, _, extra) in SCN.items():
            for k, v in extra.items():
                if k.startswith("flag_at_"):
                    self.assertEqual(assess(tl, float(k.split("_")[-1])).flags[v[0]], v[1], name)
                elif k.startswith("cleared_at_"):
                    T = float(k.split("_")[-1])
                    log = session(tl, [c for c in cps if c <= T])
                    self.assertEqual([g["reason"] for g in log[-1]["alerts_cleared"]], [v], name)
                elif k == "relation_at_60":
                    rel = {r[0]: r[1] for r in assess(tl, 60).relations}
                    self.assertEqual(rel[v[0]], v[1], name)
                elif k == "excluded":
                    self.assertEqual(assess(tl, cps[-1]).excluded[v[0]], v[1], name)

    def test_source_traceability(self):
        for name, (tl, cps, _, _) in SCN.items():
            for T in cps:
                a = assess(tl, T)
                for r in a.relations:
                    self.assertTrue(r[0] and r[2] and r[3] and r[4] and r[5] is not None, f"{name}@{T} {r}")
                for al in a.alerts:
                    for k in ("hypothesis_id", "rule", "event_id", "source_reference", "evidence_type", "available_at"):
                        self.assertNotIn(al.get(k), (None, ""), f"{name}@{T} {k}")
                    self.assertEqual(al["provenance"], "SIMULATED_WD")


class ExpC_FalseAlerts(unittest.TestCase):
    def test_no_negative_or_conflict_from_absence(self):
        for name in ("C_order_no_result", "C5_unknown_availability", "C6_time_inversion", "L_indication_only",
                     "C2_history_mention", "G_uncertain", "F_chronic_only"):
            tl, cps, _, _ = SCN[name]
            for T in cps:
                a = assess(tl, T)
                self.assertFalse(a.flags.get("conflict"), f"{name}@{T}")
                self.assertEqual(a.alerts, [], f"{name}@{T}")

    def test_rejections(self):
        for name, fn in SC.REJECT_CASES.items():
            with self.assertRaises(ValueError, msg=name):
                fn()

    def test_stale_alert_cleared_after_hypothesis_change(self):
        tl, *_ = SCN["H_hypothesis_changed"]
        self.assertEqual(assess(tl, 240).alerts, [])
        self.assertEqual(assess(tl, 240).hypothesis_id, "h2")


class V3bBridge(unittest.TestCase):
    def test_classes_preserved(self):
        self.assertEqual(classify(SC.CHR_TXT, "v3b")[0], "CHRONIC_OR_PERSISTENT")   # 만성 ≠ PE 없음
        self.assertEqual(classify(SC.UNC_TXT, "v3b")[0], "UNCERTAIN")
        self.assertEqual(classify(SC.IND_TXT, "v3b")[0], "NO_MENTION")
        self.assertEqual(classify(SC.NEG_TXT, "v3b")[0], "NEGATIVE")
        self.assertEqual(classify(SC.POS_TXT, "v3b")[0], "ACUTE_POS")

    def test_v2_v3b_difference_on_long_negation(self):
        self.assertEqual(classify(SC.LONGNEG_TXT, "v2")[0], "ACUTE_POS")
        self.assertEqual(classify(SC.LONGNEG_TXT, "v3b")[0], "NEGATIVE")
        s2 = SC.build("v2")["E_long_negation_late"]
        self.assertEqual(observed(s2[0], s2[1])[-1], ("SUPPORTED", frozenset()))     # v2 경로: 잘못된 지지
        s3 = SCN["E_long_negation_late"]
        self.assertEqual(observed(s3[0], s3[1])[-1], ("CONFLICT", frozenset({"AL1_NEW_CONFLICT"})))


if __name__ == "__main__":
    unittest.main()
