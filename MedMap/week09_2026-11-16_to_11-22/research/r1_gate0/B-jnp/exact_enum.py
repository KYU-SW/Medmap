"""[1] 정확한 기준선 (ground truth). SYNTHETIC.

독립성: 이 파일은 다른 어떤 모듈도 import 하지 않는다 (numpy, itertools 만 사용). LP/MILP 솔버를 쓰지 않는다.
방법:
  - 가능 임상 상태 S: 미확인('U')/상충('C') 조건의 모든 T/F 조합을 열거하고 의존성 위반 조합을 버린다.
  - 가중치 polytope W 의 꼭짓점: (m-1)개 부등식 + sum w = 1 을 등식으로 두는 모든 조합의 m x m 선형계를
    풀어 가능해인 것만 남기는 brute-force 꼭짓점 열거.
  - forall w (필연): o 가 최적 <=> 모든 꼭짓점 v 에서 U(o,v) >= U(o',v)  (선형 함수의 polytope 최소는 꼭짓점에서)
  - exists w (가능): W 꼭짓점만으로는 불충분(타협안 사례, HC2 O3). 그래서 W ∩ {U(o)>=U(o') for eligible o'} 라는
    확장 polytope 의 꼭짓점을 같은 brute-force 로 찾아 비어있는지 판정 (유계 polytope 는 비어있지 않으면 꼭짓점 보유).
  - exists w forall s: 모든 상태의 최적성 부등식을 합친 polytope 의 비어있음 판정 (조합 수가 LIMIT 넘으면 None).
메모이제이션: (적격 벡터, 점수 행렬) 서명이 같은 상태는 판정이 같으므로 캐시 (정확성 보존).
점수 누락(None): 기준 점수 base ∈ [0,1] 미지수로 보고 forall 판정은 최악값(o 0, 경쟁자 1), exists 판정은 최선값(o 1, 경쟁자 0) 대입.
"""
import itertools
import json
import sys
import numpy as np

TOL = 1e-9
LIMIT = 2_000_000
_COMB_CACHE = {}


def _combs(r, c):
    key = (r, c)
    if key not in _COMB_CACHE:
        _COMB_CACHE[key] = np.array(list(itertools.combinations(range(r), c)), dtype=np.int64).reshape(-1, c)
    return _COMB_CACHE[key]


def _iter_combs(r, c, chunk=200_000):
    from math import comb
    total = comb(r, c)
    if total <= 300_000:
        yield _combs(r, c)
        return
    it = itertools.combinations(range(r), c)
    while True:
        block = list(itertools.islice(it, chunk))
        if not block:
            return
        yield np.array(block, dtype=np.int64)


def vertices(G, h, first_only=False):
    """Vertices of {w : G w <= h, sum w = 1}. G includes -w_j <= 0 rows."""
    G = np.asarray(G, float)
    h = np.asarray(h, float)
    r, m = G.shape
    found = []
    for C in _iter_combs(r, m - 1):
        A = np.empty((len(C), m, m))
        A[:, :m - 1, :] = G[C]
        A[:, m - 1, :] = 1.0
        b = np.empty((len(C), m))
        b[:, :m - 1] = h[C]
        b[:, m - 1] = 1.0
        det = np.linalg.det(A)
        ok = np.abs(det) > 1e-12
        if not ok.any():
            continue
        x = np.linalg.solve(A[ok], b[ok][..., None])[..., 0]
        feas = np.all(x @ G.T <= h + 1e-9, axis=1)
        if feas.any():
            if first_only:
                return x[feas][:1]
            found.append(x[feas])
    if not found:
        return np.zeros((0, m))
    V = np.vstack(found)
    V = np.unique(np.round(V, 10), axis=0)
    return V


def w_constraints(inst):
    m = inst['m']
    G, h = [], []
    for j in range(m):
        row = [0.0] * m; row[j] = -1.0; G.append(row); h.append(0.0)
    for a, b in inst['ordinal']:
        row = [0.0] * m; row[b] = 1.0; row[a] = -1.0; G.append(row); h.append(0.0)
    for j, kind, val in inst['bounds']:
        row = [0.0] * m
        if kind == 'lo':
            row[j] = -1.0; G.append(row); h.append(-val)
        else:
            row[j] = 1.0; G.append(row); h.append(val)
    return np.array(G), np.array(h)


def all_worlds(inst):
    k, obs = inst['k'], inst['obs']
    free = [i for i in range(k) if obs[i] in ('U', 'C')]
    fixed = [1 if o == 'T' else 0 for o in obs]
    out = []
    for bits in itertools.product((0, 1), repeat=len(free)):
        s = list(fixed)
        for i, b in zip(free, bits):
            s[i] = b
        good = True
        for t, a, b in inst['deps']:
            if t == 'imp' and s[a] == 1 and s[b] == 0:
                good = False; break
            if t == 'excl' and s[a] == 1 and s[b] == 1:
                good = False; break
        if good:
            out.append(tuple(s))
    return out


