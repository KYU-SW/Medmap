"""v5-2A.2 실행: CASE 01~28 → 사건별 판독 이력 / 환자 전체 as_of 이력 / 정정만 바꾼 가상 비교 (그래프·평면표).
결과 outputs/v5_2a2_{cases,event_history,patient_history,counterfactual,attribution,graph_flat}.json. 기술 검증용. 임상 성능 NOT_EVALUATED."""
import hashlib
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid522 import COUNTERFACTUAL, EVENT_HISTORY, PATIENT_HISTORY  # noqa: E402
from hybrid522 import report as RP  # noqa: E402
from hybrid522.flat import run_flat, run_graph  # noqa: E402
from hybrid522.graphs import PatientGraph522  # noqa: E402
import run_v5_2a1 as R1  # noqa: E402  (v5-2A.1 사례 도구·검사 재사용, 실행하지 않음)
from hybrid4.graphs import Doc, Episode  # noqa: E402

S, trop, SUSP, NEG, POS, PE, ACS, PERI, WD = R1.S, R1.trop, R1.SUSP, R1.NEG, R1.POS, R1.PE, R1.ACS, R1.PERI, R1.WD
PRE_HIGH = "Clinical probability was assessed as high."
DD_ELISA = "D-dimer measured by ELISA was normal, below the age-adjusted cut-off."
EFF = " New small pericardial effusion."


def pg_(pid, sex="FEMALE", eps=(("E1", "CURRENT_EVALUATION"),)):
    p = PatientGraph522(f"SYN522-{pid}", sex)
    for e, k in eps:
        p.add_episode(Episode(e, k))
    p.case_notes = []
    return p


def pe_base(pid, **kw):
    p = pg_(pid, **kw)
    p.add_hypothesis_spec(S("h_pe", PE, WD))
    p.add_record52(Doc("n1", SUSP, "NOTE", 0.5, 1.0))
    return p


CASES = {}


def case(f):
    CASES[f.__name__] = f
    return f


def _simple_correction(pid):
    p = pe_base(pid)
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 9.5, 10.0), source_event_id="CT001")
    p.add_record52(Doc("r1c", POS, "CTPA_REPORT", 9.5, 12.0, supersedes="r1"), source_event_id="CT001")
    return p


def _interleaved(pid):
    """핵심 회귀: 10 CT 음성 / 11 검사 전 확률 노트 + 트로포닌 / 12 CT 양성 정정."""
    p = pe_base(pid)
    p.add_hypothesis_spec(S("h_acs", ACS))
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 9.5, 10.0), source_event_id="CT001")
    p.add_record52(Doc("n2", PRE_HIGH, "NOTE", 11.0, 11.0))
    p.add_observation52(trop("OBS:t11", 10.8, 40, avail=11.0), source_event_id="LAB-T11")
    p.add_record52(Doc("r1c", POS, "CTPA_REPORT", 9.5, 12.0, supersedes="r1"), source_event_id="CT001")
    return p


def _three_step(pid):
    p = pe_base(pid)
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 2.0, 6.0, supersedes="r1"), source_event_id="CT001")
    p.add_record52(Doc("r3", POS, "CTPA_REPORT", 2.0, 8.0, supersedes="r2"), source_event_id="CT001")
    return p


@case
def C01_neg_to_pos_correction():
    return _simple_correction("C01"), [10.0, 12.5]


@case
def C02_other_result_between():
    return _interleaved("C02"), [10.0, 11.5, 12.5]


@case
def C03_correction_without_other_results():
    return _simple_correction("C03"), [10.0, 12.5]


@case
def C04_patient_vs_event_differ():
    return _interleaved("C04"), [10.0, 11.5, 12.5]


@case
def C05_other_test_kept():
    return _interleaved("C05"), [11.5, 12.5]


@case
def C06_counterfactual_ct_only():
    return _interleaved("C06"), [12.5]


@case
def C07_counterfactual_vs_history():
    return _simple_correction("C07"), [10.5]


@case
def C08_before_correction():
    return _simple_correction("C08"), [11.0]


@case
def C09_after_correction():
    return _simple_correction("C09"), [12.5]


@case
def C10_three_step_correction():
    return _three_step("C10"), [9.0]


