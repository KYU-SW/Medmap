"""STEP22 sealed test 1회 평가 + STEP21 baseline 동일 subset 재채점 + gate/판정.

- 모델·hyperparameter·BEST_MODEL·auto-accept margin 임계값은 모두 selection.json(dev 로 고정)에서 읽는다. 여기서 바꾸지 않는다.
- STEP21 baseline 은 STEP21 outputs/*_predictions.csv 의 ranked_top5 를 그대로 재채점(재학습·재튜닝 없음).
  재채점기 검증: STEP21 metrics.json 의 test tier_AB Top-1·R@3·novel Top-1 과 일치해야 한다(assert).
- SVM 점수는 확률이 아니다: decision margin = top1 score − top2 score.
출력: outputs/predictions_test.csv · topk_predictions.csv · confidence_coverage.csv · metrics.json
"""
import json

import joblib

import lin_common as L

BASE_FILES = {"DICTIONARY": "exact_predictions.csv", "FUZZY": "fuzzy_predictions.csv",
              "DICTIONARY+FUZZY": "combined_predictions.csv", "PRODUCT_MAPPER": "mapper_predictions.csv"}
BASE_S21 = {"DICTIONARY": "BASELINE_EXACT", "FUZZY": "BASELINE_FUZZY",
            "DICTIONARY+FUZZY": "BASELINE_COMBINED_EXACT_THEN_FUZZY", "PRODUCT_MAPPER": "BASELINE_MEDMAP_INTAKE_MAPPER_v1_2"}
