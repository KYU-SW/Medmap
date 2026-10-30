"""STEP24 최종 판정 + 보고서 + manifest. 숫자는 모두 출력 파일에서 읽는다.

판정 규칙(실행 전 고정). Δ 는 FIXED_REGRESSION_TEST core 기준, low = LOW_SIMILARITY(<0.5, n=23), H = PRIMARY_HYBRID:
- SEMANTIC_GAIN(KoELECTRA 단독 low − Linear low): ≥ +15%p PASS · +5~15 PARTIAL · < +5 FAIL
- HYBRID_GATE: H Top-1 ≥ 0.90 & R@3 ≥ 0.97 & auto precision ≥ 0.95
- SPEED(H single p95): <100 EXCELLENT · 100~250 GOOD · 250~500 ACCEPTABLE · >500 SLOW
- STEP24_RESULT(위에서부터 첫 일치):
  B TRANSFORMER_ONLY_RECOMMENDED: KoE p95(GPU) ≤ 250ms & KoE Top-1 ≥ H Top-1 − 0.01 & KoE low ≥ H low & KoE Top-1 ≥ Linear Top-1 + 0.01 & KoE auto P ≥ 0.95
  A HYBRID_RECOMMENDED: H Top-1 ≥ Linear + 0.01 & H low ≥ Linear low + 0.05 & H p95 ≤ 250ms & H auto P ≥ 0.95
  D LIGHTWEIGHT_TRANSFORMER_INSUFFICIENT: SEMANTIC_GAIN = FAIL & H low < Linear low + 0.05
  C LINEAR_ONLY_RETAIN: 그 외
"""
import json
import platform

import s24_common as S

LAT = {"LINEAR_CHAR": "LINEAR_CHAR_CPU", "KOELECTRA_SMALL": "KOELECTRA_GPU", "HYBRID_B": "HYBRID_B_fastpath",
       "HYBRID_A": "HYBRID_A_or_C_both_models", "HYBRID_C": "HYBRID_A_or_C_both_models"}


def pct(x):
    return "—" if x in (None, "") else f"{float(x) * 100:.1f}%"


