"""실제 사례 비교용 방법 구현 (52회차, 메인 작성).

모든 방법은 같은 입력(experiments/inputs/cases_input_v1.json)을 받는다.
- B  : 이전 R5 결합 정식화(상태공간 열거 + 양화)의 일반화 재구현. 새 알고리즘 아님.
       미확인 P/Q/K 변수 전부 열거 -> 항목 상태가 모든 상태에서 같으면 확정, 아니면 보류.
       보류 원인 = 판단을 바꾸는 변수 그룹. 확인 질문 = 판단을 바꾸는 P/Q 변수(영향 항목 수 내림차순, 비용 오름차순).
- A  : MitPlan식 독자 구현(원본 미재현). 폐쇄 세계(미확인=기본값) + 점 선호(미확인 선호=수용) + 계획 1개. 보류·근거 없음.
- C  : 순차 모듈 파이프라인(독자 구현). 지침 모듈(Kleene 3값) -> 선호 모듈(확정 후보만, 미확인 선호=점 가중) -> 근거 표지.
- D  : MitPlan식 정당 확장(독자 구현). 임상 시나리오 열거 + 선호 꼭짓점 재계획 + 변수 고정 질문. 근거·지식 변수 개념 없음(K=기본값).
- ALL_HOLD, GUIDELINE_ONLY : 퇴화 기준선.
"""
import ast
import itertools

LABELS = ("APPLY", "NOT_APPLY", "SDM_CONFLICT", "HOLD")


def unknown_vars(case):
    return [k for k, s in case["vars"].items() if s.get("known") is None]


def base_state(case):
    return {k: s["known"] for k, s in case["vars"].items() if s.get("known") is not None}


def ok_constraints(case, v):
    return all(eval(c, {"__builtins__": {}}, {"v": v}) for c in case.get("constraints", []))


def item_status(item, v):
    env = {"__builtins__": {}}
    if not eval(item["applies"], env, {"v": v}):
        return "NOT_APPLY"
    if eval(item["contra"], env, {"v": v}):
        return "NOT_APPLY"
    for var, req in item["prefs"]:
        if v[var] != req:
            return "SDM_CONFLICT"
    return "APPLY"


def enumerate_states(case, fixed=None, vars_subset=None):
    base = base_state(case)
    if fixed:
        base.update(fixed)
    U = [k for k in unknown_vars(case) if k not in base]
    if vars_subset is not None:
        # 나머지 미확인은 기본값
        for k in U:
            if k not in vars_subset:
                base[k] = case["vars"][k]["default"]
        U = [k for k in U if k in vars_subset]
    doms = [case["vars"][k]["domain"] for k in U]
    out = []
    for combo in itertools.product(*doms):
        v = dict(base)
        v.update(zip(U, combo))
        if ok_constraints(case, v):
            out.append(v)
    return out, U


def _relevant(case, item, states, U):
    """판단을 바꾸는 변수: v 하나만 다른 두 상태에서 상태가 달라지는 변수."""
    rel = set()
    idx = {}
    for s in states:
        idx[tuple(sorted((k, str(s[k])) for k in U))] = item_status(item, s)
    for s in states:
        st = item_status(item, s)
        for k in U:
            for val in case["vars"][k]["domain"]:
                if val == s[k]:
                    continue
                t = dict(s)
                t[k] = val
                key = tuple(sorted((kk, str(t[kk])) for kk in U))
                if key in idx and idx[key] != st:
                    rel.add(k)
    return rel


def _quantified(case, var_subset=None):
    states, U = enumerate_states(case, vars_subset=var_subset)
    res = {}
    for iid, item in case["items"].items():
        sts = {item_status(item, s) for s in states}
        if len(sts) == 1:
            res[iid] = {"label": sts.pop(), "cause": [], "relevant": []}
        else:
            rel = _relevant(case, item, states, U)
            groups = sorted({case["vars"][k]["group"] for k in rel})
            res[iid] = {"label": "HOLD", "cause": groups, "relevant": sorted(rel)}
    return res


def _questions(case, res):
    score = {}
    for iid, r in res.items():
        if r["label"] != "HOLD":
            continue
        for k in r["relevant"]:
            if case["vars"][k]["group"] in ("P", "Q"):
                score[k] = score.get(k, 0) + 1
    return sorted(score, key=lambda k: (-score[k], case["vars"][k].get("cost", 1), k)), score


