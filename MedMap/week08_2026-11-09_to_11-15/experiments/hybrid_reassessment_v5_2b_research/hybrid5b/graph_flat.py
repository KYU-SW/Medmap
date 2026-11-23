"""Graph vs Flat 통제 비교. 같은 환자 그래프 객체(같은 기록·사건·시간·메타데이터)와 같은 Shadow 카탈로그·평가 함수를 쓰고,
입력 수집만 다르다: graph = v4 DiseaseKG 순회 + EP 간선 순회, flat = FlatRuleTable 조회 + 행 필터(+ v5-2A collect_flat, v5-2A.1 meta_log 선언)."""
from __future__ import annotations

import json

from . import comparison as CMP
from . import legacy_adapter as LA
from . import shadow_reasoner as SR
from . import temporal as TP


def _norm(x):
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k != "mode"}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    return json.loads(json.dumps(strip(x), default=str, sort_keys=True))


def diff_paths(a, b, path=""):
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        return [p for k in sorted(set(a) | set(b)) for p in (diff_paths(a.get(k), b.get(k), f"{path}/{k}") if k in a and k in b else [f"{path}/{k}"])]
    if isinstance(a, list):
        return [path] if len(a) != len(b) else [p for i, (x, y) in enumerate(zip(a, b)) for p in diff_paths(x, y, f"{path}[{i}]")]
    return [] if a == b else [path]


def compare_case(pg, as_of, policy=None) -> dict:
    out = {}
    for part, fn in (("legacy", lambda m: LA.evaluate(pg, as_of, m)), ("shadow", lambda m: SR.evaluate(pg, as_of, m, policy))):
        g, f = _norm(fn("graph")), _norm(fn("flat"))
        out[part] = {"identical": g == f, "diff_paths": diff_paths(g, f)[:10]}
    lg, sg = LA.evaluate(pg, as_of, "graph"), SR.evaluate(pg, as_of, "graph", policy)
    lf, sf = LA.evaluate(pg, as_of, "flat"), SR.evaluate(pg, as_of, "flat", policy)
    cg, cf = _norm(CMP.compare(lg, sg)), _norm(CMP.compare(lf, sf))
    out["comparison"] = {"identical": cg == cf, "diff_paths": diff_paths(cg, cf)[:10]}
    return out


def compare_temporal() -> dict:
    g, f = _norm(TP.run_temporal("graph")), _norm(TP.run_temporal("flat"))
    return {"identical": g == f, "diff_paths": diff_paths(g, f)[:10]}
