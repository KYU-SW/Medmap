"""[5] 정확한 제약 해결기 방식: scipy.optimize.milp (HiGHS). SYNTHETIC.

공통 인코딩 (상태를 이진 변수로):
  s_i ∈ {0,1} (관측 T/F 는 고정, U/C 는 자유), 의존성: imp s_a <= s_b, excl s_a + s_b <= 1
  규칙 발동 r = AND(literals):  r <= ℓ,  r >= Σℓ - (|L|-1)
  적격 e_o = NOR(r):            e_o <= 1 - r,  e_o >= 1 - Σ r
  상태 의존 점수 w_j * s_i -> z_ji (McCormick, s 이진이므로 정확)
질의 (선택지 o 마다):
  EE  (∃s∃w)  : e_o=1, ∀q: U(o)-U(q) >= -M(1-e_q)            -> 단일 MILP 실행가능성
  AA  (∀s∀w)  : 보완질의 ∃s∃w [o 부적격 ∨ ∃q 적격 U(q)-U(o) > 0] -> max t MILP, t*<=tol 이면 참
  EA  (∃s∀w)  : e_o=1, 각 q 에 대해 min_w (U(o)-U(q)) >= 0 을 LP 쌍대(y>=0, μ)로 선형화 (s 는 d 에 선형으로만 등장)
  AE  (∀s∃w)  : 보완질의 ∃s [o 부적격] 또는 ∃s [{w: o 최적} = ∅] 의 Farkas 증명서 (λ_q * s_i 는 McCormick)
  EwAs(∃w∀s)  : ∃s o 부적격이면 거짓. 아니면 cutting plane: LP master(w) + MILP separation(s) 반복.
점수 누락: forall 질의(AA, EA)는 o 0/경쟁자 1, exists 질의(EE, AE, EwAs)는 o 1/경쟁자 0 대입.
"""
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds, linprog
from scipy.sparse import lil_matrix

TOL = 1e-6  # HiGHS primal feasibility tolerance is ~1e-6 (observed -1.000001 for -1)
OPTS = dict(mip_rel_gap=1e-9, presolve=True, time_limit=120)
STATS = {'status4_retries': 0}


class Model:
    def __init__(self):
        self.lb, self.ub, self.integ = [], [], []
        self.rows, self.rlo, self.rhi = [], [], []

    def var(self, lb, ub, integer=False):
        self.lb.append(lb); self.ub.append(ub); self.integ.append(1 if integer else 0)
        return len(self.lb) - 1

    def add(self, coefs, lo=-np.inf, hi=np.inf):
        self.rows.append(coefs); self.rlo.append(lo); self.rhi.append(hi)

    def solve(self, obj=None, maximize=False):
        nv = len(self.lb)
        c = np.zeros(nv)
        if obj:
            for v, a in obj.items():
                c[v] += a
        if maximize:
            c = -c
        cons = []
        if self.rows:
            A = lil_matrix((len(self.rows), nv))
            for r, coefs in enumerate(self.rows):
                for v, a in coefs.items():
                    A[r, v] += a
            cons = [LinearConstraint(A.tocsr(), np.array(self.rlo), np.array(self.rhi))]
        res = milp(c, constraints=cons, integrality=np.array(self.integ),
                   bounds=Bounds(np.array(self.lb, float), np.array(self.ub, float)), options=OPTS)
        if res.status == 4:
            # scipy 1.17 maps HiGHS presolve-infeasible to 'Solve error' in some tiny models -> retry w/o presolve
            res = milp(c, constraints=cons, integrality=np.array(self.integ),
                       bounds=Bounds(np.array(self.lb, float), np.array(self.ub, float)),
                       options=dict(OPTS, presolve=False))
            STATS['status4_retries'] += 1
        if res.status == 2:
            return None, None
        if res.status != 0:
            raise RuntimeError(f"MILP status {res.status}: {res.message}")
        val = res.fun if not maximize else -res.fun
        return val, res.x


def base_matrix(inst, o_target, mode):
    n, m = inst['n'], inst['m']
    B = np.zeros((n, m))
    for o in range(n):
        for j in range(m):
            v = inst['base'][o][j]
            if v is None:
                v = (0.0 if o == o_target else 1.0) if mode == 'nec' else (1.0 if o == o_target else 0.0)
            B[o, j] = v
    return B


def umax(inst):
    n, m = inst['n'], inst['m']
    best = 0.0
    for o in range(n):
        for j in range(m):
            v = inst['base'][o][j]
            v = 1.0 if v is None else abs(v)
            v += sum(abs(d) for oo, jj, i, d in inst['mods'] if oo == o and jj == j)
            best = max(best, v)
    return best


