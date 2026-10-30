"""STEP23 FIXED_REGRESSION_TEST 평가(ORIGINAL vs EXPANDED, 같은 코드·같은 subset). 선택·임계값은 selection.json(dev)에서만 온다.

FIXED_REGRESSION_TEST 는 STEP21/22 에서 이미 결과를 본 test → 개발 방향 결정용, 최종 일반화 성능 주장 금지.
평가 뷰
- FULL77            : 77 class 전체 순위(기존과 동일, confuser 존재 환경) — gate·판정 기준
- PILOT20_RESTRICTED: 같은 decision score 에서 TARGET_20 만 남긴 순위(참고)
판정 규칙(실행 전 고정)
- gate(FULL77 core): NO_GO Top-1<0.70 or R@3<0.85 · GO Top-1≥0.90 & R@3≥0.97 & unseen≥0.85 & dev-고정 auto-accept P≥0.95·cov≥0.30 · else CONDITIONAL
- DATA_EXPANSION_EFFECT(BEST_MODEL family, FULL77 core Top-1 Δ = EXPANDED − ORIGINAL): ≥+20 STRONG · +10~20 MODERATE · +3~10 WEAK · <3 NONE
- LIMITATION_CASE: Δ≥+20 DATA_BOTTLENECK_DOMINANT · +3~20 DATA_AND_MODEL_LIMITATION · <+3 LINEAR_REPRESENTATION_LIMITATION
- STEP23_RESULT: GO → LINEAR_REVIVED · Δ≥+10(STRONG/MODERATE) → LINEAR_IMPROVED_BUT_INSUFFICIENT · else LINEAR_STILL_FAILED
"""
import collections
import json

import joblib
import numpy as np

import s23_common as S

NV = {"nausea", "vomiting"}
FW = {"fatigue", "limb_weakness"}
SITE = {"pain", "sore_throat", "palpitations", "heartburn"}


def ranks(model, texts):
    Sc = np.atleast_2d(model.decision_function(texts))
    cls = list(model.classes_)
    full, pil = [], []
    for row in Sc:
        order = sorted(range(len(cls)), key=lambda i: (-row[i], cls[i]))
        full.append([(cls[i], float(row[i])) for i in order])
        pil.append([(cls[i], float(row[i])) for i in order if cls[i] in S.TARGET20])
    return full, pil


def exposure(g, train_rows):
    """문장(공백 제거)에 정답 concept 학습 표현의 stem 이 그대로 있으면 seen(STEP21 정의를 조건별 학습셋에 적용)."""
    u = S.nospace(g["text_ko"])
    stems = [s for e in train_rows.get(g["primary_concept"], []) for s in S.c21.dict_stems(e)]
    return "seen" if any(s and s in u for s in stems) else "novel"


def gate(t1, r3, un, aa):
    if t1 < 0.70 or r3 < 0.85:
        return "NO_GO"
    if t1 >= 0.90 and r3 >= 0.97 and un >= 0.85 and aa:
        return "GO"
    return "CONDITIONAL"


def effect(d):
    return "STRONG" if d >= 0.20 else "MODERATE" if d >= 0.10 else "WEAK" if d >= 0.03 else "NONE"


