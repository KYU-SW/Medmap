"""v5-2A.1 실행: CASE 01~20 + 경계 사례 → 근거 그룹(그래프·평면표), 레거시 중복 9건 감사, 레지스트리 보존.
결과 outputs/v5_2a1_{cases,grouping,graph_flat,legacy_duplicate_audit}.json. 기술 검증용. 임상 성능 NOT_EVALUATED."""
import hashlib
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from hybrid521 import audit as AU, report as RP  # noqa: E402
from hybrid521.flat import compare521_flat, declarations_flat  # noqa: E402
from hybrid521.graphs import PatientGraph521  # noqa: E402
import run_v5_2a as R52  # noqa: E402  (v5-2A 사례 도구·레지스트리 검사 재사용, 실행하지 않음)
from hybrid4.graphs import Doc, Episode  # noqa: E402
from hybrid521 import lineage as LN  # noqa: E402

S, trop, SUSP, NEG, POS = R52.S, R52.trop, R52.SUSP, R52.NEG, R52.POS
PE, ACS, PERI, WD = R52.PE, R52.ACS, R52.PERI, R52.WD
SUMMARY_NEG, DISCHARGE_NEG = "CTPA negative for PE.", "CTPA showed no PE."
FILLING = "IMPRESSION: Filling defect in the right lower lobe segmental artery."


def pg_(pid, sex="UNKNOWN", eps=(("E1", "CURRENT_EVALUATION"),)):
    p = PatientGraph521(f"SYN521-{pid}", sex)
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


@case
def C01_same_event_three_docs():
    p = pe_base("C01")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("s1", SUMMARY_NEG, "NOTE", 4.5, 5.0), source_event_id="CT001")
    p.add_record52(Doc("d1", DISCHARGE_NEG, "DISCHARGE_SUMMARY", 6.0, 6.5), derived_from=("s1",))
    return p, [7.0]


@case
def C02_same_text_no_event():
    p = pe_base("C02")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0))
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 2.0, 4.5))
    return p, [5.0]


@case
def C03_different_text_same_event():
    p = pe_base("C03")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("s1", SUMMARY_NEG, "NOTE", 4.5, 5.0), derived_from=("r1",))
    return p, [6.0]


@case
def C04_different_time_ctpa():
    p = pe_base("C04")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 20.0, 21.0), source_event_id="CT002")
    return p, [22.0]


@case
def C05_same_event_different_findings():
    p = pg_("C05")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("n1", "Pleuritic chest pain.", "NOTE", 0.0, 0.5))
    p.add_record52(Doc("e1", "ECG showed diffuse ST elevation and PR depression.", "ECG", 0.5, 1.0), source_event_id="ECG-1")
    return p, [2.0]


@case
def C06_same_event_conflict():
    p = pe_base("C06")
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 2.0, 4.2), source_event_id="CT001")
    return p, [5.0]


def _correction(pid):
    p = pe_base(pid)
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r1c", NEG, "CTPA_REPORT", 2.0, 7.0, supersedes="r1"), source_event_id="CT001")
    return p


@case
def C07_explicit_correction():
    return _correction("C07"), [6.0, 8.0]


@case
def C08_before_correction():
    return _correction("C08"), [6.0]


@case
def C09_after_correction():
    return _correction("C09"), [8.0]


