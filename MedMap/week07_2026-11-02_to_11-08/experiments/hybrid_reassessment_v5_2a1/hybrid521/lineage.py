"""사건·기록·증거 출처 연결. 명시 선언(source_event_id·derived_from·exact_duplicate_of)만 쓴다.
v5-2A dependency.group_of 는 첫 부모만 따라가고 순환·사건 ID 충돌·부모 누락을 구분하지 않아, 여기서 전체 선언을 검사한다.
문제(순환·사건 ID 충돌·부모 누락·뿌리 여러 개)가 하나라도 있으면 사건을 정하지 않는다(DEPENDENCY_UNKNOWN 근거)."""
from __future__ import annotations


def declarations(rows: list) -> dict:
    """선언 행 목록(같은 기록에 여러 번 선언 가능) → 기록 키별 {events, derived_from, exact_duplicate_of}."""
    out = {}
    for m in rows:
        if not (m.get("source_event_id") or m.get("derived_from") or m.get("exact_duplicate_of")):
            continue                                                       # 빈 선언(메타데이터 없음)은 항목을 만들지 않음
        d = out.setdefault(m["record_key"], {"events": [], "derived_from": [], "exact_duplicate_of": []})
        if m.get("source_event_id") and m["source_event_id"] not in d["events"]:
            d["events"].append(m["source_event_id"])
        for p in m.get("derived_from") or ():
            if p not in d["derived_from"]:
                d["derived_from"].append(p)
        if m.get("exact_duplicate_of") and m["exact_duplicate_of"] not in d["exact_duplicate_of"]:
            d["exact_duplicate_of"].append(m["exact_duplicate_of"])
    return {k: {kk: sorted(v) for kk, v in d.items()} for k, d in sorted(out.items())}


def resolve(key: str, decl: dict, known: set) -> dict:
    """기록 키 → {event_id, basis, issues, ancestors}. basis: SOURCE_EVENT / DERIVATION_CHAIN / DERIVATION_ROOT / NO_METADATA / INVALID_METADATA."""
    issues, events, roots, anc = set(), set(), set(), []

    def dfs(k, path):
        if k in path:
            issues.add("DERIVATION_CYCLE")
            return
        if k not in known:
            issues.add(f"PARTIAL_PROVENANCE(기록 없음:{k})")
        d = decl.get(k, {"events": [], "derived_from": [], "exact_duplicate_of": []})
        if len(d["events"]) > 1:
            issues.add(f"EVENT_ID_CONFLICT(같은 기록에 사건 ID 여러 개:{k}:{d['events']})")
        events.update(d["events"])
        parents = d["derived_from"] + d["exact_duplicate_of"]
        if not parents:
            roots.add(k)
        for p in parents:
            if p not in anc:
                anc.append(p)
            dfs(p, path + (k,))

    dfs(key, ())
    if len(events) > 1:
        issues.add(f"EVENT_ID_CONFLICT(파생 사슬의 사건 ID 불일치:{sorted(events)})")
    has_children = any(key in d["derived_from"] + d["exact_duplicate_of"] for d in decl.values())
    own = decl.get(key, {"derived_from": [], "exact_duplicate_of": []})
    if issues:
        ev, basis = None, "INVALID_METADATA"
    elif events:
        ev, basis = next(iter(events)), "SOURCE_EVENT"
    elif (own["derived_from"] or own["exact_duplicate_of"]) and len(roots) == 1:
        ev, basis = f"ROOT_RECORD:{next(iter(roots))}", "DERIVATION_CHAIN"
    elif has_children and not (own["derived_from"] or own["exact_duplicate_of"]):
        ev, basis = f"ROOT_RECORD:{key}", "DERIVATION_ROOT"
    elif (own["derived_from"] or own["exact_duplicate_of"]) and len(roots) > 1:
        ev, basis = None, "INVALID_METADATA"
        issues.add(f"MULTIPLE_ROOTS({sorted(roots)})")
    else:
        ev, basis = None, "NO_METADATA"
    return {"record_key": key, "event_id": ev, "basis": basis, "issues": sorted(issues), "ancestors": anc}


def exact_pair(a: str, b: str, decl: dict) -> bool:
    return b in decl.get(a, {}).get("exact_duplicate_of", []) or a in decl.get(b, {}).get("exact_duplicate_of", [])
