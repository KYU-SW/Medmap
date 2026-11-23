"""판단 출처 귀속과 변화 원인 구분.
- 직접 귀속: 원시 판단의 증거 기록이 그 사건(명시 lineage)의 기록일 때만. 사건 연결이 없거나 메타데이터가 무효면 ATTRIBUTION_UNRESOLVED.
- 문맥 의존: v4 판단 결정 트리가 읽은 문맥 사실(검사 전 확률 등)의 출처 기록 — 다른 기록에 의존하면 표시.
- 변화 원인: EVENT_VERSION_CHANGED / PATIENT_CONTEXT_CHANGED / ATTRIBUTION_UNRESOLVED (배타적이지 않음, 함께 표시)."""
from __future__ import annotations

EVENT_CHANGED, CONTEXT_CHANGED, UNRESOLVED = "EVENT_VERSION_CHANGED", "PATIENT_CONTEXT_CHANGED", "ATTRIBUTION_UNRESOLVED"


def _keys(d, out):
    if isinstance(d, dict):
        if isinstance(d.get("key"), str):
            out.add(d["key"])
        for v in d.values():
            _keys(v, out)
    elif isinstance(d, list):
        for v in d:
            _keys(v, out)
    return out


def context_records(item: dict, known: set) -> list:
    """v4 항목 → 결정 트리가 참조한 문맥 사실 키의 출처 기록(자기 기록 제외). 결정 트리에 키가 없으면 전체 facts_used 를 상한으로 사용."""
    fu = item.get("facts_used") or {}
    keys = _keys(item.get("decision") or {}, set()) & set(fu) or set(fu)
    recs = set()
    for k in keys:
        f = fu[k]
        if f["status"] not in ("FOUND", "CONFLICT"):
            continue
        for s in f["sources"]:
            r = s.split(":", 1)[0]
            if r in known and r != item["source_record_id"]:
                recs.add(r)
    return sorted(recs)


def judgment_attribution(raw: dict, event_of_record: dict) -> dict:
    ev = event_of_record.get(raw["source_record_id"])
    if ev is None or ev["event_key"] is None:
        why = "UNRESOLVED_EVENT_LINK" if (ev is None or not ev["issues"]) else "INVALID_METADATA:" + ";".join(ev["issues"])
        return {"status": UNRESOLVED, "reason": why, "event_key": None}
    st = "DIRECT_WITH_CONTEXT_DEPENDENCY" if raw.get("context_record_ids") else "DIRECT"
    return {"status": st, "event_key": ev["event_key"], "version_id": ev["version_id"], "context_record_ids": raw.get("context_record_ids", []),
            "reason": "증거 기록이 이 사건의 판독 버전" + (" — 판단은 다른 기록의 문맥 사실에도 의존(사건 단독 판단 아님)" if raw.get("context_record_ids") else "")}


def classify_step(prev: dict, cur: dict, event_of_record: dict) -> dict:
    """두 실제 as_of 사이 변화: 사건 버전 변화와 문맥 변화를 각각 나열하고, 판단 변화마다 원인을 붙인다."""
    ps, cs = prev["record_status"], cur["record_status"]
    newly = sorted(k for k, s in cs.items() if s == "VISIBLE" and ps.get(k) != "VISIBLE")
    corrected = sorted(k for k, s in cs.items() if s in ("SUPERSEDED", "NOT_VISIBLE") and ps.get(k) == "VISIBLE")
    ev_changed = sorted({event_of_record[k]["event_key"] for k in newly + corrected if event_of_record.get(k, {}).get("event_key")})
    ctx_new = sorted(k for k in newly if not event_of_record.get(k, {}).get("event_key"))
    pr = {r["raw_id"]: r for r in prev["raw_judgments"]}
    cr = {r["raw_id"]: r for r in cur["raw_judgments"]}
    changes = []
    for rid in sorted(set(pr) | set(cr)):
        a, b = pr.get(rid), cr.get(rid)
        if a and b and (a["directional_result"], a["hold_reason"]) == (b["directional_result"], b["hold_reason"]):
            continue
        r = b or a
        rec = r["source_record_id"]
        causes = []
        if a is None or b is None:
            kind = "ADDED" if a is None else "REMOVED"
            prov = {p["record_key"]: p for p in cur["provenance"]}
            corr = prov.get(rec, {}).get("corrects", []) + prov.get(rec, {}).get("corrected_by", [])
            if rec in newly + corrected and event_of_record.get(rec, {}).get("event_key"):
                causes.append({"cause": EVENT_CHANGED, "event_key": event_of_record[rec]["event_key"], "records": [rec]})
            elif rec in newly + corrected and corr:
                causes.append({"cause": UNRESOLVED, "records": sorted({rec, *corr}),
                               "note": "명시 정정 관계는 확인됐으나 사건 연결(사건 ID·파생)이 없어 사건 버전 변화로 귀속하지 못함"})
            elif rec in newly:
                causes.append({"cause": CONTEXT_CHANGED, "records": [rec], "note": "사건 연결 없는 새 기록"})
        else:
            kind = "DIRECTION_OR_HOLD_CHANGED"
            ctx = sorted((set(a.get("context_record_ids", [])) | set(b.get("context_record_ids", []))) & set(newly + corrected))
            if ctx:
                causes.append({"cause": CONTEXT_CHANGED, "records": ctx, "note": "같은 증거·같은 판독인데 문맥 사실 출처가 새로 공개·정정됨"})
            evs = sorted({event_of_record[c]["event_key"] for c in ctx if event_of_record.get(c, {}).get("event_key")})
            if evs:
                causes.append({"cause": EVENT_CHANGED, "event_key": evs, "records": [c for c in ctx if event_of_record.get(c, {}).get("event_key")]})
        if not causes:
            causes.append({"cause": UNRESOLVED, "note": "출처 추적으로 변화 원인을 특정하지 못함"})
        changes.append({"raw_id": rid, "kind": kind, "before": a and {k: a[k] for k in ("directional_result", "hold_reason")},
                        "after": b and {k: b[k] for k in ("directional_result", "hold_reason")}, "causes": causes})
    step = []
    if ev_changed:
        step.append({"cause": EVENT_CHANGED, "event_keys": ev_changed})
    if ctx_new:
        step.append({"cause": CONTEXT_CHANGED, "records": ctx_new})
    return {"newly_available_record_ids": newly, "corrected_record_ids": corrected, "changed_record_ids": sorted(set(newly) | set(corrected)),
            "step_changes": step, "judgment_changes": changes}
