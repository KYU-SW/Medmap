"""STEP23 학습 데이터 조립 + 학습 전 통계(§18).

ORIGINAL = STEP22 CURATED 276(77 class) · EXPANDED = ORIGINAL + VALID TARGET_20 생성 표현. label space 동일(77).
출력: data/expanded_train_expressions.csv · target20_expressions.csv · confuser57_expressions.csv · class_distribution.csv
      outputs/data_stats.json
"""
import collections
import statistics

import s23_common as S


def main():
    old = [r for r in S.read_csv(S.S22 / "data/train_expressions.csv") if r["curated_include"] == "True"]
    cand = S.read_csv(S.DATA / "target20_candidates_audited.csv")
    valid = [g for g in cand if g["status"] == "VALID"]
    rows = []
    for r in old:
        rows.append({"expression": r["expression"], "canonical_id": r["canonical_id"], "canonical_name": r["canonical_name"],
                     "group": "TARGET_20" if r["canonical_id"] in S.TARGET20 else "CONFUSER_57",
                     "source_type": "existing_medmap" if r["source_type"] == "existing_medmap" else "existing_dictionary",
                     "source": r["source"], "origin": "STEP22_CURATED", "style": "", "semantic_valid": "VALID(STEP22 audit)",
                     "normalized_expression": r["normalized_expression"]})
    for g in valid:
        rows.append({"expression": g["expression"], "canonical_id": g["concept_id"], "canonical_name": S.L22.PILOT_NAMES[g["concept_id"]],
                     "group": "TARGET_20", "source_type": "synthetic_paraphrase",
                     "source": f"isolated claude -p author ({g['gen_id']}), independent claude -p audit", "origin": "STEP23_GENERATED",
                     "style": g["style"], "semantic_valid": "VALID", "normalized_expression": S.norm(g["expression"])})
    ns = collections.Counter(S.nospace(r["expression"]) for r in rows)
    assert max(ns.values()) == 1, [k for k, v in ns.items() if v > 1][:5]
    gold = S.load_gold()
    test_ns = {S.nospace(g["text_ko"]) for g in gold if g["split"] == "test"}
    assert not any(S.nospace(r["expression"]) in test_ns for r in rows), "TRAIN ↔ REGRESSION_TEST exact overlap"
    fields = list(rows[0].keys())
    S.write_csv(S.DATA / "expanded_train_expressions.csv", rows, fields)
    S.write_csv(S.DATA / "target20_expressions.csv", [r for r in rows if r["group"] == "TARGET_20"], fields)
    S.write_csv(S.DATA / "confuser57_expressions.csv", [r for r in rows if r["group"] == "CONFUSER_57"], fields)

    dist = []
    for cond in S.CONDITIONS:
        cnt = collections.Counter(r["canonical_id"] for r in rows if cond == "EXPANDED" or r["origin"] == "STEP22_CURATED")
        for c in sorted(cnt):
            dist.append({"condition": cond, "canonical_id": c, "group": "TARGET_20" if c in S.TARGET20 else "CONFUSER_57", "n": cnt[c]})

    def summ(vals):
        return {"n_classes": len(vals), "total": sum(vals), "min": min(vals), "median": statistics.median(vals), "max": max(vals),
                "imbalance_ratio_max_over_min": round(max(vals) / min(vals), 2)}
    stats = {"conditions": {}}
    for cond in S.CONDITIONS:
        d = [x for x in dist if x["condition"] == cond]
        stats["conditions"][cond] = {"all77": summ([x["n"] for x in d]),
                                     "target20": summ([x["n"] for x in d if x["group"] == "TARGET_20"]),
                                     "confuser57": summ([x["n"] for x in d if x["group"] == "CONFUSER_57"])}
    st = collections.Counter(g["status"] for g in cand)
    ov = S.read_csv(S.DATA / "overlap_audit.csv")
    vid = {g["gen_id"] for g in valid}
    stats.update({
        "n_generated": len(cand), "status_counts": dict(st), "audit_verdict_counts": dict(collections.Counter(g["audit_verdict"] for g in cand)),
        "n_unique_training_expressions": {"ORIGINAL": sum(r["origin"] == "STEP22_CURATED" for r in rows), "EXPANDED": len(rows)},
        "n_target20_expressions_expanded": sum(r["group"] == "TARGET_20" for r in rows),
        "n_confuser57_expressions": sum(r["group"] == "CONFUSER_57" for r in rows),
        "n_new_valid": len(valid),
        "test_exact_overlap_generated_before_removal": sum(o["test_exact"] == "True" for o in ov),
        "test_near_duplicate_generated_before_removal(>=0.80)": sum(float(o["test_max_ratio"]) >= 0.80 for o in ov),
        "test_exact_overlap_final_train": 0,
        "final_train_max_test_ratio": max([float(o["test_max_ratio"]) for o in ov if o["gen_id"] in vid] or [0]),
        "final_train_test_ratio_ge_0.70": sum(float(o["test_max_ratio"]) >= 0.70 for o in ov if o["gen_id"] in vid),
        "style_counts_valid": dict(collections.Counter(g["style"] for g in valid)),
        "valid_per_target_class": dict(sorted(collections.Counter(g["concept_id"] for g in valid).items())),
    })
    S.write_csv(S.DATA / "class_distribution.csv", dist)
    S.dump_json(S.OUT / "data_stats.json", stats)
    for k in ("n_unique_training_expressions", "n_target20_expressions_expanded", "n_confuser57_expressions", "status_counts",
              "test_exact_overlap_generated_before_removal", "test_near_duplicate_generated_before_removal(>=0.80)",
              "final_train_max_test_ratio", "valid_per_target_class"):
        print(k, stats[k])
    print("EXPANDED target20", stats["conditions"]["EXPANDED"]["target20"], "all77", stats["conditions"]["EXPANDED"]["all77"])


if __name__ == "__main__":
    main()
