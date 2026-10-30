"""STEP28.6 판정 + 보고서 + manifest(숫자는 outputs/·data/ 에서 읽음).

[판정 규칙 — FULL 평가 전 고정, 2026-10-11]
 STEP28_6_RESULT
  LINKING_FEASIBLE : (A+B 모두 완료) G2 이상(A·B 일치) 고유 신규 concept ≥ 10 · 구별 위반 0 · 비증상 오매핑 위험(최종) ≤ STEP28.5 병렬(같은 입력)
  PARTIAL          : 신규 concept 이 G1(단일 작성자)에만 있거나, G2 이상 1–9, 또는 위 안전 조건 하나 실패
  NOT_FEASIBLE     : 어느 작성자로도 77 밖 신규 concept 연결 0
  INTERIM          : 작성자 B 또는 조각 일부 미완료(주간 한도) — 위 판정 보류, 단일 작성자 탐색 지표만
 모든 결과는 SILVER(검증 전). 정확도·임상 안전성 주장 없음. 신규 concept MODEL_SUPPORTED=False, 49질환 모델 입력 금지.
"""
import json

import s286_common as S


def table(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join("—" if c in (None, "") else str(c) for c in r) + " |" for r in rows])


def main():
    m = S.load_json(S.OUT / "linking_metrics.json")
    iso = S.load_json(S.OUT / "authoring_isolation_check.json")
    newc = S.read_csv(S.OUT / "new_concept_candidates.csv")
    fa = m["failure_codes(silver unresolved)"]
    full = m["mode"].startswith("FULL") and m["by_source"]["SILVER442"] == 442 and m["by_source"]["WEAKNON903"] == 903
    g = m["new_distinct_concepts_by_grade"]
    g2 = g["G3_SILVER_AUDITED"] + g["G2_SILVER_AGREED"]
    risk = m["nonsymptom_mismapping_risk(weak-non)"]
    if not full:
        res = "INTERIM"
    elif g2 >= 10 and m["distinction_violations"] == 0 and risk["final"] <= risk["step28_5_parallel_on_same_inputs"]:
        res = "LINKING_FEASIBLE"
    elif g2 or g["G1_SINGLE_AUTHOR"]:
        res = "PARTIAL"
    else:
        res = "NOT_FEASIBLE"
    verdict = {"STEP28_6_RESULT": res, "mode": m["mode"], "new_distinct_concepts_by_grade": g, "PRODUCTION_READY": "NO", "SILVER_ONLY": True,
               "isolation": iso["ISOLATION"], "llm_list_price_usd_total": m["llm_list_price_usd_total(청구액 아님)"], "rules": __doc__}
    S.dump_json(S.OUT / "step28_6_verdict.json", verdict)
    seen, nrows = set(), []
    for r in newc:
        k = (r["concept_id"], r["grade"])
        if k in seen:
            continue
        seen.add(k)
        ex = [x["korean"] for x in newc if x["concept_id"] == r["concept_id"]][:3]
        nrows.append([r["concept_id"], r["english"], ", ".join(ex), r["grade"], r["check"][:60], r["audit"][:60]])
    A = m["author_A"]["silver"]
    lat = m["latency"]
    md = f"""# STEP28.6 — LLM-Assisted Korean-English Medical Concept Linking

- **STEP28_6_RESULT = {res}** · 모드 = {m['mode']} · PRODUCTION_READY = NO · 모든 대응·연결 = **SILVER(검증 전)** — 정확도·임상 안전성 주장 없음.
- 격리 작성: `claude -p --restricted --tools Read,Write`(작업 폴더 `~/medmap_step28_6_ws/`), 작성자 A = opus · B = sonnet. 격리 검사 = {iso['ISOLATION']}
  (세션별 위반: {S.dumps({k: v['violations'] for k, v in iso['sessions'].items()})}). LLM 에는 한국어 표현·지시문만 전송(모델 예측·77 목록·SNOMED/UMLS 문자열·MDRKOR 없음),
  감사자에게는 한국어 + HPO(공개) 이름·정의만.
- LLM 사용량(정가 환산, 청구액 아님): ${m['llm_list_price_usd_total(청구액 아님)']} · 호출 {m['llm_calls']} (`outputs/llm_usage.csv`). 승인 상한 $15.
- 판정 규칙: `scripts/build_report.py` 문서열. 연결·범주 규칙: `scripts/link_english_to_ontology.py`(작성 결과를 보기 전 고정).

## 1. 수치(Silver = STEP25 BERT-NER-KO 증상 span, 지금까지 작성된 입력 {m['by_source']['SILVER442']}/442)

| 항목 | 작성자 A | 작성자 B |
|---|---|---|
| 영어 의료 용어로 변환 | {A['converted_to_english']}/{A['n']} | {(m['author_B'] or {}).get('silver', {}).get('converted_to_english', '—')} |
| ontology 실제 ID 까지 연결(완전일치, 증상형) | {A['linked_to_ontology_symptom']} | {(m['author_B'] or {}).get('silver', {}).get('linked_to_ontology_symptom', '—')} |
| 77 밖 신규 후보(입력 / 고유 concept) | {A['new_inputs']} / {A['new_distinct_concepts']} | {(m['author_B'] or {}).get('silver', {}).get('new_inputs', '—')} / {(m['author_B'] or {}).get('silver', {}).get('new_distinct_concepts', '—')} |
| 범주 | {S.dumps(A['categories'])} | {S.dumps((m['author_B'] or {}).get('silver', {}).get('categories', '—'))} |

최종(A·B 통합): {S.dumps(m['final(silver)'])} · 신규 등급별 고유 concept: {S.dumps(g)}
한→영 연결률(같은 입력): STEP28.5 병렬 {m['ko_en_link_rate(silver)']['step28_5_parallel']} → STEP28.6 A {m['ko_en_link_rate(silver)']['step28_6_A_exact_ontology']}
비증상 오매핑 위험(weak-non): {S.dumps(risk)} · 작성자 충돌 {m['author_conflicts']} · STEP28.5 와 기존 concept 이 다른 의미 충돌 {m['semantic_conflicts_vs_step28_5']} · 구별 위반 {m['distinction_violations']}

## 2. 77 밖 신규 증상 후보(SILVER — NEW_ONTOLOGY_CANDIDATE, MODEL_SUPPORTED=False)

{table(nrows, ['concept', '영어(작성자)', '한국어 예', '등급', '검증기 판정', '감사'])}

## 3. 연결 실패 원인(Silver, 미해결)

{S.dumps(fa)} — `outputs/failure_analysis.csv`

## 4. 처리 시간

- LLM 작성(오프라인 단계): 230 행당 {lat['llm_authoring_seconds_per_230_rows']} s
- 런타임(대응표 조회 + ontology 완전일치 + 검증, CPU, 조상 계산 메모 warm): p50 {lat['p50_ms']} ms · p95 {lat['p95_ms']} ms (n {lat['n']}). {lat['note']}

## 5. 변경 기록(공개)

- 연결·범주 규칙은 작성 결과를 보기 전에 고정했고 이후 바꾸지 않았다. 속도 측정용으로 (a) 유사 일치 개수 세기를 생략한 런타임 경로(판정 동일 확인 = {lat.get('runtime_path_same_category_as_analysis_path')}) (b) STEP28 검증기의 조상 계산 메모(STEP28 코드 무수정)를 추가했다.
- 주간 한도: 2026-10-11 02:34 KST 작성자 A c01 은 출력 완료 후 마지막 응답에서 한도 메시지, B c01 은 시작 즉시 한도(비용 0, `logs/authoring/failed_weekly_limit/` 보존). 해제 2026-10-15 01:00 KST.

## 6. 답(현재 모드 기준)

- 변환: 작성자 A 가 {A['n']} 표현 중 {A['converted_to_english']} 개를 영어 의료 용어로 변환.
- ontology ID 연결: 증상형 {A['linked_to_ontology_symptom']} 개(완전일치만, 부분 일치는 연결로 안 셈).
- 77 밖 신규: 입력 {A['new_inputs']} · 고유 concept {A['new_distinct_concepts']} (작성자 A 단독 = G1, 확정 아님).
- 코피: `코피가` → epistaxis → HP:0000421(77 밖, 기존 EV:E_178 '비정상 출혈·멍'의 하위로 기록) — 객혈·토혈로 바뀌지 않음. 단 단일 작성자·감사 전이라 SILVER G1.
- 위험: 작성자 충돌·감사 반려·의미 충돌·비증상 오매핑은 §1. B·감사가 없으면 '같은 오류' 여부를 볼 수 없다.
- 다음 조건: (1) 작성자 B·나머지 조각·HPO 감사 완료(G2·G3) (2) 사람 검토 Gold 소량으로 G3 후보의 실제 일치 확인 (3) 신규 concept 의 질환 모델 사용은 학습 데이터·재검증 전 금지 (4) 대응표 밖 새 표현은 LLM 이 필요 — 병원 오프라인 원칙상 사전 작성 대응표만 런타임 사용.
"""
    (S.DOCS / "llm_assisted_linking_report.md").write_text(md, encoding="utf-8")
    files = sorted([p for p in S.DATA.glob("*") if p.is_file()] + [p for p in S.OUT.glob("*") if p.is_file() and p.name != "manifest.json"]
                   + list((S.STEP / "scripts").glob("*.py")) + list((S.STEP / "scripts").glob("*.sh")) + list(S.DOCS.glob("*.md")))
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP28_6_llm_assisted_linking", "verdict": {k: v for k, v in verdict.items() if k != "rules"},
                                          "files_sha256": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files},
                                          "workspace_files_sha256": {str(p.relative_to(S.WS)): S.sha256(p) for p in sorted(S.WS.rglob("*")) if p.is_file()},
                                          "local_only": ["data/ontology_links.csv·new_concept_candidates.csv(SNOMED/UMLS id·이름 일부)"]})
    print(S.dumps({k: v for k, v in verdict.items() if k != "rules"}))


if __name__ == "__main__":
    main()
