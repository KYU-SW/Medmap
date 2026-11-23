"""v5-1 실행: CASE 01~20(합성 환자·의학 의미 없는 순수 논리 사례 구분), 그래프 vs 평면표, v5-0B 레지스트리 호환성.
결과 outputs/v5_1_cases.json, v5_1_compare.json, v5_1_registry_compat.json. 기술 검증용. 임상 정확도 NOT_EVALUATED."""
import hashlib
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid5 import classification as CL, concepts as CN, ecg as EC, logic as L, observations as OB  # noqa: E402
from hybrid5.flat import evaluate_flat  # noqa: E402
from hybrid5.graphs import PatientGraph5, Reasoner5  # noqa: E402
from hybrid4.graphs import Doc, Episode, Hypothesis  # noqa: E402

PE, ACS, MI, PERI = "DX:Pulmonary embolism", "V5:DX:ACS", "V5:DX:MI", "DX:Pericarditis"
REG = H.parent / "hybrid_reassessment_v5_0/knowledge/v5_0_evidence_candidates.json"
R5 = Reasoner5()


def pg_(pid, sex="UNKNOWN", eps=("E1",)):
    p = PatientGraph5(f"SYN-{pid}", sex)
    for e in eps:
        p.add_episode(Episode(e, "CURRENT_EVALUATION"))
    return p


def H5(hid, concept, ep="E1", at=0.0, **kw):
    return CN.MultiHypothesis(hid, concept, ep, at, **kw)


def trop(oid, t, val, unit="ng/L", analyte="TROPONIN_T", assay="HIGH_SENSITIVITY", ref=14.0, pop="FEMALE", avail=None, sup=None, rec="lab", cmp="="):
    return OB.Observation(oid, "", "", analyte, f"{val} {unit}", float(val), cmp, unit, t, avail if avail is not None else t + 0.5, rec, assay_type=assay,
                          reference_upper=ref, reference_unit=unit if ref is not None else "UNKNOWN", reference_percentile="99th" if ref is not None else "UNKNOWN",
                          reference_population=pop if ref is not None else "UNKNOWN", supersedes=sup, test_name=analyte)


CASES = {}


def case(f):
    CASES[f.__name__] = f
    return f


@case
def C01_three_hypotheses():
    p = pg_("C01")
    for h in (H5("h_pe", PE, diagnosis_status="PHYSICIAN_SUSPECTED"), H5("h_acs", ACS, diagnosis_status="PHYSICIAN_SUSPECTED"), H5("h_peri", PERI, diagnosis_status="PHYSICIAN_SUSPECTED")):
        p.add_multi_hypothesis(h)
    p.add_hypothesis(Hypothesis("h_pe", "Pulmonary embolism", PE, 0.0, episode_id="E1"), True)   # 레거시 v4 PE 경로
    p.add_record(Doc("n1", "Pleuritic chest pain. Pulmonary embolism is suspected. Clinical probability was assessed as intermediate using the Wells score. "
                           "The patient is hemodynamically stable.", "NOTE", 0.5, 1.0))
    p.add_record(Doc("r1", "IMPRESSION: No evidence of pulmonary embolism.", "CTPA_REPORT", 2.0, 4.0))
    return p, [5.0]


@case
def C02_axes():
    p = pg_("C02")
    p.add_multi_hypothesis(H5("h_mi", MI, diagnosis_status="PHYSICIAN_CONFIRMED", physician_confirmation_status="CONFIRMED", presentation_axis="NSTEMI", mechanism_axis="SECONDARY"))
    p.add_record(Doc("n1", "Final diagnosis: NSTEMI. A type 2 MI was documented at the outside hospital.", "NOTE", 0.5, 1.0))
    return p, [2.0]


@case
def C03_troponin_series():
    p = pg_("C03", "FEMALE")
    p.add_multi_hypothesis(H5("h_acs", ACS, diagnosis_status="PHYSICIAN_SUSPECTED"))
    for i, (t, v) in enumerate(((0.0, 18), (1.0, 35), (3.0, 52))):
        p.add_observation(trop(f"OBS:t{i}", t, v))
    return p, [4.0]


