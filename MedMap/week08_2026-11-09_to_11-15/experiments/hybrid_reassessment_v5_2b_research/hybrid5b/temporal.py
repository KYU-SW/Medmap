"""Shadow 판단을 기존 시간·중복·정정 기능에 연결(새로 만들지 않음):
- 중복·종속 그룹: hybrid521.grouping.build_groups(원시 판단 → 근거 그룹) + hybrid521.conflict.mark_conflicts
- 사건 해석: hybrid521.lineage + hybrid522.event_history.resolve_events
- 증거 목록: hybrid52.evidence_linker.catalog(같은 as_of 입력 수집: v5-2A graph collect / flat collect_flat)
- 정정 가상 비교: hybrid522.counterfactual.replay · fixed_context(입력 이력 재생)
Shadow 도 v1 공개 정책(as_of·supersedes)을 그대로 따른다(v4 episode_inputs 경유)."""
from __future__ import annotations

from hybrid4.graphs import Episode
from hybrid52 import evidence_linker as EL
from hybrid52.flat import collect_flat
from hybrid52.hypotheses import HypothesisSpec
from hybrid521 import conflict as CF1, grouping as GP, lineage as LN
from hybrid521.flat import declarations_flat
from hybrid522 import counterfactual as CF2, event_history as EH
from hybrid522.graphs import PatientGraph522

from . import experiment_matrix as EM
from . import shadow_reasoner as SR

D = EM


def raw_from_shadow(sh: dict) -> list:
    return [{"raw_id": f"SHADOW:{j['hyp_id']}:{j['relation_id']}:{j['evidence_id']}", "raw_kind": GP.DIRECTIONAL, "hypothesis_id": j["hyp_id"],
             "disease_concept_id": "DX:Pulmonary embolism", "episode_id": j["episode_id"], "evidence_id": j["evidence_id"], "relation_id": j["relation_id"],
             "directional_result": j["direction"], "hold_reason": j["stage"], "label": "PE_SHADOW_RESEARCH"} for j in sh["judgments"]]


def group_shadow(pg, as_of: float, mode: str) -> dict:
    sh = SR.evaluate(pg, as_of, mode)
    bundle = pg.collect(as_of) if mode == "graph" else collect_flat(pg, as_of)
    rows, known = pg.declarations_graph() if mode == "graph" else declarations_flat(pg)
    decl = LN.declarations(rows)
    cats = [EL.catalog(bundle["episodes"][e]) for e in sorted(bundle["episodes"])] + [EL.catalog(bundle["unresolved"])]
    vis = {p["record_key"] for p in bundle["provenance"] if p["status_at_as_of"] == "VISIBLE"}
    raw, groups = GP.build_groups(raw_from_shadow(sh), GP.item_index(cats), vis, decl, known)
    conflicts = CF1.mark_conflicts(groups)
    eor = EH.resolve_events(decl, known, bundle["provenance"])
    return {"as_of": as_of, "mode": mode, "shadow": [{k: j[k] for k in ("evidence_id", "source_record_id", "relation_id", "direction", "stage")} for j in sh["judgments"]],
            "raw": raw, "groups": groups, "conflicts": conflicts, "counts": GP.counts(raw, groups, GP.DIRECTIONAL),
            "event_of_record": {k: v["event_key"] for k, v in eor.items()}, "provenance": {p["record_key"]: p["status_at_as_of"] for p in bundle["provenance"]}}


def _pg(cid, recs, eps=(("E1", "CURRENT_EVALUATION"),), hyp_ep="E1"):
    p = PatientGraph522(f"SYN5B-T-{cid}")
    for e, k in eps:
        p.add_episode(Episode(e, k))
    p.add_hypothesis_spec(HypothesisSpec("h_pe", "DX:Pulmonary embolism", hyp_ep, "PHYSICIAN_WORKING_DIAGNOSIS"))
    for rid, text, dt, obs, av, ep, meta in recs:
        from hybrid4.graphs import Doc
        p.add_record52(Doc(rid, text, dt, obs, av, supersedes=meta.get("supersedes")), ep, meta.get("event"), tuple(meta.get("derived_from", ())))
    return p


