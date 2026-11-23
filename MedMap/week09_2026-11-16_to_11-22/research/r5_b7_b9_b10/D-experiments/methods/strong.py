"""[합성] 강한 기준선. ground_truth.py 와 코드 공유 없음 (float + scipy HiGHS LP).
- run_B      : Baseline B  — 단일 결합 모형. 같은 숨은 변수 s 가 지침 적용·규칙 조건·근거 지지(볼록 껍질 LP)를
               동시에 결정하는 결합 상태공간 위에서 ∀/∃ 양화. 효과 미정의는 0/제외가 아닌 별도 상태로 처리.
               ∃w∀s 는 모든 상태의 최적성 부등식을 한 LP 에 넣어 계산.
- run_Bp     : Baseline B' — 모듈별 정확 계산 후 결합. (M1 임상: 상태 열거·적용·허용, M2 근거: 행동별 3값 지지 요약,
               M3 선호: 상태별 LP). 결합 시 M2 의 '미정(UNK)'을 독립 변수로 취급하고, 상태 간 선호는 상태별
               가능 최적 집합의 교집합(∀s∃w)으로 결합한다.
- run_V      : 단순 변형(기준선 아님) — B 와 같으나 시험 범위 밖 계획을 허용 불가로 제외, 지식 없음은 효과 0.
               금지 출력 F4(시험 제외=금기)를 보여 주기 위한 대조군.
"""
import itertools
import numpy as np
from scipy.optimize import linprog

TOL = 1e-9


def _states(inst):
    obs = inst["obs"]; U = [i for i in range(inst["k"]) if obs[i] == "U"]
    res = []
    for bits in itertools.product((0, 1), repeat=len(U)):
        s = [1 if o == "T" else 0 for o in obs]
        for i, b in zip(U, bits):
            s[i] = b
        if all(s[a] <= s[b] for a, b in inst["deps"]):
            res.append(tuple(s))
    return U, res


def _key(U, s):
    return ",".join("c%d=%d" % (i, s[i]) for i in U) if U else "-"


def _sat(conj, s):
    for v, val in conj:
        if s[v] != val:
            return False
    return True


def _frac(x):
    if isinstance(x, str) and "/" in x:
        a, b = x.split("/"); return float(a) / float(b)
    return float(x)


class Wset:
    def __init__(self, inst):
        c = [_frac(x) for x in inst["W"]["center"]]; r = _frac(inst["W"]["r"])
        self.bounds = [(max(0.0, ci - r), min(1.0, ci + r)) for ci in c]

    def min_dot(self, d):
        res = linprog(d, A_eq=np.ones((1, 3)), b_eq=[1.0], bounds=self.bounds, method="highs")
        assert res.status == 0, res.message
        return res.fun

    def max_tau(self, diffs):
        """max τ s.t. d·w >= τ for all d in diffs, w ∈ W. 변수 (w1,w2,w3,τ)."""
        if len(diffs) == 0:
            return 1.0
        D = np.asarray(diffs, float)
        A_ub = np.hstack([-D, np.ones((len(D), 1))])
        res = linprog([0, 0, 0, -1], A_ub=A_ub, b_ub=np.zeros(len(D)), A_eq=[[1, 1, 1, 0]], b_eq=[1.0],
                      bounds=self.bounds + [(None, 1.0)], method="highs")
        assert res.status == 0, res.message
        return -res.fun


def _in_hull_lp(points, p):
    X = np.asarray(points, float); n = len(X)
    A_eq = np.vstack([X.T, np.ones((1, n))]); b_eq = np.array([p[0], p[1], 1.0])
    res = linprog(np.zeros(n), A_eq=A_eq, b_eq=b_eq, bounds=(0, None), method="highs")
    return res.status == 0


def _cov(inst, s_val):
    c = inst["patient_cov"]
    return (float(c["x0"]), float(c["x1_base"]) + float(c["x1_delta"]) * s_val)


def _prefs(vecs, Wv):
    """vecs: {plan: vec}. returns NO, PO (plan lists), with dedupe by vector."""
    groups = {}
    for p, v in vecs.items():
        groups.setdefault(v, []).append(p)
    U = list(groups)
    PO_v, NO_v = [], []
    for v in U:
        diffs = [np.subtract(v, u) for u in U if u != v]
        if Wv.max_tau(diffs) >= -1e-9:
            PO_v.append(v)
    for v in PO_v:
        if all(Wv.min_dot(np.subtract(v, u)) >= -1e-9 for u in U if u != v):
            NO_v.append(v)
    NO = [p for v in NO_v for p in groups[v]]
    PO = [p for v in PO_v for p in groups[v]]
    return sorted(NO), sorted(PO)