KEY_CASES = ["호흡이 딸려요", "토했어요", "물만 마셔도 다 토해요", "숨이 벅차요", "가슴이 꽉 조이는 것 같아요"]
BINS = [("1-5", 1, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21+", 21, 10 ** 9)]
# 판정 규칙(실행 전 고정)
LARGE_GAIN_PP = 0.10   # B 판정: core test Top-1 과 새 표현 Top-1 이 모두 최고 기존 baseline 대비 ≥ +10%p


def subsets(gold):
    t = [g for g in gold if g["split"] == "test"]
    core = [g for g in t if L.is_core(g)]
    ab = [g for g in t if g["tier"] in "AB" and g["should_link"] == "True"]
    return {
        "core_test": core,
        "core_test_unseen_expression": [g for g in core if g["lexical_exposure"] == "novel"],
        "core_test_seen_or_overlapping": [g for g in core if g["lexical_exposure"] == "seen"],
        "ref_tier_AB_test(STEP21 denominator)": ab,
        "ref_tier_AB_novel_test(STEP21 denominator)": [g for g in ab if g["lexical_exposure"] == "novel"],
        "ref_all_test_should_link(concept only)": [g for g in t if g["should_link"] == "True"],
        "core_dev": [g for g in gold if g["split"] == "dev" and L.is_core(g)],
    }


def load_baselines():
    out = {}
    for b, f in BASE_FILES.items():
        out[b] = {r["utterance_id"]: [x for x in r["ranked_top5"].split(";") if x] for r in L.read_csv(L.S21 / "outputs" / f)}
    return out


def gate(m):
    t1, r3, un, aa = m["top1"], m["recall_at_3"], m["unseen_top1"], m["auto_accept_ok"]
    if t1 < 0.70 or r3 < 0.85:
        return "NO_GO"
    if t1 >= 0.90 and r3 >= 0.97 and un >= 0.85 and aa:
        return "GO"
    return "CONDITIONAL"


def main():
    sel = json.load(open(L.OUT / "selection.json", encoding="utf-8"))
    best = sel["BEST_MODEL"]
    gold = L.load_gold()
    S = subsets(gold)
    texts = {g["utterance_id"]: L.norm(g["text_ko"]) for g in gold}
    ids = [g["utterance_id"] for g in gold]

    # 1) 모델 예측(dev+test 전체 행, 한 번)
    preds = {}
    for v in L.VIEWS:
        for f in L.FAMILIES:
            m = joblib.load(L.STEP / sel["views"][v]["families"][f]["model_file"])
            preds[(v, f)] = dict(zip(ids, L.topk(m, [texts[u] for u in ids])))
    ranked = {f"{f}[{v}]": {u: [c for c, _ in t] for u, t in p.items()} for (v, f), p in preds.items()}

    # 2) baseline 재채점 + 재채점기 검증
    base = load_baselines()
    s21 = json.load(open(L.S21 / "outputs/metrics.json", encoding="utf-8"))["baselines"]
    for b, rk in base.items():
        ref = s21[BASE_S21[b]]["test"]
        mine = L.score(S["ref_tier_AB_test(STEP21 denominator)"], rk)
        nov = L.score(S["ref_tier_AB_novel_test(STEP21 denominator)"], rk)
        assert (mine["top1"], mine["recall_at_3"], nov["top1"]) == (
            ref["tier_AB"]["top1_accuracy"], ref["tier_AB"]["recall_at_3"], ref["tier_AB_novel"]["top1_accuracy"]), (b, mine, ref)
    systems = {**base, **ranked}

    res = {name: {sn: L.score(rows, rk) for sn, rows in S.items()} for name, rk in systems.items()}

    # 3) auto-accept(BEST_MODEL, 주 view)
    bp = preds[(L.PRIMARY_VIEW, best)]
    core = S["core_test"]
    items = sorted(({"u": g["utterance_id"], "margin": bp[g["utterance_id"]][0][1] - bp[g["utterance_id"]][1][1],
                     "correct": bp[g["utterance_id"]][0][0] == g["primary_concept"]} for g in core),
                   key=lambda x: (-x["margin"], x["u"]))
    cc_rows = []
    for q in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        k = max(1, round(len(items) * q / 100))
        acc = items[:k]
        cc_rows.append({"rule": f"top_{q}pct_margin(descriptive, test-ranked)", "margin_threshold": round(acc[-1]["margin"], 6),
                        "n_accepted": k, "AUTO_ACCEPT_COVERAGE": L.rnd(k / len(items)),
                        "AUTO_ACCEPT_PRECISION": L.rnd(sum(a["correct"] for a in acc) / k)})
    post = None
    for k in range(len(items), 0, -1):
        if sum(a["correct"] for a in items[:k]) / k >= 0.95:
            post = {"n_accepted": k, "coverage": L.rnd(k / len(items)),
                    "precision": L.rnd(sum(a["correct"] for a in items[:k]) / k)}
            break
    dev_th = sel["views"][L.PRIMARY_VIEW]["families"][best]["auto_accept_dev"]
    if dev_th:
        acc = [a for a in items if a["margin"] >= dev_th["margin_threshold"]]
        fixed = {"margin_threshold": dev_th["margin_threshold"], "n_accepted": len(acc),
                 "coverage": L.rnd(len(acc) / len(items)),
                 "precision": L.rnd(sum(a["correct"] for a in acc) / len(acc)) if acc else None}
        cc_rows.insert(0, {"rule": "dev_fixed_threshold(gate)", "margin_threshold": round(dev_th["margin_threshold"], 6),
                           "n_accepted": len(acc), "AUTO_ACCEPT_COVERAGE": fixed["coverage"],
                           "AUTO_ACCEPT_PRECISION": fixed["precision"]})
    else:
        fixed = None
    L.write_csv(L.OUT / "confidence_coverage.csv", cc_rows)
    aa_ok = bool(fixed and fixed["precision"] is not None and fixed["precision"] >= 0.95 and fixed["coverage"] >= 0.30)

    # 4) train count bin · class 별 · train 재대입 정확도
    inv = json.load(open(L.OUT / "class_inventory.json", encoding="utf-8"))
    tc = inv["pilot_class_train_counts"][L.PRIMARY_VIEW]
    bins = {}
    for name, lo, hi in BINS:
        rows = [g for g in core if lo <= tc[g["primary_concept"]] <= hi]
        bins[name] = {"classes": sorted({g["primary_concept"] for g in rows}), **L.score(rows, ranked[f"{best}[{L.PRIMARY_VIEW}]"])}
    per_class = {}
    for c in sorted({g["primary_concept"] for g in core}):
        rows = [g for g in core if g["primary_concept"] == c]
        per_class[c] = {"train_count": tc[c], **L.score(rows, ranked[f"{best}[{L.PRIMARY_VIEW}]"])}
    X, y = L.load_train(L.PRIMARY_VIEW)
    mb = joblib.load(L.STEP / sel["views"][L.PRIMARY_VIEW]["families"][best]["model_file"])
    train_fit = L.rnd(sum(p == t for p, t in zip(mb.predict(X), y)) / len(y))

    # 5) 주요 사례 · 복수 증상 정성
    key = []
    for kc in KEY_CASES:
        hits = [g for g in gold if L.norm(g["text_ko"]).replace(" ", "") == L.norm(kc).replace(" ", "")]
        if not hits:
            key.append({"text": kc, "in_dataset": False})
        for g in hits:
            t = bp[g["utterance_id"]]
            key.append({"text": kc, "in_dataset": True, "utterance_id": g["utterance_id"], "split": g["split"],
                        "is_core": L.is_core(g), "gold_patient": sorted(L.c21.patient_concepts(g)),
                        "top3": [[c, round(s, 4)] for c, s in t[:3]], "margin": round(t[0][1] - t[1][1], 4),
                        "baseline_top1": {b: (base[b][g["utterance_id"]] or [""])[0] for b in base}})
    multi = []
    for g in gold:
        if g["split"] == "test" and g["is_multi"] == "True":
            t = bp[g["utterance_id"]]
            multi.append({"utterance_id": g["utterance_id"], "gold_patient": sorted(L.c21.patient_concepts(g)),
                          "top3": [c for c, _ in t[:3]], "n_gold_in_top3": len(L.c21.patient_concepts(g) & {c for c, _ in t[:3]})})

    # 6) 파일: predictions_test.csv · topk_predictions.csv
    prow, krow = [], []
    for (v, f), p in preds.items():
        for g in gold:
            u = g["utterance_id"]
            t = p[u]
            if g["split"] == "test":
                prow.append({"model": f, "view": v, "is_best": str(f == best and v == L.PRIMARY_VIEW), "utterance_id": u,
                             "is_core": str(L.is_core(g)), "tier": g["tier"], "utt_type": g["utt_type"],
                             "lexical_exposure": g["lexical_exposure"], "text_ko": g["text_ko"],
                             "gold_primary": g["primary_concept"], "gold_patient": ";".join(sorted(L.c21.patient_concepts(g))),
                             "should_link": g["should_link"], "top1": t[0][0], "top1_score": round(t[0][1], 6),
                             "top2": t[1][0], "margin": round(t[0][1] - t[1][1], 6), "ranked_top5": ";".join(c for c, _ in t),
                             "top1_correct": str(t[0][0] in L.c21.patient_concepts(g))})
            if f == best and v == L.PRIMARY_VIEW:
                for r, (c, s) in enumerate(t, 1):
                    krow.append({"model": f, "view": v, "split": g["split"], "utterance_id": u, "is_core": str(L.is_core(g)),
                                 "rank": r, "concept": c, "decision_score": round(s, 6)})
    L.write_csv(L.OUT / "predictions_test.csv", prow)
    L.write_csv(L.OUT / "topk_predictions.csv", krow)

    # 7) gate · 판정
    bk = f"{best}[{L.PRIMARY_VIEW}]"
    gm = {"top1": res[bk]["core_test"]["top1"], "recall_at_3": res[bk]["core_test"]["recall_at_3"],
          "recall_at_5": res[bk]["core_test"]["recall_at_5"], "unseen_top1": res[bk]["core_test_unseen_expression"]["top1"],
          "auto_accept_ok": aa_ok}
    verdict = gate(gm)
    old_best = max(base, key=lambda b: (res[b]["core_test"]["top1"], res[b]["core_test"]["recall_at_3"]))
    d_top1 = gm["top1"] - res[old_best]["core_test"]["top1"]
    old_best_unseen = max(base, key=lambda b: res[b]["core_test_unseen_expression"]["top1"])
    d_unseen = gm["unseen_top1"] - res[old_best_unseen]["core_test_unseen_expression"]["top1"]
    if verdict == "GO":
        decision = "A. LINEAR_MODEL_SUFFICIENT"
    elif d_top1 >= LARGE_GAIN_PP and d_unseen >= LARGE_GAIN_PP:
        decision = "B. LINEAR_MODEL_USEFUL_BUT_INSUFFICIENT"
    else:
        decision = "C. LINEAR_MODEL_FAILED"
    same = [{"system": n, **{k: res[n]["core_test"][k] for k in ("n", "top1", "recall_at_3", "recall_at_5")},
             "unseen_n": res[n]["core_test_unseen_expression"]["n"], "unseen_top1": res[n]["core_test_unseen_expression"]["top1"],
             "seen_n": res[n]["core_test_seen_or_overlapping"]["n"], "seen_top1": res[n]["core_test_seen_or_overlapping"]["top1"],
             "core_dev_top1": res[n]["core_dev"]["top1"],
             "ref_tier_AB_top1": res[n]["ref_tier_AB_test(STEP21 denominator)"]["top1"]}
            for n in systems]
    L.write_csv(L.OUT / "same_subset_comparison.csv", same)
    out = {
        "LINEAR_NORMALIZER": verdict, "DECISION": decision, "BEST_MODEL": best, "PRIMARY_VIEW": L.PRIMARY_VIEW,
        "GPU_USED": "NO", "gate_inputs_core_test": gm,
        "gate_rule": "NO_GO if Top-1<0.70 or R@3<0.85; GO if Top-1>=0.90 & R@3>=0.97 & unseen>=0.85 & dev-fixed auto-accept P>=0.95 with coverage>=0.30; else CONDITIONAL",
        "decision_rule": f"A if GO; B if core Top-1 and unseen Top-1 both >= +{LARGE_GAIN_PP:.2f} vs best old baseline (same subset); else C",
        "old_best_same_subset": {"system": old_best, "top1": res[old_best]["core_test"]["top1"], "delta_top1": L.rnd(d_top1),
                                 "unseen_system": old_best_unseen,
                                 "unseen_top1": res[old_best_unseen]["core_test_unseen_expression"]["top1"],
                                 "delta_unseen_top1": L.rnd(d_unseen)},
        "auto_accept": {"dev_fixed": fixed, "post_hoc_test_max_coverage_at_P95(descriptive_only)": post},
        "counts": {"classes_train": inv["n_classes_curated"], "pilot_classes": inv["n_pilot_classes"],
                   "train_expressions_curated": inv["n_train_curated"], "train_expressions_raw": inv["n_train_raw"],
                   "core_dev": len(S["core_dev"]), "core_test": len(core), "UNSEEN_CLASS": inv["UNSEEN_CLASS"]},
        "train_resubstitution_top1": train_fit,
        "train_count_bins_core_test": bins, "per_class_core_test": per_class,
        "key_cases": key, "multi_symptom_qualitative_test": multi,
        "results": res, "selection": sel,
    }
    L.dump_json(L.OUT / "metrics.json", out)
    for r in same:
        print(r)
    print(verdict, decision, gm, out["old_best_same_subset"], fixed, post)


if __name__ == "__main__":
    main()
