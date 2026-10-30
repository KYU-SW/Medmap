"""STEP28.5 판정 + 보고서 + manifest. 숫자는 outputs/·data/ 에서 읽는다.

[판정 규칙 — evaluate_retrieval 실행 전 고정]
 KOREAN_ENGLISH_BRIDGE: AVAILABLE = 77 밖 증상형 concept 으로 가는 한·영 연결(ID 근거)이 10 개 이상, 또는 다국어 모델 gate 통과 ·
   PARTIAL = 연결은 있으나 전부 77 안 증상·비증상(질환·검사·약재)으로만 감 · MISSING = 연결 0
 NEW_CONCEPT_FOUND = PARALLEL 에서 한국어 입력으로 찾은 고유 신규 concept 후보 수 · VERIFIED_NEW_CONCEPT_MAPPINGS = 그중 EXACT/ACCEPTABLE
 UNKNOWN_PRESERVATION = PASS ⇔ PARALLEL 원문 보존 100% · UNKNOWN 에 표시 후보 0 · UNKNOWN 에 concept 0
 STEP28_5_RESULT: BILINGUAL_RETRIEVAL_FEASIBLE = BRIDGE AVAILABLE · 검증된 신규 ≥ 10 · UNKNOWN PASS · PARALLEL 구별 위반 0
   PARTIAL = 검증된 신규 1–9, 또는 BRIDGE AVAILABLE 이지만 검증 신규 0
   BLOCKED = 검증된 신규 0 이고 BRIDGE ≠ AVAILABLE(77 밖 신규 증상으로 가는 한·영 경로 자체가 없음 — 77 안 개선은 별도 보고)
 PRODUCTION_READY = NO
"""
import collections
import csv

import s285_common as S


def table(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join("—" if c is None else str(c) for c in r) + " |" for r in rows])


