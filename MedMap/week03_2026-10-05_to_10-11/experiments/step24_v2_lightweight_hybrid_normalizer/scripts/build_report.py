"""STEP24-v2 최종 판정 + 보고서 + manifest(PROTOCOL_DEVIATION: 학습 grid 확장). 숫자는 모두 출력 파일에서 읽는다.

판정 규칙 = STEP24-v1 과 동일(변경 없음), PRIMARY_SEED(42) 결과에 적용. 추가로 5 seed 평균에도 같은 규칙을 적용해 판정이 seed 에 강건한지 표시.
- SEMANTIC_GAIN(KoELECTRA 단독 low − Linear low): ≥ +15%p PASS · +5~15 PARTIAL · < +5 FAIL
- HYBRID_GATE: H Top-1 ≥ 0.90 & R@3 ≥ 0.97 & auto precision ≥ 0.95
- SPEED(H single p95): <100 EXCELLENT · 100~250 GOOD · 250~500 ACCEPTABLE · >500 SLOW
- STEP24_RESULT(첫 일치): B TRANSFORMER_ONLY_RECOMMENDED → A HYBRID_RECOMMENDED → D LIGHTWEIGHT_TRANSFORMER_INSUFFICIENT → C LINEAR_ONLY_RETAIN
  (조건식은 decide() 참조, v1 build_report 와 동일)
"""
import json
import platform

import s24_common as S

LAT = {"LINEAR_CHAR": "LINEAR_CHAR_CPU", "KOELECTRA_SMALL": "KOELECTRA_GPU", "HYBRID_B": "HYBRID_B_fastpath",
       "HYBRID_A": "HYBRID_A_or_C_both_models", "HYBRID_C": "HYBRID_A_or_C_both_models"}
NAMES = ["LINEAR_CHAR", "KOELECTRA_SMALL", "HYBRID_A", "HYBRID_B", "HYBRID_C"]


def pct(x):
    return "—" if x in (None, "") else f"{float(x) * 100:.1f}%"