@case
def C10_different_episodes():
    p = pg_("C10", eps=(("E0", "PAST_EPISODE"), ("E2", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_pe0", PE, WD, ep="E0"))
    p.add_hypothesis_spec(S("h_pe2", PE, WD, ep="E2", at=50.0))
    p.add_record52(Doc("n0", SUSP, "NOTE", 0.5, 1.0), episode_id="E0")
    p.add_record52(Doc("r0", NEG, "CTPA_REPORT", 2.0, 4.0), episode_id="E0", source_event_id="CT001")
    p.add_record52(Doc("n2", SUSP, "NOTE", 50.0, 50.5), episode_id="E2")
    p.add_record52(Doc("s2", SUMMARY_NEG, "NOTE", 51.0, 51.5), episode_id="E2", source_event_id="CT001")
    return p, [52.0]


@case
def C11_unresolved_episode():
    p = pg_("C11", eps=(("E0", "PAST_EPISODE"), ("E1", "CURRENT_EVALUATION")))
    p.add_hypothesis_spec(S("h_pe", PE, WD, ep="E1"))
    p.add_record52(Doc("n1", SUSP, "NOTE", 0.5, 1.0), episode_id="E1")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    return p, [5.0]


@case
def C12_same_event_different_relation():
    p = pe_base("C12")
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", FILLING, "CTPA_REPORT", 2.0, 4.5), source_event_id="CT001")
    return p, [5.0]


@case
def C13_same_event_different_target():
    p = pe_base("C13")
    p.add_hypothesis_spec(S("h_peri", PERI))
    p.add_record52(Doc("c1", "Pleuritic chest pain.", "NOTE", 0.2, 0.6))
    p.add_record52(Doc("r1", POS + " New small pericardial effusion.", "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    return p, [5.0]


@case
def C14_repeated_troponin():
    p = pg_("C14", "FEMALE")
    p.add_hypothesis_spec(S("h_acs", ACS))
    for i, (t, v) in enumerate(((0.0, 18), (1.0, 35), (3.0, 52))):
        p.add_observation52(trop(f"OBS:t{i}", t, v), source_event_id=f"LAB-T{i}")
    return p, [4.0]


@case
def C15_repeated_mention_no_event():
    p = pe_base("C15")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0))
    p.add_record52(Doc("s1", SUMMARY_NEG, "NOTE", 4.5, 5.0))
    p.add_record52(Doc("d1", DISCHARGE_NEG, "DISCHARGE_SUMMARY", 6.0, 6.5))
    return p, [7.0]


@case
def C16_weaken_grouped_sources_kept():
    return C01_same_event_three_docs()


@case
def C17_no_acs_support_after_grouping():
    p, ts = C01_same_event_three_docs()
    p.add_hypothesis_spec(S("h_acs", ACS))
    return p, ts


@case
def E01_partial_provenance():
    p = pe_base("E01")
    p.add_record52(Doc("s1", SUMMARY_NEG, "NOTE", 4.5, 5.0), derived_from=("r_missing",))
    return p, [6.0]


@case
def E02_derivation_cycle():
    p = pe_base("E02")
    p.add_record52(Doc("a1", NEG, "CTPA_REPORT", 2.0, 4.0))
    p.add_record52(Doc("a2", SUMMARY_NEG, "NOTE", 4.5, 5.0))
    p.declare_meta("a1", derived_from=("a2",))
    p.declare_meta("a2", derived_from=("a1",))
    return p, [6.0]


@case
def E03_event_id_conflict():
    p = pe_base("E03")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.declare_meta("r1", source_event_id="CT009")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 9.0, 10.0), source_event_id="CT003")
    p.add_record52(Doc("s2", SUMMARY_NEG, "NOTE", 10.5, 11.0), source_event_id="CT002", derived_from=("r2",))
    return p, [12.0]


@case
def E04_multi_step_correction():
    p = pe_base("E04")
    p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    p.add_record52(Doc("r2", NEG, "CTPA_REPORT", 2.0, 6.0, supersedes="r1"), source_event_id="CT001")
    p.add_record52(Doc("r3", POS, "CTPA_REPORT", 2.0, 8.0, supersedes="r2"), source_event_id="CT001")
    return p, [9.0]


@case
def E05_duplicate_record_id():
    p = pe_base("E05")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), source_event_id="CT001")
    try:
        p.add_record52(Doc("r1", POS, "CTPA_REPORT", 2.0, 4.5), source_event_id="CT001")
        p.case_notes.append("NOT_RAISED")
    except ValueError as e:
        p.case_notes.append(f"RAISED:{e}")
    return p, [5.0]


@case
def E06_exact_duplicate():
    p = pe_base("E06")
    p.add_record52(Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0))
    p.add_record52(Doc("r1copy", NEG, "CTPA_REPORT", 2.0, 4.1), exact_duplicate_of="r1")
    return p, [5.0]


def fabricated_judgment_check():
    """원본에 없는 판단을 그룹화에 넣으면 거부되는지(E07)."""
    from hybrid521 import grouping as GP
    p, ts = C01_same_event_three_docs()
    r = p.compare521(ts[0])
    raw = [{"raw_id": "RAW:h_pe:PE-CTPA-NEGATIVE:EV:zzz:0", "raw_kind": GP.DIRECTIONAL, "hypothesis_id": "h_pe", "disease_concept_id": PE, "episode_id": "E1",
            "evidence_id": "EV:zzz:0", "relation_id": "PE-CTPA-NEGATIVE", "directional_result": "WEAKEN", "hold_reason": "", "label": "FABRICATED"}]
    try:
        GP.build_groups(raw, {}, set(), r["evidence_grouping"]["declarations"], set())
        return "NOT_RAISED"
    except ValueError as e:
        return f"RAISED:{e}"


