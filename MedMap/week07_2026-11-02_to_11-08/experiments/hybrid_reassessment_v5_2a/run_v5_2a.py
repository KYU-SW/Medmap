"""v5-2A 실행: CASE 01~28 합성 사례 → 그래프·평면표 비교, 중복·종속, 레지스트리 보존.
결과 outputs/v5_2a_cases.json, v5_2a_comparison.json, v5_2a_graph_flat.json, v5_2a_dependency.json. 기술 검증용. 임상 성능 NOT_EVALUATED."""
import hashlib
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid52 import report as RP  # noqa: E402
from hybrid52.flat import compare_flat  # noqa: E402
from hybrid52.graphs import PatientGraph52  # noqa: E402
from hybrid52.hypotheses import HypothesisSpec  # noqa: E402
from hybrid4 import logic as LG4  # noqa: E402
from hybrid4.graphs import Doc, Episode  # noqa: E402
from hybrid5 import logic as L  # noqa: E402
from hybrid5 import observations as OB  # noqa: E402

PE, ACS, MI, PERI, INJ = "DX:Pulmonary embolism", "V5:DX:ACS", "V5:DX:MI", "DX:Pericarditis", "V5:STATE:ACUTE_MYOCARDIAL_INJURY"
REG = H.parent / "hybrid_reassessment_v5_0/knowledge/v5_0_evidence_candidates.json"
SUSP = "Pulmonary embolism is suspected. Clinical probability was assessed as intermediate using the Wells score. The patient is hemodynamically stable."
NEG = "IMPRESSION: No evidence of pulmonary embolism."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
WD, ADD, AI = "PHYSICIAN_WORKING_DIAGNOSIS", "PHYSICIAN_ADDITIONAL_HYPOTHESIS", "AI_CANDIDATE_UNCONFIRMED"


def pg_(pid, sex="UNKNOWN", eps=(("E1", "CURRENT_EVALUATION"),)):
    p = PatientGraph52(f"SYN-{pid}", sex)
    for e, k in eps:
        p.add_episode(Episode(e, k))
    p.case_notes = []
    return p


def S(hid, concept, src=ADD, ep="E1", conf="UNCONFIRMED", at=0.0):
    return HypothesisSpec(hid, concept, ep, src, conf, at)


def trop(oid, t, val, ref=14.0, pop="FEMALE", avail=None, sup=None, analyte="TROPONIN_T"):
    return OB.Observation(oid, "", "", analyte, f"{val} ng/L", float(val), "=", "ng/L", t, avail if avail is not None else t + 0.5, "lab", assay_type="HIGH_SENSITIVITY",
                          reference_upper=ref, reference_unit="ng/L" if ref is not None else "UNKNOWN", reference_percentile="99th" if ref is not None else "UNKNOWN",
                          reference_population=pop if ref is not None else "UNKNOWN", supersedes=sup, test_name=analyte)


CASES = {}


def case(f):
    CASES[f.__name__] = f
    return f


@case
def C01_three_hypotheses():
    p = pg_("C01", "FEMALE")
    for s in (S("h_pe", PE, WD), S("h_acs", ACS), S("h_peri", PERI)):
        p.add_hypothesis_spec(s)
    p.add_record52(Doc("n1", "Pleuritic chest pain. A pericardial friction rub was heard.", "NOTE", 0.5, 1.0))
    p.add_record52(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    p.add_observation52(trop("OBS:t0", 0.0, 30), source_event_id="LAB-T0")
    p.add_observation52(trop("OBS:t1", 1.0, 45), source_event_id="LAB-T1")
    return p, [5.0]


@case
def C02_working_dx_vs_ai_candidate():
    p = pg_("C02")
    p.add_hypothesis_spec(S("h_peri", PERI, WD))
    p.add_hypothesis_spec(S("h_mi_ai", MI, AI))
    for bad in (lambda: S("h_x", MI, AI, conf="CONFIRMED"), lambda: p.add_hypothesis_spec(S("h_wd2", ACS, WD))):
        try:
            bad()
            p.case_notes.append("NOT_RAISED")
        except ValueError as e:
            p.case_notes.append(f"RAISED:{e}")
    p.add_record52(Doc("n1", "Chest pain. NSTEMI was considered by the triage algorithm.", "NOTE", 0.0, 0.5))
    return p, [1.0]


@case
def C03_shared_evidence():
    p = pg_("C03", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_hypothesis_spec(S("h_mi", MI))
    p.add_observation52(trop("OBS:t0", 0.0, 30), source_event_id="LAB-T0")
    return p, [1.0]


@case
def C04_unverified_relation():
    p = pg_("C04")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("e1", "ECG showed T wave inversion in leads V1-V4.", "ECG", 0.0, 0.5), source_event_id="ECG-1")
    return p, [1.0]


@case
def C05_similar_finding_no_metadata():
    p = pg_("C05")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Chest pain. A pericardial friction rub was heard.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("n2", "A pericardial friction rub was heard.", "NOTE", 0.2, 0.7))
    return p, [1.0]


