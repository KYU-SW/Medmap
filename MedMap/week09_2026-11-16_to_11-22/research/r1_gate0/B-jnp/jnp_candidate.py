"""[6] JNP 후보 알고리즘 (전용). SYNTHETIC. 다른 프로젝트 모듈을 import 하지 않음 (exact_enum 과 코드 공유 없음).

단계
 1. 2-SAT 전파: 관측 T/F(단위절) + 의존성(imp: ¬a∨b, excl: ¬a∨¬b). 단위 전파(UP) 기반 2-SAT 판정으로
    S=∅ 검출, failed-literal 로 '강제된 리터럴' 확정 (2-SAT 에서 UP 는 반박 완전 -> 정확).
 2. 3값 적격성 가지치기: 강제값으로 규칙을 평가해 '항상 발동'(-> o 항상 부적격 -> 모든 플래그 0, LP 생략)
    / '절대 발동 안 함'(규칙 제거) / '미정' 으로 분류.
 3. 관련 변수 투영: 미정 규칙 또는 상태의존 점수에 등장하는 자유 변수만 R 로 두고, R 의 부분 할당을 DFS 로 열거.
    각 노드에서 UP 로 확장 가능성 검사 (2-SAT 은 UP 무충돌이면 나머지 만족 가능 -> 정확한 투영).
    잎마다 서명(적격 벡터, 점수 행렬)을 만들고 중복 제거.  -> 상태 수 2^|U| 대신 서명 수만큼만 LP.
 4. 서명마다 LP: pos = 최대 τ LP 1개; nec = 경쟁자별 min LP (중심점 사전검사로 조기 거짓).
    AA/EA/EE/AE 를 조기 종료 규칙으로 결합. EwAs 는 o 가 모든 서명에서 적격일 때 전체 부등식을 합친 LP 1개.
점수 누락: forall(nec) 은 o 0/경쟁자 1, exists(pos, EwAs) 는 o 1/경쟁자 0.
"""
import numpy as np
from scipy.optimize import linprog

TOL = 1e-7


class TwoSat:
    def __init__(self, k, clauses):
        self.k = k
        self.adj = {}  # literal -> implied literals ; literal = (var, val)
        for (a, va), (b, vb) in clauses:      # clause (a=va) ∨ (b=vb)
            self.adj.setdefault((a, 1 - va), []).append((b, vb))
            self.adj.setdefault((b, 1 - vb), []).append((a, va))

    def propagate(self, assign, lits):
        """assign: dict var->val (copied). returns new dict or None on conflict."""
        a = dict(assign)
        stack = list(lits)
        while stack:
            v, val = stack.pop()
            if v in a:
                if a[v] != val:
                    return None
                continue
            a[v] = val
            stack.extend(self.adj.get((v, val), []))
        return a


