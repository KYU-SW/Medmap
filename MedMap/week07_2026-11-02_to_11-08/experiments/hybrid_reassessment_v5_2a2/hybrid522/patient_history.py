"""환자 전체 as_of 이력: 각 시점에 실제 공개된 전체 환자 정보로 v5-2A.1 비교(무수정)를 실행한 결과 요약.
이 결과는 '그 시점 환자 전체 판단'이다. 판단 차이를 특정 검사 정정 하나로 단정하지 않는다(원인은 attribution.classify_step)."""
from __future__ import annotations

from . import attribution as AT


def snapshot(c521: dict, legacy_items: dict, known: set) -> dict:
    v, eg = c521["v5_2a"], c521["evidence_grouping"]
    raw = []
    for r in eg["raw_judgments"]:
        it = legacy_items.get((r["hypothesis_id"], r["relation_id"], r["evidence_id"])) if r["raw_kind"] == "RAW_DIRECTIONAL_JUDGMENT" else None
        raw.append({k: r[k] for k in ("raw_id", "raw_kind", "hypothesis_id", "episode_id", "relation_id", "evidence_id", "source_record_id", "source_event_id",
                                      "lineage_basis", "directional_result", "hold_reason", "finding_key")}
                   | {"context_record_ids": AT.context_records(it, known) if it else []})
    return {"history_type": "PATIENT_AS_OF_HISTORY", "as_of": c521["as_of"],
            "record_status": {p["record_key"]: p["status_at_as_of"] for p in v["source_provenance"]},
            "visible_record_ids": sorted(p["record_key"] for p in v["source_provenance"] if p["status_at_as_of"] == "VISIBLE"),
            "available_evidence_ids": sorted(v["dependency_items"]),
            "hypothesis_ids": sorted(h["hypothesis_id"] for h in v["hypotheses"] if h.get("hypothesis_status_at_as_of") == "EVALUATED"),
            "raw_judgment_ids": sorted(r["raw_id"] for r in raw), "raw_judgments": sorted(raw, key=lambda r: r["raw_id"]),
            "evaluation_results": {h["hypothesis_id"]: {r["criterion_id"]: r["evaluation_result"] for r in h.get("condition_evaluations", [])} for h in v["hypotheses"]},
            "v5_2a1_conflicts": eg["conflicts"], "provenance": v["source_provenance"]}


def attach(snaps: list, event_of_record: dict, active_versions) -> None:
    prev = None
    for s in snaps:
        s["active_event_versions"] = active_versions(s)
        s["diff_from_previous"] = AT.classify_step(prev, s, event_of_record) if prev else None
        prev = s
