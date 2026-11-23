"""EXP-03 합성 시나리오(전부 지어낸 사례·문장 — 실제 환자 없음). 기대 출력은 PROTOCOL.md 규칙에서 기계적으로 정해지는 값만,
구현 실행 전 고정(2026-11-03). 각 체크포인트 기대 = (요약 상태, 활성 알림 규칙 집합). 일부는 플래그·해제 사유도 고정.
"""
from __future__ import annotations

from ct_bridge import report_evidence
from reassess import PE, Evidence, HypothesisEvent, Timeline

POS_TXT = "FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism."
NEG_TXT = "FINDINGS: No filling defect.\nIMPRESSION: No pulmonary embolism."
LONGNEG_TXT = ("FINDINGS: There is no filling defect within the main, lobar, segmental, or subsegmental pulmonary arteries "
               "to suggest pulmonary embolism.\nIMPRESSION: No acute process.")
CHR_TXT = "FINDINGS: Eccentric web.\nIMPRESSION: Chronic pulmonary embolism in the right lower lobe."
UNC_TXT = "FINDINGS: See below.\nIMPRESSION: Findings suspicious for pulmonary embolism."
HIST_TXT = "FINDINGS: Lungs are clear.\nIMPRESSION: History of pulmonary embolism."
IND_TXT = "INDICATION: eval for pulmonary embolism\nFINDINGS: Lungs are clear.\nIMPRESSION: No acute process."
PERI = "DX:Pericarditis"


def symptom(enc, eid="sx1", concept="HP:0002094", status="POSITIVE", t=0.0):
    return Evidence(eid, enc, "SYMPTOM", "synthetic_triage", f"synthetic:{eid}", t, t, t, status, concept=concept)


def order(enc, eid="o1", t=60.0):
    return Evidence(eid, enc, "IMAGING_ORDER", "synthetic_order", f"synthetic:{eid}", t, t, t, "PENDING",
                    concept="CONCEPT:ctpa_filling_defect")


def base(enc, wd=True, variant="v3b") -> Timeline:
    tl = Timeline(enc)
    if wd:
        tl.set_hypothesis(HypothesisEvent("h1", enc, PE, 0.0))
    tl.add(symptom(enc))
    tl.add(order(enc))
    return tl


def with_report(enc, text, obs=100.0, avail=170.0, wd=True, variant="v3b", order_ref="o1", eid="rep1"):
    tl = base(enc, wd, variant)
    tl.add(report_evidence(eid, enc, text, obs, avail, order_ref=order_ref, variant=variant))
    return tl


def S(summary, *alerts):
    return (summary, frozenset(alerts))