def main():
    summ = S.load_json(S.OUT / "retrieval_summary.json")
    met = summ["metrics"]
    gate = S.load_json(S.OUT / "multilingual_model_gate.json")
    lat = S.load_json(S.OUT / "latency.json")
    inv = S.load_json(S.OUT / "resource_inventory.json")
    sx = S.load_json(S.OUT / "span_extraction_summary.json")
    dc = S.load_json(S.OUT / "distinction_checks.json")
    cov = S.read_csv(S.OUT / "bilingual_link_coverage.csv")
    out_sym = sum(int(c["outside_77_symptom_type"]) for c in cov)
    linked = sum(int(c["linked_to_concept_id"]) for c in cov)
    bridge = "AVAILABLE" if out_sym >= 10 or gate["MODEL_PATH_ENABLED"] else "PARTIAL" if linked else "MISSING"
    newc = S.read_csv(S.OUT / "new_concept_candidates.csv")
    par_new = {r["candidate_concept_id"] for r in newc if r["mode"] == "PARALLEL"}
    ver = {r["candidate_concept_id"] for r in newc if r["mode"] == "PARALLEL" and r["mapping_decision"] in ("EXACT", "ACCEPTABLE")}
    res_rows = S.read_csv(S.DATA / "retrieval_results.csv")
    par = [r for r in res_rows if r["mode"] == "PARALLEL"]
    unk_ok = (met["PARALLEL"]["raw_preservation_rate"] == 1.0 and not any(r["display"] for r in par if r["category"] == "UNKNOWN_SYMPTOM")
              and not any(r["concept"] for r in par if r["category"] == "UNKNOWN_SYMPTOM"))
    unk = "PASS" if unk_ok else "FAIL"
    if bridge == "AVAILABLE" and len(ver) >= 10 and unk == "PASS" and met["PARALLEL"]["distinction_violations"] == 0:
        res = "BILINGUAL_RETRIEVAL_FEASIBLE"
    elif 1 <= len(ver) <= 9 or (bridge == "AVAILABLE" and not ver):
        res = "PARTIAL"
    else:
        res = "BLOCKED"
    verdict = {"STEP28_5_RESULT": res, "KOREAN_ENGLISH_BRIDGE": bridge, "NEW_CONCEPT_FOUND": len(par_new), "VERIFIED_NEW_CONCEPT_MAPPINGS": len(ver),
               "UNKNOWN_PRESERVATION": unk, "PRODUCTION_READY": "NO", "MODEL_PATH_ENABLED": gate["MODEL_PATH_ENABLED"], "rules": __doc__}
    S.dump_json(S.OUT / "step28_5_verdict.json", verdict)

    keys = ["units", "EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE", "ko_en_link_success", "verified_new", "candidate_resolved_to_existing",
            "UNKNOWN_SYMPTOM", "UNCERTAIN", "NON_SYMPTOM", "nonsymptom_auto_mapping_risk(weak-non 903)", "unsupported_display", "distinction_violations",
            "raw_preservation_rate", "two_source_agreement"]
    mt = table([[k] + [met[m].get(k) for m in ("A_STEP28", "KO_ONLY", "EN_ONLY", "PARALLEL")] for k in keys], ["지표", "A STEP28", "B 한국어 단독", "C 영어 연결", "D 병렬"])
    smoke = S.read_csv(S.OUT / "smoke_cases.csv")
    st = table([[r["input"], r["span_text"], r["query_ko"], r["polarity"], r["category"], r["concept"] or "—", r["display"] or "—",
                 r["Q1_english_term_linked"], r["Q2_ontology_concept_with_evidence"][:80], r["violations"] or "—"] for r in smoke],
               ["입력", "구문", "검색 구문", "극성", "범주", "concept", "표시", "Q1 영어 용어 연결", "Q2 ontology concept(검증)", "구별 위반"])
    ct = table([[c["source"], c["role"], c["korean_terms"], c["linked_to_concept_id"], c["en_term_exact_ontology_hit"], c["inside_77"], c["outside_77"],
                 c["outside_77_symptom_type"]] for c in cov], ["출처", "역할", "한국어 용어", "concept 연결", "영어 문자열 일치", "77 안", "77 밖", "77 밖 증상형"])
    fc = summ["failure_codes(PARALLEL)"]
    lt = lat["single_input_cpu"]
    pr = table([[p["pair"], p["source"], p["relation"]] for p in dc["pairwise"]], ["쌍", "출처", "관계"])
    md = f"""# STEP28.5 — Korean-English Dual Symptom Concept Retrieval

- **STEP28_5_RESULT = {res}** · KOREAN_ENGLISH_BRIDGE = {bridge} · NEW_CONCEPT_FOUND = {len(par_new)} · VERIFIED_NEW_CONCEPT_MAPPINGS = {len(ver)} · UNKNOWN_PRESERVATION = {unk} · **PRODUCTION_READY = NO**
- 정답 라벨 없음 → 매핑 정확도 아님. Silver 442 는 STEP25–28 에서 여러 번 본 데이터(blind 아님). 판정 규칙 `scripts/build_report.py` 문서열(평가 전 고정).
- 제외: MDRKOR·KCD5(SRL 3) · 외부 API · 신규 다운로드. 기존 모델·STEP20–28 산출물 미수정(STEP28 색인·검증기 read-only 재사용).

## 1. 비교(구문 단위, A 는 입력 단위)

{mt}

## 2. 한국어 → 영어 연결 자원(실측, `outputs/bilingual_link_coverage.csv`)

{ct}

77 밖 증상형으로 가는 연결 = **{out_sym}**. 다국어 모델(siglip2 텍스트) gate: hit@1 {gate['hit@k']['1']} · hit@5 {gate['hit@k']['5']} · hit@10 {gate['hit@k']['10']} (기준 hit@5 ≥ 0.50, 질의 {gate['n_queries']}) → MODEL_PATH_ENABLED = {gate['MODEL_PATH_ENABLED']} (STEP28 xlm-roberta hit@5 {gate['reference_xlmr_step28']['5']}).

## 3. 구문 추출(kiwipiepy 0.23.2, 로컬)

Silver: {S.dumps(sx)}. 대조 규칙 방식(조사 제거 한 덩어리)과 핵어 일치율 {sx['kiwi_vs_rule_head_agree']}.

## 4. Smoke(회귀 확인용 — 이 문장으로 일반화 성능을 주장하지 않음)

{st}

## 5. 개념 구별(영어 색인, `outputs/distinction_checks.json`)

{pr}

MedMap curated id 분리: {S.dumps(dc['medmap_curated_ids_disjoint'])}. 검증기: {S.dumps(dc['validation_checks'])}

## 6. 실패 원인(D 병렬의 UNKNOWN·UNCERTAIN 구문)

{S.dumps(fc)}

- '영어 ontology 에는 개념이 있으나 한국어 연결이 없어 실패' = Silver 전체 **측정 불가**(정답 영어 개념·한·영 대응 자원 없음). smoke 의 코피(=Epistaxis, 지시문이 대응 명시) 1건만 확인: 영어 색인에 있음(HP:0000421·SNOMED 249366005), 한국어 연결 없음.
- LICENSE_RESTRICTION: MDRKOR 를 열지 않아 측정 불가.
- 비증상 자동 매핑 위험(병렬) 근거별: {S.dumps(summ['nonsymptom_risk_evidence_tier(PARALLEL)'])} — `outputs/weak_non_risk.csv`. 신체 부위 단독('머리·입안·손가락·명치')·
  질환명 안의 두통('혈관성 편두통')이 기존 증상으로 연결된 것이 대부분. 사후 확인이며 규칙은 고치지 않았다.

## 7. 속도·자원

{table([[k, x['p50_ms'], x['p95_ms'], x['max_ms']] for k, x in lt.items()], ['경로', 'p50 ms', 'p95 ms', 'max ms'])}

적재 {lat['pipeline_load_seconds']} s · RSS {lat['rss_after_load_mib']} MiB(peak {lat['peak_rss_mib']}) · 한국어 색인 {lat['korean_index_bytes'] / 1e6:.1f} MB · 한·영 연결표 {lat['bilingual_links_bytes'] / 1e6:.1f} MB · STEP28 ontology 색인 {lat['ontology_index_bytes'] / 1e6:.1f} MB(재사용).

## 8. 변경 기록(공개)

- smoke 를 본 뒤 고친 일반 규칙: kiwipiepy 접두사(고-혈압) 처리 · 색인 용어도 질의와 같은 원형 정규화(nkey, 부정 포함 용어 제외) · '-지 못하다' 부정 · 술어가 증상을 담으면 명사 단독 검색 안 함 · 충돌 시 후보 표시 금지 · STEP27 B4 자동수락을 독립 근거로 사용. 이후 규칙 변경 없음. 해당 smoke 결과는 회귀 확인용.
- STEP28 결함 회피: 용어집 라벨 '·' 분리 안 함 · '짧은 입력이 긴 학습 문장 안에 있으면 근거' 규칙을 길이 비율 조건으로 교체 · 제품 매퍼를 한국어 근거에서 제외(구토→오심 오매핑).

## 9. 답

1. **구문 분해**: kiwipiepy 형태소 → 연결어미·종결어미·문장부호에서 절 분리 → 절마다 명사구(핵어 = 마지막 명사)·첫 용언·부정·시점·주체 → 술어 종류별 검색 구문(통증 술어 = '부위 통증', 발생·부정 = 명사, 그 외 = 명사+용언 원형). 실패하면 원문 유지(Silver 실패 {sx['kiwi_failures']}).
2. **한국어 검색**: 기존 증상 연결 {met['KO_ONLY']['EXISTING_CANONICAL']} + 통증·부위 {met['KO_ONLY']['EXISTING_COMPOSITE']} (STEP28 {met['A_STEP28']['EXISTING_CANONICAL']} + {met['A_STEP28']['EXISTING_COMPOSITE']}). 한국어 색인에 77 밖 증상 행이 0 이라 신규 concept 은 원리상 찾을 수 없다.
3. **영어 query 출처**: 같은 MedMap/DDXPlus 레코드의 영어 이름(77 증상명·49 질환명)과 STEP20 curated id 뿐. 번역 생성 없음. 그래서 영어 경로는 기존 77·질환으로만 간다(77 밖 증상형 {out_sym}).
4. **병렬 vs 한국어 단독**: §1 표 — 병렬은 한국어 단독 대비 기존 연결 {met['PARALLEL']['EXISTING_CANONICAL'] - met['KO_ONLY']['EXISTING_CANONICAL']:+d}, 두 출처 일치 {met['PARALLEL']['two_source_agreement']}. 신규 concept 은 둘 다 0.
5. **새 증상 concept**: 한국어 입력에서 {len(par_new)}(검증 {len(ver)}). 영어 색인 자체는 Epistaxis 등 77 밖 concept 을 갖고 있다(STEP28 확인).
6. **중복**: 영어 쪽 후보가 기존 concept 으로 해소된 수 {met['PARALLEL']['candidate_resolved_to_existing']} — 신규로 만들지 않음. 신규 ID 생성 0.
7. **잘못된 연결 위험**: 비증상 903 자동 매핑 위험 {met['A_STEP28']['nonsymptom_auto_mapping_risk(weak-non 903)']}(STEP28) → {met['PARALLEL']['nonsymptom_auto_mapping_risk(weak-non 903)']}(병렬) · 근거 없는 표시 {met['A_STEP28']['unsupported_display']} → {met['PARALLEL']['unsupported_display']} · 구별 위반 {met['A_STEP28']['distinction_violations']} → {met['PARALLEL']['distinction_violations']}.
8. **가장 큰 병목**: BILINGUAL_BRIDGE_MISSING — 77 밖 증상을 가리키는 한국어 용어도, 한·영 대응표도 허용 자원에 없다. 로컬 다국어 모델 2종(xlm-roberta-base, siglip2)은 기존 라벨로도 gate 미달.
9. **속도**: 병렬 p95 {lt['PARALLEL']['p95_ms']} ms(CPU) — 실용 범위. 다국어 모델 경로는 미사용이라 포함 안 됨.
10. **STEP29**: `docs/step29_handoff.md` — 이번 구문 추출 출력(구문·극성·시점·주체·위치)을 그대로 입력으로, 정규화는 이 검색기, 부정 범위·시점 적용 범위·주체 판정을 NLU 가 담당.
"""
    (S.DOCS / "bilingual_retrieval_report.md").write_text(md, encoding="utf-8")
    files = sorted([p for p in S.DATA.glob("*") if p.is_file()] + [p for p in S.OUT.glob("*") if p.is_file() and p.name != "manifest.json"]
                   + list((S.STEP / "scripts").glob("*.py")) + list((S.STEP / "scripts").glob("*.sh")) + [S.STEP / "run_all.sh"] + list(S.DOCS.glob("*.md")))
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP28_5_bilingual_symptom_retrieval", "verdict": {k: v for k, v in verdict.items() if k != "rules"},
                                          "files_sha256": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files},
                                          "local_only_licensed": ["index/*(UMLS KOR·SNOMED·HPO 유래)", "data/retrieval_results.csv(UMLS·SNOMED id·이름 일부)"]})
    print(S.dumps({k: v for k, v in verdict.items() if k != "rules"}))


if __name__ == "__main__":
    main()
