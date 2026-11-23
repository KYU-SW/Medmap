# -*- coding: utf-8 -*-
"""B4: 원본 analyzer(src_copy, 원자 술어 추상화)로 변이 전후 규칙쌍 관계 변화를 측정.

사용: python eval_downstream.py gold        -> gold 관계(all-pairs, LSH 기본값, prefix-bug 수정판 비교)
      python eval_downstream.py mutants OPS  -> OPS(쉼표 구분, 예 M01,M02) 변이 영향
"""
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from orig_loader import D_ROOT, atomic_predicates, load_pipeline_modules, load_rules  # noqa: E402

an, z3env_mod, lsh = load_pipeline_modules()
rules = load_rules()
muts = [json.loads(l) for l in open(os.path.join(D_ROOT, "mutation_spec", "mutants_v1.jsonl"), encoding="utf-8")]
ids = [r["id"] for r in rules]
# 술어 정의: gold + 변이에서 등장한 모든 pred id 를 독립 원자로
pseudo = rules + [{"condition": m["mut_condition"]} for m in muts]
PREDS = atomic_predicates(pseudo)
ra = an.RuleAnalyzer(rules, PREDS)
ORIG_ANALYZE = an.RuleAnalyzer.analyze_pair
CONFLICT = {"local_conflict", "intrinsic_conflict", "implication_conflict", "intrinsic_disagreement",
            "implication_disagreement"}
REDUND = {"complete_redundancy", "contained_redundancy"}

content_key = {r["id"]: json.dumps([r["condition"], r["action"]], ensure_ascii=False, sort_keys=True) for r in rules}
_cache = {}
stats = Counter()


def memo_analyze(a, b):
    k = (a, b, content_key[a], content_key[b])
    if k in _cache:
        return _cache[k]
    act = an.ActionAnalyzer.analyze_pair(ra.rules[a].get("action", {}), ra.rules[b].get("action", {}))
    if act.relation == an.ActionRelation.INDEPENDENT:
        # 원본 _determine_overall_relation 첫 분기와 동일 결과(OTHERS). 조건 분석만 생략.
        res = an.RulePairResult(a, b, an.PredicateRelation.UNKNOWN, act.relation, an.RuleRelation.OTHERS, "INDEPENDENT")
        stats["shortcut_independent"] += 1
    else:
        res = ORIG_ANALYZE(ra, a, b)
        stats["full_analyze"] += 1
    _cache[k] = res
    return res


ra.analyze_pair = memo_analyze
cr = an.ConflictResolver.__new__(an.ConflictResolver)
cr.rules = rules
cr.rule_analyzer = ra

# ---- LSH 서명 캐시 (원본 _build_rule_lsh_signature 사용) ----
SIG = {rid: ra._build_rule_lsh_signature(rid) for rid in ids}
NB, RPB, THR = 20, 5, 0.3


def band_keys(sig):
    return {(b, tuple(sig[b * RPB:(b + 1) * RPB])) for b in range(NB) if (b + 1) * RPB <= len(sig)}


def est_sim(s1, s2):
    n = min(len(s1), len(s2))
    return sum(1 for k in range(n) if s1[k] == s2[k]) / n if n else 0.0


BANDS = {rid: band_keys(SIG[rid]) for rid in ids if SIG[rid]}


def cands_for(rid, sig):
    """rid 와 다른 규칙 사이의 LSH 후보쌍 (원본 _find_similar_rule_pairs_lsh 와 같은 규칙)"""
    out = set()
    if not sig:
        return out
    bk = band_keys(sig)
    for o in ids:
        if o == rid or o not in BANDS:
            continue
        if bk & BANDS[o] and est_sim(sig, SIG[o]) >= THR:
            out.add(tuple(sorted((rid, o))))
    return out


def lsh_run(cands):
    summary, analyzed = cr._collect_rule_relations(max_pairs=10 ** 9, use_lsh_filter=True, use_bucket_filter=True,
                                                   lsh_similarity_threshold=THR, lsh_num_bands=NB,
                                                   lsh_rows_per_band=RPB, candidate_pairs=set(cands))
    cr._apply_transitive_closure(summary, analyzed)
    rel = {}
    for lab in CONFLICT | REDUND:
        for r in summary[lab]:
            rel[tuple(sorted((r.rule_a, r.rule_b)))] = lab
    return rel


