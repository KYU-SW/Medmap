"""[합성] 약한 기준선.
- run_A: Baseline A — MitPlan식 통합의 **독자 구현(원본 아님, 원본 코드 비공개로 알려짐)**.
  공개 기술 수준의 일반 흐름만 따름: (1) 환자 사실 = 폐쇄 세계 가정(명시되지 않은 사실=거짓; PDDL 계열 계획기의 표준 가정),
  (2) 1차 권고 결합에서 상호작용 탐지, (3) 수정 연산자(대체 행동으로 교체)로 허용 계획 탐색,
  (4) 점 선호(W 중심) 가중 비용 최소 계획 하나 출력. 근거 지지 개념 없음(효과가 있으면 사용, 없으면 0).
  논문 세부(연산자 종류, 비용 정의, 선호 표현)와의 대응은 [미검증] — B 서브에이전트 확인 대상.
- run_C: Baseline C — 단순 독립 파이프라인(결측=정상, 상호작용 무시, 점 선호, 근거 무시). 참고용.
"""
import itertools


def _sat(conj, s):
    return all(s[v] == val for v, val in conj)


def _frac(x):
    if isinstance(x, str) and "/" in x:
        a, b = x.split("/"); return float(a) / float(b)
    return float(x)


def _true_keys(inst):
    obs = inst["obs"]; U = [i for i in range(inst["k"]) if obs[i] == "U"]
    keys = []
    for bits in itertools.product((0, 1), repeat=len(U)):
        s = [1 if o == "T" else 0 for o in obs]
        for i, b in zip(U, bits):
            s[i] = b
        if all(s[a] <= s[b] for a, b in inst["deps"]):
            keys.append((",".join("c%d=%d" % (i, s[i]) for i in U) if U else "-", tuple(s)))
    return keys


def _cwa_state(inst):
    return tuple(1 if o == "T" else 0 for o in inst["obs"])  # U -> 0 (결측=정상/거짓)


def _realized(p, G, s):
    return tuple(sorted(p[j] for j in range(len(G)) if _sat(G[j]["app"], s)))


def _emit(inst, plan, label, rules_s0, app_s0):
    """상태 개념이 없는 방법의 출력: 모든 실제 상태에 같은 주장(계획 벡터 고정, 실현 집합은 상태별로 평가)."""
    G = inst["guidelines"]
    per_state = {}
    for k, s in _true_keys(inst):
        if plan is None:
            per_state[k] = ("CONFLICT", [])
        else:
            per_state[k] = ("CONFIRMED", [list(_realized(plan, G, s))])
    return dict(final=label, per_state=per_state, ewas=None, fsew=None, app=app_s0, rules=rules_s0,
                single_plan=True, excluded_out_of_support=False)


def run_A(inst):
    G = inst["guidelines"]; acts = {a["id"]: a for a in inst["actions"]}
    s0 = _cwa_state(inst)
    w0 = [_frac(x) for x in inst["W"]["center"]]
    conf = [r for r in inst["rules"] if r["type"] == "conflict"]
    app_s0 = ["CONFIRMED_APPLY" if _sat(g["app"], s0) else "NOT_APPLY" for g in G]
    prim = tuple(g["options"][0] for g in G)
    Rp = set(_realized(prim, G, s0))
    rules_s0 = []
    for r in inst["rules"]:
        if r["type"] != "conflict":
            rules_s0.append("N/A")
        else:
            rules_s0.append("REAL" if (r["a"] in Rp and r["b"] in Rp and _sat(r["cond"], s0)) else "NONE")
    detected = "REAL" in rules_s0

    def cost(p):
        R = _realized(p, G, s0)
        eff = sum(acts[a]["effect"] if acts[a]["trial"] is not None else 0 for a in R)
        return -(w0[0] * eff - w0[1] * sum(acts[a]["pills"] for a in R) - w0[2] * sum(acts[a]["visits"] for a in R))

    def admissible(p):
        R = set(_realized(p, G, s0))
        return not any(r["a"] in R and r["b"] in R and _sat(r["cond"], s0) for r in conf)

    # 수정 연산자 탐색: 1차 권고에서 출발해 지침별 대체 행동 교체로 도달 가능한 계획 = 모든 선택지 조합
    best = None
    for p in itertools.product(*[g["options"] for g in G]):
        if admissible(p):
            c = cost(p)
            if best is None or c < best[0] - 1e-12:
                best = (c, p)
    if best is None:
        return _emit(inst, None, "REAL_CONFLICT", rules_s0, app_s0)
    return _emit(inst, best[1], "CONFIRMED_PLAN" if detected else "CONVERGED", rules_s0, app_s0)


def run_C(inst):
    G = inst["guidelines"]
    s0 = _cwa_state(inst)
    app_s0 = ["CONFIRMED_APPLY" if _sat(g["app"], s0) else "NOT_APPLY" for g in G]
    rules0 = ["N/A" if r["type"] != "conflict" else "NONE" for r in inst["rules"]]
    prim = tuple(g["options"][0] for g in G)
    return _emit(inst, prim, "CONVERGED", rules0, app_s0)
