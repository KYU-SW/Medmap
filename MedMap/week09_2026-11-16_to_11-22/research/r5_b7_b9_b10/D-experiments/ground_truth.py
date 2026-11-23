"""[합성] 정답 생성기 (후보 방법 코드와 독립).
- 임상 3값 시나리오: 미확인(U) 변수의 모든 완성 x 의존성 필터 (전수 열거)
- 선호: W(2차원 다각형, 단체 위 box)를 Fraction 정확 산술로 반평면 절단(Sutherland-Hodgman).
  ∀w 는 W 꼭짓점에서, ∃w 는 '절단 후 다각형이 비지 않음'으로 판정(= W 꼭짓점과 차이 직선의 배열 꼭짓점 전수 검사와 동치).
- 근거 상태: 시험 점들의 볼록 껍질을 Fraction 으로 정확 계산(monotone chain) 후 경계 포함 소속 판정.
LP/MILP/scipy 사용 없음. 출력: frozen/ground_truth.json
"""
import itertools, json, os, sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))


def enum_states(inst):
    obs = inst["obs"]; U = [i for i, o in enumerate(obs) if o == "U"]
    out = []
    for bits in itertools.product([0, 1], repeat=len(U)):
        s = [1 if o == "T" else 0 for o in obs]
        for i, b in zip(U, bits):
            s[i] = b
        if all(not (s[a] == 1 and s[b] == 0) for a, b in inst["deps"]):
            out.append(tuple(s))
    return U, out


def skey(U, s):
    return ",".join(f"c{i}={s[i]}" for i in U) if U else "-"


def holds(conj, s):
    return all(s[v] == val for v, val in conj)


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def hull(pts):
    P = sorted(set((F(x), F(y)) for x, y in pts))
    if len(P) <= 2:
        return P
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    H = lo[:-1] + up[:-1]
    return H


def in_hull(H, p):
    if len(H) == 1:
        return p == H[0]
    if len(H) == 2:
        a, b = H
        return cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    n = len(H)
    return all(cross(H[i], H[(i + 1) % n], p) >= 0 for i in range(n))


def clip(poly, a1, a2, b):
    """반평면 a1*w1 + a2*w2 + b >= 0 로 절단 (경계 포함, 정확 산술)."""
    out = []
    n = len(poly)
    for i in range(n):
        P, Q = poly[i], poly[(i + 1) % n]
        fp = a1 * P[0] + a2 * P[1] + b
        fq = a1 * Q[0] + a2 * Q[1] + b
        if fp >= 0:
            out.append(P)
        if (fp > 0 and fq < 0) or (fp < 0 and fq > 0):
            t = fp / (fp - fq)
            out.append((P[0] + t * (Q[0] - P[0]), P[1] + t * (Q[1] - P[1])))
    ded = []
    for p in out:
        if not ded or ded[-1] != p:
            ded.append(p)
    if len(ded) > 1 and ded[0] == ded[-1]:
        ded.pop()
    return ded


def W_poly(inst):
    c = [F(x) for x in inst["W"]["center"]]; r = F(inst["W"]["r"])
    poly = [(F(0), F(0)), (F(1), F(0)), (F(0), F(1))]
    forms = [(F(1), F(0), F(0)), (F(0), F(1), F(0)), (F(-1), F(-1), F(1))]  # w1, w2, w3=1-w1-w2
    for (a1, a2, b), ci in zip(forms, c):
        poly = clip(poly, a1, a2, b - (ci - r))      # w_i >= c_i - r
        poly = clip(poly, -a1, -a2, (ci + r) - b)    # w_i <= c_i + r
    assert poly, "W empty"
    return poly


def halfplane(d):
    """(d·w >= 0) with w3 = 1-w1-w2 -> (a1, a2, b)."""
    return d[0] - d[2], d[1] - d[2], d[2]


