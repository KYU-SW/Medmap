"""증거 중복·종속성. 명시된 메타데이터(source_event_id·derived_from·exact_duplicate_of·source_record_id)만 사용한다.
- 문장이 비슷하다는 이유로 같은 사건이라고 추측하지 않는다.
- 메타데이터가 없다는 이유로 독립이라고 판단하지 않는다(DEPENDENCY_UNKNOWN).
- 원본·중복 표현을 지우지 않는다. 중복은 그룹으로 표시만 한다(추적용, 점수·확률 없음).
- 서로 다른 시점의 실제 측정은 각자 사건 ID 가 있으면 DISTINCT_OBSERVATION 으로 남는다."""
from __future__ import annotations

from dataclasses import dataclass

EXACT, DERIVED, SHARED, DISTINCT, UNKNOWN = "EXACT_DUPLICATE", "DERIVED_FROM_SAME_SOURCE", "SHARED_EVIDENCE", "DISTINCT_OBSERVATION", "DEPENDENCY_UNKNOWN"
STATES = (EXACT, DERIVED, SHARED, DISTINCT, UNKNOWN)
POLICY = "명시 메타데이터만 사용. 없으면 DEPENDENCY_UNKNOWN. 문장 유사성으로 같은 사건 추정 없음. 중복은 표시만 하고 삭제·점수화하지 않음."


@dataclass(frozen=True)
class RecordMeta:
    record_key: str                      # 기록 ID(문서) 또는 구조화 검사 행 ID
    source_event_id: str | None = None   # 원본 검사·사건 ID
    derived_from: tuple = ()             # 이 기록이 파생된 기록 키
    exact_duplicate_of: str | None = None

    def as_row(self) -> dict:
        return {"record_key": self.record_key, "source_event_id": self.source_event_id, "derived_from": list(self.derived_from), "exact_duplicate_of": self.exact_duplicate_of}


def group_of(key: str, meta: dict, _seen=None) -> tuple:
    """(basis, group_key). basis: SOURCE_EVENT / DERIVED_CHAIN / RECORD_ONLY. 파생 사슬은 첫 부모를 따라 올라간다."""
    seen = set(_seen or ())
    m = meta.get(key)
    if key in seen or m is None:
        return "RECORD_ONLY", f"REC:{key}"
    seen.add(key)
    if m.source_event_id:
        return "SOURCE_EVENT", f"EVT:{m.source_event_id}"
    parents = list(m.derived_from) + ([m.exact_duplicate_of] if m.exact_duplicate_of else [])
    if parents:
        basis, g = group_of(parents[0], meta, seen)
        return ("SOURCE_EVENT" if basis == "SOURCE_EVENT" else "DERIVED_CHAIN"), g
    return "RECORD_ONLY", f"REC:{key}"


def _exact(a: str, b: str, meta: dict) -> bool:
    ma, mb = meta.get(a), meta.get(b)
    return bool((ma and ma.exact_duplicate_of == b) or (mb and mb.exact_duplicate_of == a))


def analyze(items: list, meta: dict) -> dict:
    """items: 증거 목록 행(item_id, record_key, finding_key, item_kind, episode_id, observation_time, available_time)."""
    groups = {}
    for it in sorted(items, key=lambda x: x["item_id"]):
        basis, g = group_of(it["record_key"], meta)
        groups.setdefault(g, []).append((it, basis))
    rows, dep_groups, dup_groups, discrepancies = {}, [], [], []
    for g in sorted(groups):
        members = groups[g]
        explicit = any(b != "RECORD_ONLY" for _, b in members)
        recs = sorted({it["record_key"] for it, _ in members})
        bykey = {}
        for it, _ in members:
            bykey.setdefault(tuple(it["finding_key"]), []).append(it)
        dup_of = {}
        if explicit:
            for n, (fk, its) in enumerate(sorted(bykey.items(), key=lambda kv: str(kv[0]))):
                if len({i["record_key"] for i in its}) >= 2:
                    did = f"DUP:{g}:{n}"
                    rel = EXACT if all(any(_exact(a["record_key"], b["record_key"], meta) for b in its if b["record_key"] != a["record_key"]) for a in its) else DERIVED
                    dup_groups.append({"duplicate_group_id": did, "dependency_group_id": g, "finding_key": list(fk), "members": sorted(i["item_id"] for i in its),
                                       "records": sorted({i["record_key"] for i in its}), "relation": rel,
                                       "independent_source_events": 1, "note": "같은 원본 사건의 반복 표현 — 독립 근거로 세지 않음(추적용, 점수 아님)"})
                    for i in its:
                        dup_of[i["item_id"]] = did
            obs = [it for it, _ in members if it["item_kind"] == "LAB_OBSERVATION"]
            for an in sorted({o["finding_key"][1] for o in obs}):
                vals = sorted({(o["finding_key"][2], o["finding_key"][3], o["finding_key"][4]) for o in obs if o["finding_key"][1] == an}, key=str)
                if len(vals) > 1:
                    discrepancies.append({"dependency_group_id": g, "analyte": an, "values": [list(v) for v in vals],
                                          "items": sorted(o["item_id"] for o in obs if o["finding_key"][1] == an), "resolution": "NOT_RESOLVED(어느 값도 삭제·선택하지 않음)"})
        for it, b in members:
            if not explicit:
                st = UNKNOWN if len(members) == 1 else DERIVED
                basis = "NO_EVENT_METADATA" if len(members) == 1 else "SAME_SOURCE_RECORD(다른 기록과의 관계는 미확인)"
            else:
                same = [o for o in bykey[tuple(it["finding_key"])] if o["record_key"] != it["record_key"]]
                st = EXACT if any(_exact(it["record_key"], o["record_key"], meta) for o in same) else DERIVED if len(members) > 1 else DISTINCT
                basis = b
            m = meta.get(it["record_key"])
            rows[it["item_id"]] = {"evidence_id": it["item_id"], "item_kind": it["item_kind"], "source_record_id": it["record_key"],
                                   "source_event_id": m.source_event_id if m else None, "derived_from": list(m.derived_from) if m else [],
                                   "exact_duplicate_of": m.exact_duplicate_of if m else None, "dependency_group_id": g, "group_basis": basis,
                                   "duplicate_group_id": dup_of.get(it["item_id"]), "dependency_status": st, "shared_evidence_hypotheses": [],
                                   "episode_id": it["episode_id"], "observation_time": it["observation_time"], "available_time": it["available_time"]}
        dep_groups.append({"dependency_group_id": g, "explicit_metadata": explicit, "members": sorted(it["item_id"] for it, _ in members), "records": recs})
    return {"policy": POLICY, "items": rows, "dependency_groups": dep_groups, "duplicate_groups": dup_groups, "value_discrepancies": discrepancies}


def source_dependency(item_ids: list, dep: dict) -> dict:
    """기준 행의 출처가 몇 개의 명시 사건 그룹에서 왔는지(정보 표시용, 점수·가중치 아님)."""
    rows = [dep["items"][i] for i in item_ids if i in dep["items"]]
    explicit = sorted({r["dependency_group_id"] for r in rows if r["dependency_status"] != UNKNOWN})
    return {"source_groups": explicit, "dependency_unknown_items": sorted(r["evidence_id"] for r in rows if r["dependency_status"] == UNKNOWN),
            "duplicate_groups": sorted({r["duplicate_group_id"] for r in rows if r["duplicate_group_id"]}), "note": "개수는 표시용 — 확률·가중치에 쓰지 않음"}
