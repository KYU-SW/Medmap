# STEP28.5 — Korean-English Dual Symptom Concept Retrieval

- **STEP28_5_RESULT = BLOCKED** · KOREAN_ENGLISH_BRIDGE = PARTIAL · NEW_CONCEPT_FOUND = 0 · VERIFIED_NEW_CONCEPT_MAPPINGS = 0 · UNKNOWN_PRESERVATION = PASS · **PRODUCTION_READY = NO**
- 정답 라벨 없음 → 매핑 정확도 아님. Silver 442 는 STEP25–28 에서 여러 번 본 데이터(blind 아님). 판정 규칙 `scripts/build_report.py` 문서열(평가 전 고정).
- 제외: MDRKOR·KCD5(SRL 3) · 외부 API · 신규 다운로드. 기존 모델·STEP20–28 산출물 미수정(STEP28 색인·검증기 read-only 재사용).

## 1. 비교(구문 단위, A 는 입력 단위)

| 지표 | A STEP28 | B 한국어 단독 | C 영어 연결 | D 병렬 |
|---|---|---|---|---|
| units | 442 | 443 | 443 | 443 |
| EXISTING_CANONICAL | 117 | 127 | 90 | 122 |
| EXISTING_COMPOSITE | 44 | 29 | 0 | 29 |
| NEW_ONTOLOGY_CANDIDATE | 0 | 0 | 0 | 0 |
| ko_en_link_success | — | — | 136 | 136 |
| verified_new | 0 | 0 | 0 | 0 |
| candidate_resolved_to_existing | — | 0 | 331 | 331 |
| UNKNOWN_SYMPTOM | 163 | 78 | 307 | 78 |
| UNCERTAIN | 107 | 180 | 22 | 181 |
| NON_SYMPTOM | 11 | 29 | 24 | 33 |
| nonsymptom_auto_mapping_risk(weak-non 903) | 30 | 47 | 17 | 49 |
| unsupported_display | 4 | 35 | 23 | 35 |
| distinction_violations | 2 | 0 | 0 | 0 |
| raw_preservation_rate | 1.0 | 1.0 | 1.0 | 1.0 |
| two_source_agreement | — | — | — | 107 |

## 2. 한국어 → 영어 연결 자원(실측, `outputs/bilingual_link_coverage.csv`)

| 출처 | 역할 | 한국어 용어 | concept 연결 | 영어 문자열 일치 | 77 안 | 77 밖 | 77 밖 증상형 |
|---|---|---|---|---|---|---|---|
| STEP21_DICT | SYMPTOM | 294 | 289 | 161 | 289 | 0 | 0 |
| STEP23_TRAIN | SYMPTOM | 1119 | 1114 | 914 | 1114 | 0 | 0 |
| TERMINOLOGY_DISEASE | DISEASE | 49 | 37 | 37 | 2 | 35 | 0 |
| TERMINOLOGY_LABEL | ANTECEDENT | 113 | 0 | 0 | 0 | 0 | 0 |
| TERMINOLOGY_LABEL | ATTRIBUTE | 23 | 9 | 0 | 0 | 9 | 0 |
| TERMINOLOGY_LABEL | SYMPTOM | 87 | 85 | 43 | 85 | 0 | 0 |
| TERMINOLOGY_VALUE | BODY_SITE | 165 | 0 | 0 | 0 | 0 | 0 |
| TERMINOLOGY_VALUE | VALUE | 34 | 0 | 0 | 0 | 0 | 0 |
| UMLS_KOR | HERB | 770 | 770 | 0 | 0 | 770 | 0 |
| UMLS_KOR | TEST | 26893 | 26893 | 0 | 0 | 26893 | 0 |

77 밖 증상형으로 가는 연결 = **0**. 다국어 모델(siglip2 텍스트) gate: hit@1 0.0 · hit@5 0.0238 · hit@10 0.0238 (기준 hit@5 ≥ 0.50, 질의 84) → MODEL_PATH_ENABLED = False (STEP28 xlm-roberta hit@5 0.0119).

