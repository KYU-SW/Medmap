# -*- coding: utf-8 -*-
"""results_static_flags.csv + logs/downstream_*.csv -> results_mutation_detection.csv, results_by_operator.csv"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import D_ROOT  # noqa: E402

BASE = ["B1", "B1_LOO", "B2", "B3", "B3_jaccard_only", "B3w", "B5"]
static = list(csv.DictReader(open(os.path.join(D_ROOT, "results_static_flags.csv"), encoding="utf-8")))
orig = {int(r["rule_idx"]): r for r in static if r["kind"] == "orig"}
muts_meta = {json.loads(l)["mutant_id"]: json.loads(l) for l in open(os.path.join(D_ROOT, "mutation_spec", "mutants_v1.jsonl"), encoding="utf-8")}
down = {}
for p in glob.glob(os.path.join(D_ROOT, "logs", "downstream_M*.csv")):
    for r in csv.DictReader(open(p, encoding="utf-8")):
        down[r["mutant_id"]] = r


def fset(s):
    return {x for x in s.split(";") if x}


rows = []
for r in static:
    if r["kind"] != "mutant":
        continue
    o = orig[int(r["rule_idx"])]; m = muts_meta[r["item_id"]]; d = down[r["item_id"]]
    row = {"mutant_id": r["item_id"], "op": r["op"], "op_name": m["op_name"], "rule_id": m["rule_id"],
           "detail": m["detail"], "new_id_in_vocab": m["new_id_in_vocab"]}
    for b in BASE:
        new = fset(r[b]) - fset(o[b])
        row[f"{b}_new_flag"] = int(bool(new))
        row[f"{b}_flags"] = ";".join(sorted(new))
    row["REFFREE_union_B1_B3_B5"] = int(row["B1_new_flag"] or row["B3_new_flag"] or row["B5_new_flag"])
    row["REFFREE_union_B1LOO_B3_B5"] = int(row["B1_LOO_new_flag"] or row["B3_new_flag"] or row["B5_new_flag"])
    row["B4_allpairs_any_change"] = int(int(d["allpairs_changed"]) > 0)
    row["B4_allpairs_conflict_change"] = int(int(d["allpairs_conflict_changed"]) > 0)
    row["B4_lsh_any_change"] = int(d["lsh_changed_any"])
    for k in ["allpairs_changed", "allpairs_conflict_changed", "allpairs_conflict_added", "allpairs_conflict_removed",
              "allpairs_conflict_retyped", "allpairs_redund_changed", "lsh_added_or_changed", "lsh_removed_or_changed",
              "lsh_conflict_added", "lsh_conflict_removed", "example_changes"]:
        row["B4_" + k] = d[k]
    row["silent_and_downstream"] = int(not row["REFFREE_union_B1_B3_B5"] and row["B4_allpairs_conflict_change"])
    rows.append(row)

with open(os.path.join(D_ROOT, "results_mutation_detection.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# 원본 위양성(플래그율)
fpr = {b: sum(1 for o in orig.values() if fset(o[b])) / len(orig) for b in BASE}

COLS = ["B1_new_flag", "B1_LOO_new_flag", "B3_new_flag", "B3_jaccard_only_new_flag", "B3w_new_flag", "B5_new_flag",
        "REFFREE_union_B1_B3_B5", "REFFREE_union_B1LOO_B3_B5", "B2_new_flag", "B4_allpairs_any_change",
        "B4_allpairs_conflict_change", "B4_lsh_any_change", "silent_and_downstream"]
groups = defaultdict(list)
for r in rows:
    groups[(r["op"], r["op_name"], "all")].append(r)
    if r["new_id_in_vocab"] not in ("", None, "None"):
        groups[(r["op"], r["op_name"], "in_vocab=" + str(r["new_id_in_vocab"]))].append(r)
summ = []
for k in sorted(groups):
    g = groups[k]
    s = {"op": k[0], "op_name": k[1], "subset": k[2], "n": len(g)}
    for c in COLS:
        s[c] = round(sum(int(x[c]) for x in g) / len(g), 3)
    s["mean_allpairs_conflict_changed"] = round(sum(int(x["B4_allpairs_conflict_changed"]) for x in g) / len(g), 2)
    summ.append(s)
tot = {"op": "ALL", "op_name": "all mutants", "subset": "all", "n": len(rows)}
for c in COLS:
    tot[c] = round(sum(int(x[c]) for x in rows) / len(rows), 3)
tot["mean_allpairs_conflict_changed"] = round(sum(int(x["B4_allpairs_conflict_changed"]) for x in rows) / len(rows), 2)
summ.append(tot)
fp = {"op": "ORIG_FLAG_RATE", "op_name": "원본 563 규칙 플래그율(위양성 기준선)", "subset": "all", "n": len(orig)}
for c in COLS:
    b = c.replace("_new_flag", "")
    fp[c] = round(fpr[b], 3) if b in fpr else ""
fp["mean_allpairs_conflict_changed"] = ""
summ.append(fp)
with open(os.path.join(D_ROOT, "results_by_operator.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)
for s in summ:
    print(s)
