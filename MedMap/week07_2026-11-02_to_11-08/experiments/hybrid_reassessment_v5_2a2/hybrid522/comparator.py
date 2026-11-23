"""세 결과 계약 분리 + 그래프·평면표 공용 실행. 모드별로 다른 것은 입력 수집 경로뿐:
graph = v5-2A.1 compare521(그래프) · declarations_graph · v4 그래프 추론기 / flat = compare521_flat · declarations_flat · v4 평면 추론기."""
from __future__ import annotations

from hybrid52.graphs import _LEGACY, legacy_v4
from hybrid521.flat import compare521_flat, declarations_flat

from . import COUNTERFACTUAL, EVENT_HISTORY, PATIENT_HISTORY
from . import counterfactual as CF, event_history as EH, patient_history as PH


def evaluate(pg, t, mode):
    return pg.compare521(t) if mode == "graph" else compare521_flat(pg, t)


def declarations(pg, mode):
    return pg.declarations_graph() if mode == "graph" else declarations_flat(pg)


def legacy_items(pg, t, mode) -> dict:
    """v4 추론기 전체 항목(문맥 사실 출처 포함). 방향 값은 읽기만 한다."""
    if not legacy_v4(pg, t, mode):
        return {}
    r = _LEGACY[mode].evaluate(pg, t)
    return {(h["hyp_id"], i["relation_id"], i["evidence_id"]): i for h in r["hypotheses"] for i in h["items"] if i.get("relation_id")}


def checkpoints(prov_all: list, as_ofs: list) -> list:
    hz = max(as_ofs)
    ts = {p["available_time"] for p in prov_all if isinstance(p["available_time"], (int, float)) and p["available_time"] <= hz}
    return sorted(ts | set(as_ofs))


def run(pg, as_ofs: list, mode: str) -> dict:
    from hybrid521 import lineage as LN
    rows, known = declarations(pg, mode)
    decl = LN.declarations(rows)
    hz = max(as_ofs)
    c_hz = evaluate(pg, hz, mode)
    prov_all = c_hz["v5_2a"]["source_provenance"]
    snaps = []
    for t in checkpoints(prov_all, as_ofs):
        c = c_hz if t == hz else evaluate(pg, t, mode)
        snaps.append(PH.snapshot(c, legacy_items(pg, t, mode), known))
    hist = EH.build(decl, known, prov_all, snaps)
    PH.attach(snaps, hist["event_of_record"], EH.active_versions_fn(hist))
    cfs = CF.run_all(pg, hist, hz, lambda g, t: evaluate(g, t, mode))
    for e in hist["events"]:
        e["patient_id"] = pg.pid
    return {"patient_id": pg.pid, "mode": mode, "reference_time": hz,
            EVENT_HISTORY: {"history_type": EVENT_HISTORY, "events": hist["events"], "unresolved_event_links": hist["unresolved_event_links"],
                            "held_records": hist["held_records"], "event_of_record": hist["event_of_record"]},
            PATIENT_HISTORY: {"history_type": PATIENT_HISTORY, "snapshots": snaps},
            COUNTERFACTUAL: {"history_type": COUNTERFACTUAL, "comparisons": cfs},
            "v5_2a1_compat": {"as_of": hz, "groups": c_hz["evidence_grouping"]["groups"], "raw_judgments": c_hz["evidence_grouping"]["raw_judgments"],
                              "note": "v5-2A.1 출력 그대로. 그 SUPERSEDED 그룹은 '정정 직전 환자 전체 상태' 재계산이므로 사건별 이력으로 쓰지 않음"},
            "active_direction_relations_v5_2a2": 0, "clinical_validation_status": "NOT_EVALUATED"}