def solve(inst):
    acts = {a["id"]: a for a in inst["actions"]}
    G = inst["guidelines"]
    plans = list(itertools.product(*[g["options"] for g in G]))
    U, S = enum_states(inst)
    assert S, "no consistent state"
    cov = inst["patient_cov"]
    hulls = {a: (hull(acts[a]["trial"]) if acts[a]["trial"] is not None else None) for a in acts}
    Wp = W_poly(inst)
    conflicts = [r for r in inst["rules"] if r["type"] == "conflict"]
    gidx = {a: gi for gi, g in enumerate(G) for a in g["options"]}

    # 정답 없음: 같은 쌍에 conflict 와 compatible 공존 + 두 지침이 어떤 상태에서 동시 적용 가능
    pairs_conf = {(r["a"], r["b"]) for r in conflicts}
    nogt = False
    for r in inst["rules"]:
        if r["type"] == "compatible" and (r["a"], r["b"]) in pairs_conf:
            ga, gb = gidx[r["a"]], gidx[r["b"]]
            if any(holds(G[ga]["app"], s) and holds(G[gb]["app"], s) for s in S):
                nogt = True

    primary = tuple(g["options"][0] for g in G)
    per_state, info = {}, {}
    app_all, rule_all = [], []
    for s in S:
        app = [holds(g["app"], s) for g in G]
        app_all.append(app)
        x1 = F(cov["x1_base"]) + F(cov["x1_delta"]) * (s[cov["x1_var"]] if cov["x1_var"] is not None else 0)
        pt = (F(cov["x0"]), x1)

        def ev(a):
            if hulls[a] is None:
                return "NOENTRY"
            return "OK" if in_hull(hulls[a], pt) else "OUT"

        def realized(p):
            return tuple(sorted(p[g] for g in range(len(G)) if app[g]))

        def admissible(p):
            R = set(realized(p))
            return not any(r["a"] in R and r["b"] in R and holds(r["cond"], s) for r in conflicts)

        Rp = set(realized(primary))
        rule_all.append([(r["type"] == "conflict" and r["a"] in Rp and r["b"] in Rp and holds(r["cond"], s)) for r in inst["rules"]])
        A = [i for i, p in enumerate(plans) if admissible(p)]
        vals, stat = {}, {}
        for i in A:
            R = realized(plans[i]); st = [ev(a) for a in R]
            if "NOENTRY" in st:
                stat[i] = "KN"
            elif "OUT" in st:
                stat[i] = "EV"
            else:
                stat[i] = "OK"
                vals[i] = (sum(F(acts[a]["effect"]) for a in R), -sum(F(acts[a]["pills"]) for a in R),
                           -sum(F(acts[a]["visits"]) for a in R))
        k = skey(U, s)
        if not A:
            per_state[k] = ("CONFLICT", []); info[k] = None; continue
        if any(stat[i] == "KN" for i in A):
            per_state[k] = ("KNOWLEDGE_GAP", []); info[k] = None; continue
        if any(stat[i] == "EV" for i in A):
            per_state[k] = ("EVIDENCE_GAP", []); info[k] = None; continue
        NO, PO = [], []
        for i in A:
            hp = [halfplane(tuple(vals[i][t] - vals[j][t] for t in range(3))) for j in A if j != i]
            if all(a1 * w[0] + a2 * w[1] + b >= 0 for (a1, a2, b) in hp for w in Wp):
                NO.append(i)
            poly = Wp
            for (a1, a2, b) in hp:
                poly = clip(poly, a1, a2, b)
                if not poly:
                    break
            if poly:
                PO.append(i)
        rs = sorted(set(tuple(realized(plans[i])) for i in (NO if NO else PO)))
        per_state[k] = ("CONFIRMED" if NO else "PREF", [list(x) for x in rs])
        info[k] = dict(A=A, vals=vals, NO=NO, PO=PO)

    # 상태 간 질의
    keys = [skey(U, s) for s in S]
    ok_all = all(info[k] is not None for k in keys)
    ewas, fsew, rnec = [], [], []
    if ok_all:
        for i in range(len(plans)):
            if not all(i in info[k]["A"] for k in keys):
                continue
            if all(i in info[k]["NO"] for k in keys):
                rnec.append(i)
            if all(i in info[k]["PO"] for k in keys):
                fsew.append(i)
            poly = Wp
            for k in keys:
                v = info[k]["vals"]
                for j in info[k]["A"]:
                    if j == i:
                        continue
                    poly = clip(poly, *halfplane(tuple(v[i][t] - v[j][t] for t in range(3))))
                    if not poly:
                        break
                if not poly:
                    break
            if poly:
                ewas.append(i)

    app_status = []
    for g in range(len(G)):
        col = [a[g] for a in app_all]
        app_status.append("CONFIRMED_APPLY" if all(col) else ("NOT_APPLY" if not any(col) else "CONDITIONAL_APPLY"))
    rule_status = []
    for ri, r in enumerate(inst["rules"]):
        if r["type"] != "conflict":
            rule_status.append("N/A"); continue
        col = [x[ri] for x in rule_all]
        rule_status.append("REAL" if all(col) else ("NONE" if not any(col) else "CONDITIONAL"))

    final = combine(per_state, rule_status, nogt)
    return dict(final=final, per_state={k: [v[0], v[1]] for k, v in per_state.items()}, ewas=ewas, fsew=fsew,
                rnec=rnec, app=app_status, rules=rule_status, n_states=len(S), n_plans=len(plans), nogt=nogt)


def combine(per_state, rule_status, nogt):
    """SPEC 5절 최종 라벨 규칙."""
    if nogt:
        return "NO_GROUND_TRUTH"
    vs = list(per_state.values())
    kinds = [v[0] for v in vs]
    same = all(v == vs[0] for v in vs)
    if same:
        k = kinds[0]
        if k == "CONFLICT":
            return "REAL_CONFLICT"
        if k == "CONFIRMED":
            return "CONVERGED" if all(r in ("NONE", "N/A") for r in rule_status) else "CONFIRMED_PLAN"
        return {"PREF": "PREFERENCE_DEPENDENT", "EVIDENCE_GAP": "EVIDENCE_SCOPE_INSUFFICIENT",
                "KNOWLEDGE_GAP": "KNOWLEDGE_GAP"}[k]
    if "CONFLICT" in kinds:
        return "CONDITIONAL_CONFLICT"
    if all(k == "CONFIRMED" for k in kinds):
        return "CONDITIONAL_PLAN"
    return "INFO_HOLD"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "inputs", "instances.json")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "frozen", "ground_truth.json")
    insts = json.load(open(src))["instances"]
    out = {}
    for inst in insts:
        out[inst["id"]] = solve(inst)
    json.dump({"note": "[합성] 전수 열거 정답. 의학적 사실 아님.", "gt": out}, open(dst, "w"), indent=0)
    from collections import Counter
    c = Counter((inst["exp"], out[inst["id"]]["final"]) for inst in insts)
    for k in sorted(c):
        print(k, c[k])


if __name__ == "__main__":
    main()
