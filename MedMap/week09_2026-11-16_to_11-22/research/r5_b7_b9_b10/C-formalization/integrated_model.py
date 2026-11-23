"""MedMap B7+B9+B10 통합 정식화 — 작은 합성 모형 (SUBAGENT C).

[합성 실험] 모든 약·규칙·효과·조건은 가상(SYNTHETIC)이다. 의학적 정확성 주장 없음.
목적: B7(상호작용) + B9(불완전 선호·부담) + B10(근거 적용 범위, 효과 미정의)을
하나의 양화(quantified) 질의 집합으로 표현하고,
(1) 전수 열거 + LP (정답 기준, brute)  와
(2) scipy milp 단일 MILP (AA, EE, CLOSE_P)
가 같은 판정을 내는지 확인한다.

자연(nature) 변수 그룹
  P : 환자 임상 변수 (3값 관측 T/F/U/C + 의존성)            -> 환자 정보로 닫힘
  K : 지식 변수 (미확인 상호작용 u, 효과 구간 e, ⊥)          -> 의학 지식으로 닫힘
  Q : 선호 변수 (가중치 w ∈ W polytope, 부담 상한 Bcap)        -> 선호 확인으로 닫힘
효과 미정의(⊥) = (-∞, +∞) 구간. 0 으로 두지 않는다. 계산에서는 ±M (M 은 효용 범위보다 충분히 큼).
"""
from __future__ import annotations
import itertools, json, sys, time
import numpy as np
from scipy.optimize import linprog, milp, LinearConstraint, Bounds

M_BOT = 10.0          # ⊥ 를 표현하는 큰 값 (효용 범위 약 ±1 보다 충분히 큼)
TOL = 1e-7