def table(rows, cols, head=None):
    out = ["| " + " | ".join(head or cols) + " |", "|" + "---|" * len(cols)]
    return "\n".join(out + ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def speed(p95):
    return "EXCELLENT" if p95 < 100 else "GOOD" if p95 <= 250 else "ACCEPTABLE" if p95 <= 500 else "SLOW"


def decide(t, low, p95, H):
    """t(name, key) / low(name) / p95(name). v1 과 같은 조건."""
    K, Lc = "KOELECTRA_SMALL", "LINEAR_CHAR"
    gain = low(K) - low(Lc)
    sem = "PASS" if gain >= 0.15 else "PARTIAL" if gain >= 0.05 else "FAIL"
    hg = t(H, "top1") >= 0.90 and t(H, "recall_at_3") >= 0.97 and (t(H, "auto_precision") or 0) >= 0.95
    if p95(K) <= 250 and t(K, "top1") >= t(H, "top1") - 0.01 and low(K) >= low(H) and t(K, "top1") >= t(Lc, "top1") + 0.01 and (t(K, "auto_precision") or 0) >= 0.95:
        r = "TRANSFORMER_ONLY_RECOMMENDED"
    elif t(H, "top1") >= t(Lc, "top1") + 0.01 and low(H) >= low(Lc) + 0.05 and p95(H) <= 250 and (t(H, "auto_precision") or 0) >= 0.95:
        r = "HYBRID_RECOMMENDED"
    elif sem == "FAIL" and low(H) < low(Lc) + 0.05:
        r = "LIGHTWEIGHT_TRANSFORMER_INSUFFICIENT"
    else:
        r = "LINEAR_ONLY_RETAIN"
    return r, sem, gain, hg


def main():
    P = S.seed_out(S.PRIMARY_SEED)
    hm, ag, ks = S.load_json(P / "hybrid_metrics.json"), S.load_json(P / "agreement_summary.json"), S.load_json(P / "koelectra_selection.json")
    lat, env, imp = S.load_json(S.OUT / "latency.json"), S.load_json(S.ENV_JSON), S.load_json(S.OUT / "implementation_check.json")
    gsel, sv = S.load_json(S.OUT / "koelectra_selection.json"), S.load_json(S.OUT / "seed_variability.json")
    R, H = hm["results"], hm["PRIMARY_HYBRID"]
    p95 = lambda n: lat["single_message"][LAT[n]]["p95_ms"]  # noqa: E731
    res, sem, gain, hg = decide(lambda n, k: R[n]["core_test"][k], lambda n: R[n]["low_similarity_lt_0.5"]["top1"], p95, H)
    sm = sv["summary"]
    res_mean, sem_mean, gain_mean, _ = decide(lambda n, k: sm[n][{"top1": "test_top1", "recall_at_3": "test_recall_at_3"}.get(k, k)]["mean"],
                                              lambda n: sm[n]["low_sim_top1"]["mean"], p95, H)
    decision = {"STEP24_RESULT": res, "STEP24_RESULT_on_5seed_mean": res_mean, "PROTOCOL_DEVIATION": "KoELECTRA 학습 grid 확장(v1 학습 붕괴), 사용자 승인 2026-10-09",
                "GPU_USED": "YES", "MODEL": S.HF_REPO, "PRIMARY_HYBRID": H, "SEMANTIC_GAIN": sem, "semantic_gain_pp": S.rnd(gain),
                "SEMANTIC_GAIN_5seed_mean": sem_mean, "semantic_gain_pp_5seed_mean": S.rnd(gain_mean), "HYBRID_GATE": "PASS" if hg else "FAIL",
                "SPEED_PRIMARY_HYBRID": speed(p95(H)), "IMPLEMENTATION_OK": imp["IMPLEMENTATION_OK"], "NEW_BLIND_HOLDOUT_REQUIRED": "YES",
                "test_name": "FIXED_REGRESSION_TEST(blind 아님)", "rules": __doc__}
    S.dump_json(S.OUT / "decision.json", decision)

    A = []
    a = A.append
    a("# STEP24-v2 — Lightweight Korean Encoder + Linear Hybrid (PROTOCOL_DEVIATION)\n")
    a(f"- STEP24_RESULT = **{res}** (seed {S.PRIMARY_SEED}) · 5 seed 평균 기준 = **{res_mean}** · SEMANTIC_GAIN = **{sem}** ({gain * 100:+.1f}%p; "
      f"5 seed 평균 {gain_mean * 100:+.1f}%p) · HYBRID_GATE({H}) = **{decision['HYBRID_GATE']}** · SPEED({H}) = **{decision['SPEED_PRIMARY_HYBRID']}**")
    a(f"- PROTOCOL_DEVIATION: v1 사전 등록 grid(lr≤5e-5, epoch≤8)에서 KoELECTRA 학습 붕괴(학습 정확도 4.3%, 단일 class) → 학습 grid 만 확장(사용자 승인). "
      "데이터·dev·test·Hybrid 정책·판정 규칙은 v1 그대로. v1 결과 폴더는 수정하지 않음(data/v1_snapshot_sha256.txt).")
    a(f"- MODEL = {S.HF_REPO}@{S.HF_REVISION[:7]} (Apache-2.0) · GPU {env['gpu_name']} · IMPLEMENTATION_OK = {imp['IMPLEMENTATION_OK']} · NEW_BLIND_HOLDOUT_REQUIRED = YES")
    a("- FIXED_REGRESSION_TEST 는 여러 번 본 regression test → 모델 비교용, 최종 blind 성능 아님. 설정·epoch·α·임계값은 모두 dev 로만 선택.\n")
    a("## 1. 구현 검사 (학습셋만)\n")
    a(table([{"check": k, "PASS": v["PASS"], "detail": json.dumps({kk: vv for kk, vv in v.items() if kk not in ("PASS", "example")}, ensure_ascii=False)[:160]}
             for k, v in imp.items() if isinstance(v, dict)], ["check", "PASS", "detail"]))
    a(f"\n{imp['IMPLEMENTATION_OK_rule']} T7b 는 T7 FAIL 확인 뒤 추가한 사후 검사(같은 64문장·600 step).\n")
    a("## 2. 학습 grid (dev 선택, seed 42)\n")
    grid = S.read_csv(S.OUT / "koelectra_dev_grid.csv")
    a(table(grid, ["grid_index", "lr", "epochs", "loss", "best_epoch", "best_dev_top1", "best_dev_recall_at_3", "best_dev_loss", "train_acc_at_best",
                   "min_dev_loss_epoch", "final_dev_loss", "dev_loss_rise_after_min", "final_train_acc", "final_dev_top1", "train_seconds", "peak_vram_alloc_mib"]))
    a(f"\n선택: grid {gsel['selected_grid_index']} {json.dumps(gsel['selected_params'])} · seed 42 재학습 = grid run 일치 {gsel['primary_seed_matches_grid_run']}. "
      f"규칙: {gsel['selection_rule']}.\n")
    a("과적합 판단: `dev_loss_rise_after_min` > 0 이면 dev loss 최저점 이후 상승(과적합 신호). checkpoint 는 학습 정확도가 아니라 dev 기준 epoch.\n")
    a("## 3. seed 변동성 (선택 설정 고정, seed 42–46)\n")
    a(table([{"model": m, **{k: (f"{pct(v['mean'])} ± {v['std'] * 100:.1f}" if v else "—") for k, v in sm[m].items()}} for m in NAMES],
            ["model", "dev_top1", "test_top1", "test_recall_at_3", "low_sim_top1", "auto_precision", "auto_coverage"]))
    a(f"\nseed 별 dev Top-1: {json.dumps(gsel['seed_dev_top1'])} · best epoch: {json.dumps(gsel['seed_best_epochs'])} · "
      f"Linear 오답·KoELECTRA 정답(core): {json.dumps(sv['linear_wrong_transformer_correct']['per_seed'])} · "
      f"그중 low-sim: {json.dumps(sv['low_sim_linear_wrong_transformer_correct']['per_seed'])} · "
      f"Linear 정답·KoELECTRA 오답: {json.dumps(sv['linear_correct_transformer_wrong']['per_seed'])} · PRIMARY_HYBRID: {json.dumps(sv['primary_hybrid_per_seed'])}\n")
    a(f"## 4. 핵심 비교 (seed {S.PRIMARY_SEED}, core 109)\n")
    rows = []
    for n in NAMES:
        c = R[n]["core_test"]
        rows.append({"model": n, "top1": pct(c["top1"]), "r3": pct(c["recall_at_3"]), "r5": pct(c["recall_at_5"]), "macro": pct(c["macro_top1"]),
                     "low_sim(n=23)": pct(R[n]["low_similarity_lt_0.5"]["top1"]), "auto_P": pct(c["auto_precision"]), "auto_cov": pct(c["auto_coverage"]),
                     "p50_ms": lat["single_message"][LAT[n]]["p50_ms"], "p95_ms": p95(n), "dev_top1": pct(R[n]["core_dev"]["top1"])})
    a(table(rows, list(rows[0].keys())))
    a(f"\nHYBRID_B Transformer 호출률 test {pct(R['HYBRID_B']['transformer_call_rate']['core_test'])}. HYBRID_C α = {hm['config']['alpha(dev)']}(dev).\n")
    a("## 5. 표면 유사도 구간별 Top-1 (seed 42)\n")
    br = S.read_csv(P / "similarity_bucket_metrics.csv")
    piv = {}
    for r in br:
        piv.setdefault(r["bucket"], {"bucket": r["bucket"], "n": r["n"]})[r["model"]] = pct(r["top1"])
    a(table(list(piv.values()), ["bucket", "n"] + NAMES))
    a("\n## 6. Agreement (seed 42, core)\n")
    a(table([{"cell": k, "n": v, "low_sim_n": ag["low_similarity_lt_0.5"].get(k, 0)} for k, v in sorted(ag["core_test"].items())], ["cell", "n", "low_sim_n"]))
    a("\n## 7. 오류 분류 (seed 42)\n")
    for n, d in ag["error_categories"].items():
        a(f"- {n}: " + ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])))
    a("\n## 8. 자원 · 속도\n")
    a(f"- 학습 peak VRAM(seed 42) alloc {ks['training_peak_vram']['alloc_mib']} MiB / reserved {ks['training_peak_vram']['reserved_mib']} MiB · "
      f"추론 peak alloc {lat['inference_peak_vram']['alloc_mib']} MiB / reserved {lat['inference_peak_vram']['reserved_mib']} MiB")
    a(f"- grid 12 run 총 학습 {sum(float(r['train_seconds']) for r in grid):.0f}s")
    a(table([{"path": k, **v} for k, v in lat["single_message"].items()], ["path", "n", "mean_ms", "median_ms", "p50_ms", "p95_ms", "max_ms"]))
    a(f"\nbatch GPU {lat['batch_gpu_koelectra']['batch_size']}문장: {lat['batch_gpu_koelectra']['median_ms_per_batch']} ms. STT 제외.\n")
    a("## 9. 한계\n")
    a("- low-sim subset n=23(1문장 = 4.3%p). dev 59 로 epoch·설정을 고름 → dev 낙관 편향 가능. FIXED_REGRESSION_TEST 는 blind 아님.")
    a("- 학습·test 모두 Claude 계열 작성 합성 문장. 실제 환자 발화 0. production 미연결.")
    (S.STEP / "docs/lightweight_hybrid_report.md").write_text("\n".join(A) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "outputs", "docs", "scripts", "models") for p in (S.STEP / d).glob("*") if p.is_file() and p.name != "manifest.json")
    files += sorted(p for p in (S.STEP / "outputs/seeds").rglob("*") if p.is_file())
    files += sorted(p for p in S.MODELS.glob("koelectra_small_seed*/*") if p.is_file())
    man = {"step": "STEP24-v2", "protocol_deviation": decision["PROTOCOL_DEVIATION"], "seeds": S.SEEDS, "python": platform.python_version(),
           "gpu": env["gpu_name"], "torch": env["torch"], "transformers": env["transformers"], "model_download": env["model"],
           "inputs": {str(p.relative_to(S.REPO)): S.sha256(p) for p in (S.S23 / "data/expanded_train_expressions.csv", S.S23 / "outputs/selection.json",
                                                                        S.c21.DATA / "pilot_gold.csv", S.PRETRAINED / "model.safetensors")},
           "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files}}
    S.dump_json(S.OUT / "manifest.json", man)
    print(json.dumps({k: v for k, v in decision.items() if k != "rules"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
