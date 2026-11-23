"""실제 사례 비교 실험 실행 + 채점 (52회차). 사용: python -I -B run_v1.py <out_dir>
입력: experiments/inputs/cases_input_v1.json, evaluation/REF_R_v1.json(동결, sha 검사)
채점 지표: evaluation/agentC/METRIC_DESIGN.md 의 CC/WC/AD/UD, U, S, 질문 재현율·정밀도. 모든 수치는 REF-R(연구자 작성, 비독립) 일치율이며 의료적 정확도가 아니다.
"""
import csv
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "baselines"))
import methods_v1 as M  # noqa: E402

REF_SHA = "efaa9cfe7100c39d212e9851b8522a2929d0e5ad1b81a5dc9d0456f25d0f6721"


def load():
    p = os.path.join(ROOT, "evaluation", "REF_R_v1.json")
    raw = open(p, "rb").read()
    assert hashlib.sha256(raw).hexdigest() == REF_SHA, "REF-R 해시 불일치"
    ref = json.loads(raw)
    cases = json.load(open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v1.json")))["cases"]
    return cases, ref


def classify(out_lab, ref_lab):
    if out_lab == "HOLD":
        return "AD" if ref_lab == "HOLD" else "UD"
    if ref_lab == "HOLD" or out_lab != ref_lab:
        return "WC"
    return "CC"


def utility(c, n, lw, lu):
    return (c["CC"] + c["AD"] - lw * c["WC"] - lu * c["UD"]) / n


def main(out):
    os.makedirs(out, exist_ok=True)
    cases, ref = load()
    rows, qrows, outputs, timing = [], [], {}, {}
    for mname, fn in M.METHODS.items():
        outputs[mname] = {}
        t0 = time.perf_counter()
        for cid, case in cases.items():
            o = fn(case)
            outputs[mname][cid] = o
            rc = ref["cases"][cid]
            for iid, (rl, rcause) in rc["items"].items():
                ol = o["items"][iid]["label"]
                oc = o["items"][iid]["cause"]
                cls = classify(ol, rl)
                rows.append({"method": mname, "case_id": cid, "case_type": case["case_type"], "item": iid,
                             "action": case["items"][iid]["action"], "ref": rl, "ref_cause": "+".join(rcause),
                             "out": ol, "out_cause": "+".join(oc), "class": cls,
                             "cause_match": (cls == "AD" and sorted(oc) == sorted(rcause))})
            Q = set(o["questions"])
            R = set(rc["required_confirm"])
            A = set(rc["acceptable_confirm"])
            qrows.append({"method": mname, "case_id": cid, "case_type": case["case_type"], "n_q": len(Q), "n_R": len(R),
                          "hit_R": len(Q & R), "in_A": len(Q & A), "missing_R": "|".join(sorted(R - Q)),
                          "extra": "|".join(sorted(Q - A)), "questions_ranked": "|".join(o["questions"])})
        timing[mname] = time.perf_counter() - t0

    with open(os.path.join(out, "item_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(out, "question_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys()))
        w.writeheader(); w.writerows(qrows)
    json.dump(outputs, open(os.path.join(out, "method_outputs.json"), "w"), ensure_ascii=False, indent=1, default=str)

    # 집계: 사례 종류별 + 전체(전체는 REF-R 일치율 참고용)
    strata = {"ALL": None, "REAL_WITH_PREF": "REAL_WITH_PREF", "REAL_NO_PREF": "REAL_NO_PREF", "GUIDELINE_VIGNETTE": "GUIDELINE_VIGNETTE"}
    summ = []
    for sname, st in strata.items():
        cnt = {}
        for m in M.METHODS:
            sel = [r for r in rows if r["method"] == m and (st is None or r["case_type"] == st)]
            c = {k: sum(1 for r in sel if r["class"] == k) for k in ("CC", "WC", "AD", "UD")}
            c["n"] = len(sel)
            c["cause_match"] = sum(1 for r in sel if r["cause_match"])
            cnt[m] = c
        for lw, lu in [(5, 1), (2, 0.5), (2, 1), (2, 2), (5, 0.5), (5, 2), (10, 0.5), (10, 1), (10, 2)]:
            U = {m: utility(cnt[m], cnt[m]["n"], lw, lu) for m in M.METHODS}
            uref = max(U["ALL_HOLD"], U["GUIDELINE_ONLY"])
            for m in M.METHODS:
                qs = [q for q in qrows if q["method"] == m and (st is None or q["case_type"] == st)]
                nR = sum(q["n_R"] for q in qs); hR = sum(q["hit_R"] for q in qs)
                nQ = sum(q["n_q"] for q in qs); inA = sum(q["in_A"] for q in qs)
                c = cnt[m]
                ref_hold = sum(1 for r in rows if r["method"] == m and (st is None or r["case_type"] == st) and r["ref"] == "HOLD")
                summ.append({"stratum": sname, "lambda_W": lw, "lambda_U": lu, "method": m, "n_items": c["n"],
                             "CC": c["CC"], "WC": c["WC"], "AD": c["AD"], "UD": c["UD"], "cause_match_in_AD": c["cause_match"],
                             "ref_hold_share": round(ref_hold / c["n"], 4),
                             "U": round(U[m], 4), "U_ref": round(uref, 4),
                             "S": round((U[m] - uref) / (1 - uref), 4) if uref < 1 else "NA",
                             "q_recall": round(hR / nR, 4) if nR else "NA", "q_precision": round(inA / nQ, 4) if nQ else "NA",
                             "q_burden_ratio": round(nQ / nR, 4) if nR else "NA",
                             "unnecessary_hold_rate": round(c["UD"] / (c["n"] - ref_hold), 4) if c["n"] - ref_hold else "NA",
                             "wrong_confirm_rate": round(c["WC"] / c["n"], 4)})
    with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader(); w.writerows(summ)

    # B7xB9 상호작용 (방법 B): 선호 변수 값을 하나씩 고정하고 결과 비교
    inter = []
    for cid, case in cases.items():
        qvars = [k for k, s in case["vars"].items() if s["group"] == "Q"]
        for q in qvars:
            dom = case["vars"][q].get("domain", ["accept", "reject"])
            res_by = {}
            for val in dom:
                c2 = json.loads(json.dumps(case))
                c2["vars"][q] = dict(c2["vars"][q], known=val)
                res_by[val] = M.run_B(c2)["items"]
            a, b = dom[0], dom[1]
            for iid in case["items"]:
                la, lb = res_by[a][iid]["label"], res_by[b][iid]["label"]
                ca, cb = res_by[a][iid]["cause"], res_by[b][iid]["cause"]
                if la != lb and "HOLD" not in (la, lb):
                    kind = "DECISION_CHANGE"
                elif la != lb:
                    kind = "HOLD_STATUS_CHANGE"
                elif la == "HOLD" and (ca != cb or res_by[a][iid]["relevant"] != res_by[b][iid]["relevant"]):
                    kind = "HOLD_CONDITION_CHANGE"
                else:
                    kind = "NO_CHANGE"
                inter.append({"case_id": cid, "case_type": case["case_type"], "pref_var": q,
                              "pref_known": case["vars"][q].get("known"), "item": iid, "action": case["items"][iid]["action"],
                              f"label_if_{a}": la, f"label_if_{b}": lb, "cause_if_a": "+".join(ca), "cause_if_b": "+".join(cb),
                              "kind": kind, "priority_change": "NOT_EVALUATED(검증된 가중치 없음)"})
    keys = sorted({k for r in inter for k in r}, key=lambda k: list(inter[0].keys()).index(k) if k in inter[0] else 99)
    with open(os.path.join(out, "b7_b9_interaction.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval="")
        w.writeheader(); w.writerows(inter)
    json.dump({"timing_sec": timing, "ref_sha256": REF_SHA,
               "input_sha256": hashlib.sha256(open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v1.json"), "rb").read()).hexdigest(),
               "methods_sha256": hashlib.sha256(open(os.path.join(ROOT, "baselines", "methods_v1.py"), "rb").read()).hexdigest()},
              open(os.path.join(out, "run_meta.json"), "w"), indent=1)
    print("done", out)


if __name__ == "__main__":
    main(sys.argv[1])
