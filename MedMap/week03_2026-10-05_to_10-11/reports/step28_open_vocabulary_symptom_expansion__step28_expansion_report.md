# STEP28 — MedMap Open-Vocabulary Symptom Expansion

- **STEP28_RESULT = PARTIAL_FEASIBILITY** · KOREAN_ONTOLOGY_LINKING = PARTIAL · NEW_CONCEPT_RETRIEVAL = PARTIAL · CONCEPT_DUPLICATION_CONTROL = PASS · UNKNOWN_PRESERVATION = PASS · PRODUCT_INTEGRATION = HOLD · **PRODUCTION_READY = NO**
- 외부 Gold 없음 → 아래 수치는 매핑 정확도가 아니다. Silver 442 = BERT-NER-KO 증상(ST) span(자동 판정, 사람 검증 아님). 판정 규칙: `scripts/build_report.py` 문서열(평가 전 고정).
- 기존 모델(Linear·KoELECTRA·Hybrid B·B4·STEP27 POLICY_D)·49질환 모델·제품 코드·PatientState 미수정. 신규 다운로드·번역 API·유료 API 없음. STEP27 산출물 SHA 불변(변경 0건).

## 1. 핵심 수치(Silver 442)

| 항목 | 값 |
|---|---|
| 입력 한국어 표현 | 442 |
| 기존 canonical 연결 | 117 |
| 기존 속성 조합(pain+부위) | 44 |
| 신규 ontology concept 후보(자동, 검증 전) | 0 (입력 0) |
| 의미 검증이 필요한 후보 | 0 |
| 검증된 신규 concept 입력(EXACT/ACCEPTABLE) | 0 |
| UNKNOWN(원문 보존) | 163 |
| NON_SYMPTOM | 11 |
| UNCERTAIN | 107 |
| 근거 없는 후보 표시(proxy) STEP27 → STEP28 | 27 → 4 입력 (표시 입력 74 → 176) |
| 원문 보존율 | 100.0% |
| CPU p50 / p95 (STEP28 전체, 442 입력) | 10.223 / 12.995 ms |
| 색인 크기 / 생성 시간 | 265.0 MB / 22.2 s (원본 약 3.46 GB) |

§11 분류: {"5_UNCLEAR": 107, "2_EXISTING_COMPOSITE": 44, "6_KOREAN_LINK_MISSING": 163, "1_EXISTING_CANONICAL": 117, "4_NON_SYMPTOM": 11}

## 2. 한국어 → ontology 연결 경로(실측)

| 경로 | 자원 | 결과 |
|---|---|---|
| A | MedMap 한국어 용어(STEP23 1,119·STEP21 294·용어집 223)·제품 매퍼 alias·STEP27 모델 | 기존 77 concept 연결 161 입력 |
| B | A → STEP20 curated HPO/SNOMED/UMLS id | 기존 concept 의 표준 id 부여(신규 아님) |
| K | UMLS KOR SRL 0: LNC-KO-KR 검사명 · TKMT 약재명 (27663행) | 비증상(검사·약재) 근거로만 사용 |
| C | 로컬 xlm-roberta-base 평균 풀링 → HPO 영어 | 타당성 gate hit@5 = 1.2% · hit@1 0.0% (기준 50%, 질의 84 = 기존 증거 한국어 라벨) → PATH_C_ENABLED = False |
| D | 연결 자원 없음 | UNKNOWN(KOREAN_LINK_MISSING) |
| (제외) | UMLS KOR SRL 3: MDRKOR(MedDRA 한국어 119994행) · KCD5(11001행) | 이용 조건 확인 필요 → 색인에 넣지 않음 |

경로별 입력 수: {"A(MedMap 한국어 용어/규칙/모델)": 177, "D(연결 자원 없음)": 163, "D(증상 근거도 없음)": 91, "K/A(비증상 근거)": 11}

## 3. 대표 사례(회귀 확인용 — 이 사례로 규칙을 만들거나 일반화 성능을 주장하지 않음)