def build(variant="v3b") -> dict:
    v = variant
    sc = {}
    sc["A_consistent"] = (with_report("A", POS_TXT, variant=v), [0, 60, 120, 180],
                          [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("SUPPORTED")], {})
    tl = with_report("A2", POS_TXT, variant=v)
    tl.add(Evidence("dd1", "A2", "LAB", "synthetic_lab", "synthetic:dd1", 30.0, 50.0, 50.0, "NEGATIVE", concept="HP:0033106"))
    sc["A2_ddimer_negative_no_exclusion"] = (tl, [0, 60, 120, 180], [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("SUPPORTED")],
                                             {"relation_at_60": ("dd1", "NO_KNOWLEDGE")})
    sc["B_explicit_conflict"] = (with_report("B", NEG_TXT, variant=v), [0, 60, 120, 180],
                                 [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("CONFLICT", "AL1_NEW_CONFLICT")], {})
    sc["C_order_no_result"] = (base("C", variant=v), [0, 60, 120, 180],
                               [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("PENDING")], {})
    sc["D_result_not_yet_available"] = (with_report("D", POS_TXT, obs=70.0, avail=300.0, variant=v), [0, 60, 120, 180, 300],
                                        [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("PENDING"), S("SUPPORTED")], {})
    sc["E_long_negation_late"] = (with_report("E", LONGNEG_TXT, variant=v), [0, 60, 120, 180],
                                  [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("CONFLICT", "AL1_NEW_CONFLICT")], {"v3b_only": True})
    sc["F_chronic_only"] = (with_report("F", CHR_TXT, variant=v), [0, 60, 180],
                            [S("SUPPORTED"), S("PENDING"), S("INSUFFICIENT")], {"flag_at_180": ("chronic_only", True)})
    sc["G_uncertain"] = (with_report("G", UNC_TXT, variant=v), [0, 60, 180],
                         [S("SUPPORTED"), S("PENDING"), S("UNKNOWN")], {})
    tl = with_report("H", NEG_TXT, variant=v)
    tl.set_hypothesis(HypothesisEvent("h2", "H", PERI, 200.0))
    sc["H_hypothesis_changed"] = (tl, [0, 60, 180, 240],
                                  [S("SUPPORTED"), S("PENDING"), S("CONFLICT", "AL1_NEW_CONFLICT"), S("SUPPORTED")],
                                  {"cleared_at_240": "HYPOTHESIS_CHANGED"})
    tl = with_report("I1", POS_TXT, variant=v)
    tl.add(report_evidence("rep1c", "I1", NEG_TXT, 100.0, 280.0, order_ref="o1", variant=v, supersedes="rep1", revision_id="r2"))
    sc["I1_correction_pos_to_neg"] = (tl, [0, 180, 300],
                                      [S("SUPPORTED"), S("SUPPORTED"), S("CONFLICT", "AL1_NEW_CONFLICT", "AL2_SUPPORT_RETRACTED")], {})
    tl = with_report("I2", NEG_TXT, variant=v)
    tl.add(report_evidence("rep1c", "I2", POS_TXT, 100.0, 280.0, order_ref="o1", variant=v, supersedes="rep1", revision_id="r2"))
    sc["I2_correction_neg_to_pos"] = (tl, [0, 180, 300], [S("SUPPORTED"), S("CONFLICT", "AL1_NEW_CONFLICT"), S("SUPPORTED")],
                                      {"cleared_at_300": "RESOLVED_BY_CORRECTION"})
    tl = with_report("J1", UNC_TXT, obs=100.0, avail=150.0, variant=v)
    tl.add(order("J1", "o2", 200.0))
    tl.add(report_evidence("rep2", "J1", POS_TXT, 220.0, 260.0, order_ref="o2", variant=v))
    sc["J1_uncertain_then_repeat_positive"] = (tl, [0, 180, 240, 300],
                                               [S("SUPPORTED"), S("UNKNOWN"), S("UNKNOWN"), S("SUPPORTED")],
                                               {"flag_at_240": ("pending", True)})
    tl = with_report("J2", POS_TXT, obs=100.0, avail=150.0, variant=v)
    tl.add(order("J2", "o2", 200.0))
    tl.add(report_evidence("rep2", "J2", NEG_TXT, 220.0, 260.0, order_ref="o2", variant=v))
    sc["J2_positive_then_repeat_negative"] = (tl, [0, 180, 300],
                                              [S("SUPPORTED"), S("SUPPORTED"), S("CONFLICT", "AL1_NEW_CONFLICT")],
                                              {"flag_at_300": ("support", True)})
    sc["K_no_hypothesis"] = (with_report("K", NEG_TXT, wd=False, variant=v), [0, 60, 180],
                             [S("NO_HYPOTHESIS"), S("NO_HYPOTHESIS"), S("NO_HYPOTHESIS")], {})
    sc["L_indication_only"] = (with_report("L", IND_TXT, variant=v), [0, 60, 180],
                               [S("SUPPORTED"), S("PENDING"), S("UNKNOWN")], {})
    sc["C2_history_mention"] = (with_report("C2", HIST_TXT, variant=v), [0, 60, 180],
                                [S("SUPPORTED"), S("PENDING"), S("UNKNOWN")], {})
    tl = base("C5", variant=v)
    tl.add(report_evidence("rep1", "C5", POS_TXT, 100.0, None, order_ref="o1", variant=v))
    sc["C5_unknown_availability"] = (tl, [0, 60, 180, 300], [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("PENDING")],
                                     {"excluded": ("EXCLUDED_UNKNOWN_AVAILABILITY", 1)})
    tl = base("C6", variant=v)
    tl.add(report_evidence("rep1", "C6", POS_TXT, 200.0, 150.0, order_ref="o1", variant=v))
    sc["C6_time_inversion"] = (tl, [0, 60, 180, 300], [S("SUPPORTED"), S("PENDING"), S("PENDING"), S("PENDING")],
                               {"excluded": ("EXCLUDED_TIME_INVERSION", 1)})
    return sc


REJECT_CASES = {
    "C3_missing_source": lambda: Timeline("C3").add(Evidence("x", "C3", "SYMPTOM", "synthetic", "", 0.0, 0.0, 0.0, "POSITIVE",
                                                             concept="HP:0002094")),
    "C4_cross_encounter": lambda: Timeline("C4").add(Evidence("x", "OTHER", "SYMPTOM", "synthetic", "synthetic:x", 0.0, 0.0, 0.0,
                                                              "POSITIVE", concept="HP:0002094")),
}
