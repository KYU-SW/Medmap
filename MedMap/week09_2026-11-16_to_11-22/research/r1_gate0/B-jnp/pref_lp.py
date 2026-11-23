"""[2] 불완전 선호 전체 고려 — 상태 하나(고정 s)에서 LP 로 필연/가능 최적 판정. SYNTHETIC.

  nec(o): o 적격이고, 모든 적격 경쟁자 q 에 대해 min_{w∈W} (v_o - v_q)·w >= -tol   (q 마다 LP 1개)
  pos(o): max τ s.t. w∈W, (v_o - v_q)·w >= τ  (모든 적격 q)  ;  τ* >= -tol 이면 가능 최적   (LP 1개)
  pos_multi(rows): 여러 상태의 최적성 부등식을 한 LP 로 (exists w forall s 용)
scipy.optimize.linprog (HiGHS) 사용. exact_enum.py 와 코드 공유 없음.
"""
import numpy as np
from scipy.optimize import linprog

TOL = 1e-7


def w_system(inst):
    m = inst['m']
    A, b = [], []
    for a, c in inst['ordinal']:
        row = np.zeros(m); row[c] = 1; row[a] = -1; A.append(row); b.append(0.0)
    lo = np.zeros(m); hi = np.ones(m)
    for j, kind, val in inst['bounds']:
        if kind == 'lo':
            lo[j] = max(lo[j], val)
        else:
            hi[j] = min(hi[j], val)
    A = np.array(A) if A else np.zeros((0, m))
    return A, np.array(b), list(zip(lo, hi))


def scores(inst, s, o_target=-1, mode=None):
    """mode None: no missing; 'nec': o missing->0, others->1; 'pos': o->1, others->0"""
    n, m = inst['n'], inst['m']
    V = np.zeros((n, m))
    for o in range(n):
        for j in range(m):
            v = inst['base'][o][j]
            if v is None:
                if mode == 'nec':
                    v = 0.0 if o == o_target else 1.0
                elif mode == 'pos':
                    v = 1.0 if o == o_target else 0.0
                else:
                    v = 0.0
            V[o, j] = v
    for o, j, i, d in inst['mods']:
        if s[i] == 1:
            V[o, j] += d
    return V


def min_over_W(d, Wsys):
    A, b, bnds = Wsys
    m = len(d)
    res = linprog(d, A_ub=A if len(A) else None, b_ub=b if len(A) else None,
                  A_eq=np.ones((1, m)), b_eq=[1.0], bounds=bnds, method='highs')
    if res.status != 0:
        raise RuntimeError(f"LP failed {res.message}")
    return res.fun


def max_over_W(d, Wsys):
    return -min_over_W(-np.asarray(d), Wsys)


def nec(V, el, o, Wsys):
    if not el[o]:
        return False
    for q in range(len(el)):
        if q != o and el[q] and min_over_W(V[o] - V[q], Wsys) < -TOL:
            return False
    return True


def pos_multi(rows, Wsys):
    """exists w in W with r·w >= 0 for all rows r (rows = v_o - v_q)."""
    A, b, bnds = Wsys
    m = len(bnds)
    if len(rows) == 0:
        return True
    R = np.array(rows)
    # variables [w, tau]; maximize tau ; constraints -R w + tau <= 0 ; tau <= 1
    c = np.zeros(m + 1); c[-1] = -1
    A_ub = np.hstack([-R, np.ones((len(R), 1))])
    b_ub = np.zeros(len(R))
    if len(A):
        A_ub = np.vstack([A_ub, np.hstack([A, np.zeros((len(A), 1))])])
        b_ub = np.concatenate([b_ub, b])
    A_eq = np.hstack([np.ones((1, m)), np.zeros((1, 1))])
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=[1.0],
                  bounds=list(bnds) + [(None, 1.0)], method='highs')
    if res.status != 0:
        raise RuntimeError(f"LP failed {res.message}")
    return -res.fun >= -TOL


def pos(V, el, o, Wsys):
    if not el[o]:
        return False
    rows = [V[o] - V[q] for q in range(len(el)) if q != o and el[q]]
    return pos_multi(rows, Wsys)


def state_flags(inst, s, el, o, Wsys):
    """(nec, pos) for one state with missing-score substitution."""
    miss = any(v is None for row in inst['base'] for v in row)
    Vn = scores(inst, s, o, 'nec' if miss else None)
    Vp = scores(inst, s, o, 'pos' if miss else None)
    return nec(Vn, el, o, Wsys), pos(Vp, el, o, Wsys)


def categorize(inst, flags, Wsys, empty=False):
    n, m = inst['n'], inst['m']
    cat = {}
    for o in range(n):
        if empty:
            cat[o] = 'INSUFFICIENT'; continue
        AA, EE, AE, EA = flags[o][:4]
        own = False
        for j in range(m):
            if inst['base'][o][j] is None:
                e = np.zeros(m); e[j] = 1
                if max_over_W(e, Wsys) > TOL:
                    own = True
        cat[o] = ('INSUFFICIENT' if own else 'ALWAYS' if AA else 'EXCLUDED' if not EE
                  else 'CONDITIONAL' if EA else 'UNDETERMINED')
    return cat
