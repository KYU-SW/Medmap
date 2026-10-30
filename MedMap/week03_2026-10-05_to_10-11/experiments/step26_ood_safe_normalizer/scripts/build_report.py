"""STEP26 판정 + 보고서 2종 + manifest. 숫자는 outputs/ 에서 읽는다.

사전 판정 기준(지시문 §15, Hybrid B 대비, HELD_OUT·regression 보고값):
 C1 WEAK_NON_SYMPTOM auto-accept rate 상대 감소 ≥ 70% · C2 regression auto precision ≥ 0.95 · C3 regression auto coverage ≥ 0.30
 C4 disagreement auto-accept count 상대 감소 ≥ 70%('대폭') · C5 CPU p95 ≤ 50 ms
 5개 모두 → REJECTION_POLICY_USEFUL · 3–4개 → PARTIAL · 그 외 INSUFFICIENT. (weak-label proxy·합성 regression 기반 engineering 판정)
"""
import json

import s26_common as S


def table(rows, cols, head=None):
    out = ["| " + " | ".join(head or cols) + " |", "|" + "---|" * len(cols)]
    return "\n".join(out + ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def pct(x):
    return "—" if x in (None, "") else f"{float(x) * 100:.1f}%"


def main():
    sel = S.load_json(S.OUT / "policy_selection.json")
    best = sel["BEST_POLICY"]
    comp = {r["policy"]: r for r in S.read_csv(S.OUT / "rejection_policy_comparison.csv")}
    lat = S.load_json(S.OUT / "latency.json")
    leak = S.load_json(S.OUT / "leakage_audit.json")
    stc = S.load_json(S.OUT / "status_classifier.json")
    dist = S.read_csv(S.OUT / "status_distribution.csv")
    pri = S.read_csv(S.OUT / "priority_cases.csv")
    smoke = S.load_json(S.OUT / "illustrative_smoke.json")
    hb, nw, lo = comp["HYBRID_B"], comp[best], comp["LINEAR_ONLY"]
    f = float
    p95 = lat["single_message_cpu"][f"SAFE_NORMALIZER_{best}"]["p95_ms"]
    c = {"C1_WN_rel_reduction": 1 - f(nw["EVAL_WN_auto_rate"]) / f(hb["EVAL_WN_auto_rate"]),
         "C2_reg_precision": f(nw["REG_auto_precision"]), "C3_reg_coverage": f(nw["REG_auto_coverage"]),
         "C4_disagree_rel_reduction": 1 - f(nw["EVAL_disagree_auto"]) / f(hb["EVAL_disagree_auto"]), "C5_p95_ms": p95}
    passed = {"C1": c["C1_WN_rel_reduction"] >= 0.70, "C2": c["C2_reg_precision"] >= 0.95, "C3": c["C3_reg_coverage"] >= 0.30,
              "C4": c["C4_disagree_rel_reduction"] >= 0.70, "C5": p95 <= 50}
    n = sum(passed.values())
    result = "REJECTION_POLICY_USEFUL" if n == 5 else "PARTIAL" if n >= 3 else "INSUFFICIENT"
    ev_ws = next(d for d in dist if d["set"] == "EXT_EVAL" and d["weak_label"] == "WEAK_SYMPTOM")
    ev_wn = next(d for d in dist if d["set"] == "EXT_EVAL" and d["weak_label"] == "WEAK_NON_SYMPTOM")
    reg = next(d for d in dist if d["set"] == "INT_REGRESSION_CORE")
    verdict = {"STEP26_RESULT": result, "BEST_POLICY": best, "EXTERNAL_GOLD_AVAILABLE": "NO", "CANONICAL_ACCURACY_VALIDATED": "NO", "GPU_USED": "NO",
               "criteria_values": {k: round(v, 4) for k, v in c.items()}, "criteria_pass": passed,
               "weak_symptom_to_NON_SYMPTOM_eval": f"{ev_ws['NON_SYMPTOM']}/{ev_ws['n']}", "rules": __doc__}
    S.dump_json(S.OUT / "step26_verdict.json", verdict)

    rows = []
    for name, key in (("Weak-negative auto-accept rate (EVAL)", "EVAL_WN_auto_rate"), ("Weak-symptom auto-accept rate (EVAL)", "EVAL_WS_auto_rate"),
                      ("Disagreement auto-accept count (EVAL)", "EVAL_disagree_auto"), ("Regression auto-accept precision", "REG_auto_precision"),
                      ("Regression auto-accept coverage", "REG_auto_coverage"), ("Unknown(=not auto) rate (EVAL)", "EVAL_unknown_rate")):
        fmt = (lambda v: v) if "count" in name else pct
        rows.append({"metric": name, "Linear": fmt(lo[key]), "Hybrid B": fmt(hb[key]), f"New {best}": fmt(nw[key])})
    rows.append({"metric": "CPU p95 latency (ms)", "Linear": lat["single_message_cpu"]["LINEAR_ONLY"]["p95_ms"],
                 "Hybrid B": lat["single_message_cpu"]["HYBRID_B"]["p95_ms"], f"New {best}": p95})
    A = [f"# STEP26 — OOD Detection + UNKNOWN Handling\n",
         f"- STEP26_RESULT = **{result}** ({n}/5) · BEST_POLICY = **{best}** {json.dumps(sel['policies'][best]['params'])} · EXTERNAL_GOLD_AVAILABLE = NO · "
         "CANONICAL_ACCURACY_VALIDATED = NO · GPU_USED = NO",
         "- EXT 지표 = 외부 NER 범주 weak-label proxy(MedMap concept 정답 아님). REG = 합성 FIXED_REGRESSION_TEST(실제 환자 성능 아님). 둘을 합친 정확도는 없다.",
         "- HELD_OUT_EXTERNAL_EVALUATION 은 STEP25 에서 전체 예측을 이미 본 데이터 → frozen retrospective evaluation(blind 아님). 임계값·정책은 DEV(외부 dev + STEP23 core dev 59)로만 선택.\n",
         "## 1. 핵심 비교\n", table(rows, ["metric", "Linear", "Hybrid B", f"New {best}"]),
         f"\n판정 기준 값: {json.dumps(verdict['criteria_values'])} · 통과 {json.dumps(passed)}\n",
         "## 2. 정책 전체(HELD_OUT·REG 는 보고 전용, 선택은 DEV CV)\n",
         table(list(comp.values()), ["policy", "is_best", "DEV_CV_WN_auto", "DEV_CV_core_prec", "DEV_CV_core_cov", "EVAL_WN_auto_rate", "EVAL_WS_auto_rate",
                                     "EVAL_MIXED_auto_rate", "EVAL_disagree_auto", "REG_auto_precision", "REG_auto_coverage", "KMC_auto_rate", "params"]),
         f"\nLIGHTWEIGHT_GATE 승격 = {sel['gate_promoted']}(DEV CV 에서 core precision < 0.95 → feasible 아님). 규칙: policy_lib 문서열.\n",
         "## 3. 상태 분포 (KNOWN / UNCERTAIN / UNKNOWN / NON)\n", table(dist, list(dist[0].keys())),
         f"\nNON_SYMPTOM 임계값 T_non = {stc['T_non']}(EXT_DEV CV weak precision ≥ 0.95, core dev NON 률 ≤ 5% 인 최소값). EXT_DEV 상태는 학습에 쓴 데이터라 in-sample.\n",
         f"- HELD_OUT weak-symptom {ev_ws['n']} 중 NON_SYMPTOM {ev_ws['NON_SYMPTOM']} → 증상 표현이 '증상 아님'으로 빠지는 손해(원문은 보존).",
         f"- HELD_OUT weak-non-symptom {ev_wn['n']} 중 NON {ev_wn['NON_SYMPTOM']} · UNCERTAIN {ev_wn['UNCERTAIN']} · UNKNOWN {ev_wn['UNKNOWN_SYMPTOM']} · 자동 수락 {ev_wn['KNOWN_SYMPTOM']}.",
         f"- REG {reg['n']}: KNOWN {reg['KNOWN_SYMPTOM']}(정답 {reg['known_correct(internal only)']}) · UNCERTAIN {reg['UNCERTAIN']} · UNKNOWN {reg['UNKNOWN_SYMPTOM']} · NON {reg['NON_SYMPTOM']}.\n",
         "## 4. 우선 점검 사례 (외부 데이터에 실제 존재)\n",
         table(pri, ["kind", "text", "weak_label", "linear", "koelectra", "hybrid_b", "new_auto", "status", "candidates"]),
         "\n## 5. Illustrative smoke (데이터에 없는 예시 — 지표·조정에 미사용)\n",
         table([{"input": s["input"], "existing_hybrid_b": f"{s['existing_hybrid_b']} ({'auto' if s['existing_hybrid_b_auto'] else 'confirm'})",
                 "new_status": s["new_output"]["status"], "candidates": ";".join(s["new_output"]["candidate_ids"]), "reason": s["new_output"]["reason"]} for s in smoke],
               ["input", "existing_hybrid_b", "new_status", "candidates", "reason"]),
         "\n## 6. 속도·자원\n", f"```json\n{json.dumps(lat, ensure_ascii=False, indent=1)}\n```",
         "\n## 7. 데이터·누수\n", f"```json\n{json.dumps(leak, ensure_ascii=False, indent=1)}\n```",
         "\n## 8. 검증되지 않은 위험\n",
         "- canonical 정확도: 외부 Gold 0 → 자동 수락된 외부 표현이 맞는 concept 인지 미확인.",
         "- 미지원 증상의 확인 후보가 틀릴 수 있음: '코피가' → 자동 수락은 막혔지만 확인 후보가 객혈·토혈(77 에 비출혈 concept 없음).",
         "- weak label 잡음: KBMC Treatment 에 '전립선' 같은 신체 부위가 섞이는 등 annotation 자체 오류 존재.",
         "- 지원 증상 손실: REG 자동 수락 coverage 90.8%(Hybrid B) → 정책 값으로 감소, 나머지는 확인 질문으로 넘어감(UX 부담).",
         "- COMPLEX 판정은 정규식 규칙(부정·과거·타인·연결어·40자) — 누락·과잉 판정 미검증."]
    (S.DOCS / "ood_detection_report.md").write_text("\n".join(A) + "\n", encoding="utf-8")

    ex = {s["input"]: s["new_output"] for s in smoke}
    B = ["# SafeNormalizer 출력 인터페이스(실험용, production 미연결)\n",
         "모든 상태에서 `source_text` 원문을 보존한다. 어떤 상태도 환자 기록을 직접 수정하지 않는다.\n",
         table([{"status": "KNOWN_SYMPTOM", "decision": "AUTO_ACCEPT", "condition": f"{best} 통과(COMPLEX 아님)", "ux": "\"호흡곤란으로 정리했어요.\""},
                {"status": "UNCERTAIN", "decision": "ASK_CONFIRMATION", "condition": "두 모델 동의하나 확신 부족 → 후보 최대 3", "ux": "\"말씀하신 증상을 정확히 분류하지 못했어요. 다음 중 가까운 표현이 있나요?\""},
                {"status": "UNCERTAIN", "decision": "NEEDS_CONFIRMATION", "condition": "COMPLEX_INPUT 또는 판단 불가", "ux": "\"조금 더 자세히 알려주실 수 있을까요?\" (복합 문장은 증상별로 나눠 확인)"},
                {"status": "UNKNOWN_SYMPTOM", "decision": "NEEDS_CONFIRMATION", "condition": "모델 불일치 + 증상 같음", "ux": "\"현재 지원하는 증상 목록에서 정확히 연결되지 않았어요. 말씀하신 내용은 그대로 기록할게요.\""},
                {"status": "NON_SYMPTOM", "decision": "DO_NOT_MAP", "condition": f"non_symptom_score ≥ {stc['T_non']}", "ux": "\"증상보다는 질환이나 병력에 해당할 수 있어요. 증상 기록과 분리해서 확인할게요.\""}],
               ["status", "decision", "condition", "ux"]),
         "\n## 예시 출력(illustrative smoke, 실제 실행 결과)\n"] + [f"### {k}\n```json\n{json.dumps(v, ensure_ascii=False, indent=1, default=str)}\n```" for k, v in ex.items()] + [
         "\n주의: UNKNOWN 은 진단이 아니다. NON_SYMPTOM 은 '증상 기록에 자동 매핑하지 않음'이지 삭제가 아니다. model_evidence 의 점수는 확률이 아니다."]
    (S.DOCS / "safe_normalization_interface.md").write_text("\n".join(B) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "outputs", "docs", "scripts", "models") for p in (S.STEP / d).glob("*") if p.is_file() and p.name != "manifest.json")
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP26", "seed": S.SEED, "frozen_models": {"linear": str(S.S23 / "models/linear_char_expanded.joblib"),
                                                                                             "koelectra": str(S.KOE_DIR)},
                                          "thresholds_existing": {"T_lin": S.T_LIN, "T_koe": S.T_KOE},
                                          "inputs": {str(p): S.sha256(p) for p in sorted(S.RAW.rglob("*")) if p.is_file()},
                                          "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files}})
    print(json.dumps({k: v for k, v in verdict.items() if k != "rules"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
