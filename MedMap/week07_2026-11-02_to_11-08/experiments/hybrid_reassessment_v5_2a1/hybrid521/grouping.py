"""원시 판단 → 근거 그룹. 원시 판단은 그대로 보존하고, 그룹은 원시 판단 ID 를 가리키기만 한다(새 판단을 만들지 않음).
그룹 키 = (가설, 에피소드, 확인된 사건, 같은 소견(개념·상태·결과), 같은 관계/기준). 하나라도 다르면 합치지 않는다.
사건을 확인할 수 없으면 원시 판단마다 별도 그룹(DEPENDENCY_UNKNOWN) — 독립 근거라는 뜻이 아님."""
from __future__ import annotations

from . import lineage as LN

EXACT, SAME_EVENT, DISTINCT, UNKNOWN = "EXACT_DUPLICATE", "DERIVED_FROM_SAME_EVENT", "DISTINCT_OBSERVATION", "DEPENDENCY_UNKNOWN"
CONFLICT, SUPERSEDED = "CONFLICTING_EVENT_EVIDENCE", "SUPERSEDED_EVIDENCE"
STATES = (EXACT, SAME_EVENT, DISTINCT, UNKNOWN, CONFLICT, SUPERSEDED)
DIRECTIONAL, CRITERION = "RAW_DIRECTIONAL_JUDGMENT", "RAW_CRITERION_INPUT"


def raw_uses(v52: dict) -> list:
    """v5-2A 비교 결과에서 원시 사용 목록: 레거시 v4 방향 판단(그대로) + 원자 기준 입력(비방향)."""
    out = []
    for h in v52["hypotheses"]:
        if h.get("hypothesis_status_at_as_of") != "EVALUATED":
            continue
        for i in (h.get("legacy_v4") or {}).get("items", []):
            out.append({"raw_id": f"RAW:{h['hypothesis_id']}:{i['relation_id']}:{i['evidence_id']}", "raw_kind": DIRECTIONAL, "hypothesis_id": h["hypothesis_id"],
                        "disease_concept_id": h["disease_concept_id"], "episode_id": h["diagnosis_episode_id"], "evidence_id": i["evidence_id"],
                        "relation_id": i["relation_id"], "directional_result": i["direction"], "hold_reason": i["hold_reason"], "label": "LEGACY_V4_UNVALIDATED"})
        for r in h.get("condition_evaluations", []):
            if r["criterion_role"] in ("COMPOSITE", "NO_VERIFIED_RULE"):
                continue
            for iid in r["input_item_ids"]:
                out.append({"raw_id": f"USE:{h['hypothesis_id']}:{r['criterion_id']}:{iid}", "raw_kind": CRITERION, "hypothesis_id": h["hypothesis_id"],
                            "disease_concept_id": h["disease_concept_id"], "episode_id": h["diagnosis_episode_id"], "evidence_id": iid,
                            "relation_id": r["criterion_id"], "directional_result": "NONE(NON_DIRECTIONAL_CRITERION_INPUT)", "hold_reason": "",
                            "label": "RESEARCH_CRITERION_INPUT"})
    return sorted(out, key=lambda x: x["raw_id"])


def item_index(catalogs: list) -> dict:
    """항목 ID → 출처 행(v5-2A evidence_linker.catalog 결과)."""
    return {i: {k: r[k] for k in ("record_key", "finding_key", "episode_id", "available_time", "observation_time", "item_kind")} for c in catalogs for i, r in c.items()}


def _item(iid: str, idx: dict, vis: set, ep: str):
    if iid in idx:
        return idx[iid]
    rec, suf = iid.rsplit(":", 1) if ":" in iid else (iid, "")
    if suf in ("CMR", "text") and rec in vis:
        return {"record_key": rec, "finding_key": ["RECORD_PATTERN", suf], "episode_id": ep, "available_time": None, "observation_time": None, "item_kind": "RECORD_PATTERN"}
    return None