def eligible(inst, s):
    el = [True] * inst['n']
    for o, lits in inst['rules']:
        if all(s[i] == v for i, v in lits):
            el[o] = False
    return tuple(el)


def score_matrix(inst, s, fill_self, fill_other, o_target):
    n, m = inst['n'], inst['m']
    V = np.zeros((n, m))
    for o in range(n):
        for j in range(m):
            b = inst['base'][o][j]
            if b is None:
                b = fill_self if o == o_target else fill_other
            V[o, j] = b
    for o, j, i, d in inst['mods']:
        if s[i] == 1:
            V[o, j] += d
    return V


def solve(inst):
    n, m = inst['n'], inst['m']
    G, h = w_constraints(inst)
    WV = vertices(G, h)
    S = all_worlds(inst)
    flags = {}
    has_missing = any(b is None for row in inst['base'] for b in row)
    if len(S) == 0:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)}, n_worlds=0,
                    cat={o: 'INSUFFICIENT' for o in range(n)})
    cache_nec, cache_pos = {}, {}

    def nec(o, s, el):
        if not el[o]:
            return False
        V = score_matrix(inst, s, 0.0, 1.0, o) if has_missing else score_matrix(inst, s, 0, 0, -1)
        key = (o, el, V.tobytes())
        if key in cache_nec:
            return cache_nec[key]
        U = WV @ V.T  # (nv, n)
        res = True
        for q in range(n):
            if q != o and el[q] and np.any(U[:, o] - U[:, q] < -TOL):
                res = False; break
        cache_nec[key] = res
        return res

    def pos_rows(o, s, el):
        V = score_matrix(inst, s, 1.0, 0.0, o) if has_missing else score_matrix(inst, s, 0, 0, -1)
        rows = [V[q] - V[o] for q in range(n) if q != o and el[q]]  # (v_q - v_o) w <= 0
        return rows, V

    def pos(o, s, el):
        if not el[o]:
            return False
        rows, V = pos_rows(o, s, el)
        key = (o, el, V.tobytes())
        if key in cache_pos:
            return cache_pos[key]
        G2 = np.vstack([G] + [np.array(rows)]) if rows else G
        h2 = np.concatenate([h, np.zeros(len(rows))])
        res = len(vertices(G2, h2, first_only=True)) > 0
        cache_pos[key] = res
        return res

    els = [eligible(inst, s) for s in S]
    for o in range(n):
        N = [nec(o, s, el) for s, el in zip(S, els)]
        P = [pos(o, s, el) for s, el in zip(S, els)]
        AA, EE, AE, EA = all(N), any(P), all(P), any(N)
        # exists w forall s
        EwAs = None
        if not all(el[o] for el in els):
            EwAs = False
        elif not AE:
            EwAs = False
        else:
            rows = set()
            for s, el in zip(S, els):
                rr, _ = pos_rows(o, s, el)
                for r_ in rr:
                    rows.add(tuple(np.round(r_, 12)))
            rows = [np.array(r_) for r_ in rows]
            rows = [r_ for r_ in rows if not np.all(r_ <= TOL)]  # always satisfied on simplex
            if any(np.all(r_ > TOL) for r_ in rows):
                EwAs = False
            else:
                from math import comb
                Gt = np.vstack([G] + rows) if rows else G
                ht = np.concatenate([h, np.zeros(len(rows))])
                if comb(len(Gt), m - 1) > LIMIT:
                    EwAs = None
                else:
                    EwAs = len(vertices(Gt, ht, first_only=True)) > 0
        flags[o] = [int(AA), int(EE), int(AE), int(EA), (None if EwAs is None else int(EwAs))]
    # category
    cat = {}
    for o in range(n):
        AA, EE, AE, EA, _ = flags[o]
        own_missing = False
        for j in range(m):
            if inst['base'][o][j] is None:
                e = np.zeros(m); e[j] = 1.0
                if WV.shape[0] and np.max(WV @ e) > TOL:
                    own_missing = True
        if own_missing:
            cat[o] = 'INSUFFICIENT'
        elif AA:
            cat[o] = 'ALWAYS'
        elif not EE:
            cat[o] = 'EXCLUDED'
        elif EA:
            cat[o] = 'CONDITIONAL'
        else:
            cat[o] = 'UNDETERMINED'
    return dict(flags=flags, cat=cat, n_worlds=len(S))


if __name__ == "__main__":
    inst = json.load(open(sys.argv[1]))
    if 'k' not in inst:
        for name, x in inst.items():
            print(name, solve(x))
    else:
        print(solve(inst))
