# STEP28.7 — MedMap Ontology Mapping Quality & Safety Validation

- **STEP28_7_RESULT = REGRESSION** · PRODUCTION_READY = NO · STEP29 진입 = **NO_GO** · HUMAN_VERIFIED_GOLD = 0 · 모든 대응·분류 = SILVER(검증 전)
- 게이트: {"G1": "PASS", "G2": "PASS", "G3": "FAIL", "G4": "PASS", "G4b": "PASS", "G5": "PASS", "G6": "FAIL", "G7": "PASS", "G8": "PASS", "G9": "PASS", "G10": "PASS"} · C(STEP28.6) 대비 안전 지표 개선: {"weaknon_risk": false, "semantic_violations": false, "wrong_display": false}
- 판정·게이트 규칙은 평가 실행 전 `scripts/build_report.py` 문서열에 고정. 검색 규칙은 `scripts/safe_offline_retriever.py` 문서열(평가 전 고정, 변경 기록 = §12).
- 데이터는 모두 STEP21–28.6 에서 반복 관찰된 개발·회귀 자료(blind 아님). C·D 의 SILVER442·WEAKNON903·probe 수치는 **대응표가 그 입력으로 작성된 in-table 수치**다.
- 추가 LLM·외부 API·다운로드·재학습·제품 변경 0. G10(기존 산출물·제품 저장소 무변경) = PASS.

## 1. 최종 보고 항목

| 항목 | 값 |
|---|---|
| ORIGINAL_NEW_CANDIDATES | 34(보고 기준 = G3 고유 22 + G2 고유 12) · 고유 concept 33 · 전 등급 39 |
| INDEPENDENT_NEW_CONCEPTS | 16(계열 14 — tremor 하위 묶음) · HPO 감사 EXACT 14 · SNOMED 전용 UNVERIFIED 1 |
| EXISTING_SYNONYMS | 1 |
| EXISTING_SUBTYPES | 6 |
| HELD_CANDIDATES | 15 |
| REJECTED_CANDIDATES | 1 |
| ISOLATION_UNVERIFIED_CANDIDATES | 0 (격리 FAIL 조각이 지지 행에 있는 후보 2) |
| WEAK_NEGATIVE_AUTO_MAP | 8/903(C 재계산 8/903, STEP28.5 49/903) |
| SUPPORTED_AUTO_COVERAGE | 0.5893(REGRESSION168, precision 0.8788; A 0.4226/0.9859) |
| WRONG_CANDIDATE_DISPLAY | 2 |
| SEMANTIC_DISTINCTION_VIOLATIONS | 2 |
| RAW_PRESERVATION | 1.0 |
| CPU_P95 | 25.516 ms(p50 20.749 ms, n 442) · peak RSS 1348.9 MiB |
| SILVER 검사 통과 concept(신규 유지 + 기존 관계 병합) | 23 |
| HUMAN_VERIFIED_GOLD | 0 |
| PRODUCTION_READY | NO |

## 2. 34 집계 재검증(§1)

- STEP28.6 보고 34 = 등급별 고유 수의 단순 합(G3 22 + G2 12). 같은 concept 이 다른 입력에서 두 등급을 받은 경우 중복: ['HP:0002354'] → G2+ 고유 33.
- G1(단일 작성자)·REJECTED 는 34 에 포함되지 않음. 단 SCTID:55300003 는 G1·G2 둘 다라 concept 으로는 34 안. 전 등급 고유 39.
- SNOMED 전용(HPO 교차 없음) 후보: 전 등급 12 · 34 집합 10(인수인계 문서의 '11' 과 다름 — 원본 audit_manifest NOT_AUDITED_LICENSE 기준 재계산).
- STEP28.6 산출물은 수정하지 않았다(G10).

## 3. 신규 후보 분류(§3·§4) — 분류자 = STEP28.7 Claude 세션(비인간·비독립, SILVER)

