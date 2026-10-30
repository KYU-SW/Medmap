"""STEP23 보고서(docs/korean_expression_expansion_report.md) + outputs/manifest.json. 숫자는 모두 출력 파일에서 읽는다."""
import json
import platform

import sklearn

import s23_common as S


def pct(x):
    return "—" if x in (None, "") else f"{float(x) * 100:.1f}%"


def pp(x):
    return "—" if x in (None, "") else f"{float(x) * 100:+.1f}%p"


def table(rows, cols, head=None):
    out = ["| " + " | ".join(head or cols) + " |", "|" + "---|" * len(cols)]
    return "\n".join(out + ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def main():
    m = json.load(open(S.OUT / "metrics.json", encoding="utf-8"))
    ds = json.load(open(S.OUT / "data_stats.json", encoding="utf-8"))
    iso = json.load(open(S.OUT / "authoring_isolation_check.json", encoding="utf-8"))
    sel = json.load(open(S.OUT / "selection.json", encoding="utf-8"))
    comp = S.read_csv(S.OUT / "comparison_original_vs_expanded.csv")
    cls = S.read_csv(S.OUT / "classwise_improvement.csv")
    lc = S.read_csv(S.OUT / "learning_curve.csv")
    cc = S.read_csv(S.OUT / "confidence_coverage.csv")
    best = m["BEST_MODEL"]
    A = []
    a = A.append
    a("# STEP23 — Korean Symptom Expression Expansion + Linear Re-test\n")
    a(f"- STEP23_RESULT = **{m['STEP23_RESULT']}** · DATA_EXPANSION_EFFECT = **{m['DATA_EXPANSION_EFFECT']}** · "
      f"LIMITATION_CASE = **{m['LIMITATION_CASE']}** · gate(FULL77 core) = **{m['GATE_FULL77_CORE']}**")
    a(f"- BEST_MODEL = **{best}**(EXPANDED dev 선택) · GPU_USED = NO · NEW_BLIND_HOLDOUT_REQUIRED = **YES**")
    a("- 평가셋 = FIXED_REGRESSION_TEST(STEP21/22 test, 이미 여러 번 결과를 봄 → 개발 방향용, 최종 성능 아님). engineering benchmark, 임상 주장 아님.")
    a(f"- 학습 표현 출처: 기존 MedMap 사전 + 격리 `claude -p` 작성(synthetic_paraphrase, 실제 환자 문장 아님). 격리 검사 = **{iso['ISOLATION']}**.\n")
    a("## 1. 데이터 (학습 전 통계)\n")
    e, o = ds["conditions"]["EXPANDED"], ds["conditions"]["ORIGINAL"]
    a(table([
        {"k": "unique training expressions ORIGINAL → EXPANDED", "v": f"{ds['n_unique_training_expressions']['ORIGINAL']} → {ds['n_unique_training_expressions']['EXPANDED']}"},
        {"k": "TARGET_20 / CONFUSER_57 (EXPANDED)", "v": f"{ds['n_target20_expressions_expanded']} / {ds['n_confuser57_expressions']}"},
        {"k": "생성 / VALID 채택", "v": f"{ds['n_generated']} / {ds['n_new_valid']}"},
        {"k": "TARGET_20 class 당 min/median/max (ORIGINAL)", "v": f"{o['target20']['min']}/{o['target20']['median']}/{o['target20']['max']}"},
        {"k": "TARGET_20 class 당 min/median/max (EXPANDED)", "v": f"{e['target20']['min']}/{e['target20']['median']}/{e['target20']['max']}"},
        {"k": "CONFUSER_57 class 당 min/median/max", "v": f"{e['confuser57']['min']}/{e['confuser57']['median']}/{e['confuser57']['max']}"},
        {"k": "77 class imbalance (max/min) ORIGINAL → EXPANDED", "v": f"{o['all77']['imbalance_ratio_max_over_min']} → {e['all77']['imbalance_ratio_max_over_min']}"},
        {"k": "생성 중 test 완전일치(제거 전)", "v": ds["test_exact_overlap_generated_before_removal"]},
        {"k": "생성 중 test near-dup ≥0.80(제거 전)", "v": ds["test_near_duplicate_generated_before_removal(>=0.80)"]},
        {"k": "최종 학습 ↔ test 완전일치", "v": ds["test_exact_overlap_final_train"]},
        {"k": "최종 학습 ↔ test 최대 유사도 / ≥0.70 개수", "v": f"{ds['final_train_max_test_ratio']} / {ds['final_train_test_ratio_ge_0.70']}"},
    ], ["k", "v"], ["항목", "값"]))
    a(f"\n판정 집계: {json.dumps(ds['status_counts'], ensure_ascii=False)}\n\n감사자 판정: {json.dumps(ds['audit_verdict_counts'], ensure_ascii=False)}\n")
    a("## 2. ORIGINAL vs EXPANDED (FIXED_REGRESSION_TEST core 109)\n")
    a(table([{**r, "original": pct(r["original"]), "expanded": pct(r["expanded"]), "delta": pp(r["delta"])} for r in comp],
            ["model", "view", "metric", "original", "expanded", "delta"]))
    a("\nFULL77 = 77 class 전체 순위(판정 기준) · PILOT20_RESTRICTED = 같은 점수에서 TARGET_20 만 남긴 순위(참고). "
      "Unseen(STEP21 def) = 원 사전 기준 새 표현 97문장(같은 subset) · Unseen(vs condition train) = 각 조건 학습 표현 stem 미포함 문장.\n")
    a("## 3. dev 선택\n")
    a(table([{"cond": c, "family": f, "params": json.dumps(d["params"]), "dev_top1": pct(d["dev_core"]["top1"]), "dev_r3": pct(d["dev_core"]["recall_at_3"]),
              "step22_cfg_dev_top1": pct(d["step22_config_dev_top1"]),
              "dev_auto": (f"m≥{d['auto_accept_dev']['margin_threshold']:.3f} P {pct(d['auto_accept_dev']['dev_precision'])} cov {pct(d['auto_accept_dev']['dev_coverage'])}"
                           if d["auto_accept_dev"] else "없음")}
             for c, v in sel["conditions"].items() for f, d in v["families"].items()],
            ["cond", "family", "params", "dev_top1", "dev_r3", "step22_cfg_dev_top1", "dev_auto"]))
    a("\n## 4. auto-accept (decision margin, 확률 아님)\n")
    a(table(cc, ["model", "condition", "rule", "margin_threshold", "n_accepted", "AUTO_ACCEPT_COVERAGE", "AUTO_ACCEPT_PRECISION"]))
    a(f"\n## 5. class 별 ({best}, FULL77 core)\n")
    rows = sorted([r for r in cls if r["model"] == best], key=lambda r: -float(r["delta"] or 0))
    a(table([{**r, "old_top1": pct(r["old_top1"]), "new_top1": pct(r["new_top1"]), "delta": pp(r["delta"])} for r in rows],
            ["concept", "test_n", "old_train_n", "new_train_n", "old_top1", "new_top1", "delta"]))
    a("\n## 6. learning curve (CONFUSER_57 고정, seed 42/43/44 평균)\n")
    a(table(lc, list(lc[0].keys())))
    a(f"\n## 7. 남은 오류 분류 ({best} EXPANDED, core {m['n_errors_best_expanded_core']}건)\n")
    a(table([{"category": k, "n": v} for k, v in sorted(m["error_category_counts"].items(), key=lambda kv: -kv[1])], ["category", "n"]))
    a("\n규칙 순서: nausea/vomiting → fatigue/weakness → body-site → confuser dominance(EV:*) → insufficient training(<30) → "
      "semantic similarity failure(정답 top3) → unseen synonym → linear representation limitation. generic·morphological 은 자동 분류하지 않음.\n")
    a("## 8. 참고: STEP21 baseline (같은 core subset)\n")
    a(table([{"system": k, "top1": pct(v["top1"]), "r3": pct(v["recall_at_3"])} for k, v in m["reference_step21_baselines_same_core_subset"].items()],
            ["system", "top1", "r3"]))
    cs = json.load(open(S.OUT / "contamination_sensitivity.json", encoding="utf-8"))
    a("\n## 8-1. 오염 민감도(해석용, 판정·선택 미사용)\n")
    a("core test 문장을 '같은 concept 생성 학습 표현과의 최대 유사도'로 나눈 Top-1:\n")
    bins = cs["similarity_bins"]
    a(table([{k: (pct(v) if "|" in k else v) for k, v in r.items()} for r in bins], list(bins[0].keys()),
            [k.replace("|", " / ") for k in bins[0].keys()]))
    a("\n생성 표현을 dev·test 와 유사도 T 이상이면 추가 제거 후 같은 하이퍼파라미터로 재학습:\n")
    a(table([{"filter": k, "gen_kept": v["n_generated_kept"], "gen_per_class(min/med/max)": "/".join(map(str, v["target20_generated_min_median_max"])),
              **{f"{f} top1": pct(v["models"][f]["top1"]) for f in S.FAMILIES}, **{f"{f} R@3": pct(v["models"][f]["recall_at_3"]) for f in S.FAMILIES}}
             for k, v in cs["strict_refilter"].items()],
            ["filter", "gen_kept", "gen_per_class(min/med/max)"] + [f"{f} top1" for f in S.FAMILIES] + [f"{f} R@3" for f in S.FAMILIES]))
    a("\n해석: 엄격 필터에서의 하락은 학습 표현 수 감소(learning curve)와 겹쳐 있어, 전부 오염 효과로 볼 수 없다. "
      "반대로 생성 표현과 표면이 먼 문장(최저 구간)의 정확도가 다른 구간보다 뚜렷이 낮으면, 상승분 일부가 같은 작성 분포의 표면 유사성에서 왔다는 신호다.\n")
    a("\n## 9. 격리 검사\n")
    a(table([{"session": k, "PASS": v["PASS"], "model": ",".join(v["model_usage"]), "tool_calls": len(v["tool_calls"]),
              "attachments": json.dumps(v["attachments"]), "list_price_usd_estimate": round(v["list_price_usd_estimate"] or 0, 3)}
             for k, v in iso["sessions"].items()], ["session", "PASS", "model", "tool_calls", "attachments", "list_price_usd_estimate"]))
    a("\nlist_price 는 정가 환산 추정이며 실제 청구액이 아니다.\n")
    a("## 10. 한계\n")
    a("- FIXED_REGRESSION_TEST 는 blind 가 아니다. STEP21 test 와 STEP23 학습 표현 모두 Claude 계열이 작성 → 같은 분포 효과로 성능이 과대평가될 수 있다(완전일치·≥0.80 근접만 제거).")
    a("- dev 59 문장으로 선택 → 선택 분산 큼. 실제 환자 발화 0. 최종 모델 결정 전 새 blind holdout(가능하면 사람 작성·실제 발화) 필요.")
    a("- production 미연결. UMLS/SNOMED 원문 미복사.")
    rp = S.STEP / "docs/korean_expression_expansion_report.md"
    rp.write_text("\n".join(A) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "data/raw_generated", "outputs", "models", "docs", "scripts") for p in (S.STEP / d).glob("*")
                   if p.is_file() and p.name != "manifest.json")
    man = {"step": "STEP23", "seed": S.SEED, "gpu_used": False, "python": platform.python_version(), "sklearn": sklearn.__version__,
           "best_model": best, "selected_params": {c: {f: d["params"] for f, d in v["families"].items()} for c, v in sel["conditions"].items()},
           "inputs": {str(p.relative_to(S.REPO)): S.sha256(p) for p in (S.S22 / "data/train_expressions.csv", S.S22 / "data/normalizer_core_dev.csv",
                                                                        S.c21.DATA / "pilot_gold.csv", S.S22 / "outputs/same_subset_comparison.csv")},
           "authoring_workspace_files": {str(p.relative_to(S.WS)): S.sha256(p) for p in sorted(S.WS.rglob("*")) if p.is_file()},
           "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files}}
    S.dump_json(S.OUT / "manifest.json", man)
    print("report", rp, "files", len(man["files"]))


if __name__ == "__main__":
    main()