def strip(d):
    x = {k: v for k, v in d.items() if k != "mode"}
    x["v5_2a"] = {k: v for k, v in d["v5_2a"].items() if k != "mode"}
    return json.loads(json.dumps(x, default=str, sort_keys=True))


def run_case(name):
    p, ts = CASES[name]()
    gd, fd = pg_decl(p)
    out = []
    for t in ts:
        g, f = p.compare521(t), compare521_flat(p, t)
        out.append({"as_of": t, "graph": g, "flat_equal": strip(g) == strip(f), "diff_paths": R52.diff_paths(strip(g), strip(f)),
                    "grouping_equal": strip(g)["evidence_grouping"] == strip(f)["evidence_grouping"]})
    return p, out, {"declarations_equal": gd == fd, "graph": gd, "flat": fd}


def pg_decl(p):
    (gr, gk), (fr, fk) = p.declarations_graph(), declarations_flat(p)
    return {"decl": LN.declarations(gr), "known": sorted(gk)}, {"decl": LN.declarations(fr), "known": sorted(fk)}


def main():
    out = H / "outputs"
    out.mkdir(exist_ok=True)
    reg_path = R52.REG
    reg_before = hashlib.sha256(reg_path.read_bytes()).hexdigest()
    cases, grouping, gf = {}, {}, {}
    for name in CASES:
        p, res, decl = run_case(name)
        cases[name] = {"patient_id": p.pid, "case_notes": p.case_notes, "hypotheses": [s.as_row() for s in p.specs],
                       "records": [{"record_id": d.doc_id, "text": d.text, "doc_type": d.doc_type, "observed_at": d.observed_at, "available_at": d.available_at,
                                    "supersedes": d.supersedes} for d in p.docs.values()], "metadata_declarations": p.meta_log,
                       "results_as_of": [r["as_of"] for r in res]}
        grouping[name] = [{"as_of": r["as_of"], "report_markdown": RP.render(r["graph"], name), **r["graph"]["evidence_grouping"],
                           "v5_2a_legacy_items": {h["hypothesis_id"]: h["legacy_v4"]["items"] for h in r["graph"]["v5_2a"]["hypotheses"] if h.get("legacy_v4")}}
                          for r in res]
        gf[name] = {"declarations_equal": decl["declarations_equal"],
                    "evaluations": [{"as_of": r["as_of"], "identical": r["flat_equal"], "grouping_identical": r["grouping_equal"], "diff_paths": r["diff_paths"]} for r in res]}
    reg = R52.registry_check()
    reg["sha256_before_run"], reg["unchanged"] = reg_before, reg_before == reg["sha256"]
    cases["C20_registry_preserved"] = {"registry": {k: reg[k] for k in ("n", "groups", "engine_active_true", "sha256", "sha256_before_run", "unchanged", "note")}}
    cases["E07_fabricated_judgment"] = {"result": fabricated_judgment_check()}
    n = sum(len(v["evaluations"]) for v in gf.values())
    summary = {"evaluations": n, "identical": sum(x["identical"] for v in gf.values() for x in v["evaluations"]),
               "grouping_identical": sum(x["grouping_identical"] for v in gf.values() for x in v["evaluations"]),
               "declarations_equal_cases": sum(v["declarations_equal"] for v in gf.values()), "cases": gf,
               "note": "공용 규칙 — 일치는 구현 일관성 확인일 뿐 의학적 정확도 아님"}
    aud = AU.audit(H.parent / "hybrid_reassessment_v5_2a" / "outputs")
    for fn, obj in (("v5_2a1_cases.json", cases), ("v5_2a1_grouping.json", grouping), ("v5_2a1_graph_flat.json", summary),
                    ("v5_2a1_legacy_duplicate_audit.json", aud)):
        (out / fn).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"cases={len(CASES)} gf={summary['identical']}/{n} grouping={summary['grouping_identical']}/{n} decl={summary['declarations_equal_cases']}/{len(gf)} "
          f"audit_rows={aud['rows_reconstructed']} unique={aud['unique_raw_judgments']} classes={aud['class_counts']} registry={reg['n']}/{reg['engine_active_true']}/{reg['unchanged']}")


if __name__ == "__main__":
    main()
