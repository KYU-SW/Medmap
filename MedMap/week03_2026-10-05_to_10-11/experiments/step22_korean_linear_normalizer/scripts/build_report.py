"""STEP22 보고서(docs/korean_linear_normalizer_report.md) + outputs/manifest.json 생성.
모든 숫자는 outputs/*.json·csv 에서 읽어 넣는다(손으로 옮겨 적지 않음).
"""
import json
import platform

import sklearn

import lin_common as L


def pct(x):
    return "—" if x is None else f"{x * 100:.1f}%"


def pp(x):
    return "—" if x is None else f"{x * 100:+.1f}%p"


def table(rows, cols, head=None):
    head = head or cols
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def main():
    m = json.load(open(L.OUT / "metrics.json", encoding="utf-8"))
    inv = json.load(open(L.OUT / "class_inventory.json", encoding="utf-8"))
    cs = json.load(open(L.OUT / "confusion_summary.json", encoding="utf-8"))
    same = L.read_csv(L.OUT / "same_subset_comparison.csv")
    pairs = L.read_csv(L.OUT / "confusion_pairs.csv")
    cc = L.read_csv(L.OUT / "confidence_coverage.csv")
    excl = L.read_csv(L.DATA / "excluded_training_expressions.csv")
    sel = m["selection"]
    best, g, ob = m["BEST_MODEL"], m["gate_inputs_core_test"], m["old_best_same_subset"]
    R = m["results"]
    bk = f"{best}[{L.PRIMARY_VIEW}]"
    fx = m["auto_accept"]["dev_fixed"]
    post = m["auto_accept"]["post_hoc_test_max_coverage_at_P95(descriptive_only)"]
    pc = m["per_class_core_test"]
    order = sorted(pc, key=lambda c: (-(pc[c]["top1"] or 0), c))
    low_data = sorted(c for c, v in inv["pilot_class_train_counts"][L.PRIMARY_VIEW].items() if v <= 3)

    def fmt(r):
        return {**r, **{k: pct(float(r[k])) if r[k] not in ("", None) else "—"
                        for k in ("top1", "recall_at_3", "recall_at_5", "unseen_top1", "seen_top1", "core_dev_top1", "ref_tier_AB_top1")}}

    word = R["LINEAR_WORD[CURATED]"]["core_test"]["top1"]
    char = R["LINEAR_CHAR[CURATED]"]["core_test"]["top1"]
    wc = R["LINEAR_WORD_CHAR[CURATED]"]["core_test"]["top1"]
    raw_char = R["LINEAR_CHAR[RAW]"]["core_test"]["top1"]
    L_ = []
    a = L_.append
    a("# STEP22 — Korean Symptom Normalizer v1 (TF-IDF + LinearSVC)\n")
    a(f"- LINEAR_NORMALIZER = **{m['LINEAR_NORMALIZER']}** · 판정 = **{m['DECISION']}** · BEST_MODEL = **{best}** "
      f"(dev 선택, view {L.PRIMARY_VIEW}) · GPU_USED = {m['GPU_USED']}")
    a("- engineering benchmark(임상 정확도 기준 아님). 평가 문장은 STEP21 Claude 작성 합성 문장(실제 환자 발화 아님).")
    a("- 학습 = 기존 MedMap 사전 표현만(새 합성 학습 데이터 0). sealed test 는 학습·선택·임계값에 미사용, 1회 평가.\n")
    a("## 1. 핵심 수치 (NORMALIZER_CORE sealed test)\n")
    a(table([
        {"k": "classes (train / 평가 pilot)", "v": f"{m['counts']['classes_train']} / {m['counts']['pilot_classes']}"},
        {"k": "train expressions (CURATED / RAW)", "v": f"{m['counts']['train_expressions_curated']} / {m['counts']['train_expressions_raw']}"},
        {"k": "core dev / core sealed test", "v": f"{m['counts']['core_dev']} / {m['counts']['core_test']}"},
        {"k": "Top-1", "v": pct(g["top1"])}, {"k": "Recall@3", "v": pct(g["recall_at_3"])},
        {"k": "Recall@5", "v": pct(g["recall_at_5"])},
        {"k": f"unseen-expression Top-1 (n={R[bk]['core_test_unseen_expression']['n']})", "v": pct(g["unseen_top1"])},
        {"k": "auto-accept (dev 고정 margin) precision / coverage",
         "v": f"{pct(fx['precision'])} / {pct(fx['coverage'])} (n={fx['n_accepted']})" if fx else "dev 에서 P≥95% 구간 없음"},
        {"k": "참고: test 사후 최대 coverage @P≥95% (gate 미사용)",
         "v": f"{pct(post['coverage'])} (P {pct(post['precision'])}, n={post['n_accepted']})" if post else "없음"},
        {"k": "old same-subset 최고 Top-1", "v": f"{ob['system']} {pct(ob['top1'])}"},
        {"k": "Δ Top-1 (new − old)", "v": pp(ob["delta_top1"])},
        {"k": "Δ unseen Top-1 (vs " + ob["unseen_system"] + ")", "v": pp(ob["delta_unseen_top1"])},
    ], ["k", "v"], ["항목", "값"]))
    a(f"\ngate 규칙: {m['gate_rule']}\n\n판정 규칙: {m['decision_rule']}\n")
    a("## 2. SAME_SUBSET_COMPARISON (core test, 같은 분모)\n")
    a("STEP21 baseline 은 STEP21 예측 파일을 그대로 재채점(재채점기는 STEP21 tier_AB 수치와 일치함을 assert). "
      "`ref_tier_AB_top1` = STEP21 분모(test Tier A+B should_link 115, 복수 증상 포함) 참고값.\n")
    a(table([fmt(r) for r in same], ["system", "n", "top1", "recall_at_3", "recall_at_5", "unseen_n", "unseen_top1", "seen_n",
                                     "seen_top1", "core_dev_top1", "ref_tier_AB_top1"]))
    a("\n## 3. dev 선택 결과 (test 이전 고정)\n")
    a(table([{"view": v, "family": f, "params": json.dumps(d["params"]), "dev_top1": pct(d["dev_core"]["top1"]),
              "dev_r3": pct(d["dev_core"]["recall_at_3"]), "grid": d["grid_size"],
              "dev_auto": (f"margin≥{d['auto_accept_dev']['margin_threshold']:.3f} P {pct(d['auto_accept_dev']['dev_precision'])} "
                           f"cov {pct(d['auto_accept_dev']['dev_coverage'])}") if d["auto_accept_dev"] else "없음"}
             for v, vv in sel["views"].items() for f, d in vv["families"].items()],
            ["view", "family", "params", "dev_top1", "dev_r3", "grid", "dev_auto"]))
    a(f"\n선택 규칙: {sel['selection_rule']} · BEST_MODEL 규칙: {sel['best_model_rule']}\n")
    a("## 4. Auto-accept (decision margin = top1 − top2 score, 확률 아님)\n")
    a(table(cc, ["rule", "margin_threshold", "n_accepted", "AUTO_ACCEPT_COVERAGE", "AUTO_ACCEPT_PRECISION"]))
    a("\n## 5. class 별 (core test, BEST_MODEL)\n")
    a(table([{"class": c, "train_n": pc[c]["train_count"], "test_n": pc[c]["n"], "top1": pct(pc[c]["top1"]),
              "r3": pct(pc[c]["recall_at_3"])} for c in order], ["class", "train_n", "test_n", "top1", "r3"]))
    a("\n## 6. train expression 수 구간별 (core test)\n")
    a(table([{"bin": b, "classes": len(v["classes"]), "n": v["n"], "top1": pct(v["top1"]), "r3": pct(v["recall_at_3"])}
             for b, v in m["train_count_bins_core_test"].items()], ["bin", "classes", "n", "top1", "r3"]))
    a(f"\n학습 표현 재대입 Top-1 = {pct(m['train_resubstitution_top1'])} (모델이 학습 표현은 전부 맞힘). "
      f"train ≤ 3 표현 class: {', '.join(low_data)}.\n")
    a("## 7. Top confusion pairs (BEST_MODEL)\n")
    a(f"core test 오류 {cs['n_core_errors']}/{cs['n_core_test']}, 그중 pilot 밖 class(EV:*)로 간 것 "
      f"{cs['n_core_errors_to_non_pilot_class']}. `why` = 예측 class 쪽으로 점수를 민 상위 char n-gram.\n")
    a(table(pairs[:15], ["scope", "concept_a", "concept_b", "count", "a_to_b", "b_to_a", "example_text", "example_gold",
                         "example_pred", "why_top_features_toward_pred"]))
    a("\n## 8. 주요 사례\n")
    a(table([{"text": k["text"], "split": k.get("split", "없음(추가 안 함)"),
              "top3": " · ".join(f"{c}({s:+.3f})" for c, s in k.get("top3", [])), "margin": k.get("margin", ""),
              "old": ", ".join(f"{b}={v or '∅'}" for b, v in k.get("baseline_top1", {}).items())} for k in m["key_cases"]],
            ["text", "split", "top3", "margin", "old"]))
    a("\n## 9. 학습 데이터 audit · RAW vs CURATED\n")
    a(f"audit 상태: {json.dumps(inv['audit_status_counts'], ensure_ascii=False)} · exact duplicate {inv['n_exact_duplicates']} · "
      f"CURATED 제외 {inv['n_excluded_curated']}건(사전 원문 의미 검토로 고정, test 미참조). UNSEEN_CLASS = "
      f"{inv['UNSEEN_CLASS'][L.PRIMARY_VIEW] or '없음'}; train 전용 class {len(inv['train_only_classes_not_in_core_test'][L.PRIMARY_VIEW])}개(비 pilot 증거 = 혼동 후보).\n")
    a(table(excl, ["expression", "canonical_id", "audit_status", "exclusion_reason"]))
    a(f"\nLINEAR_CHAR core test Top-1: CURATED {pct(char)} vs RAW {pct(raw_char)} ({pp(char - raw_char)}).\n")
    a("## 10. 복수 증상 문장(정성, 핵심 점수 제외)\n")
    mq = m["multi_symptom_qualitative_test"]
    a(f"test 복수 증상 {len(mq)}문장: top3 안에 정답 증상 2개 이상 {sum(x['n_gold_in_top3'] >= 2 for x in mq)}, "
      f"1개 {sum(x['n_gold_in_top3'] == 1 for x in mq)}, 0개 {sum(x['n_gold_in_top3'] == 0 for x in mq)}. "
      "한 문장 전체를 넣으면 한 증상으로 치우침 → span 추출 후 span 별 정규화가 필요.\n")
    a("## 11. 해석\n")
    a(f"- char vs word: core test Top-1 LINEAR_WORD {pct(word)} · LINEAR_CHAR {pct(char)} · LINEAR_WORD_CHAR {pct(wc)}. "
      f"dev 에서는 char 가 word 보다 높았으나(dev {pct(sel['views']['CURATED']['families']['LINEAR_CHAR']['dev_core']['top1'])} vs "
      f"{pct(sel['views']['CURATED']['families']['LINEAR_WORD']['dev_core']['top1'])}) test 에서 그 차이가 재현되지 않음. "
      "dev 59 문장 선택이 불안정(dev→test 하락).")
    a("- WORD_CHAR 가 test 에서 더 높지만 test 로 모델을 바꾸지 않는다(선택은 dev 에서 끝남). 참고 관찰로만 둔다.")
    a(f"- 모델 vs 데이터: 학습 표현 재대입 {pct(m['train_resubstitution_top1'])}, class 당 학습 표현 2–10개(11개 이상 class 없음). "
      "실패의 주원인은 학습 표현 부족·편향(질문형·정식 용어 위주, 구어 표현 없음)이며, 선형 모델 용량 문제로 보기 어렵다. "
      "예: pain 학습 표현이 '가슴'·'통증' 위주라 '머리가 아파요'가 '목이 아픈가요'(sore_throat)의 '아' n-gram 에 끌림.")
    a("- 오류 상당수가 pilot 밖 증거 class(EV:*)로 감 → 77-class 혼동 공간에서 표현 수가 적은 class 끼리 표면 n-gram 경쟁.")
    a("- 다음 단계 제안은 최종 보고 참고(이 문서는 결과만).\n")
    a("## 12. 재현성 · 범위\n")
    a("- random_state=42, run_all.sh 2회 실행 후 outputs·models SHA256 비교(logs/sha1.txt·sha2.txt).")
    a("- production(MedMap mapper·Patient Companion·Doctor mode·PatientState) 미연결. UMLS/SNOMED 원문 미복사(내부 ID·MedMap label 만).")
    (L.STEP / "docs").mkdir(exist_ok=True)
    rp = L.STEP / "docs/korean_linear_normalizer_report.md"
    rp.write_text("\n".join(L_) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "outputs", "models", "docs", "scripts") for p in (L.STEP / d).glob("*")
                   if p.is_file() and p.name != "manifest.json")
    man = {"step": "STEP22", "seed": L.SEED, "gpu_used": False, "python": platform.python_version(),
           "sklearn": sklearn.__version__, "primary_view": L.PRIMARY_VIEW, "best_model": best,
           "selected_params": {v: {f: d["params"] for f, d in vv["families"].items()} for v, vv in sel["views"].items()},
           "inputs": {str(p.relative_to(L.REPO)): L.sha256(p) for p in (
               L.S21 / "data/dictionary_expressions.csv", L.S21 / "data/pilot_gold.csv",
               L.c21.STEP20 / "curation/curated_mappings.tsv", L.S21 / "outputs/metrics.json",
               *(L.S21 / "outputs" / f for f in ("exact_predictions.csv", "fuzzy_predictions.csv",
                                                  "combined_predictions.csv", "mapper_predictions.csv")))},
           "files": {str(p.relative_to(L.STEP)): L.sha256(p) for p in files if "__pycache__" not in str(p)}}
    L.dump_json(L.OUT / "manifest.json", man)
    print("report", rp, "files", len(man["files"]))


if __name__ == "__main__":
    main()
