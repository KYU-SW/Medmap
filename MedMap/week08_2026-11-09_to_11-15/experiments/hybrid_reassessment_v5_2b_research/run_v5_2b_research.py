"""v5-2B-Research 실행: PE Shadow vs Legacy(합성 사례), 정책 민감도, P0 진리표·반례 대조, 시간·중복·정정 통합, Graph/Flat, ACS·MI·심낭염 연구 분류, 다질환 비교, 신규 반례.
결과는 outputs/<RUN_ID>/ 에 저장(이전 실행 보존). 기술 검증용 — 임상 성능 NOT_EVALUATED."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid5b import P0  # noqa: E402
from hybrid5b import comparison as CMP, experiment_matrix as EM, graph_flat as GF, legacy_adapter as LA, multidisease as MD  # noqa: E402
from hybrid5b import shadow_catalog as SC, shadow_reasoner as SR, temporal as TP  # noqa: E402
import run_v5_2a as R52  # noqa: E402  (v5-2A 합성 도구·레지스트리 검사 재사용, 실행하지 않음)
from hybrid4.graphs import Doc, Episode  # noqa: E402
from hybrid52.hypotheses import HypothesisSpec  # noqa: E402
from hybrid522.graphs import PatientGraph522  # noqa: E402

RUN_ID = "run_20261109_03"
trop = R52.trop


# ---------------- PE ----------------
def run_pe_case(c: dict, mode="graph"):
    pg = EM.build_pg(c)
    L = LA.evaluate(pg, c["as_of"], mode)
    S = SR.evaluate(pg, c["as_of"], mode, c["policy"])
    cmp = CMP.compare(L, S)
    actual = {}
    for rel in c["expect"]:
        toks = sorted({EM.token(j["direction"]) for j in S["judgments"] if j["relation_id"] == rel}) or ["NONE"]
        actual[rel] = toks
    checks = {rel: {"expected": sorted(exp), "basis": basis, "actual": actual[rel], "pass": set(actual[rel]) <= set(exp)} for rel, (exp, basis) in c["expect"].items()}
    cmp_cats = sorted({r["category"] for r in cmp if r["shadow_relation"] in c["expect"]})
    cmp_check = None if not c["expect_comparison"] else {"expected": c["expect_comparison"], "actual": cmp_cats, "pass": c["expect_comparison"] in cmp_cats}
    return pg, L, S, cmp, checks, cmp_check


def policy_sensitivity(c):
    out = {}
    for hp in SC.HAEMO_POLICIES:
        for pp in SC.PRETEST_POLICIES:
            pg = EM.build_pg(c)
            S = SR.evaluate(pg, c["as_of"], "graph", {"haemo": hp, "pretest": pp})
            out[f"{hp}|{pp}"] = sorted({(j["relation_id"], j["direction"]) for j in S["judgments"] if j["relation_id"] in c["expect"]})
    return out


# ---------------- ACS·MI / 심낭염 / 다질환 ----------------
def mi_pg(cid, obs=(), texts=(), concept="V5:DX:MI", sex="FEMALE"):
    p = PatientGraph522(f"SYN5B-{cid}", sex)
    p.add_episode(Episode("E1", "CURRENT_EVALUATION"))
    p.add_hypothesis_spec(HypothesisSpec("h_mi", concept, "E1", "PHYSICIAN_ADDITIONAL_HYPOTHESIS"))
    for i, o in enumerate(obs):
        p.add_observation52(o, source_event_id=f"LAB-{cid}-{i}")
    for i, (t, av) in enumerate(texts):
        p.add_record52(Doc(f"m{i}", t, "ECG" if t.startswith("ECG") else "NOTE", av - 0.1, av))
    return p


RISE = [trop("OBS:t0", 0.0, 20), trop("OBS:t1", 2.0, 60)]
RISE_TXT = ("Troponin rose from 20 to 60 ng/L.", 2.6)
MI_CASES = {   # (builder, as_of, expected{field: allowed values or prefix}) — 실행 전 고정
    "MI01_values_no_reference": (lambda: mi_pg("MI01", [trop("OBS:a", 0.0, 30, ref=None), trop("OBS:b", 2.0, 50, ref=None)]), 3.0,
                                 {"acute_myocardial_injury": {"UNKNOWN"}, "primary_mi_box3": "NOT_ASSESSABLE"}),
    "MI02_reference_only": (lambda: mi_pg("MI02", [], [("The 99th percentile upper reference limit for women is 14 ng/L.", 1.0)]), 2.0,
                            {"acute_myocardial_injury": {"UNKNOWN"}, "primary_mi_box3": "NOT_ASSESSABLE"}),
    "MI03_serial_rise_reported": (lambda: mi_pg("MI03", RISE, [RISE_TXT]), 3.0, {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "ACUTE_INJURY_ONLY"}),
    # MI13: 뮤테이션 검사에서 '새로움 무시' 결함을 잡는 사례가 없어 추가(2026-11-09, 사후 추가 — 기대값은 Box 3 'new or presumed new' 문구에서 정함)
    "MI13_ecg_change_newness_unstated": (lambda: mi_pg("MI13", RISE, [RISE_TXT, ("ECG showed T wave inversion in leads V1-V3.", 0.5)]), 3.0,
                                         {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "ACUTE_INJURY_ONLY"}),
    "MI04_different_assays": (lambda: mi_pg("MI04", [trop("OBS:a", 0.0, 30), trop("OBS:b", 2.0, 60, analyte="TROPONIN_I")]), 3.0,
                              {"acute_myocardial_injury": {"UNKNOWN"}, "primary_mi_box3": "NOT_ASSESSABLE"}),
    "MI05_time_unknown": (lambda: mi_pg("MI05", [trop("OBS:a", None, 30, avail=0.5), trop("OBS:b", None, 60, avail=1.0)]), 3.0,
                          {"acute_myocardial_injury": {"UNKNOWN"}, "primary_mi_box3": "NOT_ASSESSABLE"}),
    "MI06_no_ischaemia": (lambda: mi_pg("MI06", RISE, [RISE_TXT]), 3.0, {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "ACUTE_INJURY_ONLY",
                                                                         "ischaemia_symptoms": "NOT_RECORDED"}),
    "MI07_ischaemia_unknown": (lambda: mi_pg("MI07", RISE, [RISE_TXT, ("Chest pain.", 0.5)]), 3.0,
                               {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "ACUTE_INJURY_ONLY", "ischaemia_symptoms": "NONSPECIFIC"}),
    "MI08_new_ecg_change": (lambda: mi_pg("MI08", RISE, [RISE_TXT, ("ECG showed new ST depression in leads V4-V6.", 0.5)]), 3.0,
                            {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "BOX3_LIKELY_COMPONENTS_PRESENT_ECG_PATH"}),
    "MI09_record_states_mi": (lambda: mi_pg("MI09", RISE, [RISE_TXT, ("Myocardial infarction was diagnosed.", 2.7)]), 3.0,
                              {"acute_myocardial_injury": {"TRUE"}, "primary_mi_box3": "ACUTE_INJURY_ONLY"}),
    "MI10_rule_in_risk": (lambda: mi_pg("MI10", RISE, [RISE_TXT, ("The 0/1h algorithm placed the patient in the rule-in zone.", 2.0)]), 3.0,
                          {"risk_stratification": "RISK_STRATIFICATION_ONLY", "primary_mi_box3": "ACUTE_INJURY_ONLY"}),
    "MI11_single_very_low": (lambda: mi_pg("MI11", [], [("High-sensitivity troponin T was below the limit of detection 1 hours after symptom onset.", 1.0)]), 2.0,
                             {"mi_rule_out_pathway": "SINGLE_SAMPLE_VERY_LOW_STATED", "mi_criteria_not_met": "UNKNOWN"}),
    "MI12_serial_all_below": (lambda: mi_pg("MI12", [trop("OBS:a", 0.0, 6), trop("OBS:b", 2.0, 7)]), 3.0,
                              {"mi_criteria_not_met": "NOT_MET_CANDIDATE", "acute_myocardial_injury": {"FALSE", "UNKNOWN"}}),
}


def pc_pg(cid, texts):
    p = PatientGraph522(f"SYN5B-{cid}")
    p.add_episode(Episode("E1", "CURRENT_EVALUATION"))
    p.add_hypothesis_spec(HypothesisSpec("h_peri", "DX:Pericarditis", "E1", "PHYSICIAN_ADDITIONAL_HYPOTHESIS"))
    for i, (t, dt, av) in enumerate(texts):
        p.add_record52(Doc(f"c{i}", t, dt, av - 0.1, av))
    return p


NEGS = [("No pericardial friction rub. No pericardial effusion on echocardiography.", "NOTE", 0.5), ("ECG was normal.", "ECG", 0.6), ("CRP 2 mg/L, normal.", "LAB", 0.7)]
PC_CASES = {   # 기대: {(presentation policy, imaging policy): 허용 등급 집합} — 실행 전 고정
    "PC01_definite_both": (lambda: pc_pg("PC01", [("Pleuritic chest pain. A pericardial friction rub was heard.", "NOTE", 0.5),
                                                  ("ECG showed diffuse ST elevation and PR depression.", "ECG", 0.6)]), 2.0,
                           {("BROAD", "A"): {"DEFINITE"}, ("BROAD", "B"): {"DEFINITE"}, ("STRICT", "A"): {"DEFINITE"}}),
    "PC02_nonspecific_pain": (lambda: pc_pg("PC02", [("Chest pain.", "NOTE", 0.5), ("CRP 40 mg/L, elevated.", "LAB", 0.6)]), 2.0,
                              {("BROAD", "A"): {"POSSIBLE", "POSSIBLE_OR_DEFINITE_UNRESOLVED"}, ("STRICT", "A"): {"NOT_GENERATED_PREREQUISITE_UNKNOWN"}}),
    "PC03_imaging_two_items": (lambda: pc_pg("PC03", [("Pleuritic chest pain. No pericardial friction rub.", "NOTE", 0.5), ("ECG was normal.", "ECG", 0.6),
                                                      ("CRP 2 mg/L, normal.", "LAB", 0.7), ("Echocardiography showed a new small pericardial effusion.", "NOTE", 0.8),
                                                      ("Cardiac MRI showed pericardial late gadolinium enhancement.", "NOTE", 0.9)]), 2.0,
                               {("BROAD", "A"): {"DEFINITE"}, ("BROAD", "B"): {"POSSIBLE"}, ("BROAD", "C"): {"GRADE_HOLD_CRQ15(A·B 결과 다름)"}}),
    "PC04_negative_no_cmr": (lambda: pc_pg("PC04", [("Pleuritic chest pain.", "NOTE", 0.4)] + NEGS), 2.0,
                             {("BROAD", "A"): {"GRADE_UNDETERMINED", "POSSIBLE_OR_DEFINITE_UNRESOLVED"}}),
    "PC05_negative_with_cmr": (lambda: pc_pg("PC05", [("Pleuritic chest pain.", "NOTE", 0.4)] + NEGS +
                                             [("Cardiac MRI showed no pericardial late gadolinium enhancement.", "NOTE", 0.9)]), 2.0,
                               {("BROAD", "A"): {"UNLIKELY_REJECTED"}, ("BROAD", "B"): {"UNLIKELY_REJECTED"}}),
    "PC06_presentation_only": (lambda: pc_pg("PC06", [("Pleuritic chest pain.", "NOTE", 0.4)]), 2.0,
                               {("BROAD", "A"): {"GRADE_UNDETERMINED", "POSSIBLE_OR_DEFINITE_UNRESOLVED"}}),
}
POLKEY = {"BROAD": "BROAD(흉통 일반, v5-1)", "STRICT": "STRICT(흉막성·체위성, §4.4.1)", "A": "POLICY_A_FIVE_ITEMS", "B": "POLICY_B_IMAGING_MERGED", "C": "POLICY_C_HOLD_IF_DEPENDS"}


def md_pg(cid, pe_text, ct_text, extra):
    p = PatientGraph522(f"SYN5B-{cid}", "FEMALE")
    p.add_episode(Episode("E1", "CURRENT_EVALUATION"))
    for hid, concept, src in (("h_pe", "DX:Pulmonary embolism", "PHYSICIAN_WORKING_DIAGNOSIS"), ("h_mi", "V5:DX:MI", "PHYSICIAN_ADDITIONAL_HYPOTHESIS"),
                              ("h_peri", "DX:Pericarditis", "PHYSICIAN_ADDITIONAL_HYPOTHESIS")):
        p.add_hypothesis_spec(HypothesisSpec(hid, concept, "E1", src))
    p.add_record52(Doc("n1", pe_text, "NOTE", 0.4, 0.5))
    p.add_record52(Doc("r1", ct_text, "CTPA_REPORT", 1.5, 2.0), None, "CT1")
    for i, o in enumerate(RISE):
        p.add_observation52(o, source_event_id=f"LAB-{cid}-{i}")
    for i, (t, dt, av) in enumerate(extra):
        p.add_record52(Doc(f"x{i}", t, dt, av - 0.1, av))
    return p


MD_CASES = {
    "MD01_pe_neg_pericarditis_injury": (lambda: md_pg("MD01", "Pleuritic chest pain. Pulmonary embolism is suspected. " + EM.PRE("low") + EM.ST, EM.NEG,
                                                      [("ECG showed diffuse ST elevation and PR depression.", "ECG", 0.6), ("CRP 40 mg/L, elevated.", "LAB", 0.7), (RISE_TXT[0], "NOTE", 2.6)]), 3.0),
    "MD02_pe_pos_injury": (lambda: md_pg("MD02", "Pulmonary embolism is suspected. " + EM.PRE("intermediate") + EM.ST, EM.POS,
                                         [("ECG showed T wave inversion in leads V1-V3.", "ECG", 0.6), (RISE_TXT[0], "NOTE", 2.6)]), 3.0),
}


# ---------------- 신규 반례(18 범주) — 기대 동작 실행 전 고정 ----------------
NEW_CE = [
    ("NCE-01", "검사 전 확률 조건 무시", "PE:B01", "SH-CTPA-NEG", {"HOLD"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-02", "혈역학 안정성 조건 무시", "PE:F01", "SH-CTPA-NEG", {"HOLD"}, "CLINICIAN_REVIEW_REQUIRED"),
    ("NCE-03", "YEARS 경로에 3단계 확률 요구", "PE:J01", "SH-DD-YEARS", {"WEAKEN"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-04", "음성 검사 적용 범위 초과(높은 확률)", "PE:A08", "SH-CTPA-NEG", {"HOLD"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-05", "D-dimer 상승을 확진 근거로", "PE:U03", "SH-DD-ELEVATED", {"NODIR"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-06", "근위부 DVT 치료 근거를 PE 확진으로", "PE:U02", "SH-PROX-DVT", {"NODIR"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-07", "치료 후 추적으로 과거 확진 부정", "PE:L01", "SH-CTPA-NEG", {"NA", "HOLD", "NONE"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-08", "ECG 소견 하나로 MI 확진", "MI:MI08", "directional_output", {None}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-09", "트로포닌 상승만으로 MI 확진", "MI:MI06", "directional_output", {None}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-10", "심근손상과 MI 혼동(기록에 MI 언급)", "MI:MI09", "primary_mi_box3", {"ACUTE_INJURY_ONLY"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-11", "심낭염 등급을 방향으로 변환", "PC:PC01", "directional_output", {None}, "RESEARCHER_INTERPRETATION"),
    ("NCE-12", "UNKNOWN 을 FALSE 로(CMR 미시행 0개 → 배제)", "PC:PC04", "grade_BROAD_A", {"GRADE_UNDETERMINED", "POSSIBLE_OR_DEFINITE_UNRESOLVED"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-13", "기록 충돌 무시", "PE:C01", "SH-CTPA-NEG", {"HOLD"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-14", "결과 공개 전 미래정보 사용", "PE:O01", "SH-CTPA-NEG", {"NONE"}, "SOURCE_SUPPORTED_EXPECTATION"),
    ("NCE-15", "동일 검사 반복 서술 독립 계산", "T:Q01_duplicate_same_event", "groups_for_CT1_WEAKEN", {1}, "RESEARCHER_INTERPRETATION"),
    ("NCE-16", "다른 에피소드 증거 혼합", "PE:M02", "SH-CTPA-NEG", {"NONE"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-17", "Shadow 결과를 임상 검증으로 표현", "ALL", "labels", {"NOT_CLINICALLY_VALIDATED"}, "RESEARCHER_INTERPRETATION"),
    ("NCE-18", "출처 없는 방향 판단", "ALL", "directional_without_source", {0}, "RESEARCHER_INTERPRETATION"),
]
# P0 반례 → 이번 사례 대응(실행 전 고정). 토큰 기대는 P0 'expected' 문구를 그대로 옮김.
P0_CE_MAP = {"CE-01": ("B01", "SH-CTPA-NEG", {"HOLD"}), "CE-02": ("D01", "SH-CTPA-NEG", {"WEAKEN"}), "CE-03": ("C01", "SH-CTPA-NEG", {"HOLD"}),
             "CE-04": ("E01", "SH-CTPA-NEG", {"HOLD"}), "CE-05": ("F01", "SH-CTPA-NEG", {"HOLD"}), "CE-06": ("A09", "SH-DD-NORMAL", {"NA"}),
             "CE-07": ("J01", "SH-DD-YEARS", {"WEAKEN"}), "CE-08": ("U07", "SH-DD-NORMAL", {"HOLD"}), "CE-09": ("U08", "SH-DD-NORMAL", {"HOLD"}),
             "CE-11": ("U02", "SH-PROX-DVT", {"NODIR"}), "CE-13": ("A12", "SH-CTPA-POS", {"HOLD", "NONE"}), "CE-28": ("F03", "SH-CTPA-NEG", {"HOLD"})}


def p0_token(text: str) -> str:
    t = text.split("(")[0].split(" ")[0]
    return {"WEAKEN": "WEAKEN", "SUPPORT": "SUPPORT", "HOLD": "HOLD", "UNDETERMINED": "HOLD", "NOT_APPLICABLE": "NA"}.get(t, "UNKNOWN_TOKEN")


def main():
    out = H / "outputs" / RUN_ID
    out.mkdir(parents=True, exist_ok=True)
    reg_before = R52.registry_check()["sha256"]
    cases, comps, policy_rows = {}, {}, {}
    by_id = {}
    for c in EM.CASES:
        pg, L, S, cmp, checks, cmp_check = run_pe_case(c)
        by_id[c["case_id"]] = (c, L, S, cmp)
        cases[c["case_id"]] = {"group": c["group"], "note": c["note"], "policy": c["policy"] or SC.DEFAULT_POLICY, "as_of": c["as_of"], "p0_scenario": c["p0_scenario"],
                               "records": [{"record_id": r[0], "text": r[1], "doc_type": r[2], "available_at": r[4], "episode": r[5], "meta": r[6]} for r in c["records"]],
                               "expectation_checks": checks, "comparison_check": cmp_check,
                               "legacy": L["judgments"], "shadow": S["judgments"], "shadow_contexts": S["contexts"]}
        comps[c["case_id"]] = cmp
        if c["group"] in ("C", "D", "E", "F", "J", "U"):
            policy_rows[c["case_id"]] = policy_sensitivity(c)
    # P0 진리표 대조
    p0rows = list(csv.DictReader(open(P0 / "knowledge/v5_2b_p0_condition_matrix.csv", encoding="utf-8")))
    relmap = {"PE-CTPA-NEGATIVE": "SH-CTPA-NEG", "PE-CTPA-POSITIVE": "SH-CTPA-POS", "PE-DDIMER-NORMAL(ELISA·연령보정)": "SH-DD-NORMAL"}
    p0cmp = []
    for row in p0rows:
        rel = relmap[row["relation"]]
        hit = [cid for cid, (c, *_r) in by_id.items() if c["p0_scenario"] == row["scenario"] and rel in c["expect"] and not c["policy"]]
        if not hit:
            p0cmp.append({**{k: row[k] for k in ("scenario", "relation", "candidate_outcome", "expectation_basis")}, "case": None, "status": "NO_MATCHING_CASE"})
            continue
        S = by_id[hit[0]][2]
        act = sorted({EM.token(j["direction"]) for j in S["judgments"] if j["relation_id"] == rel}) or ["NONE"]
        exp = p0_token(row["candidate_outcome"])
        p0cmp.append({**{k: row[k] for k in ("scenario", "relation", "candidate_outcome", "expectation_basis")}, "case": hit[0], "p0_token": exp, "shadow_actual": act,
                      "status": "AGREE" if act == [exp] else ("P0_UNDETERMINED" if exp == "UNKNOWN_TOKEN" else "DISAGREE")})
    p0ce = json.loads((P0 / "knowledge/v5_2b_p0_relation_review.json").read_text())["counterexamples"]
    p0ce_out = []
    for ce in p0ce:
        m = P0_CE_MAP.get(ce["counterexample_id"])
        if not m:
            p0ce_out.append({**ce, "mapped_case": None, "status": "NOT_EXECUTED_IN_PE_SHADOW(ACS·MI·심낭염·다질환 반례는 해당 연구 단계에서 대응)"})
            continue
        cid, rel, exp = m
        S, L = by_id[cid][2], by_id[cid][1]
        act = sorted({EM.token(j["direction"]) for j in S["judgments"] if j["relation_id"] == rel}) or ["NONE"]
        lact = sorted({CMP.ltoken(j) for j in L["judgments"] if SC.LEGACY_MAP.get(j["relation_id"]) == rel}) or ["NONE"]
        p0ce_out.append({"case_id": ce["counterexample_id"], "tested_relation": rel, "input": cid, "expected_behavior": sorted(exp), "expected_behavior_basis": ce["expectation_basis"],
                         "actual_shadow": act, "actual_legacy": lact, "discrepancy_shadow": not set(act) <= exp, "discrepancy_legacy": not set(lact) <= exp,
                         "source_reference": ce["candidate"], "review_status": "CLINICIAN_REVIEW_PENDING"})
    # 시간·중복·정정
    tg = TP.run_temporal("graph")
    tchecks = temporal_checks(tg, by_id)
    # Graph vs Flat
    gf = {cid: GF.compare_case(EM.build_pg(c), c["as_of"], c["policy"]) for cid, (c, *_r) in by_id.items()}
    gf_t = GF.compare_temporal()
    # ACS·MI / 심낭염 / 다질환
    mi, pc, md = {}, {}, {}
    for cid, (fn, t, exp) in MI_CASES.items():
        r = MD.mi_research(fn(), t)
        rc = r[0]["research_classification"] if r else {}
        isch = r[0]["ischaemia_evidence"]["symptoms"] if r else ""
        chk = {}
        for k, v in exp.items():
            a = isch if k == "ischaemia_symptoms" else rc.get(k)
            chk[k] = {"expected": sorted(v) if isinstance(v, set) else v, "actual": a,
                      "pass": (a in v) if isinstance(v, set) else str(a).startswith(v)}
        mi[cid] = {"result": r, "checks": chk}
    for cid, (fn, t, exp) in PC_CASES.items():
        r = MD.pericarditis_research(fn(), t)
        chk = {}
        for (pp, ip), allowed in exp.items():
            a = r[0]["policies"][POLKEY[pp]][POLKEY[ip]]
            chk[f"{pp}|{ip}"] = {"expected": sorted(allowed), "actual": a, "pass": a in allowed}
        pc[cid] = {"result": r, "checks": chk}
    for cid, (fn, t) in MD_CASES.items():
        pg = fn()
        md[cid] = MD.comparison(pg, t, SR.evaluate(pg, t, "graph"))
    new_ce = new_counterexamples(by_id, tg, mi, pc)
    reg_after = R52.registry_check()
    payload = {
        "shadow_cases.json": {"run_id": RUN_ID, "cases": cases, "policy_sensitivity": policy_rows},
        "legacy_shadow_comparison.json": {"run_id": RUN_ID, "comparisons": comps, "p0_matrix_agreement": p0cmp, "p0_counterexamples": p0ce_out},
        "temporal_dependency_comparison.json": {"run_id": RUN_ID, "graph": tg, "checks": tchecks, "fabricated_raw": TP.fabricated_check()},
        "graph_flat_comparison.json": {"run_id": RUN_ID, "pe_cases": gf, "temporal": gf_t},
        "multidisease_research.json": {"run_id": RUN_ID, "acs_mi": mi, "pericarditis": pc, "multi_disease": md},
        "rule_discrepancy_analysis.json": {"run_id": RUN_ID, "new_counterexamples": new_ce, "summary": summarize(comps, cases, p0cmp, gf, gf_t, tchecks, mi, pc, new_ce, p0ce_out),
                                           "registry": {"n": reg_after["n"], "active": reg_after["engine_active_true"], "unchanged": reg_before == reg_after["sha256"]}},
    }
    for fn, obj in payload.items():
        (out / fn).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (H / "knowledge").mkdir(exist_ok=True)
    (H / "knowledge" / "shadow_pe_relations.json").write_text(json.dumps({"engine": "PE_SHADOW_RESEARCH", "engine_active": False, "policies": {"haemo": SC.HAEMO_POLICIES,
                                                                          "pretest": SC.PRETEST_POLICIES, "default": SC.DEFAULT_POLICY}, "relations": SC.catalog_rows()},
                                                                         ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write_matrix(cases)
    s = payload["rule_discrepancy_analysis.json"]["summary"]
    print(json.dumps({k: s[k] for k in ("pe_cases", "pe_expectation_checks", "comparison_categories", "graph_flat", "temporal_checks", "mi_checks", "pc_checks",
                                        "new_counterexamples", "p0_matrix")}, ensure_ascii=False))


def temporal_checks(tg, by_id):
    def last(cid):
        return tg[cid]["history"][-1]
    p1 = tg["P01_correction"]["history"]
    p2 = tg["P02_correction_with_context_change"]
    q = last("Q01_duplicate_same_event")
    ct1_weaken = [g for g in q["groups"] if g["source_event_id"] == "CT1" and g["directional_result"] == "WEAKEN"]
    return {
        "1_duplicate_not_independent": {"pass": len(ct1_weaken) == 1 and len(ct1_weaken[0]["raw_judgment_ids"]) >= 2, "groups": len(ct1_weaken)},
        "2_no_event_dependency_unknown": {"pass": all(g["dependency_status"] == "DEPENDENCY_UNKNOWN" for g in last("T01_no_event_metadata")["groups"])},
        "3_correction_vs_context_separated": {"pass": p2["counterfactual"]["fixed_context_identical"] and "n2" in p2["counterfactual"]["fixed_context_record_ids"],
                                              "before": p2["counterfactual"]["before_result"], "after": p2["counterfactual"]["after_result"]},
        "4_other_episode_not_applied": {"pass": by_id["M02"][2]["judgments"] == []},
        "5_no_future_results": {"pass": by_id["O01"][2]["judgments"] == [] and all(j["source_record_id"] != "r1c" for j in p1[1]["shadow"])},
        "6_counterfactual_labelled": {"pass": tg["P01_correction"]["counterfactual"]["historical_status"] == "NOT_HISTORICAL_OBSERVATION"
                                      and tg["P01_correction"]["counterfactual"]["causal_status"] == "NOT_CAUSAL_PROOF"},
        "7_event_vs_patient_not_confused": {"pass": all("history" in tg[c] for c in tg), "note": "사건별 귀속은 v5-2A.2 event_history 규칙, 여기서는 그룹·정정 재생만 연결"},
        # 정정(2026-11-09): 처음 p1[0](as_of 3.0, r1 공개 4.0 전)에 SUPPORT 를 기대한 것은 검사 작성 오류 — 공개 전 판단 없음 + 5.0 SUPPORT + 8.0 WEAKEN 으로 강화
        "8_shadow_follows_time_policy": {"pass": p1[0]["shadow"] == [] and [x["direction"] for x in p1[1]["shadow"] if x["relation_id"] == "SH-CTPA-POS"] == ["SUPPORT"]
                                         and [x["direction"] for x in p1[2]["shadow"] if x["relation_id"] == "SH-CTPA-NEG"] == ["WEAKEN"]
                                         and not any(x["source_record_id"] == "r1" for x in p1[2]["shadow"])},
        "conflict_same_event_detected": {"pass": len(last("R01_same_event_conflict")["conflicts"]) >= 1 or
                                         any(g["dependency_status"] == "DERIVED_FROM_SAME_EVENT" for g in last("R01_same_event_conflict")["groups"])},
        "distinct_events_not_merged": {"pass": len([g for g in last("S01_distinct_events")["groups"] if g["directional_result"] == "WEAKEN"]) == 2},
    }


def new_counterexamples(by_id, tg, mi, pc):
    rows = []
    for cid, title, ref, target, exp, basis in NEW_CE:
        kind, _, key = ref.partition(":")
        if kind in ("MI", "PC"):
            key = next(k for k in (mi if kind == "MI" else pc) if k.split("_")[0] == key)
        if kind == "PE":
            S, L = by_id[key][2], by_id[key][1]
            act = sorted({EM.token(j["direction"]) for j in S["judgments"] if j["relation_id"] == target}) or ["NONE"]
            lact = sorted({CMP.ltoken(j) for j in L["judgments"] if SC.LEGACY_MAP.get(j["relation_id"]) == target}) or ["NONE"]
            ok, lok = set(act) <= exp, set(lact) <= exp
        elif kind == "MI":
            r = mi[key]["result"][0]
            act = [r["directional_output"]] if target == "directional_output" else [r["research_classification"][target].split("(")[0]]
            lact, ok, lok = ["N/A"], set(act) <= exp, None
        elif kind == "PC":
            r = pc[key]["result"][0]
            act = [r["directional_output"]] if target == "directional_output" else [r["policies"][POLKEY["BROAD"]][POLKEY["A"]]]
            lact, ok, lok = ["N/A"], set(act) <= exp, None
        elif kind == "T":
            q = tg[key]["history"][-1]
            act = [len([g for g in q["groups"] if g["source_event_id"] == "CT1" and g["directional_result"] == "WEAKEN"])]
            lact, ok, lok = ["N/A"], set(act) <= exp, None
        else:
            alls = [j for (_c, _l, S, _m) in by_id.values() for j in S["judgments"]]
            if target == "labels":
                act = sorted({"NOT_CLINICALLY_VALIDATED" if "NOT_CLINICALLY_VALIDATED" in j["labels"] else "MISSING" for j in alls})
            else:
                act = [sum(1 for j in alls if j["direction"] in ("SUPPORT", "WEAKEN") and not j["applied_sources"])]
            lact, ok, lok = ["N/A"], set(act) <= exp, None
        rows.append({"case_id": cid, "tested_relation": target, "input": ref, "title": title, "expected_behavior": sorted(map(str, exp)), "expected_behavior_basis": basis,
                     "actual_behavior": act, "actual_legacy": lact, "discrepancy": not ok, "legacy_discrepancy": (None if lok is None else not lok),
                     "source_reference": "relation_review(P0)·shadow_pe_relations", "review_status": "CLINICIAN_REVIEW_PENDING"})
    return rows


def summarize(comps, cases, p0cmp, gf, gf_t, tchecks, mi, pc, new_ce, p0ce):
    allc = [r for v in comps.values() for r in v]
    exp = [x for v in cases.values() for x in v["expectation_checks"].values()]
    cmpc = [v["comparison_check"] for v in cases.values() if v["comparison_check"]]
    return {"pe_cases": len(cases), "pe_judgments": {"legacy": sum(len(v["legacy"]) for v in cases.values()), "shadow": sum(len(v["shadow"]) for v in cases.values())},
            "pe_expectation_checks": {"total": len(exp), "pass": sum(x["pass"] for x in exp), "by_basis": dict(Counter(x["basis"] for x in exp)),
                                      "fail_ids": [cid for cid, v in cases.items() for r, x in v["expectation_checks"].items() if not x["pass"]]},
            "comparison_expectation_checks": {"total": len(cmpc), "pass": sum(x["pass"] for x in cmpc)},
            "comparison_categories": dict(Counter(r["category"] for r in allc)),
            "candidate_flags": dict(Counter(r["candidate_flag"] for r in allc if r["candidate_flag"])),
            "drivers": dict(Counter(d.split(":")[0].split("(")[0] for r in allc for d in r["drivers"])),
            "shadow_review_required": sum(1 for v in cases.values() for j in v["shadow"] if j["clinician_review_required"]),
            "graph_flat": {"pe_cases": len(gf), "legacy_identical": sum(v["legacy"]["identical"] for v in gf.values()),
                           "shadow_identical": sum(v["shadow"]["identical"] for v in gf.values()), "comparison_identical": sum(v["comparison"]["identical"] for v in gf.values()),
                           "temporal_identical": gf_t["identical"]},
            "temporal_checks": {k: v["pass"] for k, v in tchecks.items()},
            "mi_checks": {"total": sum(len(v["checks"]) for v in mi.values()), "pass": sum(x["pass"] for v in mi.values() for x in v["checks"].values()),
                          "fail": [f"{c}:{k}" for c, v in mi.items() for k, x in v["checks"].items() if not x["pass"]]},
            "pc_checks": {"total": sum(len(v["checks"]) for v in pc.values()), "pass": sum(x["pass"] for v in pc.values() for x in v["checks"].values()),
                          "fail": [f"{c}:{k}" for c, v in pc.items() for k, x in v["checks"].items() if not x["pass"]]},
            "new_counterexamples": {"total": len(new_ce), "shadow_discrepancy": sum(r["discrepancy"] for r in new_ce),
                                    "legacy_discrepancy": sum(1 for r in new_ce if r["legacy_discrepancy"]), "legacy_discrepancy_ids": [r["case_id"] for r in new_ce if r["legacy_discrepancy"]]},
            "p0_counterexamples": {"mapped": sum(1 for r in p0ce if r.get("input")), "shadow_discrepancy": sum(1 for r in p0ce if r.get("discrepancy_shadow")),
                                   "legacy_discrepancy": sum(1 for r in p0ce if r.get("discrepancy_legacy")), "not_executed": sum(1 for r in p0ce if not r.get("input"))},
            "p0_matrix": dict(Counter(r["status"] for r in p0cmp)),
            "note": "합성 사례 기준 규칙 적합성·구현 일관성. 임상 정확도·민감도·특이도·AUROC 아님"}


def write_matrix(cases):
    rows = []
    for cid, v in cases.items():
        for rel, x in v["expectation_checks"].items():
            rows.append({"case_id": cid, "group": v["group"], "policy": json.dumps(v["policy"], ensure_ascii=False), "relation": rel, "expected": "|".join(x["expected"]),
                         "basis": x["basis"], "shadow_actual": "|".join(x["actual"]), "pass": x["pass"], "p0_scenario": v["p0_scenario"] or "",
                         "legacy_actual": "|".join(sorted({CMP.ltoken(j) for j in v["legacy"] if SC.LEGACY_MAP.get(j["relation_id"]) == rel}) or ["NONE"])})
    with open(H / "knowledge" / "shadow_condition_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
