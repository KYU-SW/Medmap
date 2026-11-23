"""K1 narrowed-problem minimal experiment.
2x2: criteria structure {gold hand-coded, regex baseline} x missing-data semantics {3-valued Kleene, closed-world}.
Outputs results_*.csv in B-k1-data/. Synthetic patients only; not medical safety judgement.
"""
import csv
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "code"))
from regex_baseline import extract  # noqa: E402

T, F, U = "T", "F", "U"
TRIALS = {"DAPA-CKD": "NCT03036150", "EMPA-KIDNEY": "NCT03594110", "CREDENCE": "NCT02065791",
          "FIDELIO-DKD": "NCT02540993", "FLOW": "NCT03819153", "SCORED": "NCT03315143"}
NUMERIC = {"age", "egfr", "uacr", "hba1c", "k", "nyha", "sbp"}
DAYS = {"recent_cv_days", "glp1_days"}


def leaf(a, p, closed):
    raw = p.get(a["v"], "NA")
    if raw in ("NA", ""):
        return F if closed else U
    if "eq" in a:
        if raw == a["eq"]:
            return T
        if a.get("n_as_unknown") and raw == "N":
            return F if closed else U
        return F
    if a["v"] in DAYS and raw == "none":
        return F
    v, x = float(raw), a["x"]
    ok = {">=": v >= x, ">": v > x, "<=": v <= x, "<": v < x}[a["cmp"]]
    return T if ok else F


def ev(node, p, closed):
    if "and" in node:
        r = [ev(n, p, closed) for n in node["and"]]
        return F if F in r else (U if U in r else T)
    if "or" in node:
        r = [ev(n, p, closed) for n in node["or"]]
        return T if T in r else (U if U in r else F)
    return leaf(node, p, closed)


def label(crit, p, closed):
    inc = ev(crit["inclusion"], p, closed)
    exc = [ev(e, p, closed) for e in crit["exclusion"]]
    if inc == F or T in exc:
        return "INELIGIBLE"
    if inc == U or U in exc:
        return "UNDETERMINED"
    return "ELIGIBLE"


def main():
    gold = json.load(open(os.path.join(BASE, "gold", "gold_criteria.json")))
    pts = list(csv.DictReader(open(os.path.join(BASE, "gold", "patients_synthetic.csv"))))
    regex = {}
    for t, nct in TRIALS.items():
        d = json.load(open(os.path.join(BASE, "data", "ctgov", nct + ".json")))
        regex[t] = extract(d["protocolSection"]["eligibilityModule"]["eligibilityCriteria"])
    json.dump(regex, open(os.path.join(BASE, "results_regex_extracted_criteria.json"), "w"), indent=1)

    rows = []
    for p in pts:
        for t in TRIALS:
            rows.append({"pid": p["pid"], "trial": t,
                         "gold_3v": label(gold[t], p, False), "gold_cw": label(gold[t], p, True),
                         "regex_3v": label(regex[t], p, False), "regex_cw": label(regex[t], p, True)})
    with open(os.path.join(BASE, "results_pairs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    # summary vs gold_3v
    summ = []
    for m in ("gold_cw", "regex_3v", "regex_cw"):
        agree = sum(r[m] == r["gold_3v"] for r in rows)
        over = sum(r[m] == "ELIGIBLE" and r["gold_3v"] != "ELIGIBLE" for r in rows)
        over_inel = sum(r[m] == "ELIGIBLE" and r["gold_3v"] == "INELIGIBLE" for r in rows)
        hide_u = sum(r["gold_3v"] == "UNDETERMINED" and r[m] != "UNDETERMINED" for r in rows)
        summ.append({"method": m, "n_pairs": len(rows), "agree_with_gold_3v": agree,
                     "agreement": round(agree / len(rows), 3),
                     "false_ELIGIBLE_total": over, "false_ELIGIBLE_when_gold_INELIGIBLE": over_inel,
                     "gold_UNDETERMINED_not_flagged": hide_u})
    with open(os.path.join(BASE, "results_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0])); w.writeheader(); w.writerows(summ)

    # confusion matrices
    conf = []
    for m in ("gold_cw", "regex_3v", "regex_cw"):
        c = Counter((r["gold_3v"], r[m]) for r in rows)
        for (g, b), n in sorted(c.items()):
            conf.append({"method": m, "gold_3v": g, "pred": b, "n": n})
    with open(os.path.join(BASE, "results_confusion.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "gold_3v", "pred", "n"]); w.writeheader(); w.writerows(conf)

    # per-trial
    pt = []
    for t in TRIALS:
        rr = [r for r in rows if r["trial"] == t]
        pt.append({"trial": t, **{f"{m}_agree": sum(r[m] == r["gold_3v"] for r in rr) for m in ("gold_cw", "regex_3v", "regex_cw")},
                   "n": len(rr), "gold_dist": dict(Counter(r["gold_3v"] for r in rr))})
    with open(os.path.join(BASE, "results_per_trial.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pt[0])); w.writeheader(); w.writerows(pt)

    # spot-check: hand labels vs gold evaluator
    sc = list(csv.DictReader(open(os.path.join(BASE, "gold", "gold_manual_spotcheck.csv"))))
    look = {(r["pid"], r["trial"]): r for r in rows}
    sc_out = [{**s, "gold_evaluator": look[(s["pid"], s["trial"])]["gold_3v"],
               "match": s["expected_label"] == look[(s["pid"], s["trial"])]["gold_3v"]} for s in sc]
    with open(os.path.join(BASE, "results_spotcheck.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sc_out[0])); w.writeheader(); w.writerows(sc_out)

    print("gold_3v distribution:", dict(Counter(r["gold_3v"] for r in rows)))
    for s in summ:
        print(s)
    print("spotcheck match:", sum(s["match"] for s in sc_out), "/", len(sc_out))
    for s in sc_out:
        if not s["match"]:
            print("  MISMATCH", s)
    for p in pt:
        print(p)


if __name__ == "__main__":
    main()