@case
def C03b_troponin_series_with_reported_rise():
    p, ts = C03_troponin_series()
    p.add_record(Doc("n2", "Troponin rose from 18 to 52 ng/L over 3 hours.", "NOTE", 3.5, 3.6))
    return p, ts


@case
def C04_different_assays():
    p = pg_("C04", "FEMALE")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_observation(trop("OBS:a", 0.0, 20))
    p.add_observation(trop("OBS:b", 1.0, 0.05, unit="ng/mL", analyte="TROPONIN_I", assay="UNKNOWN", ref=None))
    p.add_observation(trop("OBS:c", 2.0, 30, assay="UNKNOWN"))
    return p, [3.0]


@case
def C05_different_units():
    p = pg_("C05")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_record(Doc("l1", "Troponin I 0.08 ng/mL.", "LAB", 0.0, 0.5))
    p.add_record(Doc("l2", "Troponin I 80 ng/L.", "LAB", 2.0, 2.5))
    return p, [3.0]


@case
def C06_no_reference():
    p = pg_("C06", "MALE")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_record(Doc("l1", "High-sensitivity troponin T was 30 ng/L.", "LAB", 0.0, 0.5))
    return p, [1.0]


@case
def C07_diffuse_ste():
    p = pg_("C07")
    p.add_multi_hypothesis(H5("h_peri", PERI, diagnosis_status="PHYSICIAN_SUSPECTED"))
    p.add_record(Doc("n1", "Sharp chest pain worse on inspiration.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0))
    return p, [2.0]


@case
def C08_unclear_leads():
    p = pg_("C08")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_record(Doc("e1", "ECG: ST elevation in some leads.", "ECG", 0.5, 1.0))
    return p, [2.0]


@case
def C10b_pericarditis_all_negative():
    p = pg_("C10b")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "Chest pain. No pericardial friction rub. No pericardial effusion on echocardiography.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("e1", "ECG was normal.", "ECG", 0.5, 1.0))
    p.add_record(Doc("l1", "CRP 2 mg/L, normal.", "LAB", 0.5, 1.0))
    p.add_record(Doc("m1", "Cardiac MRI showed no pericardial late gadolinium enhancement.", "NOTE", 1.0, 1.5))
    return p, [2.0]


@case
def C10c_pericarditis_not_recorded():
    p = pg_("C10c")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "Chest pain.", "NOTE", 0.0, 0.5))
    return p, [1.0]


@case
def C11_conflict():
    p = pg_("C11")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "Chest pain. A pericardial friction rub was heard.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("n2", "No pericardial friction rub.", "NOTE", 0.2, 0.7))
    p.add_record(Doc("l1", "CRP 40 mg/L, elevated.", "LAB", 0.5, 1.0))
    return p, [2.0]


@case
def C12_duplicate_criterion():
    p = pg_("C12")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "Chest pain.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("l1", "CRP 40 mg/L, elevated.", "LAB", 0.5, 1.0))
    p.add_record(Doc("l2", "CRP 55 mg/L, elevated.", "LAB", 1.0, 1.5))
    return p, [2.0]


@case
def C13_no_presentation():
    p = pg_("C13")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "A pericardial friction rub was heard.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("l1", "CRP 40 mg/L, elevated.", "LAB", 0.5, 1.0))
    return p, [2.0]