## 3. 구문 추출(kiwipiepy 0.23.2, 로컬)

Silver: {"silver_rows": 443, "silver_inputs": 442, "kiwi_failures": 1, "multi_span_inputs": 1, "pred_class": {"NONE": 371, "OTHER": 47, "PAIN": 19, "OCCUR": 6}, "kiwi_vs_rule_head_agree": 0.4582}. 대조 규칙 방식(조사 제거 한 덩어리)과 핵어 일치율 0.4582.

## 4. Smoke(회귀 확인용 — 이 문장으로 일반화 성능을 주장하지 않음)

| 입력 | 구문 | 검색 구문 | 극성 | 범주 | concept | 표시 | Q1 영어 용어 연결 | Q2 ontology concept(검증) | 구별 위반 |
|---|---|---|---|---|---|---|---|---|---|
| 코피가 나요 | 코피가 나 | 코피 | POSITIVE_OR_UNSTATED | UNKNOWN_SYMPTOM | — | — | NO | NO | — |
| 머리가 아파요 | 머리가 아파 | 머리 통증 | POSITIVE_OR_UNSTATED | EXISTING_COMPOSITE | pain | pain | Pain (site as attribute: chest/head/abdomen …) | HP:0012531(DUPLICATE_OF_EXISTING:pain);HP:0100749(DUPLICATE_OF_EXISTING:pain);SC | — |
| 열이 없어요 | 열이 없 | 열 | NEGATIVE | EXISTING_CANONICAL | fever | fever | Fever | HP:0001945(DUPLICATE_OF_EXISTING:fever);SCTID:386661006(DUPLICATE_OF_EXISTING:fe | — |
| 숨이 차요 | 숨이 차 | 숨 차다 | POSITIVE_OR_UNSTATED | EXISTING_CANONICAL | dyspnea | dyspnea | Dyspnea | HP:0002094(DUPLICATE_OF_EXISTING:dyspnea);HP:0002875(DUPLICATE_OF_EXISTING:dyspn | — |
| 토했어요 | 토했 | 토하다 | POSITIVE_OR_UNSTATED | EXISTING_CANONICAL | vomiting | vomiting | Hematemesis;Nausea;Vomiting | HP:0002018(DUPLICATE_OF_EXISTING:nausea);SCTID:422587007(DUPLICATE_OF_EXISTING:n | — |
| 메스꺼워요 | 메스꺼워 | 메스껍다 | POSITIVE_OR_UNSTATED | EXISTING_CANONICAL | nausea | nausea | Nausea | HP:0002018(DUPLICATE_OF_EXISTING:nausea);SCTID:422587007(DUPLICATE_OF_EXISTING:n | — |
| 목이 아파요 | 목이 아파 | 목 통증 | POSITIVE_OR_UNSTATED | EXISTING_CANONICAL | sore_throat | sore_throat | Sore throat | HP:0033050(DUPLICATE_OF_EXISTING:sore_throat);SCTID:267102003(DUPLICATE_OF_EXIST | — |
| 고혈압 | 고혈압 | 고혈압 | POSITIVE_OR_UNSTATED | UNCERTAIN | — | — | NO | NO | — |
| 결핵 | 결핵 | 결핵 | POSITIVE_OR_UNSTATED | NON_SYMPTOM | — | — | Tuberculosis | SCTID:56717001(NOT_SYMPTOM_TYPE);CUI:C0041296(NOT_IN_INDEX) | — |
| 어제부터 코피가 나고 머리가 아파요. 열은 없어요. | 코피가 나 | 코피 | POSITIVE_OR_UNSTATED | UNKNOWN_SYMPTOM | — | — | NO | NO | — |
| 어제부터 코피가 나고 머리가 아파요. 열은 없어요. | 머리가 아파 | 머리 통증 | POSITIVE_OR_UNSTATED | EXISTING_COMPOSITE | pain | pain | Pain (site as attribute: chest/head/abdomen …) | HP:0012531(DUPLICATE_OF_EXISTING:pain);HP:0100749(DUPLICATE_OF_EXISTING:pain);SC | — |
| 어제부터 코피가 나고 머리가 아파요. 열은 없어요. | 열은 없 | 열 | NEGATIVE | EXISTING_CANONICAL | fever | fever | Fever | HP:0001945(DUPLICATE_OF_EXISTING:fever);SCTID:386661006(DUPLICATE_OF_EXISTING:fe | — |

## 5. 개념 구별(영어 색인, `outputs/distinction_checks.json`)

| 쌍 | 출처 | 관계 |
|---|---|---|
| Epistaxis vs Hemoptysis | HP | DISTINCT |
| Epistaxis vs Hemoptysis | SCTID | DISTINCT |
| Epistaxis vs Hematemesis | HP | DISTINCT |
| Epistaxis vs Hematemesis | SCTID | DISTINCT |
| Vomiting vs Nausea | HP | DISTINCT |
| Vomiting vs Nausea | SCTID | DISTINCT |
| Headache vs Pain | HP | DISTINCT |
| Headache vs Pain | SCTID | A_IS_A_B |

MedMap curated id 분리: {"vomiting vs nausea": true, "hemoptysis vs hematemesis": true}. 검증기: {"Epistaxis": {"HP": "NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_178", "SCTID": "NO_DEFINITION;NARROWER_THAN_EXISTING:EV:E_178"}, "Headache": {"HP": "NARROWER_AS_ATTRIBUTE:pain+E_55(site)", "SCTID": "NARROWER_AS_ATTRIBUTE:pain+E_55(site)"}, "Fever": {"HP": "DUPLICATE_OF_EXISTING:fever", "SCTID": "DUPLICATE_OF_EXISTING:fever"}, "Vomiting": {"HP": "DUPLICATE_OF_EXISTING:vomiting", "SCTID": "DUPLICATE_OF_EXISTING:vomiting"}, "Nausea": {"HP": "DUPLICATE_OF_EXISTING:nausea", "SCTID": "DUPLICATE_OF_EXISTING:nausea"}, "Hemoptysis": {"HP": "DUPLICATE_OF_EXISTING:hemoptysis", "SCTID": "DUPLICATE_OF_EXISTING:hemoptysis"}, "Hematemesis": {"HP": "DUPLICATE_OF_EXISTING:hematemesis", "SCTID": "DUPLICATE_OF_EXISTING:hematemesis"}}

## 6. 실패 원인(D 병렬의 UNKNOWN·UNCERTAIN 구문)

{"BILINGUAL_BRIDGE_MISSING": 220, "CONCEPT_AMBIGUITY": 21, "KOREAN_NORMALIZATION_FAILURE": 17, "SPAN_EXTRACTION_FAILURE": 1}

- '영어 ontology 에는 개념이 있으나 한국어 연결이 없어 실패' = Silver 전체 **측정 불가**(정답 영어 개념·한·영 대응 자원 없음). smoke 의 코피(=Epistaxis, 지시문이 대응 명시) 1건만 확인: 영어 색인에 있음(HP:0000421·SNOMED 249366005), 한국어 연결 없음.
- LICENSE_RESTRICTION: MDRKOR 를 열지 않아 측정 불가.
- 비증상 자동 매핑 위험(병렬) 근거별: {"PHRASE": 28, "EXACT": 14, "MODEL_AUTO(B4)": 1, "PAIN+SITE_RULE": 6} — `outputs/weak_non_risk.csv`. 신체 부위 단독('머리·입안·손가락·명치')·
  질환명 안의 두통('혈관성 편두통')이 기존 증상으로 연결된 것이 대부분. 사후 확인이며 규칙은 고치지 않았다.

## 7. 속도·자원

| 경로 | p50 ms | p95 ms | max ms |
|---|---|---|---|
| SPAN_EXTRACTION | 0.043 | 0.106 | 0.396 |
| KO_ONLY | 21.958 | 27.103 | 30.204 |
| EN_ONLY | 10.64 | 16.267 | 24.449 |
| PARALLEL | 22.332 | 27.612 | 50.416 |

적재 5.26 s · RSS 1342.5 MiB(peak 1345.6) · 한국어 색인 25.3 MB · 한·영 연결표 7.6 MB · STEP28 ontology 색인 265.0 MB(재사용).

## 8. 변경 기록(공개)

- smoke 를 본 뒤 고친 일반 규칙: kiwipiepy 접두사(고-혈압) 처리 · 색인 용어도 질의와 같은 원형 정규화(nkey, 부정 포함 용어 제외) · '-지 못하다' 부정 · 술어가 증상을 담으면 명사 단독 검색 안 함 · 충돌 시 후보 표시 금지 · STEP27 B4 자동수락을 독립 근거로 사용. 이후 규칙 변경 없음. 해당 smoke 결과는 회귀 확인용.
- STEP28 결함 회피: 용어집 라벨 '·' 분리 안 함 · '짧은 입력이 긴 학습 문장 안에 있으면 근거' 규칙을 길이 비율 조건으로 교체 · 제품 매퍼를 한국어 근거에서 제외(구토→오심 오매핑).

## 9. 답

1. **구문 분해**: kiwipiepy 형태소 → 연결어미·종결어미·문장부호에서 절 분리 → 절마다 명사구(핵어 = 마지막 명사)·첫 용언·부정·시점·주체 → 술어 종류별 검색 구문(통증 술어 = '부위 통증', 발생·부정 = 명사, 그 외 = 명사+용언 원형). 실패하면 원문 유지(Silver 실패 1).
2. **한국어 검색**: 기존 증상 연결 127 + 통증·부위 29 (STEP28 117 + 44). 한국어 색인에 77 밖 증상 행이 0 이라 신규 concept 은 원리상 찾을 수 없다.
3. **영어 query 출처**: 같은 MedMap/DDXPlus 레코드의 영어 이름(77 증상명·49 질환명)과 STEP20 curated id 뿐. 번역 생성 없음. 그래서 영어 경로는 기존 77·질환으로만 간다(77 밖 증상형 0).
4. **병렬 vs 한국어 단독**: §1 표 — 병렬은 한국어 단독 대비 기존 연결 -5, 두 출처 일치 107. 신규 concept 은 둘 다 0.
5. **새 증상 concept**: 한국어 입력에서 0(검증 0). 영어 색인 자체는 Epistaxis 등 77 밖 concept 을 갖고 있다(STEP28 확인).
6. **중복**: 영어 쪽 후보가 기존 concept 으로 해소된 수 331 — 신규로 만들지 않음. 신규 ID 생성 0.
7. **잘못된 연결 위험**: 비증상 903 자동 매핑 위험 30(STEP28) → 49(병렬) · 근거 없는 표시 4 → 35 · 구별 위반 2 → 0.
8. **가장 큰 병목**: BILINGUAL_BRIDGE_MISSING — 77 밖 증상을 가리키는 한국어 용어도, 한·영 대응표도 허용 자원에 없다. 로컬 다국어 모델 2종(xlm-roberta-base, siglip2)은 기존 라벨로도 gate 미달.
9. **속도**: 병렬 p95 27.612 ms(CPU) — 실용 범위. 다국어 모델 경로는 미사용이라 포함 안 됨.
10. **STEP29**: `docs/step29_handoff.md` — 이번 구문 추출 출력(구문·극성·시점·주체·위치)을 그대로 입력으로, 정규화는 이 검색기, 부정 범위·시점 적용 범위·주체 판정을 NLU 가 담당.

## 10. 재현성

`run_all.sh` 2회 — 결정적 산출물 16개 SHA 동일(`logs/sha1.txt`·`sha2.txt`, SHA_IDENTICAL). siglip2 임베딩은 최초 1회 계산(1,801 s) 후 캐시 재사용(문자열 일치 assert).
