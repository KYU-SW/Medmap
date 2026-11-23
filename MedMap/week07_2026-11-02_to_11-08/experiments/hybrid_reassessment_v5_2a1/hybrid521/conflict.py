"""충돌과 정정. 동시 충돌(정정 관계 없음)은 어느 쪽도 지우지 않고 CONFLICTING_EVENT_EVIDENCE 로 표시한다.
정정(supersedes/CORRECTS)은 v1 공개 정책을 따른다: 정정 공개 전에는 원본, 이후에는 정정본이 현재 판단이고, 원본 판단은 SUPERSEDED_EVIDENCE 로 보존한다."""
from __future__ import annotations

from .grouping import SUPERSEDED, UNKNOWN


def mark_conflicts(groups: list) -> list:
    """같은 가설·에피소드·확인된 사건·같은 개념인데 상태/결과가 다른 그룹 → 서로 충돌로 표시. 반환: 충돌 묶음 목록."""
    by = {}
    for g in groups:
        if g["dependency_status"] in (UNKNOWN, SUPERSEDED) or not g["source_event_id"]:
            continue
        fk = g["finding_id"]
        by.setdefault((g["hypothesis_id"], g["episode_id"], g["source_event_id"], fk[0], fk[1]), []).append(g)
    out = []
    for key, gs in sorted(by.items(), key=lambda kv: str(kv[0])):
        states = {tuple(map(str, g["finding_id"][2:])) for g in gs}
        if len(states) > 1:
            ids = sorted(g["group_id"] for g in gs)
            for g in gs:
                g["conflict_status"] = "CONFLICTING_EVENT_EVIDENCE"
                g["conflict_partner_groups"] = [i for i in ids if i != g["group_id"]]
            out.append({"hypothesis_id": key[0], "episode_id": key[1], "source_event_id": key[2], "concept": key[4], "groups": ids,
                        "states": sorted(list(s) for s in states), "resolution": "NOT_RESOLVED(정정 관계 없음 — 어느 판단도 제거·선택하지 않음)"})
    return out


def corrected_records(provenance: list) -> dict:
    """정정된 기록 → {corrected_by, superseded_at}. 공개된 정정본만(다단계 정정 포함: 중간본도 대체되면 대상)."""
    av = {p["record_key"]: p["available_time"] for p in provenance}
    out = {}
    for p in provenance:
        if p["corrected_by"] and p["status_at_as_of"] in ("SUPERSEDED", "NOT_VISIBLE"):
            ts = [av[c] for c in p["corrected_by"] if isinstance(av.get(c), (int, float))]
            if ts:
                out[p["record_key"]] = {"corrected_by": p["corrected_by"], "superseded_at": min(ts), "available_time": p["available_time"]}
    return out


def superseded_groups(hist_groups: list, hist_raw: list, rec: str, info: dict, hist_as_of: float) -> list:
    """정정 직전 시점(hist_as_of)의 그룹에서 정정된 기록(rec)의 원시 판단만 남겨 SUPERSEDED_EVIDENCE 그룹으로 보존."""
    out = []
    raw_by = {r["raw_id"]: r for r in hist_raw}
    for g in hist_groups:
        keep = [rid for rid in g["raw_judgment_ids"] if raw_by[rid]["source_record_id"] == rec]
        if not keep:
            continue
        out.append({**g, "group_id": f"SUP:{rec}:{g['group_id']}", "raw_judgment_ids": keep,
                    "evidence_ids": sorted({raw_by[r]["evidence_id"] for r in keep}), "source_record_ids": [rec], "dependency_status": SUPERSEDED,
                    "conflict_status": "NONE", "conflict_partner_groups": [],
                    "correction_status": f"SUPERSEDED_BY:{info['corrected_by']} at {info['superseded_at']}",
                    "valid_interval": [info["available_time"], info["superseded_at"]], "observed_at_as_of": hist_as_of,
                    "grouping_reason": f"정정 기록에 의해 대체된 이전 판단(정정 전 {hist_as_of} 시점 출력) — 감사·출처 추적용 보존, 현재 판단 아님"})
    return out


def annotate_corrections(groups: list, provenance: list) -> None:
    corrects = {p["record_key"]: p["corrects"] for p in provenance if p["corrects"]}
    for g in groups:
        c = sorted({x for r in g["source_record_ids"] for x in corrects.get(r, [])})
        if c and g["dependency_status"] != SUPERSEDED:
            g["correction_status"] = f"CORRECTED_VERSION(supersedes {c})"