# ---------------------------------------------------------------------------
# 1. 주 인스턴스 (합성)
# ---------------------------------------------------------------------------
MAIN = {
    "name": "MAIN_SYNTH",
    "clin_vars": ["hasA", "hasB", "ckd", "hk", "age75"],
    # T=확인 참, F=확인 거짓, U=미확인, C=출처 상충(T 기록과 F 기록 공존)
    "obs": {"hasA": "T", "hasB": "T", "ckd": "U", "hk": "C", "age75": "T"},
    "provenance": {"hasA": "진단목록(확인)", "hasB": "진단목록(확인)", "ckd": "검사 없음(미확인)",
                    "hk": "기록1=T, 기록2=F (상충)", "age75": "생년(확인)"},
    "deps": [("imp", "hk", "ckd")],            # hk=1 -> ckd=1 (가상 의존성)
    "know_vars": ["u_B1S"],                     # B1+S 상호작용 지식 미확인 (u=1 이면 금기)
    "bcap_options": [2, 3],                     # 환자 허용 복용 수 (불명확: 2 또는 3)
    "drugs": ["A1", "A2", "B1", "B2", "S"],
    "pills": {"A1": 1, "A2": 1, "B1": 1, "B2": 2, "S": 1},
    "criteria": ["benA", "benB", "burden"],
    "W": {"order": [("benA", "benB")], "lo": {"burden": 0.1}, "hi": {"burden": 0.5}},
    # hard 제약: drugs 가 모두 처방되고 lits 가 모두 참이면 금지
    "rules": [
        {"name": "R1_A1_contra_ckd", "kind": "CONTRAINDICATION", "drugs": ["A1"], "lits": [("ckd", 1)]},
        {"name": "R2_A2B1_conflict_hk", "kind": "CONFLICT", "drugs": ["A2", "B1"], "lits": [("hk", 1)]},
        {"name": "R3_A2B2_duplicate", "kind": "DUPLICATE", "drugs": ["A2", "B2"], "lits": []},
        {"name": "R4_B1S_unknown", "kind": "UNKNOWN_INTERACTION", "drugs": ["B1", "S"], "lits": [("u_B1S", 1)]},
    ],
    "guidelines": [
        {"name": "GA", "app": [("hasA", 1)], "cover": ["A1", "A2", "S"]},
        {"name": "GB", "app": [("hasB", 1)], "cover": ["B1", "B2", "S"]},
    ],
    "outcome_bound": (-0.3, 0.6),               # 결과 척도의 논리적 범위 [a,b]
    # 효과 표: 약 -> 기준 -> P 위의 분할(첫 일치). entry type:
    #   ("IV", L, U)  : 근거 적용 가능, 구간
    #   ("OUT",)      : 기준 미충족 또는 지지 영역 밖 -> 규범에 따라 [a,b] 또는 ⊥
    #   ("PUB", L, U) : 공개 근거로 지지 판정 불가(P* 3번) -> 규범에 따라 넓힌 구간 또는 ⊥
    #   ("NONE",)     : 근거 자체 없음(E5) -> 항상 ⊥
    # B10 다섯 구분 태그: E1 기준충족, E2 유사 참가자, E3 일반화 근거
    "effects": {
        "A1": {"benA": [([("ckd", 0)], ("IV", 0.30, 0.45), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"}),
                        ([("ckd", 1)], ("OUT",), {"E1": "NOT_MET", "E2": "OUT", "E3": "UNASSESSED"})]},
        "A2": {"benA": [([("ckd", 0)], ("IV", 0.20, 0.35), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"}),
                        ([("ckd", 1), ("age75", 1)], ("PUB", 0.00, 0.40), {"E1": "MET", "E2": "PUBLIC_UNRESOLVED", "E3": "UNASSESSED"}),
                        ([("ckd", 1), ("age75", 0)], ("IV", 0.15, 0.35), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"})]},
        "B1": {"benB": [([("age75", 1)], ("OUT",), {"E1": "MET", "E2": "OUT", "E3": "UNASSESSED"}),
                        ([("age75", 0)], ("IV", 0.25, 0.40), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"})]},
        "B2": {"benB": [([("ckd", 0)], ("IV", 0.15, 0.30), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"}),
                        ([("ckd", 1)], ("IV", 0.05, 0.35), {"E1": "MET", "E2": "IN", "E3": "UNASSESSED"})]},
        "S": {"benA": [([], ("IV", 0.10, 0.20), {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"})],
              "benB": [([("ckd", 0)], ("IV", 0.00, 0.20), {"E1": "MET", "E2": "IN", "E3": "UNASSESSED"}),
                       ([("ckd", 1)], ("NONE",), {"E1": "NO_TRIAL", "E2": "NO_TRIAL", "E3": "NO_TRIAL"})]},
    },
    "synergy": [{"pair": ("A1", "B2"), "crit": "benB", "interval": (0.00, 0.10)}],
}

# 규범(전문가 선택) 매개변수: 같은 입력에 서로 다른 합리적 선택이 가능
NORMS = {
    "NORM_A": {"OUT": "bounded", "PUB": "widen"},   # OUT->[a,b], PUB->주어진 넓힌 구간
    "NORM_B": {"OUT": "bottom", "PUB": "bottom"},   # OUT, PUB -> ⊥
}


# ---------------------------------------------------------------------------
# 2. 기본 연산
# ---------------------------------------------------------------------------
def clinical_states(inst):
    vs = inst["clin_vars"]
    free = [v for v in vs if inst["obs"][v] in ("U", "C")]
    out = []
    for bits in itertools.product([0, 1], repeat=len(free)):
        s = {v: (1 if inst["obs"][v] == "T" else 0) for v in vs if inst["obs"][v] in ("T", "F")}
        s.update(dict(zip(free, bits)))
        ok = True
        for kind, a, b in inst["deps"]:
            if kind == "imp" and s[a] == 1 and s[b] == 0:
                ok = False
            if kind == "excl" and s[a] == 1 and s[b] == 1:
                ok = False
        if ok:
            out.append(s)
    return out


def know_states(inst):
    return [dict(zip(inst["know_vars"], b)) for b in itertools.product([0, 1], repeat=len(inst["know_vars"]))]


def all_plans(inst):
    d = inst["drugs"]
    return [frozenset(c) for r in range(len(d) + 1) for c in itertools.combinations(d, r)]


def lits_true(lits, env):
    return all(env[v] == val for v, val in lits)


def feasible(inst, plan, P, K, bcap):
    env = {**P, **K}
    for r in inst["rules"]:
        if all(d in plan for d in r["drugs"]) and lits_true(r["lits"], env):
            return False
    if sum(inst["pills"][d] for d in plan) > bcap:
        return False
    for g in inst["guidelines"]:
        if lits_true(g["app"], env) and not any(d in plan for d in g["cover"]):
            return False
    return True


def effect_interval(inst, drug, crit, P, norm):
    """반환 (L, U, is_bottom, tags). ⊥ 는 (-M, +M, True)."""
    table = inst["effects"].get(drug, {}).get(crit)
    if table is None:
        return (0.0, 0.0, False, {"E": "NOT_TARGET"})   # 이 기준을 겨냥하지 않음(효과 0 은 '대상 아님'으로 정의된 경우만)
    a, b = inst["outcome_bound"]
    for lits, ent, tags in table:
        if lits_true(lits, P):
            t = ent[0]
            if t == "IV":
                return (ent[1], ent[2], False, tags)
            if t == "OUT":
                if NORMS[norm]["OUT"] == "bounded":
                    return (a, b, False, tags)
                return (-M_BOT, M_BOT, True, tags)
            if t == "PUB":
                if NORMS[norm]["PUB"] == "widen":
                    return (ent[1], ent[2], False, tags)
                return (-M_BOT, M_BOT, True, tags)
            if t == "NONE":
                return (-M_BOT, M_BOT, True, tags)
    raise ValueError(f"effect table not exhaustive: {drug} {crit} {P}")


def values(inst, plan, P, xstar, mode, norm):
    """기준 벡터. mode='unfav': x* 약은 L, 그 외 U (∀ 쪽 최악). 'fav': 반대."""
    v = np.zeros(len(inst["criteria"]))
    ci = {c: i for i, c in enumerate(inst["criteria"])}
    for d in plan:
        for c in inst["criteria"]:
            if c == "burden":
                continue
            L, U, _, _ = effect_interval(inst, d, c, P, norm)
            in_x = d in xstar
            val = (L if in_x else U) if mode == "unfav" else (U if in_x else L)
            v[ci[c]] += val
    for sy in inst["synergy"]:
        p = set(sy["pair"])
        if p <= plan:
            L, U = sy["interval"]
            in_x = p <= xstar
            v[ci[sy["crit"]]] += (L if in_x else U) if mode == "unfav" else (U if in_x else L)
    v[ci["burden"]] = -sum(inst["pills"][d] for d in plan) / 5.0
    return v


def W_matrices(inst):
    """W = {w>=0, sum w = 1, G w >= h}."""
    C = inst["criteria"]; ci = {c: i for i, c in enumerate(C)}; m = len(C)
    G, h = [], []
    for a, b in inst["W"]["order"]:
        row = np.zeros(m); row[ci[a]] = 1; row[ci[b]] = -1; G.append(row); h.append(0.0)
    for c, lo in inst["W"].get("lo", {}).items():
        row = np.zeros(m); row[ci[c]] = 1; G.append(row); h.append(lo)
    for c, hi in inst["W"].get("hi", {}).items():
        row = np.zeros(m); row[ci[c]] = -1; G.append(row); h.append(-hi)
    return np.array(G).reshape(-1, m), np.array(h)


def lp_min_over_W(inst, c):
    G, h = W_matrices(inst); m = len(c)
    r = linprog(c, A_ub=-G if len(G) else None, b_ub=-h if len(G) else None,
                A_eq=np.ones((1, m)), b_eq=[1.0], bounds=[(0, None)] * m, method="highs")
    if r.status != 0:
        raise RuntimeError("W empty or LP fail")
    return r.fun


def lp_exists_w(inst, cons):
    """∃w∈W: c·w >= 0 for all c in cons."""
    G, h = W_matrices(inst); m = len(inst["criteria"])
    A = list(-G); b = list(-h)
    for c in cons:
        A.append(-np.asarray(c)); b.append(0.0)
    r = linprog(np.zeros(m), A_ub=np.array(A) if A else None, b_ub=np.array(b) if b else None,
                A_eq=np.ones((1, m)), b_eq=[1.0], bounds=[(0, None)] * m, method="highs")
    return r.status == 0


# ---------------------------------------------------------------------------
# 3. 정답 기준: 전수 열거 + LP (그룹별 ∃G ∀rest 양화)
# ---------------------------------------------------------------------------
def judge(inst, xstar, G, norm, plans, SP, SK):
    """∃(G 의 이산 변수) [∃w if Q∈G] ∀(나머지 이산) [∀w if Q∉G] [e: K∈G 이면 유리 꼭짓점, 아니면 불리]: x* 최선."""
    mode = "fav" if "K" in G else "unfav"
    dom = {"P": SP, "K": SK, "Q": inst["bcap_options"]}
    ex = [g for g in ("P", "K", "Q") if g in G]
    fa = [g for g in ("P", "K", "Q") if g not in G]
    for gv in itertools.product(*[dom[g] for g in ex]):
        asg = dict(zip(ex, gv))
        cons, ok = [], True
        for rv in itertools.product(*[dom[g] for g in fa]):
            full = {**asg, **dict(zip(fa, rv))}
            P, K, bc = full["P"], full["K"], full["Q"]
            if not feasible(inst, xstar, P, K, bc):
                ok = False; break
            vx = values(inst, xstar, P, xstar, mode, norm)
            for x in plans:
                if x == xstar or not feasible(inst, x, P, K, bc):
                    continue
                c = vx - values(inst, x, P, xstar, mode, norm)
                if "Q" in G:
                    cons.append(c)
                elif lp_min_over_W(inst, c) < -TOL:
                    ok = False; break
            if not ok:
                break
        if not ok:
            continue
        if "Q" in G:
            if lp_exists_w(inst, cons):
                return True
        else:
            return True
    return False


GROUP_SETS = [(), ("P",), ("Q",), ("K",), ("P", "Q"), ("P", "K"), ("K", "Q"), ("P", "K", "Q")]


def max_weight(inst, crit):
    c = np.zeros(len(inst["criteria"])); c[inst["criteria"].index(crit)] = -1
    return -lp_min_over_W(inst, c)


def categorize(inst, xstar, norm, plans, SP, SK):
    rec = {"plan": "+".join(sorted(xstar)) or "(none)", "norm": norm}
    if not SP:
        rec.update(category="DATA_CONFLICT"); return rec
    flags = {"".join(G) or "AA": judge(inst, xstar, G, norm, plans, SP, SK) for G in GROUP_SETS}
    rec["flags"] = flags
    feas_any = any(feasible(inst, xstar, P, K, b) for P in SP for K in SK for b in inst["bcap_options"])
    gap_states = []
    for i, P in enumerate(SP):
        # 부적격(hard) 상태에서는 효과가 판단에 쓰이지 않으므로 지식 공백으로 세지 않는다
        if not any(feasible(inst, xstar, P, K, b) for K in SK for b in inst["bcap_options"]):
            continue
        for d in xstar:
            for c in inst["criteria"]:
                if c != "burden" and effect_interval(inst, d, c, P, norm)[2] and max_weight(inst, c) > TOL:
                    gap_states.append(i)
    gap_states = sorted(set(gap_states))
    rec["own_gap_states"] = gap_states
    if not feas_any:
        cat = "HARD_EXCLUDED"
    elif gap_states and len(gap_states) == len(SP):
        cat = "KNOWLEDGE_GAP_ALL_STATES"
    elif gap_states:
        cat = "KNOWLEDGE_GAP_INFO_DEPENDENT"
    elif flags["AA"]:
        cat = "ALWAYS_BEST"
    elif not flags["PKQ"]:
        cat = "NEVER_BEST"
    else:
        single = [g for g in ("P", "Q", "K") if flags[g]]
        if single:
            cat = "CLOSABLE_BY_" + "|".join(single)
        else:
            pairs = [g for g in ("PQ", "PK", "KQ") if flags[g]]
            cat = "CLOSABLE_BY_" + "|".join(pairs) if pairs else "CLOSABLE_ONLY_BY_ALL"
    rec["category"] = cat
    return rec


# ---------------------------------------------------------------------------
# 4. MILP (scipy milp / HiGHS) — 표현 가능성 시연
# ---------------------------------------------------------------------------
class MB:
    """작은 MILP 빌더."""
    def __init__(self):
        self.lb, self.ub, self.integ, self.rows, self.obj = [], [], [], [], {}

    def var(self, lb=0.0, ub=1.0, integer=False):
        self.lb.append(lb); self.ub.append(ub); self.integ.append(1 if integer else 0)
        return len(self.lb) - 1

    def bvar(self):
        return self.var(0, 1, True)

    def add(self, coef: dict, lo=-np.inf, hi=np.inf):
        self.rows.append((coef, lo, hi))

    def AND(self, lits):
        """lits: list of (var_index, val) over binaries; returns binary z = AND(lit)."""
        if not lits:
            z = self.bvar(); self.add({z: 1}, 1, 1); return z
        z = self.bvar(); n = len(lits); s_coef = {z: 1.0}; const = 0.0
        for v, val in lits:
            # literal value = x if val==1 else 1-x
            if val == 1:
                self.add({z: 1, v: -1}, hi=0)            # z <= x
                s_coef[v] = s_coef.get(v, 0) - 1
            else:
                self.add({z: 1, v: 1}, hi=1)             # z <= 1-x
                s_coef[v] = s_coef.get(v, 0) + 1; const += 1
        # z >= sum(lit) - (n-1)  ->  z - sum(lit) >= -(n-1)
        self.add(s_coef, lo=-(n - 1) + const)
        return z

    def wprod(self, w, t):
        """q = w * t, w∈[0,1] continuous, t binary (McCormick, exact)."""
        q = self.var(0, 1)
        self.add({q: 1, w: -1}, hi=0); self.add({q: 1, t: -1}, hi=0); self.add({q: 1, w: -1, t: -1}, lo=-1)
        return q

    def solve(self, sense_max=False):
        n = len(self.lb)
        c = np.zeros(n)
        for k, v in self.obj.items():
            c[k] = -v if sense_max else v
        A = np.zeros((len(self.rows), n)); lo = np.zeros(len(self.rows)); hi = np.zeros(len(self.rows))
        for i, (coef, l, h) in enumerate(self.rows):
            for k, v in coef.items():
                A[i, k] += v
            lo[i], hi[i] = l, h
        res = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=np.array(self.integ),
                   bounds=Bounds(np.array(self.lb), np.array(self.ub)))
        return res


def nature_vars(mb, inst):
    """P, K binaries + bcap selector; returns dict name->index and bcap expression."""
    idx = {}
    for v in inst["clin_vars"]:
        o = inst["obs"][v]
        if o == "T":
            idx[v] = mb.var(1, 1, True)
        elif o == "F":
            idx[v] = mb.var(0, 0, True)
        else:
            idx[v] = mb.bvar()
    for kind, a, b in inst["deps"]:
        if kind == "imp":
            mb.add({idx[a]: 1, idx[b]: -1}, hi=0)
        else:
            mb.add({idx[a]: 1, idx[b]: 1}, hi=1)
    for v in inst["know_vars"]:
        idx[v] = mb.bvar()
    return idx


def bcap_selector(mb, inst, fixed=None):
    opts = inst["bcap_options"]
    sel = [mb.bvar() for _ in opts]
    mb.add({s: 1 for s in sel}, 1, 1)
    if fixed is not None:
        for s, o in zip(sel, opts):
            mb.add({s: 1}, 1 if o == fixed else 0, 1 if o == fixed else 0)
    return sel


def plan_viol_conjs(inst, plan, bcap_sel=None, bcap_fixed=None):
    """fixed plan -> list of conjunctions (lits over nature names) whose truth = infeasible.
    bcap: returns ('BCAP', option_index) pseudo-literals."""
    conjs = []
    for r in inst["rules"]:
        if all(d in plan for d in r["drugs"]):
            conjs.append(list(r["lits"]))
    pills = sum(inst["pills"][d] for d in plan)
    for j, o in enumerate(inst["bcap_options"]):
        if pills > o:
            conjs.append([("__BCAP__", j)])
    for g in inst["guidelines"]:
        if not any(d in plan for d in g["cover"]):
            conjs.append(list(g["app"]))
    return conjs


def conj_index(mb, idx, sel, conj):
    lits = []
    for v, val in conj:
        if v == "__BCAP__":
            lits.append((sel[val], 1))
        else:
            lits.append((idx[v], val))
    return lits


def effect_terms(mb, inst, idx, drug, crit, norm, use_low, cache):
    """returns list of (coef, binary_index) with e = Σ coef*ind (partition, exact)."""
    table = inst["effects"].get(drug, {}).get(crit)
    if table is None:
        return []
    a, b = inst["outcome_bound"]
    out = []
    for k, (lits, ent, tags) in enumerate(table):
        key = (drug, crit, k)
        if key not in cache:
            cache[key] = mb.AND([(idx[v], val) for v, val in lits])
        t = ent[0]
        if t == "IV":
            L, U = ent[1], ent[2]
        elif t == "OUT":
            L, U = (a, b) if NORMS[norm]["OUT"] == "bounded" else (-M_BOT, M_BOT)
        elif t == "PUB":
            L, U = (ent[1], ent[2]) if NORMS[norm]["PUB"] == "widen" else (-M_BOT, M_BOT)
        else:
            L, U = -M_BOT, M_BOT
        out.append((L if use_low else U, cache[key]))
    return out


def lin_value_fixed_plan(mb, inst, idx, w, plan, xstar, mode, norm, cache, qcache):
    """Σ_j w_j v_j(plan, P) as linear dict (fixed plan)."""
    expr = {}
    ci = {c: i for i, c in enumerate(inst["criteria"])}
    for d in plan:
        for c in inst["criteria"]:
            if c == "burden":
                continue
            in_x = d in xstar
            use_low = in_x if mode == "unfav" else (not in_x)
            for coef, t in effect_terms(mb, inst, idx, d, c, norm, use_low, cache):
                key = (ci[c], t)
                if key not in qcache:
                    qcache[key] = mb.wprod(w[ci[c]], t)
                expr[qcache[key]] = expr.get(qcache[key], 0) + coef
    for sy in inst["synergy"]:
        p = set(sy["pair"])
        if p <= plan:
            L, U = sy["interval"]; in_x = p <= xstar
            val = (L if in_x else U) if mode == "unfav" else (U if in_x else L)
            expr[w[ci[sy["crit"]]]] = expr.get(w[ci[sy["crit"]]], 0) + val
    pills = sum(inst["pills"][d] for d in plan)
    expr[w[ci["burden"]]] = expr.get(w[ci["burden"]], 0) - pills / 5.0
    return expr


def add_W(mb, inst):
    m = len(inst["criteria"])
    w = [mb.var(0, 1) for _ in range(m)]
    mb.add({wi: 1 for wi in w}, 1, 1)
    G, h = W_matrices(inst)
    for row, hv in zip(G, h):
        mb.add({w[j]: row[j] for j in range(m) if row[j] != 0}, lo=hv)
    return w


def milp_AA(inst, xstar, norm):
    """AA false ⇔ (a) ∃n: x* 부적격  or  (b) max_{n,w,x} U(x)-U(x*) > 0 (x 는 암묵적 이진 변수 = 조합 처방 공간)."""
    # (a)
    mb = MB(); idx = nature_vars(mb, inst); sel = bcap_selector(mb, inst)
    zs = [mb.AND(conj_index(mb, idx, sel, cj)) for cj in plan_viol_conjs(inst, xstar)]
    if zs:
        mb.add({z: 1 for z in zs}, lo=1)
        r = mb.solve()
        if r.status == 0:
            return False
    # (b)
    mb = MB(); idx = nature_vars(mb, inst); sel = bcap_selector(mb, inst); w = add_W(mb, inst)
    ci = {c: i for i, c in enumerate(inst["criteria"])}
    x = {d: mb.bvar() for d in inst["drugs"]}
    for r in inst["rules"]:   # Σ lits <= n-1
        lits = [(x[d], 1) for d in r["drugs"]] + [(idx[v], val) for v, val in r["lits"]]
        coef, const = {}, 0.0
        for v, val in lits:
            if val == 1:
                coef[v] = coef.get(v, 0) + 1
            else:
                coef[v] = coef.get(v, 0) - 1; const += 1
        mb.add(coef, hi=len(lits) - 1 - const)
    coef = {x[d]: inst["pills"][d] for d in inst["drugs"]}
    for s, o in zip(sel, inst["bcap_options"]):
        coef[s] = coef.get(s, 0) - o
    mb.add(coef, hi=0)
    for g in inst["guidelines"]:
        app = mb.AND([(idx[v], val) for v, val in g["app"]])
        cf = {x[d]: 1 for d in g["cover"]}; cf[app] = cf.get(app, 0) - 1
        mb.add(cf, lo=0)
    cache, qcache = {}, {}
    obj = {}
    # competitor value: e_i = L if i in x* else U (unfav)
    for d in inst["drugs"]:
        for c in inst["criteria"]:
            if c == "burden":
                continue
            for coef_v, t in effect_terms(mb, inst, idx, d, c, norm, d in xstar, cache):
                tt = mb.AND([(x[d], 1), (t, 1)])
                q = mb.wprod(w[ci[c]], tt)
                obj[q] = obj.get(q, 0) + coef_v
        q = mb.wprod(w[ci["burden"]], x[d])
        obj[q] = obj.get(q, 0) - inst["pills"][d] / 5.0
    for sy in inst["synergy"]:
        a_, b_ = sy["pair"]; L, U = sy["interval"]
        tt = mb.AND([(x[a_], 1), (x[b_], 1)])
        q = mb.wprod(w[ci[sy["crit"]]], tt)
        obj[q] = obj.get(q, 0) + (L if set(sy["pair"]) <= xstar else U)
    vstar = lin_value_fixed_plan(mb, inst, idx, w, xstar, xstar, "unfav", norm, cache, qcache)
    for k, v in vstar.items():
        obj[k] = obj.get(k, 0) - v
    mb.obj = obj
    r = mb.solve(sense_max=True)
    if r.status != 0:
        raise RuntimeError(f"AA MILP status {r.status}")
    return -r.fun <= 1e-6


def milp_exists(inst, xstar, norm, plans, forall_groups):
    """∃(P 및 forall_groups 에 없는 이산 변수) ∀(forall_groups 의 이산 값 확장) ∀w(쌍대) or ∃w.
    forall_groups ⊆ {'K','Q'}. EE: forall_groups=() 이고 w 존재.  CLOSE_P: forall=('K','Q'), w 전칭."""
    w_forall = "Q" in forall_groups
    mode = "unfav" if "K" in forall_groups else "fav"
    mb = MB()
    idx = nature_vars(mb, inst)
    Kdom = know_states(inst) if "K" in forall_groups else [None]
    Qdom = inst["bcap_options"] if "Q" in forall_groups else [None]
    sel_free = None if "Q" in forall_groups else bcap_selector(mb, inst)
    w = None if w_forall else add_W(mb, inst)
    G, h = W_matrices(inst); m = len(inst["criteria"])
    BIG = 100.0
    cache, qcache = {}, {}
    for Kv in Kdom:
        for Qv in Qdom:
            # 고정된 K 값: know 변수 대신 상수 사용 -> copy 별 AND 에서 상수 처리
            def lits_to_idx(conj):
                out, const_false = [], False
                for v, val in conj:
                    if v == "__BCAP__":
                        if Qv is None:
                            out.append((sel_free[val], 1))
                        elif inst["bcap_options"][val] != Qv:
                            const_false = True
                    elif Kv is not None and v in Kv:
                        if Kv[v] != val:
                            const_false = True
                    else:
                        out.append((idx[v], val))
                return out, const_false
            # x* feasible in this copy: every violation conj false
            for cj in plan_viol_conjs(inst, xstar):
                lits, cf = lits_to_idx(cj)
                if cf:
                    continue
                if not lits:
                    return False  # x* 가 이 copy 에서 상수적으로 부적격 -> ∀ 실패 (EE 면 항상 부적격)
                coef, const = {}, 0.0
                for v, val in lits:
                    if val == 1:
                        coef[v] = coef.get(v, 0) + 1
                    else:
                        coef[v] = coef.get(v, 0) - 1; const += 1
                mb.add(coef, hi=len(lits) - 1 - const)
            for x in plans:
                if x == xstar:
                    continue
                viols = []
                const_infeas = False
                for cj in plan_viol_conjs(inst, x):
                    lits, cf = lits_to_idx(cj)
                    if cf:
                        continue
                    if not lits:
                        const_infeas = True; break
                    viols.append(mb.AND(lits))
                if const_infeas:
                    continue
                f = mb.bvar()
                cf_ = {f: 1}
                for z in viols:
                    mb.add({f: 1, z: 1}, hi=1)
                    cf_[z] = 1
                mb.add(cf_, lo=1)                     # f >= 1 - Σ viol
                if w_forall:
                    # c(P) = v(x*) - v(x) ; min_w c·w >= 0 ⇔ ∃λ,μ>=0: λ + h·μ >= 0, λ + (G^T μ)_j <= c_j(P)
                    lam = mb.var(-np.inf, np.inf)
                    mu = [mb.var(0, np.inf) for _ in range(len(h))]
                    cjs = crit_exprs(mb, inst, idx, x, xstar, mode, norm, cache, Kv)
                    for j in range(m):
                        coef = {lam: 1.0}
                        for k in range(len(h)):
                            if G[k, j] != 0:
                                coef[mu[k]] = coef.get(mu[k], 0) + G[k, j]
                        const = cjs[j][1]
                        for var_i, cv in cjs[j][0].items():
                            coef[var_i] = coef.get(var_i, 0) - cv
                        mb.add(coef, hi=const)
                    coef = {lam: 1.0, f: -BIG}
                    for k in range(len(h)):
                        coef[mu[k]] = h[k]
                    mb.add(coef, lo=-BIG)
                else:
                    ex = lin_value_fixed_plan(mb, inst, idx, w, xstar, xstar, mode, norm, cache, qcache)
                    ey = lin_value_fixed_plan(mb, inst, idx, w, x, xstar, mode, norm, cache, qcache)
                    coef = dict(ex)
                    for k, v in ey.items():
                        coef[k] = coef.get(k, 0) - v
                    coef[f] = coef.get(f, 0) - BIG
                    mb.add(coef, lo=-BIG)
    r = mb.solve()
    return r.status == 0


def crit_exprs(mb, inst, idx, x, xstar, mode, norm, cache, Kv):
    """per criterion j: c_j(P) = v_j(x*) - v_j(x) as (linear dict over binaries, constant)."""
    m = len(inst["criteria"]); ci = {c: i for i, c in enumerate(inst["criteria"])}
    out = [({}, 0.0) for _ in range(m)]
    out = [[dict(), 0.0] for _ in range(m)]
    for plan, sign in ((xstar, 1.0), (x, -1.0)):
        for d in plan:
            for c in inst["criteria"]:
                if c == "burden":
                    continue
                in_x = d in xstar
                use_low = in_x if mode == "unfav" else (not in_x)
                for coef, t in effect_terms(mb, inst, idx, d, c, norm, use_low, cache):
                    out[ci[c]][0][t] = out[ci[c]][0].get(t, 0) + sign * coef
        for sy in inst["synergy"]:
            p = set(sy["pair"])
            if p <= plan:
                L, U = sy["interval"]; in_x = p <= xstar
                val = (L if in_x else U) if mode == "unfav" else (U if in_x else L)
                out[ci[sy["crit"]]][1] += sign * val
        out[ci["burden"]][1] += sign * (-sum(inst["pills"][d] for d in plan) / 5.0)
    return out