| 입력 | 집합 | STEP27 | STEP27 후보 | STEP28 | 근거 | canonical | 부위 | 표시 후보 | 연결 경로 |
|---|---|---|---|---|---|---|---|---|---|
| 코피 | REP15 | UNCERTAIN | — | UNCERTAIN | TYPE_UNCLEAR | — | — | — | D(증상 근거도 없음) |
| 객혈 | REP15 | UNKNOWN_SYMPTOM | — | EXISTING_CANONICAL | PRODUCT_ALIAS+MODEL_LEXICAL | hemoptysis | — | hemoptysis | A(MedMap 한국어 용어/규칙/모델) |
| 토혈 | REP15 | UNCERTAIN | — | EXISTING_CANONICAL | MODEL_LEXICAL | hematemesis | — | hematemesis | A(MedMap 한국어 용어/규칙/모델) |
| 두통 | REP15 | UNKNOWN_SYMPTOM | — | EXISTING_COMPOSITE | PAIN_PLUS_SITE | pain | 머리 | pain | A(MedMap 한국어 용어/규칙/모델) |
| 발열 | REP15 | UNKNOWN_SYMPTOM | — | EXISTING_CANONICAL | PRODUCT_ALIAS+MODEL_LEXICAL | fever | — | fever | A(MedMap 한국어 용어/규칙/모델) |
| 호흡곤란 | REP15 | KNOWN_SYMPTOM | dyspnea | EXISTING_CANONICAL | EXACT_TERM | dyspnea | — | dyspnea | A(MedMap 한국어 용어/규칙/모델) |
| 구토 | REP15 | UNKNOWN_SYMPTOM | — | UNCERTAIN | SOURCE_CONFLICT | — | — | nausea;vomiting | A(MedMap 한국어 용어/규칙/모델) |
| 오심 | REP15 | UNCERTAIN | — | EXISTING_CANONICAL | PRODUCT_ALIAS+MODEL_LEXICAL | nausea | — | nausea | A(MedMap 한국어 용어/규칙/모델) |
| 목 통증 | REP15 | UNKNOWN_SYMPTOM | — | UNCERTAIN | NECK_SITE_AMBIGUOUS(sore_throat vs pain+neck) | — | — | sore_throat;pain | A(MedMap 한국어 용어/규칙/모델) |
| 흉통 | REP15 | UNKNOWN_SYMPTOM | — | EXISTING_COMPOSITE | PAIN_PLUS_SITE | pain | 가슴 | pain | A(MedMap 한국어 용어/규칙/모델) |
| 복통 | REP15 | UNKNOWN_SYMPTOM | — | EXISTING_COMPOSITE | PAIN_PLUS_SITE | pain | 배 | pain | A(MedMap 한국어 용어/규칙/모델) |
| 어지럼 | REP15 | KNOWN_SYMPTOM | dizziness | EXISTING_CANONICAL | MODEL_AUTO(STEP27) | dizziness | — | dizziness | A(MedMap 한국어 용어/규칙/모델) |
| 두근거림 | REP15 | KNOWN_SYMPTOM | palpitations | EXISTING_CANONICAL | EXACT_TERM | palpitations | — | palpitations | A(MedMap 한국어 용어/규칙/모델) |
| 고혈압 | REP15 | UNCERTAIN | — | NON_SYMPTOM | PRODUCT_MAPPER_NON77:E_104(antecedent) | — | — | — | K/A(비증상 근거) |
| 결핵 | REP15 | UNCERTAIN | — | NON_SYMPTOM | DISEASE_LABEL_KO:Tuberculosis | — | — | — | K/A(비증상 근거) |
| 고혈압 | STEP27_SMOKE | UNCERTAIN | — | NON_SYMPTOM | PRODUCT_MAPPER_NON77:E_104(antecedent) | — | — | — | K/A(비증상 근거) |
| 결핵 | STEP27_SMOKE | UNCERTAIN | — | NON_SYMPTOM | DISEASE_LABEL_KO:Tuberculosis | — | — | — | K/A(비증상 근거) |
| 코피가 나요 | STEP27_SMOKE | UNCERTAIN | hemoptysis | UNKNOWN_SYMPTOM | KOREAN_LINK_MISSING | — | — | — | D(연결 자원 없음) |
| 숨이 차요 | STEP27_SMOKE | KNOWN_SYMPTOM | dyspnea | EXISTING_CANONICAL | MODEL_AUTO(STEP27) | dyspnea | — | dyspnea | A(MedMap 한국어 용어/규칙/모델) |
| 기침이 나요 | STEP27_SMOKE | KNOWN_SYMPTOM | cough | EXISTING_CANONICAL | MODEL_AUTO(STEP27) | cough | — | cough | A(MedMap 한국어 용어/규칙/모델) |
| 토했어요 | STEP27_SMOKE | KNOWN_SYMPTOM | vomiting | EXISTING_CANONICAL | MODEL_AUTO(STEP27) | vomiting | — | vomiting | A(MedMap 한국어 용어/규칙/모델) |
| 열이 나요 | STEP27_SMOKE | KNOWN_SYMPTOM | fever | EXISTING_CANONICAL | MODEL_AUTO(STEP27) | fever | — | fever | A(MedMap 한국어 용어/규칙/모델) |

