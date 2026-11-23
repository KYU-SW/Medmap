"""LEGACY_V4 판단 수집: hybrid4.reason.Reasoner(실제 카탈로그, mode).evaluate 를 그대로 호출(원본 무수정). 항목을 비교용 공통 형식으로만 바꾼다."""
from __future__ import annotations

from hybrid4 import graphs as GR
from hybrid4 import reason as RS4

_CACHE = {}


def reasoner(mode: str):
    if mode not in _CACHE:
        _CACHE[mode] = RS4.Reasoner(GR.normalized_relations(), mode)
    return _CACHE[mode]


def evaluate(pg, as_of: float, mode: str = "graph") -> dict:
    if not pg.active_hypotheses(as_of):
        return {"engine": "LEGACY_V4", "as_of": as_of, "mode": mode, "judgments": [], "abstained": []}
    r = reasoner(mode).evaluate(pg, as_of)
    js, ab = [], []
    for h in r["hypotheses"]:
        for i in h["items"]:
            row = {"engine": "LEGACY_V4", "mode": mode, "hyp_id": h["hyp_id"], "episode_id": h["episode_id"], "evidence_id": i["evidence_id"], "source_record_id": i["source_record_id"],
                   "relation_id": i.get("relation_id") or "", "direction": i["direction"], "stage": i.get("stage", ""), "hold_reason": i.get("hold_reason", ""),
                   "missing": sorted((i.get("decision") or {}).get("missing", [])),
                   "conflicts": [c.get("key") for c in (i.get("decision") or {}).get("conflicts", [])],
                   "optional_unchecked": sorted((i.get("decision") or {}).get("optional_unchecked", [])),
                   "sources": [s.get("location") for s in i.get("sources", [])] if i.get("relation_id") else []}
            (js if i.get("relation_id") else ab).append(row)
    key = lambda j: (j["hyp_id"], j["evidence_id"], j["relation_id"])  # noqa: E731
    return {"engine": "LEGACY_V4", "as_of": as_of, "mode": mode, "judgments": sorted(js, key=key), "abstained": sorted(ab, key=key)}