def label(res):
    return res.overall_relation.value


def allpairs_for(rid):
    return {tuple(sorted((rid, o))): label(ra.analyze_pair(*sorted((rid, o)))) for o in ids if o != rid}


class Quiet:
    def __enter__(self):
        self._o = sys.stdout; sys.stdout = open(os.devnull, "w")

    def __exit__(self, *a):
        sys.stdout.close(); sys.stdout = self._o


def fixed_expand(condition):
    """prefix-bug 수정판: 단어 경계 기반 치환 (비교용, 원본 아님)"""
    if not condition:
        return None
    expr = condition.replace(" AND ", " & ").replace(" OR ", " | ").replace("NOT ", "~ ")

    def rep(m):
        p = ra.pred_analyzer.predicates.get(m.group(0))
        if not p:
            raise KeyError(m.group(0))
        return "(" + p["formal_definition"].strip()[1:-1].strip() + ")"
    try:
        expr = re.sub(r"pred\.[A-Za-z0-9_]+", rep, expr)
    except KeyError:
        return None
    return f"$ {expr} $"


def run_gold():
    t = time.time()
    rows = []
    allp = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = sorted((ids[i], ids[j]))
            allp[(a, b)] = ra.analyze_pair(a, b)
    cnt = Counter(label(r) for r in allp.values())
    condcnt = Counter(r.condition_relation.value for r in allp.values() if r.action_relation != an.ActionRelation.INDEPENDENT)
    actcnt = Counter(r.action_relation.value for r in allp.values())
    with Quiet():
        gold_cands = ra._find_similar_rule_pairs_lsh(num_bands=NB, rows_per_band=RPB, similarity_threshold=THR)
        lshrel = lsh_run(gold_cands)
    # 원본 함수와 재구현 후보 생성의 일치 확인
    recon = set()
    for rid in ids:
        recon |= cands_for(rid, SIG[rid])
    # prefix-bug 수정판
    orig_expand = ra._expand_condition
    ra._expand_condition = fixed_expand
    fixed = {}
    for k, r in allp.items():
        if r.action_relation != an.ActionRelation.INDEPENDENT:
            fixed[k] = ORIG_ANALYZE(ra, *k)
    ra._expand_condition = orig_expand
    diff = [(k, label(allp[k]), label(v), allp[k].condition_relation.value, v.condition_relation.value)
            for k, v in fixed.items() if label(v) != label(allp[k]) or v.condition_relation != allp[k].condition_relation]
    # 확장 실패(UNKNOWN) 규칙
    parse_fail = []
    for r in rules:
        e = ra._expand_condition(r["condition"])
        try:
            ra.pred_analyzer.z3env.ensure_vars_for_expr(e); ra.pred_analyzer.z3env.expr(e)
        except Exception:
            parse_fail.append(r["id"])
    with open(os.path.join(D_ROOT, "results_gold_relations_allpairs.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["rule_a", "rule_b", "condition_relation", "action_relation", "overall_relation",
                                       "in_lsh_default_output"])
        for k, r in sorted(allp.items()):
            if label(r) != "others" or k in lshrel:
                w.writerow([k[0], k[1], r.condition_relation.value, r.action_relation.value, label(r),
                            lshrel.get(k, "")])
    with open(os.path.join(D_ROOT, "results_prefix_bug_diff.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["rule_a", "rule_b", "orig_overall", "fixed_overall", "orig_cond_rel", "fixed_cond_rel"])
        for d in sorted(diff):
            w.writerow([d[0][0], d[0][1], d[1], d[2], d[3], d[4]])
    summary = {"n_rules": len(ids), "n_pairs": len(allp), "allpairs_overall": dict(cnt), "allpairs_action": dict(actcnt),
               "allpairs_condition_rel_nonindependent": dict(condcnt),
               "lsh_candidates_original_fn": len(gold_cands), "lsh_candidates_reimpl": len(recon),
               "lsh_candidates_match": recon == gold_cands,
               "lsh_default_output": dict(Counter(lshrel.values())),
               "conflict_family_allpairs": sum(v for k, v in cnt.items() if k in CONFLICT),
               "conflict_family_lsh": sum(1 for v in lshrel.values() if v in CONFLICT),
               "rules_condition_expand_parse_fail": len(parse_fail), "parse_fail_ids": parse_fail,
               "prefix_bug_fix_changed_pairs": len(diff),
               "prefix_bug_fix_changed_overall": sum(1 for d in diff if d[1] != d[2]),
               "stats": dict(stats), "sec": round(time.time() - t, 1)}
    json.dump(summary, open(os.path.join(D_ROOT, "results_gold_summary.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"gold_cands": sorted(gold_cands), "lshrel": {f"{k[0]}||{k[1]}": v for k, v in lshrel.items()}},
              open(os.path.join(D_ROOT, "logs", "gold_lsh_cache.json"), "w"))
    print(json.dumps({k: v for k, v in summary.items() if k != "parse_fail_ids"}, ensure_ascii=False, indent=1))


def run_mutants(ops):
    t = time.time()
    g = json.load(open(os.path.join(D_ROOT, "logs", "gold_lsh_cache.json")))
    gold_cands = {tuple(x) for x in g["gold_cands"]}
    gold_lsh = {tuple(k.split("||")): v for k, v in g["lshrel"].items()}
    out = []
    for m in muts:
        if m["op"] not in ops:
            continue
        rid = m["rule_id"]
        before = allpairs_for(rid)
        orig_rule = ra.rules[rid]
        mut = dict(orig_rule); mut["condition"] = m["mut_condition"]; mut["action"] = m["mut_action"]
        ra.rules[rid] = mut; ra._rule_conditions[rid] = m["mut_condition"]
        content_key[rid] = json.dumps([mut["condition"], mut["action"]], ensure_ascii=False, sort_keys=True)
        old_sig = SIG[rid]; SIG[rid] = ra._build_rule_lsh_signature(rid)
        after = allpairs_for(rid)
        cands = {p for p in gold_cands if rid not in p} | cands_for(rid, SIG[rid])
        with Quiet():
            lshrel = lsh_run(cands)
        # 복원
        ra.rules[rid] = orig_rule; ra._rule_conditions[rid] = orig_rule["condition"]
        content_key[rid] = json.dumps([orig_rule["condition"], orig_rule["action"]], ensure_ascii=False, sort_keys=True)
        SIG[rid] = old_sig
        ch = [(k, before[k], after[k]) for k in before if before[k] != after[k]]
        cf = [c for c in ch if c[1] in CONFLICT or c[2] in CONFLICT]
        rd = [c for c in ch if c[1] in REDUND or c[2] in REDUND]
        add = {k: v for k, v in lshrel.items() if gold_lsh.get(k) != v}
        rem = {k: v for k, v in gold_lsh.items() if lshrel.get(k) != v}
        out.append({"mutant_id": m["mutant_id"], "op": m["op"], "rule_id": rid,
                    "allpairs_changed": len(ch), "allpairs_conflict_changed": len(cf),
                    "allpairs_conflict_added": sum(1 for c in ch if c[2] in CONFLICT and c[1] not in CONFLICT),
                    "allpairs_conflict_removed": sum(1 for c in ch if c[1] in CONFLICT and c[2] not in CONFLICT),
                    "allpairs_conflict_retyped": sum(1 for c in ch if c[1] in CONFLICT and c[2] in CONFLICT),
                    "allpairs_redund_changed": len(rd),
                    "lsh_added_or_changed": len(add), "lsh_removed_or_changed": len(rem),
                    "lsh_conflict_added": sum(1 for v in add.values() if v in CONFLICT),
                    "lsh_conflict_removed": sum(1 for k, v in rem.items() if v in CONFLICT and lshrel.get(k) not in CONFLICT),
                    "lsh_changed_any": int(bool(add or rem)),
                    "example_changes": "; ".join(f"{c[0][0] if c[0][1]==rid else c[0][1]}:{c[1]}->{c[2]}" for c in ch[:3])})
    tag = "_".join(sorted(ops))
    path = os.path.join(D_ROOT, "logs", f"downstream_{tag}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print("wrote", path, len(out), "sec", round(time.time() - t, 1), dict(stats))


if __name__ == "__main__":
    if sys.argv[1] == "gold":
        run_gold()
    else:
        run_mutants(set(sys.argv[2].split(",")))