@case
def C11_conflict_no_correction():
    p = pe_base("C11")
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 2.0, 4.2), source_event_id="CT001")
    return p, [5.0]


@case
def C12_same_event_different_findings():
    p = pe_base("C12")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("c1", "Pleuritic chest pain.", "NOTE", 0.2, 0.6))
    p.add_record52(Doc("r1", POS + EFF, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r1c", NEG + EFF, "CTPA_REPORT", 2.0, 8.0, supersedes="r1"), source_event_id="CT001")
    return p, [9.0]


@case
def C13_no_event_id():
    p = pe_base("C13")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 9.5, 10.0))
    p.add_record52(Doc("r1c", POS, "CTPA_REPORT", 9.5, 12.0, supersedes="r1"))
    return p, [12.5]


@case
def C14_unresolved_episode():
    p = pg_("C14", eps=(("E0", "PAST_EPISODE"), ("E1", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_pe", PE, WD, ep="E1"))
    p.add_record52(Doc("n1", SUSP, "NOTE", 0.5, 1.0), episode_id="E1")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    return p, [5.0]


@case
def C15_different_episodes():
    p = pg_("C15", eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_pe0", PE, WD, ep="E0"))
    p.add_hypothesis_spec(S("h_pe2", PE, WD, ep="E2", at=50.0))
    p.add_record52(Doc("n0", SUSP, "NOTE", 0.5, 1.0), episode_id="E0")
    p.add_record52(Doc("r0", NEG, "CTPA_REPORT", 2.0, 4.0), episode_id="E0", source_event_id="CT001")
    p.add_record52(Doc("n2", SUSP, "NOTE", 50.0, 50.5), episode_id="E2")
    p.add_record52(Doc("s2", "CTPA negative for PE.", "NOTE", 51.0, 51.5), episode_id="E2", source_event_id="CT001")
    return p, [52.0]


@case
def C16_judgment_not_attributed():
    p = pe_base("C16")
    p.add_record52(Doc("l1", DD_ELISA, "LAB", 1.0, 1.5))
    return p, [2.0]


@case
def C17_multi_context_dependency():
    return _interleaved("C17"), [11.5]


@case
def C20_missing_parent():
    p = pe_base("C20")
    try:
        p.add_record52(Doc("r1c", POS, "CTPA_REPORT", 9.5, 12.0, supersedes="r_missing"), source_event_id="CT001")
        p.case_notes.append("NOT_RAISED")
    except KeyError as e:
        p.case_notes.append(f"RAISED_KEYERROR:{e}")
        p.case_notes.append(f"PARTIAL_STATE_AFTER_ERROR:docs_has_r1c={'r1c' in p.docs}")
    p.add_record52(Doc("s1", "CTPA negative for PE.", "NOTE", 4.5, 5.0), derived_from=("r_missing",))
    return p, [6.0]


@case
def C21_conflicting_event_ids():
    p = pe_base("C21")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.declare_meta("r1", source_event_id="CT009")
    return p, [5.0]


@case
def C22_partial_multi_step():
    return _three_step("C22"), [7.0]


def correction_cycle_unit() -> dict:
    """CASE 19: v4 입력 API 는 존재하지 않는 기록을 정정 대상으로 받지 않아(KeyError) supersedes 순환을 만들 수 없음 → 출처 행 단위로 검사."""
    from hybrid522 import event_history as EH
    prov = [{"record_key": "a", "record_type": "CTPA_REPORT", "episode_id": "E1", "observation_time": 1.0, "available_time": 2.0, "corrects": ["b"], "corrected_by": ["b"],
             "status_at_as_of": "NOT_VISIBLE"},
            {"record_key": "b", "record_type": "CTPA_REPORT", "episode_id": "E1", "observation_time": 1.0, "available_time": 3.0, "corrects": ["a"], "corrected_by": ["a"],
             "status_at_as_of": "NOT_VISIBLE"}]
    decl = {"a": {"events": ["CT001"], "derived_from": [], "exact_duplicate_of": []}, "b": {"events": ["CT001"], "derived_from": [], "exact_duplicate_of": []}}
    snap = {"as_of": 4.0, "record_status": {"a": "NOT_VISIBLE", "b": "NOT_VISIBLE"}, "raw_judgments": [], "v5_2a1_conflicts": []}
    h = EH.build(decl, {"a", "b"}, prov, [snap])
    return {"held_records": h["held_records"], "unresolved": [(u["record_key"], u["issues"]) for u in h["unresolved_event_links"]],
            "events": [e["event_key"] for e in h["events"]]}


def strip(d):
    return json.loads(json.dumps({k: v for k, v in d.items() if k != "mode"}, default=str, sort_keys=True))


def run_case(name):
    p, ts = CASES[name]()
    g, f = run_graph(p, ts), run_flat(p, ts)
    sg, sf = strip(g), strip(f)
    eq = {k: sg[k] == sf[k] for k in (EVENT_HISTORY, PATIENT_HISTORY, COUNTERFACTUAL, "v5_2a1_compat")}
    return p, g, {"identical": sg == sf, "sections": eq, "diff_paths": R1.R52.diff_paths(sg, sf)[:20]}


def main():
    out = H / "outputs"
    out.mkdir(exist_ok=True)
    reg_before = hashlib.sha256(R1.R52.REG.read_bytes()).hexdigest()
    cases, ev, ph, cf, at, gf = {}, {}, {}, {}, {}, {}
    for name in CASES:
        p, g, cmpr = run_case(name)
        cases[name] = {"patient_id": p.pid, "case_notes": p.case_notes, "hypotheses": [s.as_row() for s in p.specs], "reference_time": g["reference_time"],
                       "records": [{"record_id": d.doc_id, "text": d.text, "doc_type": d.doc_type, "observed_at": d.observed_at, "available_at": d.available_at,
                                    "supersedes": d.supersedes} for d in p.docs.values()], "metadata_declarations": p.meta_log,
                       "report_markdown": RP.render(g, name)}
        ev[name], ph[name], cf[name] = g[EVENT_HISTORY], g[PATIENT_HISTORY], g[COUNTERFACTUAL]
        at[name] = {"event_of_record": g[EVENT_HISTORY]["event_of_record"], "unresolved_event_links": g[EVENT_HISTORY]["unresolved_event_links"],
                    "step_attribution": [{"as_of": s["as_of"], **(s["diff_from_previous"] or {})} for s in g[PATIENT_HISTORY]["snapshots"]],
                    "v5_2a1_superseded_groups": [{k: x.get(k) for k in ("group_id", "source_record_ids", "relation_id", "directional_result", "observed_at_as_of",
                                                                         "correction_status")} for x in g["v5_2a1_compat"]["groups"] if x["dependency_status"] == "SUPERSEDED_EVIDENCE"]}
        gf[name] = cmpr
    reg = R1.R52.registry_check()
    reg["sha256_before_run"], reg["unchanged"] = reg_before, reg_before == reg["sha256"]
    cases["C18_fabricated_link"] = {"v5_2a1_check": R1.fabricated_judgment_check()}
    cases["C19_correction_cycle"] = correction_cycle_unit()
    cases["C27_registry_preserved"] = {k: reg[k] for k in ("n", "groups", "engine_active_true", "sha256", "sha256_before_run", "unchanged")}
    summary = {"cases": len(gf), "identical": sum(v["identical"] for v in gf.values()),
               "section_identical": {k: sum(v["sections"][k] for v in gf.values()) for k in (EVENT_HISTORY, PATIENT_HISTORY, COUNTERFACTUAL, "v5_2a1_compat")},
               "per_case": gf, "note": "공용 규칙 — 일치는 구현 일관성 확인일 뿐 의학적 정확도 아님"}
    for fn, obj in (("v5_2a2_cases.json", cases), ("v5_2a2_event_history.json", ev), ("v5_2a2_patient_history.json", ph), ("v5_2a2_counterfactual.json", cf),
                    ("v5_2a2_attribution.json", at), ("v5_2a2_graph_flat.json", summary)):
        (out / fn).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"cases={len(CASES)}+3 graph_flat={summary['identical']}/{summary['cases']} sections={summary['section_identical']} registry={reg['n']}/{reg['engine_active_true']}/{reg['unchanged']}")


if __name__ == "__main__":
    main()
