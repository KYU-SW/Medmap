# -*- coding: utf-8 -*-
"""gold 어휘 안의 동의어 id(B3 정규화 클러스터, 수동 확인)를 정규 id 로 합쳤을 때 원본 analyzer 관계 변화 (all-pairs)."""
import copy, csv, json, os, re, sys, time
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from orig_loader import D_ROOT, atomic_predicates, load_pipeline_modules, load_rules
import eval_static as es
an, _, _ = load_pipeline_modules()
rules = load_rules()
freq = Counter(i for r in rules for i in es.all_ids(r["condition"], r["action"]))
canon = {}
for k, v in es.KEYMAP.items():
    if len(v) > 1:
        c = max(sorted(v), key=lambda x: freq[x])
        for x in v:
            if x != c: canon[x] = c
def canon_rule(r):
    r = copy.deepcopy(r)
    r["condition"] = re.sub(r"pred\.[A-Za-z0-9_]+", lambda m: canon.get(m.group(0), m.group(0)), r["condition"])
    r["action"]["subjects"] = [canon.get(s, s) for s in r["action"]["subjects"]]
    return r
def allpairs(rs):
    ra = an.RuleAnalyzer(rs, atomic_predicates(rs)); ids = [r["id"] for r in rs]; out = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = sorted((ids[i], ids[j]))
            act = an.ActionAnalyzer.analyze_pair(ra.rules[a]["action"], ra.rules[b]["action"])
            out[(a, b)] = "others" if act.relation == an.ActionRelation.INDEPENDENT else an.RuleAnalyzer.analyze_pair(ra, a, b).overall_relation.value
    return out
t = time.time()
crs = [canon_rule(r) for r in rules]
changed_rules = sum(1 for a, b in zip(rules, crs) if a != b)
g = {}
for row in csv.DictReader(open(os.path.join(D_ROOT, "results_gold_relations_allpairs.csv"), encoding="utf-8")):
    g[(row["rule_a"], row["rule_b"])] = row["overall_relation"]
c = allpairs(crs)
CF = {"local_conflict", "intrinsic_conflict", "implication_conflict", "intrinsic_disagreement", "implication_disagreement"}
diff = [(k, g.get(k, "others"), v) for k, v in c.items() if g.get(k, "others") != v]
with open(os.path.join(D_ROOT, "results_gold_synonym_merge_diff.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["rule_a", "rule_b", "gold_ids_relation", "synonym_merged_relation"])
    for k, a, b in sorted(diff): w.writerow([k[0], k[1], a, b])
summ = {"canonical_map": canon, "rules_changed_by_merge": changed_rules, "pairs_relation_changed": len(diff),
        "transitions": Counter(f"{a}->{b}" for _, a, b in diff).most_common(),
        "conflict_family_gold": sum(1 for v in g.values() if v in CF), "conflict_family_merged": sum(1 for v in c.values() if v in CF),
        "new_conflict_family_pairs": sum(1 for _, a, b in diff if b in CF and a not in CF), "sec": round(time.time() - t, 1)}
json.dump(summ, open(os.path.join(D_ROOT, "results_gold_synonym_merge_summary.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in summ.items() if k != "canonical_map"}, ensure_ascii=False, indent=1))