def add_state(M, inst):
    """s vars, deps, rule vars, eligibility vars. returns (s, e)."""
    k, n = inst['k'], inst['n']
    s = []
    for i in range(k):
        o = inst['obs'][i]
        if o == 'T':
            s.append(M.var(1, 1, True))
        elif o == 'F':
            s.append(M.var(0, 0, True))
        else:
            s.append(M.var(0, 1, True))
    for t, a, b in inst['deps']:
        if t == 'imp':
            M.add({s[a]: 1, s[b]: -1}, hi=0)
        else:
            M.add({s[a]: 1, s[b]: 1}, hi=1)
    rules_of = {o: [] for o in range(n)}
    for o, lits in inst['rules']:
        r = M.var(0, 1, True)
        # literal ℓ = s (val 1) or 1-s (val 0)
        const = 0.0; lin = {}
        for i, v in lits:
            if v == 1:
                M.add({r: 1, s[i]: -1}, hi=0)              # r <= s
                lin[s[i]] = lin.get(s[i], 0) + 1
            else:
                M.add({r: 1, s[i]: 1}, hi=1)               # r <= 1-s
                lin[s[i]] = lin.get(s[i], 0) - 1; const += 1
        # r >= Σℓ - (L-1)  ->  r - lin >= const - (L-1)
        coefs = {r: 1}
        for v_, a in lin.items():
            coefs[v_] = coefs.get(v_, 0) - a
        M.add(coefs, lo=const - (len(lits) - 1))
        rules_of[o].append(r)
    e = []
    for o in range(n):
        eo = M.var(0, 1, True)
        coefs = {eo: 1}
        for r in rules_of[o]:
            M.add({eo: 1, r: 1}, hi=1)
            coefs[r] = 1
        M.add(coefs, lo=1)                                  # e + Σr >= 1
        e.append(eo)
    return s, e


def add_w(M, inst):
    m = inst['m']
    lo = np.zeros(m); hi = np.ones(m)
    for j, kind, val in inst['bounds']:
        if kind == 'lo':
            lo[j] = max(lo[j], val)
        else:
            hi[j] = min(hi[j], val)
    w = [M.var(lo[j], hi[j]) for j in range(m)]
    M.add({x: 1 for x in w}, lo=1, hi=1)
    for a, b in inst['ordinal']:
        M.add({w[b]: 1, w[a]: -1}, hi=0)
    return w


def utility_exprs(M, inst, s, w, B):
    """U(o) as dict var->coef (linear in w and z=w*s)."""
    n, m = inst['n'], inst['m']
    zc = {}

    def z(j, i):
        if (j, i) not in zc:
            v = M.var(0, 1)
            M.add({v: 1, w[j]: -1}, hi=0)
            M.add({v: 1, s[i]: -1}, hi=0)
            M.add({v: 1, w[j]: -1, s[i]: -1}, lo=-1)
            zc[(j, i)] = v
        return zc[(j, i)]
    U = []
    for o in range(n):
        ex = {w[j]: B[o, j] for j in range(m)}
        for oo, j, i, d in inst['mods']:
            if oo == o:
                zv = z(j, i)
                ex[zv] = ex.get(zv, 0) + d
        U.append(ex)
    return U


def lin_sub(a, b, ca=1.0, cb=-1.0):
    out = {}
    for v, x in a.items():
        out[v] = out.get(v, 0) + ca * x
    for v, x in b.items():
        out[v] = out.get(v, 0) + cb * x
    return out


def q_EE(inst, o, Mbig):
    M = Model(); s, e = add_state(M, inst); w = add_w(M, inst)
    U = utility_exprs(M, inst, s, w, base_matrix(inst, o, 'pos'))
    M.ub[e[o]] = 1; M.lb[e[o]] = 1
    for q in range(inst['n']):
        if q != o:
            c = lin_sub(U[o], U[q]); c[e[q]] = c.get(e[q], 0) - Mbig
            M.add(c, lo=-Mbig)
    val, _ = M.solve()
    return val is not None


def q_AA(inst, o, Mbig):
    M = Model(); s, e = add_state(M, inst); w = add_w(M, inst)
    U = utility_exprs(M, inst, s, w, base_matrix(inst, o, 'nec'))
    n = inst['n']
    yI = M.var(0, 1, True)
    y = {q: M.var(0, 1, True) for q in range(n) if q != o}
    t = M.var(-np.inf, 1)  # tight finite bounds triggered HiGHS 'Solve error' (status 4) in tests
    sumc = {yI: 1}; sumc.update({v: 1 for v in y.values()})
    M.add(sumc, lo=1, hi=1)
    M.add({yI: 1, e[o]: 1}, hi=1)
    for q, yq in y.items():
        M.add({yq: 1, e[q]: -1}, hi=0)
        c = lin_sub({t: 1}, lin_sub(U[q], U[o]))  # t - (Uq - Uo)
        c[yq] = c.get(yq, 0) + Mbig
        M.add(c, hi=Mbig)
    val, _ = M.solve({t: 1}, maximize=True)
    if val is None:
        return True
    return val <= TOL


