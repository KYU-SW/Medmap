"""공통 평가 지표(docs/MODEL_COMPARISON_PROTOCOL.md). 모든 비율의 기본 분모는 전체 문항. 조건부 성능은 적용 범위와 함께만 낸다."""
from __future__ import annotations

import random
from collections import defaultdict

from .schema import Effect, OutcomeStatus


def direction_of_grade(g: int) -> str:
    return "DEC" if g < 0 else "INC" if g > 0 else "ZERO"


def direction_of_output(o) -> str | None:
    """등급이 있으면 등급, 없으면 효과. UNCERTAIN·근거 부족은 방향 없음 → 답했지만 일치로 치지 않음."""
    if o.status != OutcomeStatus.ANSWERED:
        return None
    if o.grade is not None:
        return direction_of_grade(o.grade)
    return {Effect.SUPPORT: "INC", Effect.WEAKEN: "DEC", Effect.CONTRADICTION: "DEC", Effect.NO_CLEAR_EFFECT: "ZERO"}.get(o.effect)


def linear_weighted_kappa(pairs, cats=(-2, -1, 0, 1, 2)) -> float | None:
    """1 - Σw·O / Σw·E, w=|i-j|/(k-1). 쌍이 없거나 기대 불일치 0 이면 None."""
    if not pairs:
        return None
    n = len(pairs)
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    O = [[0.0] * k for _ in cats]
    for a, b in pairs:
        O[idx[a]][idx[b]] += 1
    ra = [sum(r) for r in O]
    rb = [sum(O[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = abs(i - j) / (k - 1)
            num += w * O[i][j]
            den += w * ra[i] * rb[j] / n
    return None if den == 0 else 1 - num / den


def evaluate(refs, outs) -> dict:
    """refs: ReferenceLabel, outs: {item_id: ReasonerOutput}. 누락 출력은 ABSTAIN 이 아니라 MISSING 으로 세고 분모에 남긴다."""
    n = len(refs)
    rows = [(r, outs.get(r.item_id)) for r in refs]
    missing = sum(o is None for _, o in rows)
    ans = [(r, o) for r, o in rows if o is not None and o.status == OutcomeStatus.ANSWERED]
    abst = sum(o is not None and o.status == OutcomeStatus.ABSTAIN for _, o in rows)
    nimpl = sum(o is not None and o.status == OutcomeStatus.NOT_IMPLEMENTED for _, o in rows)
    dirs = [(direction_of_grade(r.grade), direction_of_output(o)) for r, o in ans]
    correct = sum(a == b for a, b in dirs)
    with_dir = [(a, b) for a, b in dirs if b is not None]
    dec = [r for r in refs if r.grade < 0]
    dec_hit = sum(1 for r, o in ans if r.grade < 0 and direction_of_output(o) == "DEC")
    opp = sum(1 for a, b in dirs if {a, b} == {"INC", "DEC"})
    kpairs = [(r.grade, o.grade) for r, o in ans if o.grade is not None]
    cit_ok = sum(1 for _, o in ans if o.citations)
    claims = sum(len(o.claims) for _, o in ans)
    return {"n_items": n, "n_answered": len(ans), "coverage": _d(len(ans), n), "abstention_rate": _d(abst, n), "not_implemented_rate": _d(nimpl, n), "missing_output": missing,
            "direction_agreement_all_items": _d(correct, n), "direction_agreement_conditional_answered": _d(correct, len(ans)), "n_answered_with_direction": len(with_dir),
            "weighted_kappa_conditional": linear_weighted_kappa(kpairs), "n_kappa_pairs": len(kpairs), "weakening_recall_all_items": _d(dec_hit, len(dec)), "n_reference_weakening": len(dec),
            "opposite_direction_rate_all_items": _d(opp, n), "opposite_direction_rate_conditional": _d(opp, len(with_dir)), "answers_with_citation": _d(cit_ok, len(ans)), "claims_total": claims,
            "unsupported_claim_rate": "NOT_EVALUABLE_WITHOUT_CLAIM_AUDIT" if claims else None}


def _d(a, b):
    return None if not b else a / b


def by_group(refs, outs) -> dict:
    g = defaultdict(list)
    for r in refs:
        g[r.group or "UNSPECIFIED"].append(r)
    return {k: evaluate(v, outs) for k, v in sorted(g.items())}


def cluster_bootstrap(refs, outs, key: str, n: int = 2000, seed: int = 0) -> dict:
    """사례 단위 재표본추출. 값이 None 인 표본은 건수로 보고."""
    cases = defaultdict(list)
    for r in refs:
        cases[r.case_id].append(r)
    ids = sorted(cases)
    if not ids:
        return {"ci": None, "n_cases": 0}
    rng = random.Random(seed)
    vals, none = [], 0
    for _ in range(n):
        s = [r for _ in ids for r in cases[ids[rng.randrange(len(ids))]]]
        v = evaluate(s, outs)[key]
        if v is None or isinstance(v, str):
            none += 1
        else:
            vals.append(v)
    if not vals:
        return {"ci": None, "n_cases": len(ids), "n_undefined": none}
    vals.sort()
    return {"ci": [vals[int(.025 * len(vals))], vals[min(len(vals) - 1, int(.975 * len(vals)))]], "n_cases": len(ids), "n_undefined": none}


def paired_cluster_bootstrap(refs, outs_a, outs_b, key: str, n: int = 2000, seed: int = 0) -> dict:
    """같은 사례 표본으로 두 모델 차이(A−B)."""
    cases = defaultdict(list)
    for r in refs:
        cases[r.case_id].append(r)
    ids = sorted(cases)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = [r for _ in ids for r in cases[ids[rng.randrange(len(ids))]]]
        a, b = evaluate(s, outs_a)[key], evaluate(s, outs_b)[key]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            vals.append(a - b)
    if not vals:
        return {"diff_ci": None, "n_cases": len(ids)}
    vals.sort()
    return {"diff_ci": [vals[int(.025 * len(vals))], vals[min(len(vals) - 1, int(.975 * len(vals)))]], "n_cases": len(ids)}