| class | 39 전체 | 34 집합(고유 33) |
|---|---|---|
| EXISTING_SYNONYM | 1 | 1 |
| EXISTING_COMPOSITE | 0 | 0 |
| EXISTING_SUBTYPE | 6 | 6 |
| NEW_INDEPENDENT_CONCEPT | 16 | 16 |
| NON_SYMPTOM | 0 | 0 |
| UNCERTAIN | 16 | 10 |

- 독립 신규(D): HP:0000738(환각), HP:0000858(생리불순), HP:0001288(보행장애), HP:0001337(떨림), HP:0002063(경직), HP:0002329(졸리움), HP:0002354(건망증상), HP:0002378(손떨림), HP:0010780(청각과민을), HP:0025258(목의 강직이), HP:0025267(코골이가), HP:0100785(불면), HP:0100812(입냄새가), SCTID:366979004(우울), SCTID:76067001(재채기), SCTID:42800007(잔떨림)
- 기존 하위(C): HP:0000421(코피가), HP:0000988(발진은), HP:0031246(마른기침의), HP:0034315(만성기침과), HP:0200034(구진), SCTID:55300003(근육경련증상이) — 부모 feature 자동 통합 금지(연구용 부모 후보만 기록)
- 보류·반려: HP:0001254(무기력), HP:0001649(빈맥증상과), HP:0008066(물집은), SCTID:119416008(윗배 불편감), SCTID:247342009(이물감), SCTID:247347003(불편감을), SCTID:271587009(뻐근한 증상이), SCTID:271787007(허탈증상), SCTID:398032003(묽은변을), SCTID:83547004(식은 땀), HP:0001123(시야 이상), HP:0001257(경축을), HP:0033031(고열), SCTID:247322000(감각의 이상을), SCTID:719399007(말막힘이나), HP:0003750(근육피로도가)
- 우선 검토: 무기력 = UNCERTAIN(피로와 HPO 계층 DISTINCT 이나 정의가 겹침, 의식 저하와 동의어 처리 안 함) · 마른기침 = cough 하위(속성 보존, 자동 통합 금지) ·
  묽은변 = 기존 diarrhea 관련(동의어 아님, 독립 신규 집계 제외, 보류) · 떨림 = Tremor 독립 신규(Chills 와 DISTINCT — STEP28.5 떨림→오한은 오류) ·
  코피 = Epistaxis, E_178(이상 출혈) 하위로 분류(객혈·토혈과 DISTINCT) · 구토·오심 = DISTINCT(관계 파일 `outputs/priority_pair_relations.json`, LOCAL_ONLY).

## 4. SNOMED 전용 후보(§5)

- 로컬 SNOMED(2026-09-01)로 id 유효·active·clinical finding 계층·부모·자식 수·77 관계를 확인(`data/snomed_local_audit.csv`, LOCAL_ONLY). 외부 전송 0.
- concept 존재·활성은 확인되나 **한국어 대응 정확성은 UNVERIFIED**(HPO 감사 불가·인간 검토 없음). 검증 완료로 표시하지 않는다.

## 5. 격리 검사 FAIL(§6)

- FAIL 세션 author_A_c03, author_A_c04, author_B_c04: 모두 작성 직후 **자기 출력 파일 1–3 행을 다시 읽고 전체 재작성**. B_c04 의 Edit 은 시도됐으나 도구 차단 오류로 실패(실제 변경은 Write).
- 다른 작성자 파일 읽기 0 · 작업 폴더 밖 접근 0 · 메모리/CLAUDE.md 주입 0. 재작성으로 바뀐 행 11 개는 모두 열 개수·비고·확신도 칸(형식 보정) — 유형·영어 용어 변경 0(`outputs/isolation_analysis.json` row_diffs).
- B_c04 실행 시점에 작성자 A 파일 6개가 out/ 에 있었음(읽은 기록 없음).
- 영향 범위: 입력 460 개(SILVER442 0 · WEAKNON903 460). provenance = ISOLATION_FAIL 유지(PASS 로 바꾸지 않음).
  정제표에서 이 행들은 양성 연결에 쓰지 않음(HOLD_ISOLATION 8), 비증상 판정(연결 거부 방향)만 허용.
