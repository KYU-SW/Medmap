"""R5 원본 결합 정식화 코드(복사본, 읽기 전용)와 메인 B 의 지침 적용 3값 판정 대조.
대상: applies 가 리터럴 논리곱으로만 된 항목(R5 스키마 'app' 로 표현 가능). 사용: python -I -B crosscheck_r5_v1.py <out_dir>
R5 의 app 은 CONFIRMED_APPLY / NOT_APPLY / CONDITIONAL_APPLY. 메인 B 는 applies 를 모든 상태에서 평가해 같은 3값으로 변환.
"""
import ast
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R5 = os.path.join(ROOT, "baselines", "agentB", "reuse", "r5_D_experiments")
sys.path.insert(0, os.path.join(R5, "methods")); sys.path.insert(0, R5)
sys.path.insert(0, os.path.join(ROOT, "baselines"))
from strong import run_B as r5_run_B  # noqa: E402
from gen_instances import W, act, base  # noqa: E402
import methods_v1 as M  # noqa: E402


def literals(expr):
    """v['x'] / not v['x'] 의 and 결합이면 [(x, 1|0)] 반환, 아니면 None."""
    node = ast.parse(expr, mode="eval").body
    parts = node.values if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And) else [node]
    out = []
    for p in parts:
        neg = False
        if isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.Not):
            neg, p = True, p.operand
        if isinstance(p, ast.Subscript) and isinstance(p.slice, ast.Constant):
            out.append((p.slice.value, 0 if neg else 1))
        else:
            return None
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    cases = json.load(open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v1.json")))["cases"]
    rows = []
    for cid, case in cases.items():
        binv = [k for k, s in case["vars"].items() if s["group"] in ("P", "K") and (s.get("known") in (True, False) or s.get("domain") == [True, False])]
        idx = {k: i for i, k in enumerate(binv)}
        obs = []
        for k in binv:
            kn = case["vars"][k].get("known")
            obs.append("U" if kn is None else ("T" if kn else "F"))
        deps = []
        if cid == "CASE_04":
            deps = [[idx["knee_oa"], idx["hip_knee_oa"]]]
        gl, acts, items = [], [], []
        for iid, it in case["items"].items():
            lits = literals(it["applies"])
            if lits is None or any(x not in idx for x, _ in lits):
                continue
            gl.append({"app": [[idx[x], b] for x, b in lits], "options": [len(acts)]})
            acts.append(act(len(acts), 1, 0, 0, None))
            items.append(iid)
        if not gl:
            continue
        inst = base(cid, "case", len(binv), obs, gl, acts, [], {"x0": 60, "x1_base": 5, "x1_delta": 0, "x1_var": None}, W(), deps=deps)
        r5 = r5_run_B(inst)["app"]
        states, _ = M.enumerate_states(case)
        for gi, iid in enumerate(items):
            vals = {bool(eval(case["items"][iid]["applies"], {"__builtins__": {}}, {"v": s})) for s in states}
            mine = "CONFIRMED_APPLY" if vals == {True} else ("NOT_APPLY" if vals == {False} else "CONDITIONAL_APPLY")
            r5v = r5[gi] if isinstance(r5, list) else r5.get(gi, r5.get(str(gi)))
            rows.append({"case_id": cid, "item": iid, "applies": case["items"][iid]["applies"], "r5_app": r5v, "main_B_app": mine, "match": r5v == mine})
    with open(os.path.join(out, "crosscheck_r5_app.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows), "match", sum(r["match"] for r in rows))


if __name__ == "__main__":
    main(sys.argv[1])