def _wG(inst):
    """G w <= h rows (ordinal, hi, -lo) as list of (dict j->coef, h)."""
    m = inst['m']
    rows = []
    for a, b in inst['ordinal']:
        rows.append(({b: 1.0, a: -1.0}, 0.0))
    lo = np.zeros(m); hi = np.ones(m)
    for j, kind, val in inst['bounds']:
        if kind == 'lo':
            lo[j] = max(lo[j], val)
        else:
            hi[j] = min(hi[j], val)
    for j in range(m):
        if hi[j] < 1.0:
            rows.append(({j: 1.0}, hi[j]))
        if lo[j] > 0.0:
            rows.append(({j: -1.0}, -lo[j]))
    return rows


def d_expr(inst, o, q, j, s, B):
    """d_j(s) = u_oj(s) - u_qj(s) as (const, dict s-var -> coef)."""
    const = B[o, j] - B[q, j]; lin = {}
    for oo, jj, i, dd in inst['mods']:
        if jj != j:
            continue
        if oo == o:
            lin[s[i]] = lin.get(s[i], 0) + dd
        elif oo == q:
            lin[s[i]] = lin.get(s[i], 0) - dd
    return const, lin


def q_EA(inst, o, Mbig):
    M = Model(); s, e = add_state(M, inst)
    B = base_matrix(inst, o, 'nec')
    n, m = inst['n'], inst['m']
    M.ub[e[o]] = 1; M.lb[e[o]] = 1
    G = _wG(inst)
    for q in range(n):
        if q == o:
            continue
        y = [M.var(0, np.inf) for _ in G]
        mu = M.var(-np.inf, np.inf)
        for j in range(m):
            const, lin = d_expr(inst, o, q, j, s, B)
            # mu - Σ_r G_rj y_r - d_j(s) <= 0
            c = {mu: 1}
            for r, (row, _) in enumerate(G):
                if j in row:
                    c[y[r]] = c.get(y[r], 0) - row[j]
            for v, a in lin.items():
                c[v] = c.get(v, 0) - a
            M.add(c, hi=const)
        # -h^T y + mu - M e_q >= -M
        c = {mu: 1, e[q]: -Mbig}
        for r, (_, hr) in enumerate(G):
            if hr != 0:
                c[y[r]] = c.get(y[r], 0) - hr
        M.add(c, lo=-Mbig)
    val, _ = M.solve()
    return val is not None


def can_be_ineligible(inst, o):
    M = Model(); s, e = add_state(M, inst)
    M.ub[e[o]] = 0
    val, _ = M.solve()
    return val is not None


def q_AE(inst, o, Mbig):
    if can_be_ineligible(inst, o):
        return False
    M = Model(); s, e = add_state(M, inst)
    B = base_matrix(inst, o, 'pos')
    n, m = inst['n'], inst['m']
    M.ub[e[o]] = 1; M.lb[e[o]] = 1
    G = _wG(inst)
    y = [M.var(0, 1) for _ in G]
    mu = M.var(-1, 1)
    lam = {q: M.var(0, 1) for q in range(n) if q != o}
    norm = {v: 1 for v in y}; norm.update({v: 1 for v in lam.values()})
    if norm:
        M.add(norm, hi=1)
    pc = {}

    def p(q, i):  # lam_q * s_i
        if (q, i) not in pc:
            v = M.var(0, 1)
            M.add({v: 1, lam[q]: -1}, hi=0)
            M.add({v: 1, s[i]: -1}, hi=0)
            M.add({v: 1, lam[q]: -1, s[i]: -1}, lo=-1)
            pc[(q, i)] = v
        return pc[(q, i)]
    for q, lq in lam.items():
        M.add({lq: 1, e[q]: -1}, hi=0)
    for j in range(m):
        # (G^T y)_j + mu - Σ_q lam_q d_qj(s) >= 0
        c = {mu: 1}
        for r, (row, _) in enumerate(G):
            if j in row:
                c[y[r]] = c.get(y[r], 0) + row[j]
        for q, lq in lam.items():
            c[lq] = c.get(lq, 0) - (B[o, j] - B[q, j])
            for oo, jj, i, dd in inst['mods']:
                if jj != j:
                    continue
                if oo == o:
                    pv = p(q, i); c[pv] = c.get(pv, 0) - dd
                elif oo == q:
                    pv = p(q, i); c[pv] = c.get(pv, 0) + dd
        M.add(c, lo=0)
    obj = {mu: -1}
    for r, (_, hr) in enumerate(G):
        if hr != 0:
            obj[y[r]] = obj.get(y[r], 0) - hr
    val, _ = M.solve(obj, maximize=True)
    if val is None:
        raise RuntimeError("AE certificate MILP infeasible (unexpected: zero certificate is feasible)")
    return not (val > TOL)