def _final(per_state, rules, nogt):
    if nogt:
        return "NO_GROUND_TRUTH"
    vals = list(per_state.values())
    kinds = [v[0] for v in vals]
    if all(v == vals[0] for v in vals):
        k = kinds[0]
        if k == "CONFLICT":
            return "REAL_CONFLICT"
        if k == "CONFIRMED":
            return "CONVERGED" if all(r in ("NONE", "N/A") for r in rules) else "CONFIRMED_PLAN"
        return dict(PREF="PREFERENCE_DEPENDENT", EVIDENCE_GAP="EVIDENCE_SCOPE_INSUFFICIENT",
                    KNOWLEDGE_GAP="KNOWLEDGE_GAP")[k]
    if "CONFLICT" in kinds:
        return "CONDITIONAL_CONFLICT"
    if all(k == "CONFIRMED" for k in kinds):
        return "CONDITIONAL_PLAN"
    return "INFO_HOLD"


def _contradiction(inst, S, G):
    gi = {a: i for i, g in enumerate(G) for a in g["options"]}
    conf = {(r["a"], r["b"]) for r in inst["rules"] if r["type"] == "conflict"}
    for r in inst["rules"]:
        if r["type"] == "compatible" and (r["a"], r["b"]) in conf:
            if any(_sat(G[gi[r["a"]]]["app"], s) and _sat(G[gi[r["b"]]]["app"], s) for s in S):
                return True
    return False


def _components(inst, S, G):
    apps = [[_sat(g["app"], s) for g in G] for s in S]
    app = []
    for j in range(len(G)):
        col = [a[j] for a in apps]
        app.append("CONFIRMED_APPLY" if all(col) else ("NOT_APPLY" if not any(col) else "CONDITIONAL_APPLY"))
    prim = [g["options"][0] for g in G]
    rules = []
    for r in inst["rules"]:
        if r["type"] != "conflict":
            rules.append("N/A"); continue
        col = []
        for s, ap in zip(S, apps):
            R = {prim[j] for j in range(len(G)) if ap[j]}
            col.append(r["a"] in R and r["b"] in R and _sat(r["cond"], s))
        rules.append("REAL" if all(col) else ("NONE" if not any(col) else "CONDITIONAL"))
    return app, rules


def _state_core(inst, plans, G, s, ev_of, mode):
    """한 결합 상태 s 에서 (kind, payload, info). ev_of(a) -> 'OK'|'OUT'|'NOENTRY'.
    mode 'B': 표준. 'V': OUT 계획 제외, NOENTRY 효과 0."""
    acts = {a["id"]: a for a in inst["actions"]}
    app = [_sat(g["app"], s) for g in G]
    conf = [r for r in inst["rules"] if r["type"] == "conflict"]
    A, vecs, status = [], {}, {}
    real = {}
    for i, p in enumerate(plans):
        R = tuple(sorted(p[j] for j in range(len(G)) if app[j]))
        Rs = set(R)
        if any(r["a"] in Rs and r["b"] in Rs and _sat(r["cond"], s) for r in conf):
            continue
        st = [ev_of(a) for a in R]
        if mode == "V" and "OUT" in st:
            continue
        A.append(i); real[i] = R
        if mode == "B" and "NOENTRY" in st:
            status[i] = "KN"
        elif mode == "B" and "OUT" in st:
            status[i] = "EV"
        else:
            status[i] = "OK"
            vecs[i] = (float(sum(acts[a]["effect"] if ev_of(a) == "OK" else 0 for a in R)),
                       -float(sum(acts[a]["pills"] for a in R)), -float(sum(acts[a]["visits"] for a in R)))
    if not A:
        return ("CONFLICT", []), None
    if any(status[i] == "KN" for i in A):
        return ("KNOWLEDGE_GAP", []), None
    if any(status[i] == "EV" for i in A):
        return ("EVIDENCE_GAP", []), None
    return vecs, (A, real)


def _label_from_vecs(vecs, A, real, Wv):
    NO, PO = _prefs(vecs, Wv)
    chosen = NO if NO else PO
    payload = sorted({real[i] for i in chosen})
    return ("CONFIRMED" if NO else "PREF", [list(x) for x in payload]), dict(A=A, vecs=vecs, NO=NO, PO=PO)


