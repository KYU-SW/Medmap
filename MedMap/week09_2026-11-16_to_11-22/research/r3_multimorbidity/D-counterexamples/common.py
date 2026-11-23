"""[가상] SYNTHETIC 공통 도구. 실제 환자·실제 약물 규칙 아님.

- solve_binary_milp: scipy.optimize.milp(HiGHS) 래퍼. 변수는 모두 이진(또는 지정 연속).
- brute force 도구: 작은 n 에서 2^n 전수 열거 (정답 생성기, MILP 와 import 독립).
"""
import itertools
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

OPTS = dict(presolve=True, time_limit=60, mip_rel_gap=0.0)


def solve_milp(c, A_rows, lo, hi, integrality, lb, ub, maximize=False):
    """c: 목적계수, A_rows: list of dense rows. 반환 (status, x, obj)."""
    c = np.asarray(c, float)
    if maximize:
        c = -c
    cons = []
    if A_rows:
        cons = [LinearConstraint(np.asarray(A_rows, float), np.asarray(lo, float), np.asarray(hi, float))]
    res = milp(c, constraints=cons, integrality=np.asarray(integrality),
               bounds=Bounds(np.asarray(lb, float), np.asarray(ub, float)), options=OPTS)
    if res.status != 0 or res.x is None:
        return res.status, None, None
    obj = -res.fun if maximize else res.fun
    return 0, res.x, obj


def all_subsets(n):
    for mask in range(1 << n):
        yield mask, [i for i in range(n) if mask >> i & 1]


def minimal_sets(sets):
    """부분집합 포함 관계에서 극소인 것만 남김."""
    sets = sorted(set(frozenset(s) for s in sets), key=len)
    out = []
    for s in sets:
        if not any(o <= s for o in out):
            out.append(s)
    return out