- 재작성 비용(실행 안 함): 같은 조각 실측 정가 환산 {'author_A_c03': '0.7903588', 'author_A_c04': '0.9155068000000001', 'author_B_c04': '0.31567339999999994'} USD — 별도 과금 승인 대상.

## 6. 정제 SILVER 대응표(§7)

- `data/cleaned_silver_mappings.csv`(1,355 행) 결정: {"ACCEPT_EXISTING": 169, "ACCEPT_SUBTYPE": 10, "ACCEPT_NON_SYMPTOM": 909, "HOLD_SEMANTIC_TYPE": 43, "NO_MAPPING": 84, "HOLD_AUTHOR_CONFLICT": 29, "HOLD_SINGLE_AUTHOR": 50, "ACCEPT_NEW_CANDIDATE": 32, "HOLD_CONCEPT_UNCERTAIN": 14, "HOLD_AUDIT_NOT_EXACT": 5, "REJECT_AUDIT": 1, "ACCEPT_EXISTING_SYNONYM": 1, "HOLD_ISOLATION": 8}
- 근거 등급: {"LEVEL_2": 1150, "LEVEL_3": 42, "LEVEL_0": 84, "LEVEL_1": 79} · LEVEL_4 = 0. LEVEL_3 = A·B 일치 + opus 감사 EXACT(감사자 = 작성자 A 와 같은 모델 → 독립 검증 아님).
- usable_by_disease_model = 전부 False. 표시 허용 = ACCEPT_EXISTING·SYNONYM 만.

## 7. 정책 비교(§12) — 단위: A·B·C 입력, D 계열 구문

| 지표 | A_STEP27_B4 | B_STEP28 | C_STEP28_6 | D_STEP28_7 | D_NO_TABLE | D_LOO |
|---|---|---|---|---|---|---|
| silver_units | 442 | 442 | 442 | 443 | 443 | 443 |
| 1_EXISTING_CANONICAL | 56 | 117 | 127 | 154 | 127 | 138 |
| 2_EXISTING_COMPOSITE | 0 | 44 | 37 | 40 | 29 | 30 |
| 3_NEW_INDEPENDENT_ontology_ids | 0 | 0 | 32 | 13 | 0 | 2 |
| 3b_NEW_units | 0 | 0 | 61 | 21 | 0 | 4 |
| 4_NEW_SUBTYPE_ontology_ids | 0 | 0 | 0 | 3 | 0 | 2 |
| 4b_SUBTYPE_units | 0 | 0 | 0 | 6 | 0 | 4 |
| 5_SILVER_SYNONYM_units | 0 | 0 | 0 | 1 | 0 | 0 |
| 6_UNCERTAIN_units | 173 | 107 | 78 | 125 | 180 | 153 |
| UNKNOWN_units | 213 | 163 | 49 | 9 | 78 | 41 |
| NON_units | 0 | 11 | 90 | 88 | 29 | 73 |
| 7_weaknon_auto_link_risk | 5 | 30 | 8 | 8 | 47 | 29 |
| 8_supported_auto_coverage | 0.4226 | 0.5655 | 0.0298 | 0.5893 | 0.5833 | 0.5833 |
| 9_regression_auto_precision | 0.9859 | 0.9579 | 1.0 | 0.8788 | 0.8776 | 0.8776 |
| 10_wrong_candidate_display_inputs | 7 | 8 | 0 | 2 | 10 | 2 |
| 11_semantic_violation_inputs | 7 | 8 | 0 | 2 | 10 | 2 |
| 12_unknown_uncertain_rate(silver units) | 0.8733 | 0.6109 | 0.2873 | 0.3025 | 0.5824 | 0.4379 |
| silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON) | 0.1267 | 0.3891 | 0.7127 | 0.6975 | 0.4176 | 0.5621 |
| 13_raw_preservation | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