## 4. ontology 개념 관계(영어 이름 조회 — 한국어 연결 아님)

| 출처 | A | B | 관계 | 가까운 공통 조상 |
|---|---|---|---|---|
| hpo | Epistaxis | Hemoptysis | DISTINCT | Phenotypic abnormality; All |
| hpo | Epistaxis | Hematemesis | DISTINCT | Abnormal bleeding; Abnormality of blood and blood-forming tissues |
| hpo | Headache | Pain | DISTINCT | Phenotypic abnormality; All |
| snomed | Bleeding from nose | Hemoptysis | DISTINCT | Respiratory finding; Bleeding |
| snomed | Bleeding from nose | Hematemesis | DISTINCT | Bleeding; Clinical finding |
| snomed | Headache | Pain | A_IS_A_B | Pain / sensation finding; Sensory nervous system finding |

검증기 판정(한국어 근거가 있다고 가정): | 개념 | HPO | HPO 판정 | SNOMED | SNOMED 판정 |
|---|---|---|---|---|
| Epistaxis | HP:0000421 | NEW_CONCEPT;NARROWER_THAN_EXISTING:EV:E_178 | SCTID:249366005 | NO_DEFINITION;NARROWER_THAN_EXISTING:EV:E_178 |
| Hemoptysis | HP:0002105 | DUPLICATE_OF_EXISTING:hemoptysis | SCTID:66857006 | DUPLICATE_OF_EXISTING:hemoptysis |
| Hematemesis | HP:0002248 | DUPLICATE_OF_EXISTING:hematemesis | SCTID:8765009 | DUPLICATE_OF_EXISTING:hematemesis |
| Headache | HP:0002315 | NARROWER_AS_ATTRIBUTE:pain+E_55(site) | SCTID:25064002 | NARROWER_AS_ATTRIBUTE:pain+E_55(site) |
| Fever | HP:0001945 | DUPLICATE_OF_EXISTING:fever | SCTID:386661006 | DUPLICATE_OF_EXISTING:fever |
| Pain | HP:0012531 | DUPLICATE_OF_EXISTING:pain | SCTID:22253000 | DUPLICATE_OF_EXISTING:pain |
| Hypertension | HP:0000822 | NOT_SYMPTOM_TYPE | SCTID:38341003 | NOT_SYMPTOM_TYPE |
| Tuberculosis | — | — | SCTID:56717001 | NOT_SYMPTOM_TYPE |

## 5. STEP27 ↔ STEP28 (Silver 같은 입력)

| STEP27 | STEP28 | n |
|---|---|---|
| COMPLEX_INPUT | UNCERTAIN | 1 |
| KNOWN_SYMPTOM | EXISTING_CANONICAL | 42 |
| KNOWN_SYMPTOM | EXISTING_COMPOSITE | 1 |
| KNOWN_SYMPTOM | UNCERTAIN | 11 |
| NON_SYMPTOM | NON_SYMPTOM | 3 |
| UNCERTAIN | EXISTING_CANONICAL | 47 |
| UNCERTAIN | EXISTING_COMPOSITE | 12 |
| UNCERTAIN | NON_SYMPTOM | 7 |
| UNCERTAIN | UNCERTAIN | 91 |
| UNCERTAIN | UNKNOWN_SYMPTOM | 64 |
| UNKNOWN_SYMPTOM | EXISTING_CANONICAL | 28 |
| UNKNOWN_SYMPTOM | EXISTING_COMPOSITE | 31 |
| UNKNOWN_SYMPTOM | NON_SYMPTOM | 1 |
| UNKNOWN_SYMPTOM | UNCERTAIN | 4 |
| UNKNOWN_SYMPTOM | UNKNOWN_SYMPTOM | 99 |