@case
def C14_pericarditis_definite_research():
    p = pg_("C14")
    p.add_multi_hypothesis(H5("h_peri", PERI, diagnosis_status="PHYSICIAN_SUSPECTED"))
    p.add_record(Doc("n1", "Pleuritic chest pain. A pericardial friction rub was heard. No pericardial effusion on echocardiography.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0))
    p.add_record(Doc("l1", "CRP 40 mg/L (reference < 5 mg/L), elevated.", "LAB", 0.5, 1.0))
    return p, [2.0]


@case
def C14b_pericarditis_possible_research():
    p = pg_("C14b")
    p.add_multi_hypothesis(H5("h_peri", PERI))
    p.add_record(Doc("n1", "Chest pain. No pericardial friction rub. No pericardial effusion on echocardiography.", "NOTE", 0.0, 0.5))
    p.add_record(Doc("e1", "ECG was normal.", "ECG", 0.5, 1.0))
    p.add_record(Doc("l1", "CRP 40 mg/L, elevated.", "LAB", 0.5, 1.0))
    p.add_record(Doc("m1", "Cardiac MRI showed no pericardial late gadolinium enhancement.", "NOTE", 1.0, 1.5))
    return p, [2.0]


@case
def C15_late_result():
    p = pg_("C15", "FEMALE")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_observation(trop("OBS:early", 0.0, 10, avail=0.5))
    p.add_observation(trop("OBS:late", 1.0, 40, avail=5.0))
    return p, [4.0, 5.0]


@case
def C16_corrected_troponin():
    p = pg_("C16", "FEMALE")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_observation(trop("OBS:v1", 0.0, 12, avail=0.5))
    p.add_observation(trop("OBS:v2", 1.0, 95, avail=1.5))
    p.add_observation(trop("OBS:v2c", 1.0, 25, avail=3.0, sup="OBS:v2"))
    return p, [2.0, 3.0]


@case
def C17_candidates_vs_working_dx():
    p = pg_("C17")
    p.add_multi_hypothesis(H5("h_peri", PERI, diagnosis_status="PHYSICIAN_CONFIRMED", physician_confirmation_status="CONFIRMED"))
    p.add_record(Doc("n1", "NSTEMI was diagnosed at an outside hospital. History of myocardial infarction.", "NOTE", 0.0, 0.5))
    return p, [1.0]


@case
def C20_unsupported():
    p = pg_("C20")
    p.add_multi_hypothesis(H5("h_acs", ACS))
    p.add_record(Doc("n1", "Echocardiography suggested Takotsubo cardiomyopathy. ECG showed a Brugada pattern.", "NOTE", 0.0, 0.5))
    return p, [1.0]


def pure_logic():
    """CASE 09·10·11·12: 의학 의미 없는 합성 조건(K-of-N 의미 검증)."""
    def F(k, v):
        return L.Fact(k, "FOUND", v, (v,), (f"src:{k}",)) if v in (True, False) else L.Fact(k, "CONFLICT", None, (True, False), (f"a:{k}", f"b:{k}")) if v == "C" else L.Fact(k, "NOT_FOUND")
    items = tuple((f"c{i}", L.Atom(f"c{i}", (True,))) for i in range(5))

    def run(vals, op, k):
        r = L.eval_kofn(L.KofN("syn", op, k, items), {f"c{i}": F(f"c{i}", v) for i, v in enumerate(vals)})
        return {x: r[x] for x in ("value", "undetermined_reason", "confirmed_true_count", "confirmed_false_count", "unknown_count", "conflict_count", "minimum_true", "maximum_possible_true", "unresolved_conditions")}
    out = {"C09_2T_3U": {"AT_LEAST_2": run([True, True, None, None, None], "AT_LEAST_K", 2), "AT_LEAST_3": run([True, True, None, None, None], "AT_LEAST_K", 3),
                         "EXACTLY_2": run([True, True, None, None, None], "EXACTLY_K", 2)},
           "C09b_2T_1F_2U": {"AT_LEAST_2": run([True, True, False, None, None], "AT_LEAST_K", 2), "AT_LEAST_3": run([True, True, False, None, None], "AT_LEAST_K", 3)},
           "C10_all_false": {"AT_LEAST_1": run([False] * 5, "AT_LEAST_K", 1), "EXACTLY_0": run([False] * 5, "EXACTLY_K", 0)},
           "C10_1T_4F": {"EXACTLY_1": run([True, False, False, False, False], "EXACTLY_K", 1)},
           "C10_all_unknown": {"EXACTLY_0": run([None] * 5, "EXACTLY_K", 0)},
           "C11_conflict_only": {"AT_LEAST_2": run([True, "C", False, False, False], "AT_LEAST_K", 2)},
           "C11_conflict_and_unknown": {"AT_LEAST_3": run([True, "C", None, False, False], "AT_LEAST_K", 3)}}
    try:
        L.KofN("dup", "AT_LEAST_K", 1, (("c1", L.Atom("c1", (True,))), ("c1", L.Atom("c1", (True,)))))
        out["C12_duplicate_ids"] = "NOT_REJECTED(오류)"
    except ValueError as e:
        out["C12_duplicate_ids"] = f"REJECTED: {e}"
    return out


def registry_compat():
    j = json.loads(REG.read_text(encoding="utf-8"))
    M = {"ACS5-01": ["NEEDS_CLINICAL_REVIEW"], "ACS5-02": ["STRUCTURALLY_COMPATIBLE"], "ACS5-03": ["NEEDS_CONTEXT_FIELD", "NEEDS_CLINICAL_REVIEW"], "ACS5-04": ["NEEDS_CONTEXT_FIELD"],
         "ACS5-05": ["NEEDS_CONTEXT_FIELD", "NEEDS_CLINICAL_REVIEW"], "ACS5-07": ["NEEDS_CONTEXT_FIELD"], "ACS5-08": ["NEEDS_CONTEXT_FIELD"], "ACS5-09": ["NEEDS_TEMPORAL_INPUT", "NEEDS_CLINICAL_REVIEW"],
         "ACS5-11": ["NEEDS_CONTEXT_FIELD"], "ACS5-12": ["NEEDS_NUMERIC_INPUT"], "ACS5-13": ["NEEDS_TEMPORAL_INPUT"], "ACS5-14": ["NEEDS_CONTEXT_FIELD"],
         "PE5-01": ["NEEDS_CONTEXT_FIELD"], "PE5-03": ["NEEDS_CONTEXT_FIELD"], "PE5-04": ["NEEDS_CONTEXT_FIELD"], "PE5-07": ["STRUCTURALLY_COMPATIBLE"], "PE5-08": ["STRUCTURALLY_COMPATIBLE"],
         "PERI5-01": ["STRUCTURALLY_COMPATIBLE", "NEEDS_CLINICAL_REVIEW"], "PERI5-02": ["STRUCTURALLY_COMPATIBLE", "NEEDS_CLINICAL_REVIEW"], "PERI5-04": ["STRUCTURALLY_COMPATIBLE"],
         "PERI5-05": ["STRUCTURALLY_COMPATIBLE"], "PERI5-06": ["STRUCTURALLY_COMPATIBLE"], "PERI5-07": ["STRUCTURALLY_COMPATIBLE"], "PERI5-08": ["STRUCTURALLY_COMPATIBLE"],
         "PERI5-09": ["NEEDS_CONTEXT_FIELD"], "PERI5-10": ["NEEDS_CONTEXT_FIELD"], "PERI5-11": ["NEEDS_TEMPORAL_INPUT"], "PERI5-12": ["STRUCTURALLY_COMPATIBLE"]}
    WHY = {"ACS5-01": "손상 분류 구현. 상승·하강 '유의성' 기준이 원문에 없어 기록 진술만 사용", "ACS5-03": "허혈 증상 판정 필드 없음", "ACS5-04": "영상 관상동맥 병변·벽운동 필드 없음",
           "ACS5-07": "안정 상태는 명시 문구만", "ACS5-08": "증상 양상(안정 시·악화) 필드 없음", "ACS5-09": "채혈 시점 기준 원문 수치 없음", "ACS5-11": "rule-in/out 알고리즘 결과 문구 추출 없음",
           "ACS5-12": "유도별 mm·성별·연령 기준 적용 안 함(mm 값만 추출)", "ACS5-13": "지표 MI 와 재발 에피소드 연결 필요", "ACS5-14": "관상동맥 비폐쇄 판독 필드 없음",
           "PE5-01": "활력징후(SBP·승압제·저관류) 추출 없음", "PE5-03": "입원 여부 필드 없음", "PE5-04": "임신 필드 없음", "PERI5-01": "K-of-N·등급 구현(연구용). 등급→방향 연결은 전문의 검토",
           "PERI5-02": "위와 같음", "PERI5-09": "TTE 정상 소견 추출 없음", "PERI5-10": "좌심실 기능 새 장애 필드 없음", "PERI5-11": "경과(관해 후 재발) 시점 필드 없음"}
    rows = []
    for c in j["candidates"]:
        st = ["DO_NOT_ACTIVATE"] if c["v5_0b_group"] == "C" else M[c["candidate_id"]]
        rows.append({"candidate_id": c["candidate_id"], "v5_0b_group": c["v5_0b_group"], "v5_1_status": st, "reason": WHY.get(c["candidate_id"], c["v5_0b_group_reason"] if c["v5_0b_group"] == "C" else ""),
                     "engine_active": c["engine_active"], "activated_in_v5_1": False})
    return {"registry_sha256": hashlib.sha256(REG.read_bytes()).hexdigest(), "n": len(rows), "ids": sorted(r["candidate_id"] for r in rows),
            "active_in_registry": sum(r["engine_active"] for r in rows), "activated_in_v5_1": 0, "rows": rows}


def strip(r):
    return json.dumps(r, sort_keys=True, default=str, ensure_ascii=False).replace('"mode": "graph"', '"mode": "X"').replace('"mode": "flat"', '"mode": "X"')


if __name__ == "__main__":
    res, cmp_ = {}, []
    for name, f in CASES.items():
        p, ts = f()
        res[name] = {"graph_stats": p.g.stats(), "states": []}
        for t in ts:
            g = R5.evaluate(p, t)
            legacy = {h["hyp_id"]: h["legacy_v4"]["items"] for h in g["hypotheses"] if "legacy_v4" in h}
            fl = evaluate_flat(p, t, legacy)
            res[name]["states"].append(g)
            cmp_.append({"case": name, "as_of": t, "identical": strip(g) == strip(fl)})
    res["PURE_LOGIC_C09_C12"] = pure_logic()
    try:
        CN.MultiHypothesis("x", "DX:Aortic dissection", "E1", 0.0)
        res["C20_unsupported_hypothesis"] = "ACCEPTED(오류)"
    except ValueError as e:
        res["C20_unsupported_hypothesis"] = f"REJECTED: {e}"
    try:
        CN.MultiHypothesis("x", MI, "E1", 0.0, mechanism_axis="STEMI")
        res["C02_axis_mixing"] = "ACCEPTED(오류)"
    except ValueError as e:
        res["C02_axis_mixing"] = f"REJECTED: {e}"
    reg = registry_compat()
    (H / "outputs/v5_1_cases.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (H / "outputs/v5_1_compare.json").write_text(json.dumps({"rows": cmp_, "all_identical": all(x["identical"] for x in cmp_), "n": len(cmp_)}, ensure_ascii=False, indent=1), encoding="utf-8")
    (H / "outputs/v5_1_registry_compat.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, v in res.items():
        if not isinstance(v, dict) or "states" not in v:
            print("==", name, json.dumps(v, ensure_ascii=False)[:900])
            continue
        for st in v["states"]:
            for h in st["hypotheses"]:
                cls = [{k: c.get(k) for k in ("guideline_classification", "criteria_count_range", "uncertainty_state", "acute_injury", "chronic_injury_considered", "criteria_states", "imaging_count_sensitivity")} for c in h["classifications"]]
                pairs = [(s["analyte"], [(p["from"], p["to"], p["comparable"], p["abs_delta"], p["delta_status"][:40]) for p in s["pairs"]], [(p["obs_id"], p["reference_check"]["status"], p["reference_check"].get("sex_specific_reference")) for p in s["points"]]) for s in h["series"]]
                print(f"== {name}@{st['as_of']} {h['hyp_id']} {h['concept_id']} [{h['diagnosis_status']}] pres={h['presentation_axis']} mech={h['mechanism_axis']} sup={h['supporting_evidence_ids']} weak={h['weakening_evidence_ids']}")
                if pairs:
                    print("    series", pairs)
                if h["ecg_findings"]:
                    print("    ecg", [(f["finding_type"], f["assertion_status"], f["lead_or_distribution"], f["notes"]) for f in h["ecg_findings"]])
                if cls:
                    print("    cls", json.dumps(cls, ensure_ascii=False, default=str)[:700])
                if h["ai_candidates_unconfirmed"]:
                    print("    cand", [(c["concept_id"], c["attributes"], c["assertion"], c["diagnosis_status"]) for c in h["ai_candidates_unconfirmed"]])
                if h.get("legacy_v4"):
                    print("    legacy", h["legacy_v4"])
                if h["excluded_by_v5_override"] or h["unresolved_episode_link_ids"]:
                    print("    override/unresolved", h["excluded_by_v5_override"], h["unresolved_episode_link_ids"])
    print("graph==flat", all(x["identical"] for x in cmp_), len(cmp_), "registry", reg["n"], "active", reg["active_in_registry"], reg["activated_in_v5_1"])