def solve(inst):
    k, n, m = inst['k'], inst['n'], inst['m']
    clauses = []
    for t, a, b in inst['deps']:
        clauses.append(((a, 0), (b, 1)) if t == 'imp' else ((a, 0), (b, 0)))
    ts = TwoSat(k, clauses)
    units = [(i, 1 if o == 'T' else 0) for i, o in enumerate(inst['obs']) if o in ('T', 'F')]
    stats = dict(n_signatures=0, n_lp=0, n_relevant=0, n_forced=0, pruned_options=0)
    root = ts.propagate({}, units)
    sat = root is not None
    if sat:  # complete 2-SAT check (greedy with UP; residual is subset of clauses)
        cur = root
        for v in range(k):
            if v in cur:
                continue
            nxt = ts.propagate(cur, [(v, 1)])
            if nxt is None:
                nxt = ts.propagate(cur, [(v, 0)])
            if nxt is None:
                sat = False; break
            cur = nxt
    if not sat:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)}, cat={o: 'INSUFFICIENT' for o in range(n)},
                    stats=stats)
    forced = dict(root)
    for v in range(k):
        if v in forced:
            continue
        if ts.propagate(root, [(v, 1)]) is None:
            forced = ts.propagate(forced, [(v, 0)])
        elif ts.propagate(root, [(v, 0)]) is None:
            forced = ts.propagate(forced, [(v, 1)])
    stats['n_forced'] = len(forced)
    # 3-valued rules
    live_rules = []
    never = [False] * n
    for o, lits in inst['rules']:
        if any(i in forced and forced[i] != v for i, v in lits):
            continue  # never fires
        rest = [(i, v) for i, v in lits if i not in forced]
        if not rest:
            never[o] = True  # always fires -> o never eligible
        else:
            live_rules.append((o, rest))
    stats['pruned_options'] = sum(never)
    R = sorted({i for _, lits in live_rules for i, _ in lits} |
               {i for o, j, i, d in inst['mods'] if i not in forced})
    stats['n_relevant'] = len(R)
    freq = {i: 0 for i in R}
    for _, lits in live_rules:
        for i, _ in lits:
            freq[i] += 1
    R.sort(key=lambda i: -freq[i])

    def sig_of(a):
        el = tuple((not never[o]) and not any(all(a.get(i) == v for i, v in lits)
                                             for oo, lits in live_rules if oo == o) for o in range(n))
        modbits = tuple(a.get(i, forced.get(i)) for _, _, i, _ in inst['mods'])
        return el, modbits
    sigs = set()

    def dfs(idx, a):
        if idx == len(R):
            sigs.add(sig_of(a)); return
        v = R[idx]
        if v in a:
            dfs(idx + 1, a); return
        for val in (0, 1):
            b = ts.propagate(a, [(v, val)])
            if b is not None:
                dfs(idx + 1, b)
    dfs(0, forced)
    sigs = sorted(sigs)
    stats['n_signatures'] = len(sigs)

    # weights
    lo = np.zeros(m); hi = np.ones(m)
    for j, kind, val in inst['bounds']:
        if kind == 'lo':
            lo[j] = max(lo[j], val)
        else:
            hi[j] = min(hi[j], val)
    bnds = list(zip(lo, hi))
    Aord = []
    for a, b in inst['ordinal']:
        r = np.zeros(m); r[b] = 1; r[a] = -1; Aord.append(r)
    Aord = np.array(Aord).reshape(-1, m)

    def lp(c, A_ub, b_ub, bounds, nvar):
        stats['n_lp'] += 1
        A_eq = np.zeros((1, nvar)); A_eq[0, :m] = 1
        res = linprog(c, A_ub=A_ub if len(A_ub) else None, b_ub=b_ub if len(A_ub) else None,
                      A_eq=A_eq, b_eq=[1.0], bounds=bounds, method='highs')
        if res.status != 0:
            raise RuntimeError(res.message)
        return res
    # a feasible interior-ish point for pre-checks: Chebyshev-free: maximize min slack is overkill; use LP center proxy
    wc = lp(np.zeros(m), Aord, np.zeros(len(Aord)), bnds, m).x

    miss = any(v is None for row in inst['base'] for v in row)

    def V_of(modbits, o, mode):
        V = np.zeros((n, m))
        for q in range(n):
            for j in range(m):
                x = inst['base'][q][j]
                if x is None:
                    x = (0.0 if q == o else 1.0) if mode == 'nec' else (1.0 if q == o else 0.0)
                V[q, j] = x
        for (q, j, i, d), bit in zip(inst['mods'], modbits):
            if bit == 1:
                V[q, j] += d
        return V

    def pos_rows_ok(rows):
        if not rows:
            return True
        R_ = np.array(rows)
        if np.all(R_ @ wc >= -TOL):
            return True
        c = np.zeros(m + 1); c[-1] = -1
        A = np.hstack([-R_, np.ones((len(R_), 1))]); b = np.zeros(len(R_))
        if len(Aord):
            A = np.vstack([A, np.hstack([Aord, np.zeros((len(Aord), 1))])]); b = np.r_[b, np.zeros(len(Aord))]
        res = lp(c, A, b, bnds + [(None, 1.0)], m + 1)
        return -res.fun >= -TOL

    def nec_ok(V, el, o):
        comps = [q for q in range(n) if q != o and el[q]]
        if any((V[o] - V[q]) @ wc < -TOL for q in comps):
            return False
        for q in comps:
            res = lp(V[o] - V[q], Aord, np.zeros(len(Aord)), bnds, m)
            if res.fun < -TOL:
                return False
        return True

    flags, cat = {}, {}
    for o in range(n):
        if never[o] or not any(el[o] for el, _ in sigs):
            flags[o] = [0, 0, 0, 0, 0]; continue
        AA = True; EA = False; EE = False; AE = True
        for el, mb in sigs:
            if not el[o]:
                AA = False; AE = False; continue
            need_nec = AA or not EA
            nv = None
            if need_nec:
                nv = nec_ok(V_of(mb, o, 'nec' if miss else None), el, o)
                if not nv:
                    AA = False
                else:
                    EA = True
            if nv and not miss:
                pv = True
            elif (not EE) or AE:
                Vp = V_of(mb, o, 'pos' if miss else None)
                pv = pos_rows_ok([Vp[o] - Vp[q] for q in range(n) if q != o and el[q]])
            else:
                pv = None
            if pv is True:
                EE = True
            elif pv is False:
                AE = False
        if AA:
            EwAs = True
        elif not AE:
            EwAs = False
        else:
            rows = []
            for el, mb in sigs:
                Vp = V_of(mb, o, 'pos' if miss else None)
                rows += [Vp[o] - Vp[q] for q in range(n) if q != o and el[q]]
            EwAs = pos_rows_ok(rows)
        flags[o] = [int(AA), int(EE), int(AE), int(EA), int(EwAs)]
    for o in range(n):
        own = False
        for j in range(m):
            if inst['base'][o][j] is None:
                c = np.zeros(m); c[j] = -1
                if -lp(c, Aord, np.zeros(len(Aord)), bnds, m).fun > TOL:
                    own = True
        AA, EE, AE, EA, _ = flags[o]
        cat[o] = ('INSUFFICIENT' if own else 'ALWAYS' if AA else 'EXCLUDED' if not EE
                  else 'CONDITIONAL' if EA else 'UNDETERMINED')
    return dict(flags=flags, cat=cat, stats=stats)


if __name__ == "__main__":
    import json, sys
    d = json.load(open(sys.argv[1]))
    for name, x in d.items():
        print(name, solve(x))