def _master(inst, rows):
    m = inst['m']
    lo = np.zeros(m); hi = np.ones(m)
    for j, kind, val in inst['bounds']:
        if kind == 'lo':
            lo[j] = max(lo[j], val)
        else:
            hi[j] = min(hi[j], val)
    A, b = [], []
    for a, c_ in inst['ordinal']:
        r = np.zeros(m + 1); r[c_] = 1; r[a] = -1; A.append(r); b.append(0)
    for d in rows:
        A.append(np.concatenate([-d, [1.0]])); b.append(0)
    c = np.zeros(m + 1); c[-1] = -1
    res = linprog(c, A_ub=np.array(A) if A else None, b_ub=np.array(b) if A else None,
                  A_eq=np.concatenate([np.ones(m), [0]])[None, :], b_eq=[1],
                  bounds=list(zip(lo, hi)) + [(-10, 1)], method='highs')
    if res.status != 0:
        raise RuntimeError(res.message)
    return res.x[:m], -res.fun


def q_EwAs(inst, o, Mbig, max_iter=1000):
    if can_be_ineligible(inst, o):
        return False, 0
    B = base_matrix(inst, o, 'pos')
    n, m = inst['n'], inst['m']
    cuts = []
    for it in range(max_iter):
        wstar, tau = _master(inst, cuts)
        if tau < -TOL:
            return False, it
        M = Model(); s, e = add_state(M, inst)
        y = {q: M.var(0, 1, True) for q in range(n) if q != o}
        if not y:
            return True, it
        t = M.var(-np.inf, np.inf)
        M.add({v: 1 for v in y.values()}, lo=1, hi=1)
        for q, yq in y.items():
            M.add({yq: 1, e[q]: -1}, hi=0)
            const = 0.0; lin = {}
            for j in range(m):
                cj, lj = d_expr(inst, o, q, j, s, B)
                const += wstar[j] * cj
                for v, a in lj.items():
                    lin[v] = lin.get(v, 0) + wstar[j] * a
            # t >= const + lin - M(1-yq)  ->  t - lin - M yq >= const - M
            c = {t: 1, yq: -Mbig}
            for v, a in lin.items():
                c[v] = c.get(v, 0) - a
            M.add(c, lo=const - Mbig)
        val, x = M.solve({t: 1})
        if val is None or val >= -TOL:
            return True, it
        sv = np.round(x[s]).astype(int)
        # cuts for all competitors eligible in s*
        el = [True] * n
        for oo, lits in inst['rules']:
            if all(sv[i] == v for i, v in lits):
                el[oo] = False
        V = B.copy()
        for oo, j, i, d in inst['mods']:
            if sv[i] == 1:
                V[oo, j] += d
        for q in range(n):
            if q != o and el[q]:
                cuts.append(V[o] - V[q])
    raise RuntimeError("EwAs cutting plane did not converge")


def solve(inst):
    n = inst['n']
    M0 = Model(); add_state(M0, inst)
    if M0.solve()[0] is None:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)}, cat={o: 'INSUFFICIENT' for o in range(n)},
                    iters=0)
    Mbig = 2 * umax(inst) + 2
    flags = {}
    iters = 0
    for o in range(n):
        EE = q_EE(inst, o, Mbig)
        if not EE:
            flags[o] = [0, 0, 0, 0, 0]; continue
        AA = q_AA(inst, o, Mbig)
        EA = True if AA else q_EA(inst, o, Mbig)
        AE = True if AA else q_AE(inst, o, Mbig)
        if AE:
            EwAs, it = (True, 0) if AA else q_EwAs(inst, o, Mbig)
            iters += it
        else:
            EwAs = False
        flags[o] = [int(AA), int(EE), int(AE), int(EA), int(EwAs)]
    # category (own-missing check via LP max w_j)
    m = inst['m']
    cat = {}
    for o in range(n):
        own = False
        for j in range(m):
            if inst['base'][o][j] is None:
                Mx = Model(); w = add_w(Mx, inst)
                val, _ = Mx.solve({w[j]: 1}, maximize=True)
                if val is not None and val > TOL:
                    own = True
        AA, EE, AE, EA, _ = flags[o]
        cat[o] = ('INSUFFICIENT' if own else 'ALWAYS' if AA else 'EXCLUDED' if not EE
                  else 'CONDITIONAL' if EA else 'UNDETERMINED')
    return dict(flags=flags, cat=cat, iters=iters)


if __name__ == "__main__":
    import json, sys
    d = json.load(open(sys.argv[1]))
    for name, x in d.items():
        print(name, solve(x))