BASE = EM.R("n1", EM.SUS + " " + EM.PRE("intermediate") + EM.ST, 1.0)
TCASES = {
    "P01_correction": ([BASE, EM.R("r1", EM.POS, 4.0, event="CT1"), EM.R("r1c", EM.NEG, 7.0, event="CT1", supersedes="r1")], [3.0, 5.0, 8.0]),
    "P02_correction_with_context_change": ([EM.R("n1", EM.SUS + " " + EM.PRE("intermediate") + EM.ST, 1.0), EM.R("r1", EM.NEG, 4.0, event="CT1"),
                                            EM.R("n2", EM.PRE("high"), 5.0), EM.R("r1c", EM.POS, 7.0, event="CT1", supersedes="r1")], [4.5, 6.0, 8.0]),
    "Q01_duplicate_same_event": ([BASE, EM.R("r1", EM.NEG, 4.0, event="CT1"), EM.R("s1", "CTPA negative for PE.", 5.0, dt="NOTE", event="CT1"),
                                  EM.R("d1", "CTPA showed no PE.", 6.0, dt="NOTE", derived_from=("s1",))], [7.0]),
    "R01_same_event_conflict": ([BASE, EM.R("r1", EM.POS, 4.0, event="CT1"), EM.R("r2", EM.NEG, 4.2, event="CT1")], [5.0]),
    "S01_distinct_events": ([BASE, EM.R("r1", EM.NEG, 4.0, event="CT1"), EM.R("r2", EM.NEG, 20.0, event="CT2")], [21.0]),
    "T01_no_event_metadata": ([BASE, EM.R("r1", EM.NEG, 4.0), EM.R("r2", EM.NEG, 4.5)], [5.0]),
}


def run_temporal(mode: str = "graph") -> dict:
    out = {}
    for cid, (recs, ts) in TCASES.items():
        p = _pg(cid, recs)
        out[cid] = {"history": [group_shadow(p, t, mode) for t in ts]}
        if cid.startswith("P0"):
            hz = ts[-1]
            chain = {"r1", "r1c"}
            res = {}
            for keep in ("r1", "r1c"):
                g, inj = CF2.replay(p, keep, chain - {keep}, hz)
                res[keep] = {"shadow": [{k: j[k] for k in ("evidence_id", "relation_id", "direction", "stage")} for j in SR.evaluate(g, hz, mode)["judgments"]],
                             "fixed_context": CF2.fixed_context(g, hz, chain), "injected": inj}
            same = res["r1"]["fixed_context"] == res["r1c"]["fixed_context"]
            out[cid]["counterfactual"] = {**CF2.LABELS, "reference_time": hz, "changed_event_id": "CT1", "before_record_id": "r1", "after_record_id": "r1c",
                                          "fixed_context_identical": same, "fixed_context_record_ids": res["r1"]["fixed_context"]["record_ids"],
                                          "before_result": res["r1"]["shadow"], "after_result": res["r1c"]["shadow"], "engine": "PE_SHADOW_RESEARCH"}
    return out


def fabricated_check() -> str:
    p = _pg("FAB", [BASE, EM.R("r1", EM.NEG, 4.0, event="CT1")])
    bundle = p.collect(5.0)
    rows, known = p.declarations_graph()
    raw = [{"raw_id": "SHADOW:h_pe:SH-CTPA-NEG:EV:zzz:0", "raw_kind": GP.DIRECTIONAL, "hypothesis_id": "h_pe", "disease_concept_id": "DX:Pulmonary embolism",
            "episode_id": "E1", "evidence_id": "EV:zzz:0", "relation_id": "SH-CTPA-NEG", "directional_result": "WEAKEN", "hold_reason": "", "label": "FABRICATED"}]
    try:
        GP.build_groups(raw, GP.item_index([EL.catalog(bundle["episodes"]["E1"])]), set(), LN.declarations(rows), known)
        return "NOT_RAISED"
    except ValueError as e:
        return f"RAISED:{e}"