def _joint_queries(keys, info, plans, Wv):
    if not all(info.get(k) is not None for k in keys):
        return [], [], []
    ewas, fsew, rnec = [], [], []
    for i in range(len(plans)):
        if not all(i in info[k]["A"] for k in keys):
            continue
        if all(i in info[k]["NO"] for k in keys):
            rnec.append(i)
        if all(i in info[k]["PO"] for k in keys):
            fsew.append(i)
        diffs = []
        for k in keys:
            v = info[k]["vecs"]
            seen = set()
            for j in info[k]["A"]:
                if j != i and v[j] not in seen:
                    seen.add(v[j]); diffs.append(np.subtract(v[i], v[j]))
        if Wv.max_tau(diffs) >= -1e-9:
            ewas.append(i)
    return ewas, fsew, rnec


def run_B(inst, mode="B"):
    G = inst["guidelines"]
    plans = list(itertools.product(*[g["options"] for g in G]))
    U, S = _states(inst)
    Wv = Wset(inst)
    nogt = _contradiction(inst, S, G)
    app, rules = _components(inst, S, G)
    hull_cache = {}
    xv = inst["patient_cov"]["x1_var"]

    def ev_factory(s):
        sv = s[xv] if xv is not None else 0
        def ev_of(a):
            act = inst["actions"][a]
            if act["trial"] is None:
                return "NOENTRY"
            key = (a, sv)
            if key not in hull_cache:
                hull_cache[key] = _in_hull_lp(act["trial"], _cov(inst, sv))
            return "OK" if hull_cache[key] else "OUT"
        return ev_of

    per_state, info = {}, {}
    for s in S:
        k = _key(U, s)
        r, ex = _state_core(inst, plans, G, s, ev_factory(s), mode)
        if ex is None:
            per_state[k] = r; info[k] = None
        else:
            per_state[k], info[k] = _label_from_vecs(r, ex[0], ex[1], Wv)
    keys = [_key(U, s) for s in S]
    ewas, fsew, rnec = _joint_queries(keys, info, plans, Wv)
    return dict(final=_final(per_state, rules, nogt), per_state=per_state, ewas=ewas, fsew=fsew, app=app,
                rules=rules, single_plan=False, excluded_out_of_support=(mode == "V"))


def run_V(inst):
    return run_B(inst, mode="V")


def run_Bp(inst):
    G = inst["guidelines"]
    plans = list(itertools.product(*[g["options"] for g in G]))
    # M1 임상 모듈
    U, S = _states(inst)
    nogt = _contradiction(inst, S, G)
    app, rules = _components(inst, S, G)
    # M2 근거 모듈: 임상 상태를 보지 않고 공변량 변수의 가능한 값 {0,1}(미확인이면) 에서 행동별 3값 요약
    xv = inst["patient_cov"]["x1_var"]
    if xv is None:
        svals = [0]
    else:
        o = inst["obs"][xv]
        svals = [0, 1] if o == "U" else [1 if o == "T" else 0]
    summ = {}
    for act in inst["actions"]:
        if act["trial"] is None:
            summ[act["id"]] = "NOENTRY"; continue
        res = {_in_hull_lp(act["trial"], _cov(inst, v)) for v in svals}
        summ[act["id"]] = "SUP" if res == {True} else ("UNSUP" if res == {False} else "UNK")
    unk_acts = sorted(a for a, v in summ.items() if v == "UNK")
    # M3 선호 모듈 + 결합: 임상 상태 × (UNK 행동들의 SUP/UNSUP 독립 완성)
    Wv = Wset(inst)
    per_state, info = {}, {}
    for s in S:
        k = _key(U, s)
        outs = []
        for comp in itertools.product(("OK", "OUT"), repeat=len(unk_acts)):
            cm = dict(zip(unk_acts, comp))
            ev_of = lambda a, cm=cm: cm[a] if a in cm else {"SUP": "OK", "UNSUP": "OUT", "NOENTRY": "NOENTRY"}[summ[a]]
            r, ex = _state_core(inst, plans, G, s, ev_of, "B")
            if ex is None:
                outs.append((r, None))
            else:
                outs.append(_label_from_vecs(r, ex[0], ex[1], Wv))
        labs = [o[0] for o in outs]
        if all(l == labs[0] for l in labs):
            per_state[k] = labs[0]; info[k] = outs[0][1]
        else:
            per_state[k] = ("EVIDENCE_GAP", []); info[k] = None  # 지지 미정 -> 근거 판정 보류
    keys = [_key(U, s) for s in S]
    # 상태 간 결합: 상태별 PO 교집합 (∀s∃w) 을 '강건 가능 최적' 으로 보고
    if all(info.get(k) is not None for k in keys):
        fsew = [i for i in range(len(plans)) if all(i in info[k]["A"] and i in info[k]["PO"] for k in keys)]
    else:
        fsew = []
    return dict(final=_final(per_state, rules, nogt), per_state=per_state, ewas=list(fsew), fsew=fsew, app=app,
                rules=rules, single_plan=False, excluded_out_of_support=False)