def main():
    sel = json.load(open(S.OUT / "selection.json", encoding="utf-8"))
    best = sel["BEST_MODEL"]
    gold = S.load_gold()
    ids = [g["utterance_id"] for g in gold]
    G = {g["utterance_id"]: g for g in gold}
    texts = [S.norm(g["text_ko"]) for g in gold]
    core = [g for g in gold if g["split"] == "test" and S.is_core(g)]
    assert len(core) == 109
    train_rows = {}
    for cond in S.CONDITIONS:
        X, y = S.load_condition(cond)
        d = collections.defaultdict(list)
        for x, c in zip(X, y):
            d[c].append(x)
        train_rows[cond] = d

    P = {}
    for cond, cv in sel["conditions"].items():
        for fam, fv in cv["families"].items():
            full, pil = ranks(joblib.load(S.STEP / fv["model_file"]), texts)
            P[(cond, fam)] = {"FULL77": dict(zip(ids, full)), "PILOT20_RESTRICTED": dict(zip(ids, pil))}

    def metrics(cond, fam, view, rows):
        rk = {u: [c for c, _ in t] for u, t in P[(cond, fam)][view].items()}
        s = S.score(rows, rk)
        s["macro_top1"] = S.macro_top1(rows, rk)
        return s

    res = {}
    for (cond, fam), _ in P.items():
        for view in ("FULL77", "PILOT20_RESTRICTED"):
            nov21 = [g for g in core if g["lexical_exposure"] == "novel"]
            novc = [g for g in core if exposure(g, train_rows[cond]) == "novel"]
            res[f"{fam}|{cond}|{view}"] = {
                "core": metrics(cond, fam, view, core), "unseen_step21_def": metrics(cond, fam, view, nov21),
                "seen_step21_def": metrics(cond, fam, view, [g for g in core if g["lexical_exposure"] == "seen"]),
                "unseen_vs_condition_train": metrics(cond, fam, view, novc),
                "core_dev": metrics(cond, fam, view, [g for g in gold if g["split"] == "dev" and S.is_core(g)])}

    # auto-accept (dev 고정 → test 1회), FULL77
    aa, cc_rows = {}, []
    for (cond, fam), p in P.items():
        th = sel["conditions"][cond]["families"][fam]["auto_accept_dev"]
        items = sorted(({"m": p["FULL77"][g["utterance_id"]][0][1] - p["FULL77"][g["utterance_id"]][1][1],
                         "ok": p["FULL77"][g["utterance_id"]][0][0] == g["primary_concept"], "u": g["utterance_id"]} for g in core),
                       key=lambda x: (-x["m"], x["u"]))
        if th:
            acc = [a for a in items if a["m"] >= th["margin_threshold"]]
            aa[(cond, fam)] = {"margin_threshold": th["margin_threshold"], "dev_precision": th["dev_precision"], "dev_coverage": th["dev_coverage"],
                               "n_accepted": len(acc), "coverage": S.rnd(len(acc) / len(items)),
                               "precision": S.rnd(sum(a["ok"] for a in acc) / len(acc)) if acc else None}
        else:
            aa[(cond, fam)] = None
        cc_rows.append({"model": fam, "condition": cond, "rule": "dev_fixed_threshold",
                        **({"margin_threshold": round(aa[(cond, fam)]["margin_threshold"], 6), "n_accepted": aa[(cond, fam)]["n_accepted"],
                            "AUTO_ACCEPT_COVERAGE": aa[(cond, fam)]["coverage"], "AUTO_ACCEPT_PRECISION": aa[(cond, fam)]["precision"]}
                           if aa[(cond, fam)] else {"margin_threshold": "NONE(dev 에 P≥0.95 구간 없음)"})})
        for q in (10, 20, 30, 50, 100):
            k = max(1, round(len(items) * q / 100))
            cc_rows.append({"model": fam, "condition": cond, "rule": f"top_{q}pct_margin(descriptive)", "margin_threshold": round(items[k - 1]["m"], 6),
                            "n_accepted": k, "AUTO_ACCEPT_COVERAGE": S.rnd(k / len(items)),
                            "AUTO_ACCEPT_PRECISION": S.rnd(sum(a["ok"] for a in items[:k]) / k)})
    S.write_csv(S.OUT / "confidence_coverage.csv", cc_rows)

    # 비교표
    comp = []
    for fam in S.FAMILIES:
        for view in ("FULL77", "PILOT20_RESTRICTED"):
            o, e = res[f"{fam}|ORIGINAL|{view}"], res[f"{fam}|EXPANDED|{view}"]
            for name, a, b in [("Top-1", o["core"]["top1"], e["core"]["top1"]), ("Recall@3", o["core"]["recall_at_3"], e["core"]["recall_at_3"]),
                               ("Recall@5", o["core"]["recall_at_5"], e["core"]["recall_at_5"]),
                               ("Unseen Top-1 (STEP21 def, n=97)", o["unseen_step21_def"]["top1"], e["unseen_step21_def"]["top1"]),
                               ("Unseen Top-1 (vs condition train)", o["unseen_vs_condition_train"]["top1"], e["unseen_vs_condition_train"]["top1"]),
                               ("Macro accuracy (20 class)", o["core"]["macro_top1"], e["core"]["macro_top1"]),
                               ("dev core Top-1", o["core_dev"]["top1"], e["core_dev"]["top1"])]:
                comp.append({"model": fam, "view": view, "metric": name, "original": a, "expanded": b, "delta": S.rnd(b - a)})
            if view == "FULL77":
                ao, ae = aa[("ORIGINAL", fam)], aa[("EXPANDED", fam)]
                for name, k in (("Auto-accept precision (dev-fixed)", "precision"), ("Auto-accept coverage (dev-fixed)", "coverage")):
                    a, b = (ao or {}).get(k), (ae or {}).get(k)
                    comp.append({"model": fam, "view": view, "metric": name, "original": a, "expanded": b,
                                 "delta": S.rnd(b - a) if a is not None and b is not None else ""})
    S.write_csv(S.OUT / "comparison_original_vs_expanded.csv", comp)

    # class 별
    cls_rows = []
    dist = {(r["condition"], r["canonical_id"]): int(r["n"]) for r in S.read_csv(S.DATA / "class_distribution.csv")}
    for fam in S.FAMILIES:
        for c in S.TARGET20:
            rows = [g for g in core if g["primary_concept"] == c]
            acc = {cond: S.rnd(sum(P[(cond, fam)]["FULL77"][g["utterance_id"]][0][0] == c for g in rows) / len(rows)) if rows else None
                   for cond in S.CONDITIONS}
            cls_rows.append({"model": fam, "concept": c, "test_n": len(rows), "old_train_n": dist[("ORIGINAL", c)], "new_train_n": dist[("EXPANDED", c)],
                             "old_top1": acc["ORIGINAL"], "new_top1": acc["EXPANDED"],
                             "delta": S.rnd(acc["EXPANDED"] - acc["ORIGINAL"]) if rows else None})
    S.write_csv(S.OUT / "classwise_improvement.csv", cls_rows)

    # 예측 파일
    prow, krow = [], []
    for (cond, fam), p in P.items():
        for g in gold:
            if g["split"] != "test":
                continue
            u, t = g["utterance_id"], p["FULL77"][g["utterance_id"]]
            prow.append({"model": fam, "condition": cond, "is_best": str(fam == best), "utterance_id": u, "is_core": str(S.is_core(g)),
                         "tier": g["tier"], "lexical_exposure_step21": g["lexical_exposure"], "gold_primary": g["primary_concept"],
                         "gold_patient": ";".join(sorted(S.c21.patient_concepts(g))), "should_link": g["should_link"],
                         "top1": t[0][0], "top1_score": round(t[0][1], 6), "margin": round(t[0][1] - t[1][1], 6),
                         "ranked_top5": ";".join(c for c, _ in t[:5]), "pilot20_top1": p["PILOT20_RESTRICTED"][u][0][0],
                         "top1_correct": str(t[0][0] in S.c21.patient_concepts(g))})
            if fam == best and cond == "EXPANDED":
                for r, (c, s) in enumerate(t[:5], 1):
                    krow.append({"model": fam, "condition": cond, "utterance_id": u, "is_core": str(S.is_core(g)), "rank": r, "concept": c,
                                 "decision_score": round(s, 6)})
    S.write_csv(S.OUT / "predictions_regression.csv", prow)
    S.write_csv(S.OUT / "topk_predictions.csv", krow)

    # 오류 분류(BEST_MODEL EXPANDED, core). test 문장으로 학습셋을 고치지 않는다.
    err = []
    tn = {c: dist[("EXPANDED", c)] for c in S.TARGET20}
    for g in core:
        t = P[("EXPANDED", best)]["FULL77"][g["utterance_id"]]
        gc, pc = g["primary_concept"], t[0][0]
        if pc == gc:
            continue
        pair = {gc, pc}
        top3, top5 = [c for c, _ in t[:3]], [c for c, _ in t[:5]]
        cat = ("nausea/vomiting confusion" if pair == NV else "fatigue/weakness confusion" if pair <= FW else
               "body-site confusion" if pair <= SITE else "confuser dominance" if pc.startswith("EV:") else
               "insufficient training" if tn[gc] < 30 else "semantic similarity failure" if gc in top3 else
               "unseen synonym" if exposure(g, train_rows["EXPANDED"]) == "novel" else "linear representation limitation")
        err.append({"model": best, "condition": "EXPANDED", "utterance_id": g["utterance_id"], "text_ko": g["text_ko"], "gold": gc, "pred": pc,
                    "gold_rank": (top5.index(gc) + 1) if gc in top5 else ">5", "margin": round(t[0][1] - t[1][1], 6),
                    "exposure_vs_expanded_train": exposure(g, train_rows["EXPANDED"]), "category": cat})
    S.write_csv(S.OUT / "error_analysis.csv", err, ["model", "condition", "utterance_id", "text_ko", "gold", "pred", "gold_rank", "margin",
                                                     "exposure_vs_expanded_train", "category"])

    # 판정
    b_e, b_o = res[f"{best}|EXPANDED|FULL77"], res[f"{best}|ORIGINAL|FULL77"]
    ae = aa[("EXPANDED", best)]
    aa_ok = bool(ae and ae["precision"] is not None and ae["precision"] >= 0.95 and ae["coverage"] >= 0.30)
    verdict = gate(b_e["core"]["top1"], b_e["core"]["recall_at_3"], b_e["unseen_step21_def"]["top1"], aa_ok)
    d = b_e["core"]["top1"] - b_o["core"]["top1"]
    eff = effect(d)
    case = "DATA_BOTTLENECK_DOMINANT" if d >= 0.20 else "DATA_AND_MODEL_LIMITATION" if d >= 0.03 else "LINEAR_REPRESENTATION_LIMITATION"
    result = "LINEAR_REVIVED" if verdict == "GO" else "LINEAR_IMPROVED_BUT_INSUFFICIENT" if d >= 0.10 else "LINEAR_STILL_FAILED"
    s22 = {r["system"]: r for r in S.read_csv(S.S22 / "outputs/same_subset_comparison.csv")}
    out = {"STEP23_RESULT": result, "DATA_EXPANSION_EFFECT": eff, "LIMITATION_CASE": case, "GATE_FULL77_CORE": verdict,
           "BEST_MODEL": best, "GPU_USED": "NO", "NEW_BLIND_HOLDOUT_REQUIRED": "YES", "test_name": "FIXED_REGRESSION_TEST",
           "delta_top1_best_family_full77_core": S.rnd(d), "auto_accept_ok": aa_ok,
           "auto_accept": {f"{f}|{c}": aa[(c, f)] for (c, f) in aa},
           "results": res, "error_category_counts": dict(collections.Counter(e["category"] for e in err)),
           "n_errors_best_expanded_core": len(err),
           "reference_step21_baselines_same_core_subset": {k: {"top1": s22[k]["top1"], "recall_at_3": s22[k]["recall_at_3"]}
                                                          for k in ("DICTIONARY", "FUZZY", "DICTIONARY+FUZZY", "PRODUCT_MAPPER")},
           "rules": __doc__}
    S.dump_json(S.OUT / "metrics.json", out)
    for r in comp:
        if r["view"] == "FULL77":
            print(r)
    print(result, eff, case, verdict, best, S.rnd(d), aa[("EXPANDED", best)], out["error_category_counts"])


if __name__ == "__main__":
    main()