@case
def C06_same_result_repeated():
    p = pg_("C06")
    p.add_hypothesis_spec(S("h_pe", PE, WD))
    p.add_record52(Doc("n1", SUSP, "NOTE", 0.5, 1.0))
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CTPA-1")
    p.add_record52(Doc("s1", "CTPA negative for PE.", "NOTE", 4.5, 5.0), derived_from=("r1",))
    p.add_record52(Doc("d1", "No evidence of pulmonary embolism on CTPA.", "DISCHARGE_SUMMARY", 6.0, 6.5), derived_from=("s1",))
    return p, [7.0]


@case
def C07_repeated_tests():
    p = pg_("C07", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    for i, (t, v) in enumerate(((0.0, 18), (1.0, 35), (3.0, 52))):
        p.add_observation52(trop(f"OBS:t{i}", t, v), source_event_id=f"LAB-T{i}")
    return p, [4.0]


@case
def C08_same_event_different_values():
    p = pg_("C08", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_observation52(trop("OBS:t1", 1.0, 30), source_event_id="LAB-T1")
    p.add_record52(Doc("n1", "High-sensitivity troponin T was 300 ng/L.", "NOTE", 1.0, 2.0), source_event_id="LAB-T1")
    return p, [3.0]


@case
def C09_duplicate_vs_repeat():
    p = pg_("C09", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_observation52(trop("OBS:t0", 0.0, 30), source_event_id="LAB-T0")
    p.add_record52(Doc("n1", "High-sensitivity troponin T was 30 ng/L.", "NOTE", 0.0, 1.0), source_event_id="LAB-T0")
    p.add_observation52(trop("OBS:t2", 2.0, 30), source_event_id="LAB-T2")
    return p, [3.0]


@case
def C10_derived_findings_same_event():
    p = pg_("C10")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Pleuritic chest pain.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    return p, [2.0]


def _peri_true(pid):
    p = pg_(pid)
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Pleuritic chest pain. A pericardial friction rub was heard. No pericardial effusion on echocardiography.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    p.add_record52(Doc("l1", "CRP 40 mg/L (reference < 5 mg/L), elevated.", "LAB", 0.5, 1.0), source_event_id="LAB-CRP-1")
    return p


@case
def C11_condition_true():
    return _peri_true("C11"), [2.0]


@case
def C12_condition_false():
    p = pg_("C12")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Chest pain. No pericardial friction rub. No pericardial effusion on echocardiography.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("e1", "ECG was normal.", "ECG", 0.5, 1.0))
    p.add_record52(Doc("l1", "CRP 2 mg/L, normal.", "LAB", 0.5, 1.0))
    p.add_record52(Doc("m1", "Cardiac MRI showed no pericardial late gadolinium enhancement.", "NOTE", 1.0, 1.5))
    return p, [2.0]


@case
def C13_condition_unknown():
    p = pg_("C13")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Chest pain.", "NOTE", 0.0, 0.5))
    return p, [1.0]


@case
def C14_conflict():
    p = pg_("C14")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Chest pain. A pericardial friction rub was heard.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("n2", "No pericardial friction rub.", "NOTE", 0.2, 0.7))
    return p, [1.0]


@case
def C15_order_only():
    p = pg_("C15", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("n1", "Troponin was ordered.", "NOTE", 1.0, 1.0))
    p.add_test_order("trop1", "TROPONIN", "ORDER", 1.0, "E1")
    p.add_test_order("trop1", "TROPONIN", "COLLECT", 1.5, "E1")
    return p, [2.0]


@case
def C16_result_availability():
    p = pg_("C16", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    for ev, at in (("ORDER", 0.0), ("COLLECT", 0.5), ("RESULT", 5.0)):
        p.add_test_order("trop1", "TROPONIN", ev, at, "E1")
    p.add_observation52(trop("OBS:late", 0.5, 40, avail=5.0), source_event_id="LAB-T0")
    return p, [4.0, 5.0]


@case
def C17_report_correction():
    p = pg_("C17")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Pleuritic chest pain.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("m1", "Echocardiography showed no pericardial effusion.", "ECHO_REPORT", 1.0, 2.0), source_event_id="ECHO-1")
    p.add_record52(Doc("m1c", "Corrected report: echocardiography showed a new small pericardial effusion.", "ECHO_REPORT", 1.0, 4.0, supersedes="m1"),
                   source_event_id="ECHO-1")
    return p, [3.0, 5.0]


@case
def C18_past_vs_current_episode():
    p = pg_("C18", "FEMALE", eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_acs", ACS, ep="E2", at=100.0))
    p.add_hypothesis_spec(S("h_pe", PE, WD, ep="E2", at=100.0))
    p.add_record52(Doc("r0", POS, "CTPA_REPORT", 2.0, 4.0), episode_id="E0", source_event_id="CTPA-OLD")
    p.add_observation52(trop("OBS:old", 3.0, 80), episode_id="E0", source_event_id="LAB-OLD")
    p.add_record52(Doc("n2", "Chest pain.", "NOTE", 100.0, 100.5), episode_id="E2")
    return p, [101.0]


@case
def C19_unresolved_episode():
    p = pg_("C19", eps=(("E0", "PAST_EPISODE"), ("E1", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_peri", PERI, ep="E1"))
    p.add_record52(Doc("n1", "Pleuritic chest pain.", "NOTE", 0.0, 0.5), episode_id="E1")
    p.add_record52(Doc("l1", "CRP 40 mg/L, elevated.", "LAB", 0.5, 1.0))
    return p, [2.0]


@case
def C20_pericarditis_grade_vs_direction():
    p = _peri_true("C20")
    return p, [2.0]


@case
def C21_troponin_change_not_mi():
    p = pg_("C21", "FEMALE")
    p.add_hypothesis_spec(S("h_mi", MI))
    for i, (t, v) in enumerate(((0.0, 10), (1.0, 40), (3.0, 80))):
        p.add_observation52(trop(f"OBS:t{i}", t, v), source_event_id=f"LAB-T{i}")
    p.add_record52(Doc("n2", "Troponin rose from 10 to 80 ng/L over 3 hours.", "NOTE", 3.5, 3.6))
    return p, [4.0]


@case
def C22_pr_depression_mislink():
    p = pg_("C22")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Pleuritic chest pain. History of depression.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("e1", "ECG showed PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    return p, [2.0]


@case
def C23_test_name_mention():
    p = pg_("C23")
    p.add_hypothesis_spec(S("h_pe", PE, WD))
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("n1", "CTPA was ordered. Troponin to be checked.", "NOTE", 0.5, 1.0))
    return p, [2.0]


@case
def C24_pe_weaken_not_acs_support():
    p = pg_("C24")
    p.add_hypothesis_spec(S("h_pe", PE, WD))
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("n1", SUSP, "NOTE", 0.5, 1.0))
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CTPA-1")
    return p, [5.0]


@case
def C25_concurrent_diseases():
    p = _peri_true("C25")
    p.sex = "FEMALE"
    p.add_hypothesis_spec(S("h_inj", INJ))
    p.add_hypothesis_spec(S("h_acs", ACS))
    for i, (t, v) in enumerate(((0.0, 20), (2.0, 60))):
        p.add_observation52(trop(f"OBS:t{i}", t, v), source_event_id=f"LAB-T{i}")
    p.add_record52(Doc("n3", "Troponin rose from 20 to 60 ng/L.", "NOTE", 2.5, 2.6))
    return p, [3.0]


@case
def C26_graph_flat_full():
    p = pg_("C26", "FEMALE")
    for s in (S("h_pe", PE, WD), S("h_acs", ACS), S("h_mi", MI), S("h_peri", PERI), S("h_late", INJ, at=9.0)):
        p.add_hypothesis_spec(s)
    p.add_record52(Doc("n0", SUSP, "NOTE", 0.5, 1.0))
    p.add_record52(Doc("n1", "Pleuritic chest pain. A pericardial friction rub was heard. Troponin was ordered.", "NOTE", 0.5, 1.0))
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CTPA-1")
    p.add_record52(Doc("s1", "CTPA negative for PE.", "NOTE", 4.5, 5.0), derived_from=("r1",))
    p.add_record52(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    p.add_record52(Doc("x1", "PE suspected. History of depression. ECG showed a Brugada pattern.", "NOTE", 0.5, 1.0))
    p.add_observation52(trop("OBS:t0", 0.0, 30), source_event_id="LAB-T0")
    p.add_observation52(trop("OBS:t1", 2.0, 70, avail=6.0), source_event_id="LAB-T1")
    p.add_test_order("trop2", "TROPONIN", "ORDER", 1.0, "E1")
    p.add_test_order("trop2", "TROPONIN", "COLLECT", 2.0, "E1")
    p.add_test_order("trop2", "TROPONIN", "RESULT", 6.0, "E1")
    return p, [3.0, 5.0, 7.0, 10.0]


@case
def C28_unsupported_concept():
    p = pg_("C28")
    try:
        S("h_tako", "DX:Takotsubo cardiomyopathy")
        p.case_notes.append("NOT_RAISED")
    except ValueError as e:
        p.case_notes.append(f"RAISED:{e}")
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("n1", "Echocardiography suggested Takotsubo cardiomyopathy. ECG showed a Brugada pattern.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("n2", "PE suspected.", "NOTE", 0.0, 0.5))
    return p, [1.0]


def registry_check() -> dict:
    """CASE 27: v5-0B 후보 37개 — 읽기 전용. 구조 표현 가능 여부만(의학적 사용 가능 판정 아님)."""
    raw = REG.read_bytes()
    d = json.loads(raw)
    c = d["candidates"]
    groups = {}
    for x in c:
        groups[x["v5_0b_group"]] = groups.get(x["v5_0b_group"], 0) + 1
    rows = []
    for x in c:
        st = []
        for k in ("required_conditions", "alternative_conditions", "exclusion_conditions"):
            if x.get(k):
                try:
                    r = L.eval5(LG4.from_dict(x[k]), {})
                    st.append((k, "REPRESENTABLE", r["value"]))
                except Exception as e:  # noqa: BLE001
                    st.append((k, f"NOT_REPRESENTABLE:{type(e).__name__}", None))
        rows.append({"candidate_id": x["candidate_id"], "group": x["v5_0b_group"], "engine_active": x["engine_active"], "engine_status": x["engine_status"],
                     "structure": st, "used_in_v5_2a_comparison": False})
    return {"sha256": hashlib.sha256(raw).hexdigest(), "n": len(c), "groups": groups, "engine_active_true": sum(bool(x["engine_active"]) for x in c),
            "candidates": rows, "note": "구조 표현 가능 ≠ 의학적 사용 가능. 그룹 A 도 활성화하지 않음. B·C 는 판단에 사용 안 함."}


def strip(d):
    return json.loads(json.dumps({k: v for k, v in d.items() if k != "mode"}, default=str, sort_keys=True))


def diff_paths(a, b, path=""):
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        return [p for k in sorted(set(a) | set(b)) for p in (diff_paths(a.get(k), b.get(k), f"{path}/{k}") if k in a and k in b else [f"{path}/{k}"])]
    if isinstance(a, list):
        return [path] if len(a) != len(b) else [p for i, (x, y) in enumerate(zip(a, b)) for p in diff_paths(x, y, f"{path}[{i}]")]
    return [] if a == b else [path]


def run_case(name):
    p, ts = CASES[name]()
    out = []
    for t in ts:
        g, f = p.compare(t), compare_flat(p, t)
        sub = p.comparison_subgraph(g)
        out.append({"as_of": t, "graph": g, "flat_equal": strip(g) == strip(f), "diff_paths": diff_paths(strip(g), strip(f)),
                    "comparison_subgraph": {"nodes": len(sub.nodes), "edge_types": sorted({e["rel"] for v in sub.out.values() for e in v})}})
    return p, out


def main():
    (H / "outputs").mkdir(exist_ok=True)
    reg_before = hashlib.sha256(REG.read_bytes()).hexdigest()
    cases, comparison, gf, dep = {}, {}, {}, {}
    for name in CASES:
        p, res = run_case(name)
        cases[name] = {"patient_id": p.pid, "case_notes": p.case_notes, "hypotheses": [s.as_row() for s in p.specs],
                       "records": [{"record_id": d.doc_id, "text": d.text, "doc_type": d.doc_type, "observed_at": d.observed_at, "available_at": d.available_at,
                                    "supersedes": d.supersedes, **({"meta": p.meta[d.doc_id].as_row()} if d.doc_id in p.meta else {})} for d in p.docs.values()],
                       "structured_observations": [o.as_row() | {"meta": p.meta[o.obs_id].as_row() if o.obs_id in p.meta else None} for o in p.obs if o.source_type == "STRUCTURED_LAB"],
                       "test_events": [{"episode_id": e, "test_id": t.test_id, "event": t.event, "at": t.at, "test_kind": p.test_kinds.get(t.test_id)} for e, t in p.tests],
                       "results": [{"as_of": r["as_of"], "comparison": r["graph"]} for r in res]}
        comparison[name] = [{"as_of": r["as_of"], "report_markdown": RP.render(r["graph"], name),
                             **{k: r["graph"][k] for k in ("working_diagnosis", "shared_findings", "hypothesis_specific_findings", "missing_information", "pending_results",
                                                            "conflicting_information", "unresolved_episode_links", "no_verified_rule", "unmapped_and_unevaluated_findings")}}
                            for r in res]
        gf[name] = [{"as_of": r["as_of"], "identical": r["flat_equal"], "diff_paths": r["diff_paths"], "comparison_subgraph": r["comparison_subgraph"]} for r in res]
        dep[name] = [{"as_of": r["as_of"], **{k: r["graph"][k] for k in ("dependency_policy", "dependency_items", "dependency_groups", "duplicate_evidence_groups", "value_discrepancies")}}
                     for r in res]
    reg = registry_check()
    reg["sha256_before_run"], reg["unchanged"] = reg_before, reg_before == reg["sha256"]
    cases["C27_registry_preserved"] = {"registry": reg}
    n = sum(len(v) for v in gf.values())
    gf_summary = {"evaluations": n, "identical": sum(x["identical"] for v in gf.values() for x in v), "cases": gf,
                  "note": "공용 평가 함수를 쓰므로 일치는 구현 일관성 확인일 뿐 — 임상 정확도 검증 아님"}
    for fn, obj in (("v5_2a_cases.json", cases), ("v5_2a_comparison.json", comparison), ("v5_2a_graph_flat.json", gf_summary), ("v5_2a_dependency.json", dep)):
        (H / "outputs" / fn).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"cases={len(CASES)}+registry graph_flat={gf_summary['identical']}/{n} registry_n={reg['n']} active={reg['engine_active_true']} unchanged={reg['unchanged']}")


if __name__ == "__main__":
    main()