- Q1 STEP27 UNKNOWN/UNCERTAIN 384 중 기존 증상으로 회수 118 · 신규 ontology 후보 0 · 검증된 신규 0
- Q4 STEP27 KNOWN 인데 STEP28 기존 아님 11 · 다른 canonical 0
- 비증상(EXT_EVAL weak-non 903): STEP28 {"UNCERTAIN": 632, "NON_SYMPTOM": 204, "UNKNOWN_SYMPTOM": 37, "EXISTING_COMPOSITE": 13, "EXISTING_CANONICAL": 17} · 증상으로 연결 30 · 신규 concept 0 (STEP27 {"UNCERTAIN": 718, "NON_SYMPTOM": 131, "UNKNOWN_SYMPTOM": 48, "KNOWN_SYMPTOM": 5, "COMPLEX_INPUT": 1})
- 내부 합성 문장(기존 증상 차단 여부): {"INT_DEV_CORE": {"n": 59, "categories": {"EXISTING_COMPOSITE": 3, "UNKNOWN_SYMPTOM": 12, "EXISTING_CANONICAL": 34, "UNCERTAIN": 10}, "existing_rate": 0.6271, "existing_precision_vs_gold": 0.9459, "blocked(gold supported → NON/NEW/UNKNOWN)": 12, "step27_known": 30, "step27_known_now_not_existing": 1}, "INT_REGRESSION_CORE": {"n": 109, "categories": {"EXISTING_COMPOSITE": 5, "EXISTING_CANONICAL": 53, "UNKNOWN_SYMPTOM": 34, "UNCERTAIN": 17}, "existing_rate": 0.5321, "existing_precision_vs_gold": 0.9655, "blocked(gold supported → NON/NEW/UNKNOWN)": 34, "step27_known": 41, "step27_known_now_not_existing": 0}}
- 중복 통제: {"candidates_resolved_to_existing(dup/narrower-attr/broader)": 0, "new_ids_unique": 0, "new_id_collision_with_77": 0} · 미지원 처리: {"UNKNOWN_with_display": 0, "UNKNOWN_with_canonical": 0}

## 6. 속도·자원

| 경로 | p50 ms | p95 ms | max ms |
|---|---|---|---|
| STEP27_ROUTER | 10.057 | 12.937 | 15.69 |
| PRODUCT_MAPPER | 0.026 | 0.044 | 0.09 |
| ONTOLOGY_KOR_LOOKUP | 0.009 | 0.017 | 0.07 |
| STEP28_FULL | 10.223 | 12.995 | 27.195 |

파이프라인 적재 3.65 s · RSS 적재 후 706.0 MiB · peak 768.5 MiB · 색인 265.0 MB(SQLite, 요청마다 원본 순회 없음).

## 7. 평가 후 발견한 결함(사후 확인 — 규칙은 고치지 않음, 다음 단계 수정 대상)

- **비증상 → 증상 연결 증가**: EXT_EVAL weak-non 903 중 STEP28 기존 증상 연결 30 (STEP27 자동수락 5). 근거별 {"PAIN_PLUS_SITE": 13, "MODEL_AUTO(STEP27)": 5, "MODEL_LEXICAL": 8, "PRODUCT_ALIAS+MODEL_LEXICAL": 3, "PRODUCT_ALIAS": 1}. 원인 후보: (a) 어휘 근거 lexical_support 가 '입력이 학습 문장 안에 들어 있음'을 허용 → 신체 부위 단독(어깨·허벅지·머리)·약 이름('기침 억제제')이 통과 (b) 통증 합성어 규칙이 질환명 안의 '두통'(혈관성 편두통·근긴장성 두통)에도 걸림 (c) weak label 잡음('흉통' 이 비증상 태그).
- **'통증' 단독 표현 손실**: STEP27 KNOWN → STEP28 비기존 11 입력, 근거별 {"EXACT_TERM_MULTI": 11}. 원인: 용어집 라벨을 '·' 로 나눌 때 EV:E_9('림프절(멍울) 부음·통증')에서 '통증' 조각이 생겨 pain 과 겹침(EXACT_TERM_MULTI).
- **제품 매퍼 구토→오심**: 내부 합성 문장 기존 연결 오답 {"INT_DEV_CORE": [["웩웩거리면서 토했어요", "vomiting", "nausea"], ["정신이 아찔해요", "dizziness", "confusion"]], "INT_REGRESSION_CORE": [["헛구역질만 계속 나요", "vomiting", "nausea"], ["노란 물 같은 걸 토했어요", "vomiting", "nausea"]]} — PRODUCT_ALIAS 경로가 제품 매퍼의 기존 오매핑(E_148)을 그대로 가져옴. '구토' 단독은 SOURCE_CONFLICT(UNCERTAIN).
- 위 결함을 Silver·EXT_EVAL 결과를 본 뒤 고치면 사후 조정이므로 이번 수치는 사전 고정 규칙 그대로다.