def run_B(case):
    res = _quantified(case)
    q, sc = _questions(case, res)
    for iid, r in res.items():
        r["evidence_scope"] = case["items"][iid]["evidence_scope"]
        # 질문으로 닫히는지: P/Q 를 모두 고정해도 K 때문에 갈리면 닫히지 않음
        r["closable_by_asking"] = (r["label"] != "HOLD") or ("K" not in r["cause"])
    return {"items": res, "questions": q, "question_scores": sc}


def run_D(case):
    """MitPlan식 확장: K 변수는 기본값(지식 공백 개념 없음), P·Q 는 시나리오/꼭짓점 열거."""
    pq = [k for k in unknown_vars(case) if case["vars"][k]["group"] in ("P", "Q")]
    res = _quantified(case, var_subset=set(pq))
    q, sc = _questions(case, res)
    return {"items": res, "questions": q, "question_scores": sc}


def run_A(case):
    v = base_state(case)
    for k in unknown_vars(case):
        v[k] = case["vars"][k]["default"]
    res = {iid: {"label": item_status(it, v), "cause": [], "relevant": []} for iid, it in case["items"].items()}
    return {"items": res, "questions": [], "question_scores": {}}


def run_GUIDELINE_ONLY(case):
    """지침만(선호 무시) + 폐쇄 세계."""
    v = base_state(case)
    for k in unknown_vars(case):
        v[k] = case["vars"][k]["default"]
    res = {}
    for iid, it in case["items"].items():
        it2 = dict(it, prefs=[])
        res[iid] = {"label": item_status(it2, v), "cause": [], "relevant": []}
    return {"items": res, "questions": [], "question_scores": {}}


def run_ALL_HOLD(case):
    res = {iid: {"label": "HOLD", "cause": [], "relevant": []} for iid in case["items"]}
    q = [k for k in unknown_vars(case) if case["vars"][k]["group"] in ("P", "Q")]
    return {"items": res, "questions": q, "question_scores": {}}


# ---- C: Kleene 3값 ----
U3 = "U"


def _k_eval(node, v):
    if isinstance(node, ast.Expression):
        return _k_eval(node.body, v)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Subscript):
        key = node.slice.value if isinstance(node.slice, ast.Constant) else node.slice
        return v.get(key, U3)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        x = _k_eval(node.operand, v)
        return U3 if x == U3 else (not x)
    if isinstance(node, ast.BoolOp):
        vals = [_k_eval(x, v) for x in node.values]
        if isinstance(node.op, ast.And):
            if any(x is False for x in vals):
                return False
            return U3 if any(x == U3 for x in vals) else True
        if any(x is True for x in vals):
            return True
        return U3 if any(x == U3 for x in vals) else False
    raise ValueError(ast.dump(node))


def _names(expr):
    out = set()
    for n in ast.walk(ast.parse(expr, mode="eval")):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
            out.add(n.slice.value)
    return out


def run_C(case):
    v = base_state(case)  # 미확인은 키 없음 -> U
    res = {}
    qcount = {}
    for iid, it in case["items"].items():
        app = _k_eval(ast.parse(it["applies"], mode="eval"), v)
        con = _k_eval(ast.parse(it["contra"], mode="eval"), v)
        # 지침 모듈: applies AND NOT contra
        if app is False or con is True:
            lab = "NOT_APPLY"
        elif app is True and con is False:
            lab = "CAND"
        else:
            lab = "HOLD"
        if lab == "HOLD":
            unk = [k for k in (_names(it["applies"]) | _names(it["contra"])) if k not in v]
            for k in unk:
                if case["vars"][k]["group"] in ("P", "Q"):
                    qcount[k] = qcount.get(k, 0) + 1
            res[iid] = {"label": "HOLD", "cause": ["P"], "relevant": sorted(unk)}
            continue
        if lab == "NOT_APPLY":
            res[iid] = {"label": "NOT_APPLY", "cause": [], "relevant": []}
            continue
        # 선호 모듈: 확정 후보만. 미확인 선호 = 점 가중(기본값)
        outl = "APPLY"
        for var, req in it["prefs"]:
            val = v[var] if var in v else case["vars"][var]["default"]
            if val != req:
                outl = "SDM_CONFLICT"
        res[iid] = {"label": outl, "cause": [], "relevant": []}
    q = sorted(qcount, key=lambda k: (-qcount[k], case["vars"][k].get("cost", 1), k))
    return {"items": res, "questions": q, "question_scores": qcount}


METHODS = {"B": run_B, "A": run_A, "C": run_C, "D": run_D, "ALL_HOLD": run_ALL_HOLD, "GUIDELINE_ONLY": run_GUIDELINE_ONLY}
