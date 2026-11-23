"""[합성] Baseline B 의 MILP 판: 상태 열거 없이 하나의 MILP 안에 3값 임상 변수(이진), 지침 적용(논리곱 선형화),
조건부 규칙, 근거 지지(공유 변수 c_xv 에 대한 선형 표: OUT_a(s) = t0 + (t1-t0)*c_xv), 경쟁 계획 선택(원-핫)을 넣고,
∃w∀s 질의를 반례 유도 절단(CEGAR: 주 LP over w ↔ 부 MILP over (s,q))으로 푼다.
출력: ewas(계획 번호 목록), app(지침 적용 3값). ground_truth.py / strong.py 와 코드 공유 없음.
"""
import itertools
import numpy as np
from scipy.optimize import milp, linprog, LinearConstraint, Bounds

TOL = 1e-9


def _frac(x):
    if isinstance(x, str) and "/" in x:
        a, b = x.split("/"); return float(a) / float(b)
    return float(x)


def _hull_lp(points, p):
    X = np.asarray(points, float); n = len(X)
    r = linprog(np.zeros(n), A_eq=np.vstack([X.T, np.ones((1, n))]), b_eq=[p[0], p[1], 1.0], bounds=(0, None), method="highs")
    return r.status == 0


class Model:
    """변수 배치: c(미확인 변수) | app_g | y_{g,o} | z_{g,o} | 보조(문제별)."""

    def __init__(self, inst):
        self.inst = inst
        self.G = inst["guidelines"]
        self.U = [i for i in range(inst["k"]) if inst["obs"][i] == "U"]
        self.cidx = {v: j for j, v in enumerate(self.U)}
        self.nc = len(self.U)
        self.ng = len(self.G)
        self.opts = [(g, o) for g in range(self.ng) for o in self.G[g]["options"]]
        self.oidx = {go: j for j, go in enumerate(self.opts)}
        self.gof = {o: g for g, o in self.opts}
        self.base_n = self.nc + self.ng + 2 * len(self.opts)
        cov = inst["patient_cov"]; xv = cov["x1_var"]
        self.acts = {a["id"]: a for a in inst["actions"]}
        self.bad = {}  # action -> (const, coef on c_xv) : 1 이면 효과 미정의(NOENTRY/OUT)
        for a, act in self.acts.items():
            if act["trial"] is None:
                self.bad[a] = (1.0, 0.0, None); continue
            if xv is None or inst["obs"][xv] != "U":
                sv = 0 if xv is None else (1 if inst["obs"][xv] == "T" else 0)
                o = 0.0 if _hull_lp(act["trial"], (cov["x0"], cov["x1_base"] + cov["x1_delta"] * sv)) else 1.0
                self.bad[a] = (o, 0.0, None)
            else:
                o0 = 0.0 if _hull_lp(act["trial"], (cov["x0"], cov["x1_base"])) else 1.0
                o1 = 0.0 if _hull_lp(act["trial"], (cov["x0"], cov["x1_base"] + cov["x1_delta"])) else 1.0
                self.bad[a] = (o0, o1 - o0, xv)
        c = [_frac(x) for x in inst["W"]["center"]]; r = _frac(inst["W"]["r"])
        self.wb = [(max(0.0, ci - r), min(1.0, ci + r)) for ci in c]

    # 리터럴 -> (상수, {변수열: 계수})
    def lit(self, v, val):
        o = self.inst["obs"][v]
        if o != "U":
            return (1.0 if (o == "T") == (val == 1) else 0.0), {}
        j = self.cidx[v]
        return (0.0, {j: 1.0}) if val == 1 else (1.0, {j: -1.0})

    def iapp(self, g):
        return self.nc + g

    def iy(self, g, o):
        return self.nc + self.ng + self.oidx[(g, o)]

    def iz(self, g, o):
        return self.nc + self.ng + len(self.opts) + self.oidx[(g, o)]

    def base_rows(self, n, rows, lo, hi, with_q):
        def add(coefs, l, h):
            rw = np.zeros(n)
            for j, v in coefs.items():
                rw[j] += v
            rows.append(rw); lo.append(l); hi.append(h)
        for a, b in self.inst["deps"]:  # c_a <= c_b
            ca, da = self.lit(a, 1); cb, db = self.lit(b, 1)
            co = {}
            for j, v in da.items():
                co[j] = co.get(j, 0) + v
            for j, v in db.items():
                co[j] = co.get(j, 0) - v
            add(co, -np.inf, cb - ca)
        for g, gd in enumerate(self.G):
            L = gd["app"]
            if not L:
                add({self.iapp(g): 1.0}, 1.0, 1.0); continue
            tot_c, tot = 0.0, {}
            for v, val in L:  # app <= lit
                cst, d = self.lit(v, val)
                co = {self.iapp(g): 1.0}
                for j, x in d.items():
                    co[j] = co.get(j, 0) - x
                add(co, -np.inf, cst)
                tot_c += cst
                for j, x in d.items():
                    tot[j] = tot.get(j, 0) + x
            co = {self.iapp(g): 1.0}  # app >= Σlit - (L-1)
            for j, x in tot.items():
                co[j] = co.get(j, 0) - x
            add(co, tot_c - (len(L) - 1), np.inf)
        if with_q:
            for g, gd in enumerate(self.G):
                add({self.iy(g, o): 1.0 for o in gd["options"]}, 1.0, 1.0)
                for o in gd["options"]:  # z = app ∧ y
                    add({self.iz(g, o): 1.0, self.iy(g, o): -1.0}, -np.inf, 0.0)
                    add({self.iz(g, o): 1.0, self.iapp(g): -1.0}, -np.inf, 0.0)
                    add({self.iz(g, o): 1.0, self.iy(g, o): -1.0, self.iapp(g): -1.0}, -1.0, np.inf)
            for r in self.inst["rules"]:  # q 허용: z_a + z_b + Σcond <= 1 + |cond|
                if r["type"] != "conflict":
                    continue
                co = {self.iz(self.gof[r["a"]], r["a"]): 1.0, self.iz(self.gof[r["b"]], r["b"]): 1.0}
                cs = 0.0
                for v, val in r["cond"]:
                    cst, d = self.lit(v, val); cs += cst
                    for j, x in d.items():
                        co[j] = co.get(j, 0) + x
                add(co, -np.inf, 1.0 + len(r["cond"]) - cs)
        return add

    def solve(self, n, rows, lo, hi, obj=None):
        integ = np.ones(n)
        A = np.array(rows) if rows else np.zeros((0, n))
        res = milp(c=np.zeros(n) if obj is None else obj, constraints=[LinearConstraint(A, lo, hi)] if rows else [],
                   integrality=integ, bounds=Bounds(0, 1))
        return res

    def exists_state(self, extra):
        n = self.base_n + 8 * len(self.inst["rules"]) + 2 * len(self.opts) + 4
        rows, lo, hi = [], [], []
        add = self.base_rows(n, rows, lo, hi, with_q=extra.get("with_q", False))
        extra["fn"](add, n)
        res = self.solve(n, rows, lo, hi)
        return res.status == 0, res

    def app_status(self):
        out = []
        for g in range(self.ng):
            t, _ = self.exists_state({"fn": lambda add, n, g=g: add({self.iapp(g): 1.0}, 1.0, 1.0)})
            f, _ = self.exists_state({"fn": lambda add, n, g=g: add({self.iapp(g): 1.0}, 0.0, 0.0)})
            out.append("CONFIRMED_APPLY" if not f else ("NOT_APPLY" if not t else "CONDITIONAL_APPLY"))
        return out

    def badexpr(self, a, col_coef=1.0):
        c0, c1, xv = self.bad[a]
        return c0, ({self.cidx[xv]: c1} if (xv is not None and c1 != 0) else {})

    def any_gap_state(self):
        """∃s ∃q: q 허용 ∧ q 의 실현 행동 중 효과 미정의 존재 (그 상태 라벨이 GAP/EWAS 불가)."""
        def fn(add, n):
            base = self.base_n
            us = []
            for j, (g, o) in enumerate(self.opts):
                u = base + j; us.append(u)
                add({u: 1.0, self.iz(g, o): -1.0}, -np.inf, 0.0)
                c0, d = self.badexpr(o)
                co = {u: 1.0}
                for jj, x in d.items():
                    co[jj] = co.get(jj, 0) - x
                add(co, -np.inf, c0)
            add({u: 1.0 for u in us}, 1.0, np.inf)
        return self.exists_state({"fn": fn, "with_q": True})[0]

    def p_inadmissible_state(self, p):
        rules = [r for r in self.inst["rules"] if r["type"] == "conflict" and r["a"] in p and r["b"] in p]
        if not rules:
            return False
        def fn(add, n):
            base = self.base_n
            ts = []
            for k, r in enumerate(rules):
                t = base + k; ts.append(t)
                add({t: 1.0, self.iapp(self.gof[r["a"]]): -1.0}, -np.inf, 0.0)
                add({t: 1.0, self.iapp(self.gof[r["b"]]): -1.0}, -np.inf, 0.0)
                for v, val in r["cond"]:
                    cst, d = self.lit(v, val)
                    co = {t: 1.0}
                    for j, x in d.items():
                        co[j] = co.get(j, 0) - x
                    add(co, -np.inf, cst)
            add({t: 1.0 for t in ts}, 1.0, np.inf)
        return self.exists_state({"fn": fn})[0]

    def val(self, a, w):
        act = self.acts[a]
        return act["effect"] * w[0] - act["pills"] * w[1] - act["visits"] * w[2]

    def vec(self, a):
        act = self.acts[a]
        return np.array([act["effect"], -act["pills"], -act["visits"]], float)

    def worst_competitor(self, p, w):
        """min_{s,q 허용} (v_p(s) - v_q(s))·w. 반환 (값, 차이 벡터)."""
        n = self.base_n
        rows, lo, hi = [], [], []
        self.base_rows(n, rows, lo, hi, with_q=True)
        obj = np.zeros(n)
        for g in range(self.ng):
            obj[self.iapp(g)] += self.val(p[g], w)
        for (g, o) in self.opts:
            obj[self.iz(g, o)] -= self.val(o, w)
        res = self.solve(n, rows, lo, hi, obj)
        assert res.status == 0, res.message
        x = np.round(res.x)
        d = np.zeros(3)
        for g in range(self.ng):
            if x[self.iapp(g)] > 0.5:
                d += self.vec(p[g])
        for (g, o) in self.opts:
            if x[self.iz(g, o)] > 0.5:
                d -= self.vec(o)
        return res.fun, d

    def master(self, cuts):
        if not cuts:
            return 1.0, self._any_w()
        D = np.array(cuts)
        A_ub = np.hstack([-D, np.ones((len(D), 1))])
        r = linprog([0, 0, 0, -1], A_ub=A_ub, b_ub=np.zeros(len(D)), A_eq=[[1, 1, 1, 0]], b_eq=[1.0],
                    bounds=self.wb + [(None, 1.0)], method="highs")
        assert r.status == 0
        return -r.fun, r.x[:3]

    def _any_w(self):
        r = linprog([0, 0, 0], A_eq=[[1, 1, 1]], b_eq=[1.0], bounds=self.wb, method="highs")
        return r.x

    def ewas(self, max_iter=200):
        plans = list(itertools.product(*[g["options"] for g in self.G]))
        if self.any_gap_state():
            return [], {"gap": True, "iters": 0}
        out, iters = [], 0
        for i, p in enumerate(plans):
            if self.p_inadmissible_state(p):
                continue
            cuts = []
            for _ in range(max_iter):
                iters += 1
                tau, w = self.master(cuts) if cuts else (1.0, self._any_w())
                if tau < -TOL:
                    break
                val, d = self.worst_competitor(p, w)
                if val >= -1e-7:
                    out.append(i); break
                cuts.append(d)
            else:
                raise RuntimeError("CEGAR max_iter")
        return out, {"gap": False, "iters": iters}


def run_Bmilp(inst):
    m = Model(inst)
    ew, meta = m.ewas()
    return dict(ewas=ew, app=m.app_status(), meta=meta)