def build_groups(raw: list, idx: dict, vis: set, decl: dict, known: set) -> tuple:
    """반환 (raw_rows, groups). 출처를 찾을 수 없는 판단은 거부(ValueError) — 원본에 없는 판단을 만들지 않기 위함."""
    raw_rows, buckets = [], {}
    for r in raw:
        it = _item(r["evidence_id"], idx, vis, r["episode_id"])
        if it is None:
            raise ValueError(f"SOURCE_NOT_FOUND: {r['raw_id']} 의 증거 {r['evidence_id']} 가 원본 출처에 없음")
        res = LN.resolve(it["record_key"], decl, known)
        row = {**r, "source_record_id": it["record_key"], "finding_key": list(it["finding_key"]), "item_episode_id": it["episode_id"],
               "available_time": it["available_time"], "observation_time": it["observation_time"], "source_event_id": res["event_id"],
               "lineage_basis": res["basis"], "lineage_issues": res["issues"], "derived_from_chain": res["ancestors"]}
        raw_rows.append(row)
        if res["event_id"]:
            key = (r["raw_kind"], r["hypothesis_id"], r["episode_id"], res["event_id"], tuple(map(str, it["finding_key"])), r["relation_id"])
        else:
            key = ("UNKNOWN", r["raw_id"])
        buckets.setdefault(key, []).append(row)
    groups = []
    for n, (key, rows) in enumerate(sorted(buckets.items(), key=lambda kv: str(kv[0]))):
        recs = sorted({x["source_record_id"] for x in rows})
        first = rows[0]
        if key[0] == "UNKNOWN":
            st = UNKNOWN
            why = "사건 확인 불가: " + ("; ".join(first["lineage_issues"]) if first["lineage_issues"] else "사건 ID·파생 관계 메타데이터 없음") + " — 독립 근거로 보지 않음"
        elif len(recs) >= 2:
            st = EXACT if all(any(LN.exact_pair(a, b, decl) for b in recs if b != a) for a in recs) else SAME_EVENT
            why = f"동일 검사 사건({first['source_event_id']})의 반복 기록 — 같은 소견·같은 관계·같은 가설·같은 에피소드"
        elif len(rows) >= 2:
            st = SAME_EVENT
            why = f"같은 기록 안 반복 표현(사건 {first['source_event_id']})"
        else:
            st = DISTINCT
            why = f"확인된 사건({first['source_event_id']})의 단일 판단"
        dirs = sorted({x["directional_result"] for x in rows})
        groups.append({"group_id": f"GRP:{first['hypothesis_id']}:{n}", "group_kind": first["raw_kind"], "hypothesis_id": first["hypothesis_id"],
                       "episode_id": first["episode_id"], "source_event_id": first["source_event_id"] if key[0] != "UNKNOWN" else None,
                       "finding_id": first["finding_key"], "relation_id": first["relation_id"], "raw_judgment_ids": sorted(x["raw_id"] for x in rows),
                       "evidence_ids": sorted({x["evidence_id"] for x in rows}), "source_record_ids": recs, "dependency_status": st,
                       "directional_result": dirs[0] if len(dirs) == 1 else "NOT_SINGLE_VALUED(원시 판단을 그대로 보라)",
                       "representative_is_new_judgment": False, "conflict_status": "NONE", "conflict_partner_groups": [], "correction_status": "NONE",
                       "grouping_reason": why, "available_times": sorted({x["available_time"] for x in rows if isinstance(x["available_time"], (int, float))})})
    for g in groups:                                                     # 같은 사건의 다른 소견·관계는 병합하지 않되 '별개 사건'이라고도 하지 않음
        if g["dependency_status"] == DISTINCT:
            peers = [o["group_id"] for o in groups if o is not g and o["source_event_id"] == g["source_event_id"]
                     and (o["hypothesis_id"], o["episode_id"]) == (g["hypothesis_id"], g["episode_id"])]
            if peers:
                g["dependency_status"] = SAME_EVENT
                g["grouping_reason"] = f"같은 사건({g['source_event_id']})의 다른 소견·관계 — 별도 그룹 유지(병합 안 함), 같은 사건 그룹 {sorted(peers)}"
    for g in groups:
        for rid in g["raw_judgment_ids"]:
            next(x for x in raw_rows if x["raw_id"] == rid)["group_id"] = g["group_id"]
    return raw_rows, groups


def counts(raw_rows: list, groups: list, kind: str) -> dict:
    rr = [r for r in raw_rows if r["raw_kind"] == kind]
    gg = [g for g in groups if g["group_kind"] == kind]
    return {"raw_count": len(rr), "group_count": len(gg),
            "raw_in_multi_member_groups": sum(len(g["raw_judgment_ids"]) for g in gg if len(g["raw_judgment_ids"]) >= 2),
            "dependency_unknown_raw": sum(len(g["raw_judgment_ids"]) for g in gg if g["dependency_status"] == UNKNOWN),
            "conflict_groups": sum(g["conflict_status"] != "NONE" for g in gg),
            "superseded_groups": sum(g["dependency_status"] == SUPERSEDED for g in gg),
            "note": "그룹 수는 증거 강도·확률·통계적 독립 근거 수가 아님(명시 메타데이터 기준 표시 단위)"}
