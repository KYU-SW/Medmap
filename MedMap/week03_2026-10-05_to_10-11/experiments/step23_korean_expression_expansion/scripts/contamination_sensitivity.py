"""STEP23 오염 민감도(1회, 판정·선택에 미사용 — 해석용).

배경: STEP21 test 와 STEP23 생성 표현이 모두 Claude 계열 작성 → 생성 중 test 완전일치 17·≥0.80 근접 20건이 실제로 나왔다.
≥0.80 은 제거했지만 그보다 약한 표면 유사성이 성능을 끌어올렸는지 확인한다.
1) 유사도 구간별 정확도: core test 문장마다 '같은 concept 생성 학습 표현과의 최대 difflib ratio'로 구간을 나눠 ORIGINAL/EXPANDED Top-1
2) STRICT 재학습: 생성 표현 중 test(177)·dev(97) 어느 문장과든 ratio ≥ T(0.70, 0.60, 0.50)인 것을 추가 제거 → selection.json 의
   EXPANDED 하이퍼파라미터 그대로 재학습 → core test Top-1/R@3. (제거만 하고 대체·재선택 없음, T 는 실행 전 고정)
출력: outputs/contamination_sensitivity.json · outputs/contamination_similarity_bins.csv
"""
import difflib
import json

import joblib

import s23_common as S

TS = [0.70, 0.60, 0.50]
BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 1.01)]


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def main():
    sel = json.load(open(S.OUT / "selection.json", encoding="utf-8"))
    rows = S.read_csv(S.DATA / "expanded_train_expressions.csv")
    gen = [r for r in rows if r["origin"] == "STEP23_GENERATED"]
    gold = S.load_gold()
    core = [g for g in gold if g["split"] == "test" and S.is_core(g)]
    gold_ns = [S.nospace(g["text_ko"]) for g in gold]
    gen_ns = [S.nospace(r["expression"]) for r in gen]
    gmax = [max(ratio(x, t) for t in gold_ns) for x in gen_ns]          # 생성 표현 ↔ dev+test 최대 유사도

    preds = {}
    for cond in S.CONDITIONS:
        for fam in S.FAMILIES:
            m = joblib.load(S.STEP / sel["conditions"][cond]["families"][fam]["model_file"])
            preds[(cond, fam)] = dict(zip([g["utterance_id"] for g in core], m.predict([S.norm(g["text_ko"]) for g in core])))
    bins = []
    sim = {g["utterance_id"]: max([ratio(S.nospace(g["text_ko"]), x) for x, r in zip(gen_ns, gen) if r["canonical_id"] == g["primary_concept"]] or [0])
           for g in core}
    for lo, hi in BINS:
        rs = [g for g in core if lo <= sim[g["utterance_id"]] < hi]
        row = {"max_ratio_to_same_concept_generated": f"[{lo:.2f},{min(hi, 1):.2f})", "n": len(rs)}
        for (cond, fam), p in preds.items():
            row[f"{fam}|{cond}"] = S.rnd(sum(p[g["utterance_id"]] == g["primary_concept"] for g in rs) / len(rs)) if rs else None
        bins.append(row)
    S.write_csv(S.OUT / "contamination_similarity_bins.csv", bins)

    strict = {}
    X0 = [r["normalized_expression"] for r in rows if r["origin"] == "STEP22_CURATED"]
    y0 = [r["canonical_id"] for r in rows if r["origin"] == "STEP22_CURATED"]
    for T in TS:
        keep = [(r["normalized_expression"], r["canonical_id"]) for r, mx in zip(gen, gmax) if mx < T]
        X, y = X0 + [k for k, _ in keep], y0 + [c for _, c in keep]
        per = {}
        for fam in S.FAMILIES:
            m = S.build(fam, sel["conditions"]["EXPANDED"]["families"][fam]["params"]).fit(X, y)
            tk = S.topk(m, [S.norm(g["text_ko"]) for g in core])
            rk = {g["utterance_id"]: [c for c, _ in t] for g, t in zip(core, tk)}
            s = S.score(core, rk)
            per[fam] = {"top1": s["top1"], "recall_at_3": s["recall_at_3"], "recall_at_5": s["recall_at_5"], "macro_top1": S.macro_top1(core, rk),
                        "unseen_step21_def_top1": S.score([g for g in core if g["lexical_exposure"] == "novel"], rk)["top1"]}
        cnt = {}
        for _, c in keep:
            cnt[c] = cnt.get(c, 0) + 1
        strict[f"T<{T:.2f}"] = {"n_generated_kept": len(keep), "n_generated_removed": len(gen) - len(keep),
                                "target20_generated_min_median_max": [min(cnt.values()), sorted(cnt.values())[len(cnt) // 2], max(cnt.values())],
                                "models": per}
    out = {"note": "해석용 1회 분석. BEST_MODEL·판정·임계값 선택에 쓰지 않음.", "similarity_bins": bins, "strict_refilter": strict,
           "generated_max_ratio_to_dev_or_test_quantiles": {q: round(sorted(gmax)[int(q * (len(gmax) - 1))], 4) for q in (0.5, 0.9, 0.99)}}
    S.dump_json(S.OUT / "contamination_sensitivity.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