## 8. 재현성

{"files_compared": 18, "identical": 17, "different": ["index/ontology_index.sqlite"], "sqlite_note": "index/ontology_index.sqlite 바이트 차이는 meta 표(빌드 소요 시간)뿐 — 추가 재빌드 후 meta 제외 7개 표(concept·sct_status·term·xref·sty·kor_term·hpo_alt) 정렬 내용 해시 동일 확인", "runs": "run_all.sh 2회(logs/run1.log·run2.log, sha1/sha2.txt)"}

## 9. 답

1. **77개 제한에서 얼마나 벗어났나**: 한국어 입력 기준으로는 거의 못 벗어났다. 검증된 신규 concept 입력 0/442. 대신 STEP27 이 UNKNOWN/UNCERTAIN 으로 남긴 표현 중 118 개가 기존 concept·속성 조합(두통 → pain+머리 등)으로 회수됐다 — 이것은 77 밖 확장이 아니라 77 안 연결 개선이다.
2. **한국어 ↔ 영어 ontology 연결**: MedMap 자체 한국어 용어(기존 77)를 거쳐 STEP20 curated id 로 연결(경로 A/B)한 것만 근거가 있다. 로컬 SRL 0 한국어 자원은 검사명·약재명뿐이고, HPO·SNOMED International 에는 한국어가 없다. 로컬 xlm-roberta-base 는 gate 미달(hit@5 1.2%, 기존 증거 한국어 라벨 84개 기준).
3. **찾은 새 concept**: 영어 색인·검증기에서는 Epistaxis(HP:0000421 · SNOMED 249366005)를 77 밖 concept 으로 찾고 객혈·토혈과 DISTINCT 로 구분했으며 기존 EV:E_178(비정상 출혈·멍)의 하위임을 기록했다. 그러나 한국어 '코피' → Epistaxis 를 잇는 로컬 허용 자원이 없어 한국어 입력에서는 연결하지 않았다(UNKNOWN 원문 보존).
4. **중복 처리**: 같은 id·같은 CUI 는 기존(DUPLICATE_OF_EXISTING), 속성 칸이 있는 기존 concept 의 하위는 기존+속성(Headache → pain+E_55), 속성 칸 없는 기존 concept 의 하위는 상위 연결을 기록한 신규 후보(Epistaxis → E_178 하위). 신규 id 의 77 충돌 0.
5. **코피/객혈/토혈**: 객혈·토혈은 기존 concept(hemoptysis·hematemesis), 코피는 hemoptysis 후보 표시 없이 UNKNOWN/UNCERTAIN(§3). ontology 상 세 개념은 DISTINCT(§4).
6. **두통·발열**: 두통 = pain + 부위(머리), 발열 = fever(제품 alias + KoE 어휘 근거). STEP27 의 오분류(77 밖 검색 대상)를 정정.
7. **여전히 못 찾는 증상**: UNKNOWN 163 — 예: 코피가, 염증이, 감기, 가래에, 염증, 염증을, 감각이상, 실신전단계, 염증이나, 저린 증상이, 고름이, 대사성 어지럼증의, 말초성 어지럼증은, 중추성 어지럼증은, 출혈이, 피로에, 경련, 기억저하, 마비가, 감기에서. 전부 한국어 연결 자원 부재(경로 D).
8. **기존 질환 모델에 바로 못 쓰는 이유**: 49질환 모델 입력은 DDXPlus 증거 223개 고정. 신규 concept 은 모델 feature 가 아니라 MODEL_SUPPORTED = False — 쓰려면 학습 데이터에 그 증상이 기록된 환자 표본과 재학습·재검증이 필요(이번 범위 밖).
9. **MedMap 연결에 필요한 것**: (a) 한국어 ↔ ontology 연결 자원 결정 — MDRKOR(MedDRA 한국어) 이용 조건 확인 또는 라이선스 확인된 한국어 의학 용어집 (b) 사람 검증 Gold(77 안/밖 라벨) (c) 제품 매퍼 구토→오심 오매핑 정리(SOURCE_CONFLICT 원인) (d) '목' 부위 모호성(인후통 vs 목 통증) 확인 질문 UX (e) PatientState 에 미지원 증상 원문 슬롯 설계(PRODUCT_INTEGRATION = HOLD).
10. **STEP29**: `docs/step29_handoff.md` — 문장 → 언급 span 분리 → 각 span 을 STEP28 Expansion 으로 정규화 + 부정·시점·주체 slot. 자동 실행하지 않음.
