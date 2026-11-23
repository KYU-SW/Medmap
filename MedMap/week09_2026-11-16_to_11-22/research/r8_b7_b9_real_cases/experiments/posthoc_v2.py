"""[사후 분석] run 결과를 본 뒤 추가. 사용: python -I -B posthoc_v1.py <run_dir>
1) 조건부 결과 변화: 선호 값에 따라 보류 항목의 '확인 후 가능한 결론 집합'이 달라지는지(B).
2) 확인 질문 구성: B 질문의 P/Q 비율.
3) 실제 결정·저자 기대안과 방법 출력 대조(정답 아님).
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "baselines"))
import methods_v1 as M  # noqa: E402


def possible(case, iid):
    states, _ = M.enumerate_states(case)
    return sorted({M.item_status(case["items"][iid], s) for s in states})


def main(run):
    cases = json.load(open(os.path.join(ROOT, "experiments", "inputs", "cases_input_v2.json")))["cases"]
    out = []
    for cid, case in cases.items():
        for q, spec in case["vars"].items():
            if spec["group"] != "Q":
                continue
            dom = spec.get("domain", ["accept", "reject"])
            for iid in case["items"]:
                ps = {}
                for val in dom:
                    c2 = json.loads(json.dumps(case))
                    c2["vars"][q] = dict(c2["vars"][q], known=val)
                    ps[val] = possible(c2, iid)
                if ps[dom[0]] != ps[dom[1]]:
                    out.append({"case_id": cid, "case_type": case["case_type"], "pref_var": q, "pref_known": spec.get("known"),
                                "item": iid, "action": case["items"][iid]["action"],
                                "possible_if_" + dom[0]: "/".join(ps[dom[0]]), "possible_if_" + dom[1]: "/".join(ps[dom[1]])})
    keys = []
    for r in out:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(run, "posthoc_conditional_outcome_change.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval="")
        w.writeheader(); w.writerows(out)

    outputs = json.load(open(os.path.join(run, "method_outputs.json")))
    qc = []
    for cid, case in cases.items():
        qs = outputs["B"][cid]["questions"]
        qc.append({"case_id": cid, "case_type": case["case_type"], "n_questions": len(qs),
                   "n_P": sum(1 for k in qs if case["vars"][k]["group"] == "P"),
                   "n_Q": sum(1 for k in qs if case["vars"][k]["group"] == "Q"),
                   "ranked": "|".join(f"{k}({case['vars'][k]['group']},{outputs['B'][cid]['question_scores'][k]})" for k in qs)})
    with open(os.path.join(run, "posthoc_question_composition.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qc[0].keys()))
        w.writeheader(); w.writerows(qc)

    ap = json.load(open(os.path.join(ROOT, "evaluation", "ACTUAL_PRACTICE_v1.json")))["items"]
    rows = []
    for cid, items in ap.items():
        for iid, (act, note) in items.items():
            r = {"case_id": cid, "item": iid, "action": cases[cid]["items"][iid]["action"], "actual": act, "note": note}
            for m in ("B", "A", "C", "D"):
                r[m] = outputs[m][cid]["items"][iid]["label"]
            rows.append(r)
    with open(os.path.join(run, "posthoc_actual_practice_comparison.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("posthoc done")


if __name__ == "__main__":
    main(sys.argv[1])
