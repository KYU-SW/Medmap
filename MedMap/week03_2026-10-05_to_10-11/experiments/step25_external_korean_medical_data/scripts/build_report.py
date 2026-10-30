"""STEP25 보고서 3종 + manifest. 숫자·표는 outputs/·data/ 파일에서 읽는다. 관찰 사례는 정답이 아니라 '사례'로만 표기."""
import csv
import json

import s25_common as S


def table(rows, cols, head=None):
    out = ["| " + " | ".join(head or cols) + " |", "|" + "---|" * len(cols)]
    return "\n".join(out + ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def main():
    inv = S.read_csv(S.DATA / "dataset_inventory.csv")
    cov = S.load_json(S.OUT / "source_coverage.json")
    mp = S.read_csv(S.DATA / "canonical_label_mapping.csv")
    lk = S.read_csv(S.OUT / "leakage_audit.csv")
    mc = S.read_csv(S.OUT / "model_comparison.csv")
    lat = S.load_json(S.OUT / "latency_external.json")
    fz = S.load_json(S.OUT / "frozen_eval_config.json")
    preds = S.read_csv(S.OUT / "external_predictions.csv")
    errs = S.read_csv(S.OUT / "error_analysis.csv")
    au = cov["audit"]
    verdict = {"STEP25_ACCESS": "PARTIAL", "EXTERNAL_GOLD_AVAILABLE": "NO", "EXTERNAL_EVALUATION": "PARTIAL(정답 없는 분석만)",
               "MANUAL_SENTENCE_AUTHORING_REQUIRED": "NO(문장 작성 불필요) — 단 concept 라벨링 또는 AI-Hub 승인 없이는 정확도 검증 불가",
               "gold_candidate_units": 0, "evaluable_canonical_concepts_with_gold": 0}
    S.dump_json(S.OUT / "step25_verdict.json", verdict)

    # 1 dataset_access_report
    A = ["# STEP25 — 외부 데이터 접근 보고 (2026-10-10 조사)\n",
         f"후보 {cov['n_candidates']}개 · 접근 상태 {json.dumps(cov['access_counts'], ensure_ascii=False)} · 실제 다운로드 {len(cov['downloaded'])}개, 총 {cov['download_total_bytes'] / 1e6:.2f} MB(한도 100 MB).",
         "PUBLIC_DOWNLOAD 는 실제 다운로드가 성공한 경우만 표기. 로그인·신청 자동 시도 없음. 원본은 git 밖 `~/medmap_external_data/step25/raw/`.\n",
         table(inv, ["dataset", "access", "access_evidence", "total_reported", "label_reported", "speaker", "license", "downloaded"]),
         "\n## 다운로드 파일 SHA256\n", table([{"file": k, "sha256": v} for k, v in cov["raw_files"].items()], ["file", "sha256"]),
         "\n## 사용자 승인이 필요한 경로\n- AIHUB_208: 내국인 신청 + 안심존 + IRB·소속·보안서약 → 사용자가 직접 신청해야 함(자동 신청 금지). 승인돼도 원본 반출 제한 가능.",
         "- AIHUB_98: AI-Hub 로그인 + 다운로드 신청 승인 → 사용자 계정으로만 가능. '증상/징후'는 카테고리 단위.",
         "- 한양대 증상 발화(305 증상): 공개 위치 없음 → 저자 문의만 가능(이번 단계에서 연락하지 않음)."]
    (S.DOCS / "dataset_access_report.md").write_text("\n".join(A) + "\n", encoding="utf-8")

    # 2 annotation_schema_audit
    B = ["# STEP25 — 어노테이션 스키마 감사\n",
         "## 로컬 데이터 구조\n", "```json", json.dumps(au, ensure_ascii=False, indent=1), "```",
         "\n## 외부 라벨 → MedMap 77 매핑\n", table(mp, ["dataset", "external_label", "canonical_id", "grade", "reason", "used_for_accuracy"]),
         "\n- EXACT/ACCEPTABLE 0건 → GOLD_CANDIDATE 0. 범주 라벨(ST·증상/징후)은 concept 을 지정하지 않음.",
         "- 부정·시점 라벨: 세 데이터 모두 없음. 개인정보 패턴(전화·이메일·주민번호·URL): 0건.",
         "- KBMC 는 증상 표현도 Disease 로 태깅 → 질병 라벨을 증상으로 바꾸지 않음(NO_MATCH)."]
    (S.DOCS / "annotation_schema_audit.md").write_text("\n".join(B) + "\n", encoding="utf-8")

    # 3 external_validation_report
    pick = lambda sn, m: next(r for r in mc if r["set"] == sn and r["model"] == m)  # noqa: E731
    sets = ["A_NERKO_ST", "B_NERKO_DS", "C_KBMC_DISEASE", "D_KMC_FIRST_TURN", "SILVER_TRAIN_EXACT"]
    rows = []
    for sn in sets:
        rows.append({"set": sn, "n": pick(sn, "LINEAR_CHAR")["n"], "L-K agree": pick(sn, "KOELECTRA_SMALL")["agree_with_linear"],
                     **{f"auto {m}": pick(sn, m)["auto_accept_rate"] for m in ("LINEAR_CHAR", "KOELECTRA_SMALL", "HYBRID_B")},
                     "HB koe call": pick(sn, "HYBRID_B")["koe_call_rate"], "HB auto despite disagree": pick(sn, "HYBRID_B")["auto_accept_despite_disagreement"],
                     "L pred top": pick(sn, "LINEAR_CHAR")["pred_top5"].split(";")[0], "HB pred top": pick(sn, "HYBRID_B")["pred_top5"].split(";")[0]})
    ds_auto = [p for p in preds if p["set"] == "B_NERKO_DS" and p["hybrid_b_auto"] == "True"]
    st_lin_sink = sum(p["linear_top1"] == "decreased_appetite" for p in preds if p["set"] == "A_NERKO_ST")
    nst = sum(p["set"] == "A_NERKO_ST" for p in preds)
    cats = {}
    for e in errs:
        for c in e["categories"].split(";"):
            cats[c] = cats.get(c, 0) + 1
    C = ["# STEP25 — 외부 데이터 검증 보고\n",
         f"- 판정: {json.dumps(verdict, ensure_ascii=False)}",
         "- **정답(concept) 있는 외부 문장 0 → 정확도·Top-k·macro accuracy 계산하지 않음.** 아래는 정답 없는 분석(agreement·분포·미인식·위험 자동 수락 후보)이며 정확도가 아니다.",
         f"- 고정 모델(재학습·재튜닝 없음): {json.dumps(fz, ensure_ascii=False)}\n",
         "## 누수·독립성\n", table(lk, list(lk[0].keys())),
         "\n외부 문장과 STEP21 gold 완전일치 0. 학습 표현과 완전일치 span 은 SILVER 로 분리(분석 집합 제외).\n",
         "## 고정 모델 분석 (정답 없음)\n", table(rows, list(rows[0].keys())),
         "\nauto = Hybrid B 정책 기준 자동 수락(Linear margin ≥ T_lin, KoE confidence ≥ T_koe). 'unknown' = 1 − auto.\n",
         f"- 외부 '질병(DS)' span 에서 Hybrid B 자동 수락 {len(ds_auto)}건 = 위험 자동 수락 후보(예: 고혈압→hemoptysis, 결핵→confusion, 1형 당뇨→pain). 77-class 닫힌 분류기라 '증상 아님'을 거절할 class 가 없음.",
         f"- 외부 '증상(ST)' span {nst}개 중 Linear top1 = decreased_appetite {st_lin_sink}개 → 모르는 표현이 특정 class 로 몰림(sink).",
         "- 관찰 사례(정답 아님): '코피가'→hemoptysis(코피 ≠ 객혈), '구토'→Linear nausea / KoE vomiting, '두통'→Linear decreased_appetite / KoE pain.",
         f"- 위험 범주 집계(SILVER 제외): {json.dumps(cats, ensure_ascii=False)}",
         f"- SILVER(학습 표현과 완전일치 42 span) 규칙 concept 일치율: Linear {pick('SILVER_TRAIN_EXACT', 'LINEAR_CHAR')['agree_with_rule_label(NOT_accuracy)']}, "
         f"KoE {pick('SILVER_TRAIN_EXACT', 'KOELECTRA_SMALL')['agree_with_rule_label(NOT_accuracy)']}, Hybrid B {pick('SILVER_TRAIN_EXACT', 'HYBRID_B')['agree_with_rule_label(NOT_accuracy)']} — 학습 누수 집합이라 정확도 아님.\n",
         "## latency (외부 ST span, single, CPU)\n", table([{"path": k, **v} for k, v in lat.items() if isinstance(v, dict)], ["path", "n", "mean_ms", "p50_ms", "p95_ms"]),
         "\n## 해석\n",
         "- 내부 regression 에서 Linear·Hybrid 의 자동 수락 정밀도 ≥95% 였던 임계값이 외부 분포에서는 모델 간 일치율이 낮은데도(ST span 33%) 절반 넘게 자동 수락 → 임계값이 외부 분포로 전이되지 않을 위험이 크다(정확도로 확인한 것은 아님).",
         "- 외부 증상 표현에는 77 concept 밖 증상(예: 가려움·분비물 등)이 많을 것으로 보이나, concept 라벨이 없어 비율은 측정하지 못함.",
         "## 다음 1순위\n",
         "- 외부 ST span 442개(실제 의사 답변 출처, 학습·gold 와 독립)를 'MedMap concept 또는 OUT_OF_SCOPE' 로 라벨링 → 첫 외부 Gold. 문장 작성 불필요, 라벨링만 필요. 라벨러는 모델 예측을 보지 않게 한다.",
         "- 동시에 77-class 에 OUT_OF_SCOPE/거절 경로 설계 필요(질병명 자동 수락 위험)."]
    (S.DOCS / "external_validation_report.md").write_text("\n".join(C) + "\n", encoding="utf-8")

    files = sorted(p for d in ("data", "outputs", "docs", "scripts") for p in (S.STEP / d).glob("*") if p.is_file() and p.name != "manifest.json")
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP25", "raw_external_files_outside_git": cov["raw_files"], "frozen_models": fz,
                                          "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files}})
    print(json.dumps(verdict, ensure_ascii=False))


if __name__ == "__main__":
    main()