def table(rows, cols, head=None):
    out = ["| " + " | ".join(head or cols) + " |", "|" + "---|" * len(cols)]
    return "\n".join(out + ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def speed(p95):
    return "EXCELLENT" if p95 < 100 else "GOOD" if p95 <= 250 else "ACCEPTABLE" if p95 <= 500 else "SLOW"


def main():
    hm = S.load_json(S.OUT / "hybrid_metrics.json")
    tm = S.load_json(S.OUT / "transformer_metrics.json")
    lat = S.load_json(S.OUT / "latency.json")
    ag = S.load_json(S.OUT / "agreement_summary.json")
    env = S.load_json(S.OUT / "environment.json")
    ks = S.load_json(S.OUT / "koelectra_selection.json")
    R, H = hm["results"], hm["PRIMARY_HYBRID"]
    t = lambda n, k="top1": R[n]["core_test"][k]  # noqa: E731
    low = lambda n: R[n]["low_similarity_lt_0.5"]["top1"]  # noqa: E731
    p95 = lambda n: lat["single_message"][LAT[n]]["p95_ms"]  # noqa: E731
    gain = low("KOELECTRA_SMALL") - low("LINEAR_CHAR")
    sem = "PASS" if gain >= 0.15 else "PARTIAL" if gain >= 0.05 else "FAIL"
    hg = t(H) >= 0.90 and t(H, "recall_at_3") >= 0.97 and (t(H, "auto_precision") or 0) >= 0.95
    K = "KOELECTRA_SMALL"
    if (p95(K) <= 250 and t(K) >= t(H) - 0.01 and low(K) >= low(H) and t(K) >= t("LINEAR_CHAR") + 0.01 and (t(K, "auto_precision") or 0) >= 0.95):
        res = "TRANSFORMER_ONLY_RECOMMENDED"
    elif (t(H) >= t("LINEAR_CHAR") + 0.01 and low(H) >= low("LINEAR_CHAR") + 0.05 and p95(H) <= 250 and (t(H, "auto_precision") or 0) >= 0.95):
        res = "HYBRID_RECOMMENDED"
    elif sem == "FAIL" and low(H) < low("LINEAR_CHAR") + 0.05:
        res = "LIGHTWEIGHT_TRANSFORMER_INSUFFICIENT"
    else:
        res = "LINEAR_ONLY_RETAIN"
    decision = {"STEP24_RESULT": res, "GPU_USED": "YES", "MODEL": S.HF_REPO, "PRIMARY_HYBRID": H, "SEMANTIC_GAIN": sem,
                "semantic_gain_pp": S.rnd(gain), "HYBRID_GATE": "PASS" if hg else "FAIL", "SPEED_PRIMARY_HYBRID": speed(p95(H)),
                "NEW_BLIND_HOLDOUT_REQUIRED": "YES", "test_name": "FIXED_REGRESSION_TEST", "rules": __doc__}
    S.dump_json(S.OUT / "decision.json", decision)

    names = ["LINEAR_CHAR", "KOELECTRA_SMALL", "HYBRID_A", "HYBRID_B", "HYBRID_C"]
    A = []
    a = A.append
    a("# STEP24 — Lightweight Korean Encoder + Linear Hybrid Normalizer\n")
    a(f"- STEP24_RESULT = **{res}** · SEMANTIC_GAIN = **{sem}** ({gain * 100:+.1f}%p) · HYBRID_GATE({H}) = **{decision['HYBRID_GATE']}** · "
      f"SPEED({H}) = **{decision['SPEED_PRIMARY_HYBRID']}**")
    a(f"- MODEL = {S.HF_REPO}@{S.HF_REVISION[:7]} (Apache-2.0, {env['model']['total_bytes'] / 1e6:.1f} MB) · GPU_USED = YES ({env['gpu_name']}) · NEW_BLIND_HOLDOUT_REQUIRED = YES")
    a("- 데이터 고정(STEP23 EXPANDED 1,119 · core dev 59 · FIXED_REGRESSION_TEST core 109), 모델만 변경. 선택·임계값·α 는 dev 에서만. regression test 는 blind 아님 → 모델 비교용.")
    a("- 정규화 모델일 뿐: 부정·시점·화자·복수 증상 span 은 NLU 범위. softmax 는 분류 confidence(임상 확률 아님).\n")
    a("## 1. 핵심 비교 (core 109)\n")
    rows = []
    for n in names:
        c = R[n]["core_test"]
        rows.append({"model": n, "top1": pct(c["top1"]), "r3": pct(c["recall_at_3"]), "r5": pct(c["recall_at_5"]), "macro": pct(c["macro_top1"]),
                     "low_sim_top1(n=23)": pct(low(n)), "unseen(STEP21)": pct(R[n]["unseen_step21_def"]["top1"]),
                     "auto_P": pct(c["auto_precision"]), "auto_cov": pct(c["auto_coverage"]), "confirm_rate": pct(c["confirmation_rate"]),
                     "p50_ms": lat["single_message"][LAT[n]]["p50_ms"], "p95_ms": p95(n), "dev_top1": pct(R[n]["core_dev"]["top1"])})
    a(table(rows, list(rows[0].keys())))
    a(f"\nHYBRID_B Transformer 호출률: test {pct(R['HYBRID_B']['transformer_call_rate']['core_test'])} · dev {pct(R['HYBRID_B']['transformer_call_rate']['core_dev'])}. "
      f"PRIMARY_HYBRID = {H}(dev 선택). HYBRID_C α = {hm['config']['alpha(dev)']}(dev).\n")
    a("## 2. 표면 유사도 구간별 Top-1\n")
    br = S.read_csv(S.OUT / "similarity_bucket_metrics.csv")
    piv = {}
    for r in br:
        piv.setdefault(r["bucket"], {"bucket": r["bucket"], "n": r["n"]})[r["model"]] = pct(r["top1"])
    a(table(list(piv.values()), ["bucket", "n"] + names))
    a("\n## 3. Agreement (core test)\n")
    a(table([{"cell": k, "n": v, "low_sim_n": ag["low_similarity_lt_0.5"].get(k, 0)} for k, v in sorted(ag["core_test"].items())], ["cell", "n", "low_sim_n"]))
    a(f"\n일치율 {pct(ag['agree_rate'])}, 일치 시 정답률 {pct(ag['agree_precision'])}.\n")
    a("## 4. 오류 분류\n")
    for n, d in ag["error_categories"].items():
        a(f"- {n}: " + ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])))
    a("\n## 5. KoELECTRA 학습 (dev 선택)\n")
    a(f"- 선택: {json.dumps(ks['params'])} · 고정 {json.dumps(ks['fixed'])} · dev Top-1 {pct(ks['dev_core']['top1'])} · 재학습 일치 {ks['refit_matches_grid_dev']}")
    a(f"- 학습 peak VRAM alloc {ks['training_peak_vram']['alloc_mib']} MiB / reserved {ks['training_peak_vram']['reserved_mib']} MiB · "
      f"추론 peak alloc {lat['inference_peak_vram']['alloc_mib']} MiB / reserved {lat['inference_peak_vram']['reserved_mib']} MiB")
    a(f"- max_length = {env['selected_max_length']} (토큰 길이 p99 {env['token_length_quantiles']['0.99']}, 최대 {env['token_length_max']})")
    grid = S.read_csv(S.OUT / "koelectra_dev_grid.csv")
    a("\n" + table(grid, ["grid_index", "epochs", "lr", "loss", "dev_top1", "dev_recall_at_3", "train_seconds", "peak_vram_alloc_mib"]))
    a("\n## 6. Latency (single message, warm-up 후 327회, STT 제외)\n")
    a(table([{"path": k, **v} for k, v in lat["single_message"].items()], ["path", "n", "mean_ms", "median_ms", "p50_ms", "p95_ms", "max_ms"]))
    a(f"\nbatch(GPU, {lat['batch_gpu_koelectra']['batch_size']} 문장): {lat['batch_gpu_koelectra']['median_ms_per_batch']} ms/batch · "
      f"{lat['batch_gpu_koelectra']['median_ms_per_sentence']} ms/문장. CPU threads {lat['torch_cpu_threads']}.\n")
    a("## 7. 한계\n")
    a("- FIXED_REGRESSION_TEST 는 blind 아님. low-similarity subset n=23(1문장 = 4.3%p) → 차이 해석 주의.")
    a("- 학습·test 모두 Claude 계열 작성 합성 문장. 실제 환자 발화 0. production 미연결.")
    (S.STEP / "docs").mkdir(exist_ok=True)
    (S.STEP / "docs/lightweight_hybrid_report.md").write_text("\n".join(A) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "outputs", "docs", "scripts", "models", "models/koelectra_small") for p in (S.STEP / d).glob("*")
                   if p.is_file() and p.name != "manifest.json")
    man = {"step": "STEP24", "seed": S.SEED, "python": platform.python_version(), "gpu": env["gpu_name"], "torch": env["torch"],
           "transformers": env["transformers"], "model_download": env["model"],
           "inputs": {str(p.relative_to(S.REPO)): S.sha256(p) for p in (S.S23 / "data/expanded_train_expressions.csv", S.S23 / "outputs/selection.json",
                                                                        S.c21.DATA / "pilot_gold.csv")},
           "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files}}
    S.dump_json(S.OUT / "manifest.json", man)
    print(json.dumps({k: v for k, v in decision.items() if k != "rules"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
