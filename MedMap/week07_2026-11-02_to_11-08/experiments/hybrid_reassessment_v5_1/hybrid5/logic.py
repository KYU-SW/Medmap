"""v4 4값 논리 재사용 + K-of-N(AT_LEAST_K, EXACTLY_K).
Atom 평가는 v4 eval_cond 를 그대로 호출하고, And/Or/Not 결합 규칙도 v4 와 같다(K-of-N 이 없으면 v4 와 결과 동일 — 테스트로 확인).
K-of-N 은 독립 기준(서로 다른 criterion_id)만 받는다. 같은 기준의 중복 근거는 기준 사실(Fact) 단계에서 하나로 합친다."""
from __future__ import annotations

from dataclasses import dataclass

from hybrid4 import logic as LG

T, F, U, C = LG.T, LG.F, LG.U, LG.C
Atom, And, Or, Not, Fact = LG.Atom, LG.And, LG.Or, LG.Not, LG.Fact


@dataclass(frozen=True)
class KofN:
    condition_id: str
    op: str                      # AT_LEAST_K / EXACTLY_K
    k: int
    items: tuple                 # ((criterion_id, node), ...)

    def __post_init__(self):
        if self.op not in ("AT_LEAST_K", "EXACTLY_K"):
            raise ValueError(self.op)
        ids = [c for c, _ in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.condition_id}: 같은 기준 ID 중복 — 종속·중복 기준은 독립 항목으로 세지 않음")
        if not 0 <= self.k <= len(ids):
            raise ValueError("k 범위")

    def to_dict(self):
        return {"op": self.op, "condition_id": self.condition_id, "k": self.k, "items": [{"criterion_id": c, "node": n.to_dict()} for c, n in self.items]}


def _outcome(op, k, x):
    """충족 개수 x 일 때 결과."""
    return (x >= k) if op == "AT_LEAST_K" else (x == k)


def eval5(node, facts: dict) -> dict:
    if isinstance(node, Atom):
        return LG.eval_cond(node, facts)
    if isinstance(node, Not):
        r = eval5(node.item, facts)
        return {"op": "NOT", "value": {T: F, F: T}.get(r["value"], r["value"]), "children": [r], "missing": r["missing"], "conflicts": r["conflicts"]}
    if isinstance(node, KofN):
        return eval_kofn(node, facts)
    kids = [eval5(i, facts) for i in node.items]
    vals = [x["value"] for x in kids]
    if isinstance(node, And):
        v = F if F in vals else C if C in vals else U if U in vals else T
    elif isinstance(node, Or):
        v = T if T in vals else C if C in vals else U if U in vals else F
    else:
        raise TypeError(type(node))
    out = {"op": "AND" if isinstance(node, And) else "OR", "value": v, "children": kids, "missing": sorted({m for x in kids for m in x["missing"]}),
           "conflicts": [c for x in kids for c in x["conflicts"]]}
    if v == T and isinstance(node, Or):
        out["true_paths"] = [i for i, x in enumerate(kids) if x["value"] == T]
    return out


def eval_kofn(node: KofN, facts: dict) -> dict:
    per = [(cid, eval5(n, facts)) for cid, n in node.items]
    st = {cid: r["value"] for cid, r in per}
    t, f = sum(v == T for v in st.values()), sum(v == F for v in st.values())
    u, c = sum(v == U for v in st.values()), sum(v == C for v in st.values())
    lo, hi = t, t + u + c
    if all(_outcome(node.op, node.k, x) for x in range(lo, hi + 1)):
        v, why = T, ""
    elif not any(_outcome(node.op, node.k, x) for x in range(lo, hi + 1)):
        v, why = F, ""
    else:
        # 미확정: 충돌 항목 수를 고정했을 때 미확인만으로도 결과가 갈리는지 / 충돌 때문에만 갈리는지
        unk_affects = any(len({_outcome(node.op, node.k, t + j + x) for x in range(0, u + 1)}) > 1 for j in range(0, c + 1))
        conf_affects = c > 0 and any(len({_outcome(node.op, node.k, t + i + j) for j in range(0, c + 1)}) > 1 for i in range(0, u + 1))
        v = C if conf_affects else U
        why = "CONFLICT_AND_UNKNOWN" if conf_affects and unk_affects else "CONFLICT_ONLY" if conf_affects else "UNKNOWN_ONLY"
    sup = sorted({s for cid, r in per if r["value"] == T for s in _sources(r)})
    return {"op": node.op, "condition_id": node.condition_id, "k": node.k, "n": len(per), "value": v, "evaluation_result": v, "undetermined_reason": why,
            "confirmed_true_count": t, "confirmed_false_count": f, "unknown_count": u, "conflict_count": c, "minimum_true": lo, "maximum_possible_true": hi,
            "criteria": {cid: r["value"] for cid, r in per}, "unresolved_conditions": [cid for cid, r in per if r["value"] in (U, C)],
            "conflicting_sources": [x for cid, r in per for x in r["conflicts"]], "supporting_evidence_ids": sup, "children": [r for _, r in per],
            "missing": sorted({m for _, r in per for m in r["missing"]}), "conflicts": [x for _, r in per for x in r["conflicts"]]}


def _sources(r):
    if r["op"] == "ATOM":
        return r.get("sources", [])
    return [s for k in r.get("children", []) for s in _sources(k)]


def combine_evidence(criterion_id: str, items: list) -> Fact:
    """같은 기준의 여러 근거(각 (value: True/False, source)) → 기준 사실 1개. 같은 방향 중복은 1개로, 반대 방향이 섞이면 CONFLICT."""
    vals = sorted({v for v, _ in items}, key=str)
    src = tuple(s for _, s in items)
    if not items:
        return Fact(criterion_id, "NOT_FOUND")
    if len(vals) > 1:
        return Fact(criterion_id, "CONFLICT", None, tuple(vals), src)
    return Fact(criterion_id, "FOUND", vals[0], tuple(vals), src)
