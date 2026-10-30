"""STEP22 confusion 분석(BEST_MODEL, 주 view). 예측 파일만 읽는다(재학습·재선택 없음).

- confusion_matrix.csv : core test, gold(행) × top1(열) count
- confusion_pairs.csv  : 무방향 pair 별 count(방향별 분리), 대표 문장, '왜' 근거 = 예측 class 쪽으로 점수를 민 상위 feature
                         (x_i × (w_pred,i − w_gold,i), 학습 표현과 겹친 n-gram). scope = core_test 우선, 10쌍 미만이면
                         ref_tier_AB_test(STEP21 분모) 오류를 별도 scope 로 덧붙인다.
"""
import collections
import json

import joblib
import numpy as np

import lin_common as L


def explain(model, text, pred, gold, k=5):
    feats = model.named_steps["feats"]
    svm = model.named_steps["svm"]
    x = feats.transform([text]).toarray()[0]
    names = feats.get_feature_names_out()
    cls = list(svm.classes_)
    if gold not in cls:
        return ""
    d = x * (svm.coef_[cls.index(pred)] - svm.coef_[cls.index(gold)])
    idx = [i for i in np.argsort(-d)[:k] if d[i] > 0]
    return " | ".join(f"'{names[i].split('__')[-1]}'" for i in idx)


def main():
    sel = json.load(open(L.OUT / "selection.json", encoding="utf-8"))
    best = sel["BEST_MODEL"]
    model = joblib.load(L.STEP / sel["views"][L.PRIMARY_VIEW]["families"][best]["model_file"])
    P = [r for r in L.read_csv(L.OUT / "predictions_test.csv") if r["is_best"] == "True"]
    core = [r for r in P if r["is_core"] == "True"]
    ab = [r for r in P if r["tier"] in ("A", "B") and r["should_link"] == "True"]

    labels = sorted({r["gold_primary"] for r in core})
    cols = labels + sorted({r["top1"] for r in core} - set(labels))
    cm = collections.Counter((r["gold_primary"], r["top1"]) for r in core)
    L.write_csv(L.OUT / "confusion_matrix.csv",
                [{"gold\\pred": g, **{c: cm.get((g, c), 0) for c in cols}, "n": sum(cm.get((g, c), 0) for c in cols)} for g in labels],
                ["gold\\pred"] + cols + ["n"])

    def pairs(rows, scope):
        err = [r for r in rows if r["top1_correct"] == "False"]
        grp = collections.defaultdict(list)
        for r in err:
            grp[frozenset((r["gold_primary"], r["top1"]))].append(r)
        out = []
        for p, rs in sorted(grp.items(), key=lambda kv: (-len(kv[1]), sorted(kv[0]))):
            a, b = sorted(p) if len(p) == 2 else (next(iter(p)), next(iter(p)))
            ex = sorted(rs, key=lambda r: r["utterance_id"])[0]
            out.append({"scope": scope, "concept_a": a, "concept_b": b, "count": len(rs),
                        "a_to_b": sum(r["gold_primary"] == a and r["top1"] == b for r in rs),
                        "b_to_a": sum(r["gold_primary"] == b and r["top1"] == a for r in rs),
                        "example_utterance_id": ex["utterance_id"], "example_text": ex["text_ko"],
                        "example_gold": ex["gold_primary"], "example_pred": ex["top1"],
                        "why_top_features_toward_pred": explain(model, L.norm(ex["text_ko"]), ex["top1"], ex["gold_primary"]),
                        "all_utterance_ids": ";".join(sorted(r["utterance_id"] for r in rs))})
        return out

    rows = pairs(core, "core_test")
    if len(rows) < 10:
        rows += pairs(ab, "ref_tier_AB_test")
    L.write_csv(L.OUT / "confusion_pairs.csv", rows)
    pred_cnt = collections.Counter(r["top1"] for r in core if r["top1_correct"] == "False")
    L.dump_json(L.OUT / "confusion_summary.json", {
        "model": best, "view": L.PRIMARY_VIEW, "n_core_test": len(core),
        "n_core_errors": sum(r["top1_correct"] == "False" for r in core),
        "n_core_errors_to_non_pilot_class": sum(r["top1_correct"] == "False" and r["top1"] not in L.PILOT for r in core),
        "most_frequent_wrong_predictions": pred_cnt.most_common(10)})
    for r in rows[:12]:
        print(r["scope"], r["concept_a"], r["concept_b"], r["count"], r["example_text"], r["why_top_features_toward_pred"])


if __name__ == "__main__":
    main()
