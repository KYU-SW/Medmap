"""[3] 기존 강건 선호 비교 (ROR 식 necessary/possible pairwise 관계) — 상태 하나에서. SYNTHETIC.

  a ≿_N b  <=>  min_{w∈W} U(a)-U(b) >= 0      (Greco et al. UTA-GMS/GRIP 식 필연 관계의 가중합 버전)
  a ≿_P b  <=>  max_{w∈W} U(a)-U(b) >= 0
  필연 최선(pairwise) : a 적격 ∧ ∀ 적격 b: a ≿_N b       -> forall w 최적과 정확히 동치 (∀w∀b = ∀b∀w)
  가능 최선(pairwise) : a 적격 ∧ ∀ 적격 b: a ≿_P b       -> exists w 최적의 '근사'. ∃w∀b ≠ ∀b∃w 이므로 과대 판정 가능
"""
import numpy as np
from pref_lp import min_over_W, max_over_W, TOL


def relations(V, el, Wsys):
    n = len(el)
    N = np.zeros((n, n), bool); P = np.zeros((n, n), bool)
    for a in range(n):
        for b in range(n):
            if a == b or not (el[a] and el[b]):
                continue
            d = V[a] - V[b]
            N[a, b] = min_over_W(d, Wsys) >= -TOL
            P[a, b] = max_over_W(d, Wsys) >= -TOL
    return N, P


def best_flags(V, el, Wsys):
    """returns per option (nec_best, pos_best_pairwise)."""
    N, P = relations(V, el, Wsys)
    n = len(el)
    out = []
    for a in range(n):
        if not el[a]:
            out.append((False, False)); continue
        others = [b for b in range(n) if b != a and el[b]]
        out.append((all(N[a, b] for b in others), all(P[a, b] for b in others)))
    return out