- 비증상 903·Silver 442 는 약한 라벨, REGRESSION168 은 합성(gold) — 하나의 정확도로 합치지 않음.
- REGRESSION168: A coverage 0.4226(정답 70/71) · D coverage 0.5893(정답 87/99). D 오답 예: [['오바이트했어요', 'vomiting', 'nausea'], ['정신이 아찔해요', 'dizziness', 'confusion'], ['속이 쓰려요', 'heartburn', 'pain'], ['어제 밤부터 왼쪽 가슴이 쥐어짜듯 아파요', 'pain', 'palpitations'], ['숨 쉴 때마다 옆구리가 찌르듯이 아파요', 'pain', 'dyspnea']]
- 재현 확인(A·B 라이브 ↔ 기존 파일 불일치 수): {"A_STEP27_B4:SILVER442": 60, "A_STEP27_B4:WEAKNON903": 0, "A_STEP27_B4:REGRESSION168": 0, "B_STEP28:SILVER442": 0, "B_STEP28:WEAKNON903": 0, "B_STEP28:REGRESSION168": 0} · C 비증상 위험 재계산 {'recomputed': 8, 'reported': 8}

## 8. 비증상 자동 연결(§9)

- STEP28.6(C) 위험 입력 8: 만성기침과, 심계항진이라고, 흉통과, 흉통을, 흉통의, 흉통이, 흉통이라고, 흉통이란 — 원인 {"SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 8}
- STEP28.7(D) 위험 입력 8: 양쪽 팔을들어→limb_weakness(KO:MODEL_B4); 심계항진이라고→palpitations(KO:EXACT); 감각의 이상을→EV:E_178(KO:PHRASE); 만성기침과→cough(KO:EXACT); 말초성마비→limb_weakness(KO:PHRASE); 경추성 어지럼증의→dizziness(KO:EXACT); 외 음 부 근→palpitations(KO:EXACT); 치아 주위→dizziness(KO:PHRASE) — 원인(사전 분류) {"OTHER": 3, "SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 2, "SUBSTRING(PHRASE)": 3}
- D 의 위험은 전부 STEP28.5 한국어 경로(KO)에서 발생: 대응표 행이 단일 작성자·충돌·격리 FAIL 보류라 KO 결과를 덮지 않음(사전 규칙). 사후 확인한 KO 색인 결함(이번 단계 미수정):
  1글자 핵어 완전일치('외 음 부 근' 의 '근' ← '가슴 두근' → palpitations) · 일반 명사 부분 일치('주위'·'이상' → dizziness·E_178) · 질환명 안 증상어('경추성 어지럼증' → dizziness) · B4 모델('양쪽 팔을들어' → limb_weakness).
  C(STEP28.6) 의 8 건(흉통 6 · 심계항진 1 · 만성기침 1)은 두 작성자 모두 증상형으로 쓴 실제 증상 용어(약한 비증상 라벨 쪽 의심). D 에서 흉통 6 은 KO 경로가 연결하지 못했고(NO_KOREAN_MATCH —
  77 지원 증상 '흉통' 의 KO 누락) 대응표 행이 격리 FAIL 보류라 UNCERTAIN, 심계항진·만성기침은 KO EXACT 로 연결(eval_rows.csv).
- 'SYMPTOM_TERM_WEAK_LABEL_CONFLICT' = 두 작성자 모두 증상형으로 쓰고 한국어 기존 검색도 증상으로 본 단어(약한 비증상 라벨 쪽 의심). 원문 문맥이 없는 단어 조각이라 증상 문맥 여부는 확인 불가.
  이 경우를 UNKNOWN 으로 돌려 수치를 맞추지 않았다.

## 9. 후보 표시 안전성(§10) — probe(사용자 지정, 이미 노출된 사례)

| 입력 | A_STEP27_B4 | B_STEP28 | C_STEP28_6 | D_STEP28_7 | D_LOO | 제품 매퍼(read-only) |
|---|---|---|---|---|---|---|
| 코피 | UNCERTAIN: | UNCERTAIN: | UNKNOWN_SYMPTOM: | EXISTING_SUBTYPE:EV:E_178 | EXISTING_SUBTYPE:EV:E_178 |  |
| 토했어요 | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | E_148:POSITIVE ⚠VOMITING_AS_NAUSEA |
| 떨림 | UNKNOWN_SYMPTOM: | UNKNOWN_SYMPTOM: | NEW_ONTOLOGY_CANDIDATE:HP:0001337 | UNCERTAIN: | UNCERTAIN: |  |
| 고혈압 | UNCERTAIN: | NON_SYMPTOM: | NON_SYMPTOM: | NON_SYMPTOM: | UNCERTAIN: | E_104:POSITIVE |
| 기침 억제제 | UNCERTAIN: ⚠ANTITUSSIVE_AS_COUGH | EXISTING_CANONICAL:cough ⚠ANTITUSSIVE_AS_COUGH | NON_SYMPTOM: | NON_SYMPTOM: | UNCERTAIN: | E_201:POSITIVE ⚠ANTITUSSIVE_AS_COUGH |
| 무기력 | EXISTING_CANONICAL:fatigue | EXISTING_CANONICAL:fatigue | NEW_ONTOLOGY_CANDIDATE:HP:0001254 | EXISTING_CANONICAL:fatigue | EXISTING_CANONICAL:fatigue |  |
| 마른기침 | EXISTING_CANONICAL:cough | EXISTING_CANONICAL:cough | UNKNOWN_SYMPTOM: | EXISTING_CANONICAL:cough | EXISTING_CANONICAL:cough | E_201:POSITIVE |
| 설사 | EXISTING_CANONICAL:diarrhea | EXISTING_CANONICAL:diarrhea | UNKNOWN_SYMPTOM: | EXISTING_CANONICAL:diarrhea | EXISTING_CANONICAL:diarrhea |  |
| 묽은변 | EXISTING_CANONICAL:diarrhea | EXISTING_CANONICAL:diarrhea | UNKNOWN_SYMPTOM: | EXISTING_CANONICAL:diarrhea | EXISTING_CANONICAL:diarrhea |  |
| 구토 | UNKNOWN_SYMPTOM: | UNCERTAIN: | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | EXISTING_CANONICAL:vomiting | E_148:POSITIVE ⚠VOMITING_AS_NAUSEA |
| 오심 | UNCERTAIN: | EXISTING_CANONICAL:nausea | EXISTING_CANONICAL:nausea | UNCERTAIN: | UNCERTAIN: | E_148:POSITIVE |
| 코피가 나요 | UNCERTAIN: ⚠EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS | UNKNOWN_SYMPTOM: | NEW_ONTOLOGY_CANDIDATE:HP:0000421 | EXISTING_SUBTYPE:EV:E_178 | EXISTING_SUBTYPE:EV:E_178 |  |
| 머리가 아파요 | EXISTING_CANONICAL:pain | EXISTING_COMPOSITE:pain | EXISTING_COMPOSITE:pain | EXISTING_COMPOSITE:pain | EXISTING_COMPOSITE:pain | E_53:POSITIVE |
| 열이 없어요 | UNCERTAIN: | UNCERTAIN: | UNCERTAIN: | EXISTING_CANONICAL:fever | EXISTING_CANONICAL:fever | E_91:NEGATIVE |
| 숨이 차요 | EXISTING_CANONICAL:dyspnea | EXISTING_CANONICAL:dyspnea | EXISTING_CANONICAL:dyspnea | EXISTING_CANONICAL:dyspnea | EXISTING_CANONICAL:dyspnea | E_66:POSITIVE |
| 메스꺼워요 | EXISTING_CANONICAL:nausea | EXISTING_CANONICAL:nausea | EXISTING_CANONICAL:nausea | EXISTING_CANONICAL:nausea | EXISTING_CANONICAL:nausea | E_148:POSITIVE |
| 목이 아파요 | EXISTING_CANONICAL:sore_throat | UNCERTAIN: | EXISTING_CANONICAL:sore_throat | EXISTING_CANONICAL:sore_throat | UNCERTAIN: | E_53:POSITIVE |
| 결핵 | UNCERTAIN: | NON_SYMPTOM: | NON_SYMPTOM: | NON_SYMPTOM: | NON_SYMPTOM: |  |
| 어제부터 코피가 나고 머리가 아파요. 열은 없어요. | UNCERTAIN: | UNCERTAIN: | UNKNOWN_SYMPTOM: | EXISTING_SUBTYPE;EXISTING_COMPOSITE;EXISTING_CANONICAL:EV:E_178;pain;fever | EXISTING_SUBTYPE;EXISTING_COMPOSITE;EXISTING_CANONICAL:EV:E_178;pain;fever | E_53:POSITIVE;E_91:NEGATIVE |

- ⚠ = 구별 위반. 제품 매퍼는 read-only 로 탐지만(제품 코드 변경 없음).
- 사후 관찰(probe, `data/eval_rows.csv` reasons): '떨림' D = UNCERTAIN(KO PHRASE chills ↔ SILVER tremor 충돌 — 오한 연결은 막았으나 tremor 도 반환 안 함) · '무기력'·'묽은변' D = fatigue·diarrhea 자동(KO PHRASE·EXACT) — concept 감사 보류(F)와 다름: 사전 규칙상 SILVER 보류는 KO 결과를 덮지 않음(사용자 결정 필요) · '오심' D = UNCERTAIN(KO 가 NON 으로 판정 ↔ SILVER nausea 충돌 — STEP28.5 KO 결함) · 제품 매퍼는 '토했어요'·'구토' → E_148(오심), '기침 억제제' → E_201(기침) 여전히 POSITIVE.

## 10. 답(§19)

1. 원래 34(고유 33) 중 독립 신규 증상 후보 = 16(전 등급 16, tremor 계열 묶으면 14). SILVER·비인간 분류.
2. 기존 77 과 겹치는 개념(동의어+속성+하위) = 7.
3. 기존 증상의 하위 유형 = 6.
4. HPO 감사 일치 22 = 'A·B 두 LLM 일치 + 같은 계열 LLM 의 HPO 정의 대비 자동 감사 EXACT' = LEVEL_3 SILVER. 독립 검증·인간 Gold 아님.
5. SNOMED 전용 = id·활성·계층·77 관계까지 로컬 확인. 한국어 대응 정확성은 확인 불가(UNVERIFIED).
6. 격리 FAIL 은 자기 출력 재읽기·재작성(형식 보정만 확인)으로 교차 오염 증거는 없으나 규칙 위반 → 해당 460 입력(전부 WEAKNON903)의 양성 연결을 쓰지 않음. Silver442 신규 후보에는 영향 없음, 만성기침 1개 보류.
7. 비증상 자동 연결 8건(STEP28.6) 원인: {"SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 8} — 전부 두 작성자가 증상형으로 쓴 실제 증상 용어(흉통·심계항진·만성기침)로 약한 비증상 라벨과 충돌. 질환·약물·부위·부분 일치 원인은 0.
8. STEP28.6 대비 안전성: 개선 아님(동률·공식 검사기로는 악화). 비증상 위험 8 → 8(원인 종류는 바뀜: 실제 증상어 → KO 오연결) · 구별 위반 0 → 2(v2 0 → 0) · 잘못된 후보 표시 0 → 2. 단 C 는 표 밖 입력을 처리하지 못하고, D 는 A(STEP27)·B(STEP28) 대비 구별 위반(v2)이 4·6 → 0.
9. 기존 증상 자동 처리율(REGRESSION168): A 0.4226 · D 0.5893 · D_NO_TABLE 0.5833 — 감소 아니오(A 대비).
10. 처음 보는 표현: 대응표는 사전(완전일치)이라 표 밖 표현은 STEP28.5 한국어 경로·B4 로만 처리. D_LOO(같은 원문 행 제외) Silver 결정률 0.5621 vs D 0.6975 · 신규 id 2 vs 13. → 77 밖 신규 증상은 사전 기반 표현만 가능.
11. 병원 오프라인: 런타임 LLM·네트워크 불필요(CPU p95 25.516 ms, RSS 1348.9 MiB). 대응표 확장에는 오프라인 LLM 작성 단계(과금 승인)가 필요.
12. STEP29 인터페이스: `docs/step29_interface.md`(구문 위치·부정·시점·주체는 STEP28.5 추출값 전달, 검증 안 됨) → 공식 NO_GO(사전 규칙: hard 게이트 G3 FAIL) · 탐색 v2 CONDITIONAL_GO(검사기 결함 제외 시). 바로 쓸 수 있는 형태이나 STEP28.5 KO 경로 정밀도(G6) 문제를 안고 간다.
13. STEP29 전 필수: 인간 검토 Gold 소량(독립 신규 16·하위 6·우선 보류) · 부정·시점·주체 검증 · 격리 FAIL 조각 재작성 여부 결정(과금) · 약한 비증상 라벨 정정 방법.

## 11. 사후 발견·탐색적 결과(EXPLORATORY_POST_HOC — 공식 판정 아님, 1차 결과를 본 뒤 작성)

- **공식 판정 REGRESSION 의 원인 = 검사기 결함**: 사전 고정 구별 검사기에 STEP28.6 규칙에 없던 '토할·토해'(구토)와 동사 '떨려·떨리'(떨림)를 넣음 → REGRESSION168 의 정답 연결 2건('토할 것 같아요'=gold nausea, '몸이 덜덜 떨려요'=gold chills)을 위반으로 셈. 검색기 결함 아님. 공식 판정은 그대로 둔다.
- v2 재채점(검사기만 STEP28.6 원형·명사 '떨림' 으로, 모델 재실행 없음 — `outputs/exploratory_v2.json`): 구별 위반 입력 A_STEP27_B4 4 · B_STEP28 6 · C_STEP28_6 0 · D_STEP28_7 0 · D_NO_TABLE 8 · D_LOO 0 → **STEP28_7_RESULT_EXPLORATORY_V2 = NO_GAIN**(게이트 {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS", "G4b": "PASS", "G5": "PASS", "G6": "FAIL", "G7": "PASS", "G8": "PASS", "G9": "PASS", "G10": "PASS"}).
  D_NO_TABLE(=STEP28.5 KO) 의 위반 8 은 '떨림 → 오한' — 정제 대응표가 막음. C 와 동률인 이유: C 는 표 밖 입력을 처리하지 않음(REGRESSION168 coverage 0.0298).
- G6 FAIL 은 v2 에서도 유지: D 의 regression 오답은 D_NO_TABLE 과 같은 STEP28.5 KO 경로 오류(첫 자동 구문 기준; 진단 'gold 가 어느 자동 구문에든 있음' D 0.5238 · A 0.4167).
- A(STEP27) 재현 불일치(SILVER442 60): STEP27 파일은 EXT 세트에 out-of-fold 비증상 점수(routing_decisions)를 쓰고 라이브는 전체 분류기 점수를 씀(STEP27 analyze_routing_errors.py 118–135 행 확인) → UNCERTAIN↔UNKNOWN 차이. 나머지 세트 불일치 0.

## 12. 변경 기록(공개)

- 평가 전 기능 점검(§14 예시 문장)에서 대응표 조회 키 결함: '머리가 아파' 의 명사구 '머리'(신체 부위 NON 행)가 통증 구문을 막음 → STEP28.5 qkeys 와 같은 규칙(술어가 증상을 담으면 명사구 단독 키 안 씀)으로 수정. 이 예시는 probe 에 포함되므로 그 결과는 회귀 확인용.
- concept 분류 결정(`data/concept_review_decisions.csv`)은 사실 표를 본 뒤 평가 전에 작성. 평가 후 수정 없음.
- 1차 평가 후(공식 판정 고정 뒤) 추가: `scripts/evaluate_exploratory_v2.py`(검사기 v2 재채점, 공식 판정 아님) · 보고서 집계 수정(비증상 원인 표를 정책별 위험 행만 세도록) · run_all.sh 에 v2 와 보고서 재생성 단계 추가. 검색 규칙·게이트·공식 판정 규칙은 바꾸지 않음.
