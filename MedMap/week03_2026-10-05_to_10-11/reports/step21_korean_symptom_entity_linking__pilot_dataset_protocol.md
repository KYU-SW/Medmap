# Pilot dataset protocol (STEP21)

## label space
- STEP20 `curation/curated_mappings.tsv` 에서 role ∈ {SYMPTOM, SIGN, COMPOSITE} 인 87개 evidence = canonical symptom 공간. 그 외 23개(속성·수식어·노출)는 class 로 쓰지 않는다.
- pilot 20 concept 과 DDXPlus evidence 연결: {"pain": ["E_53", "E_14"], "dyspnea": ["E_66", "E_64", "E_67"], "fever": ["E_91"], "cough": ["E_201", "E_203", "E_77"], "nausea": ["E_148"], "vomiting": ["E_211", "E_166"], "diarrhea": ["E_51"], "dizziness": ["E_76"], "loc": ["E_159"], "palpitations": ["E_155", "E_164"], "fatigue": ["E_89", "E_88"], "limb_weakness": ["E_84", "E_176"], "swelling": ["E_151"], "hemoptysis": ["E_45"], "hematemesis": ["E_210"], "confusion": ["E_39"], "chills": ["E_94"], "sore_throat": ["E_97"], "heartburn": ["E_173"], "decreased_appetite": ["E_32", "E_161"]}
- 선정 기준: (1) DDXPlus 학습 데이터에서 자주 나오는 초기 증상(initial_evidence_ko frequent_ids 포함) (2) 응급·감별 가치(객혈·토혈·의식 소실·흉통) (3) 한국어 표현 다양성이 큰 것.
- 사용자 후보와의 차이:
  - 흉통·두통·복통 → 별도 concept 아님. `pain` + site attribute (DDXPlus E_53 + E_55 구조, STEP20 결론).
  - 실신 → inventory 에 syncope 없음 → `loc`(E_159 의식 소실)로 대체.
  - 전신 쇠약 → generalized weakness concept 없음 → `limb_weakness`(E_84·E_176)로 대체; "온몸에 힘이 없어요"는 Tier D(피로/쇠약 애매)로 둠.
  - 의식 변화 → `confusion`(E_39).
  - 변비 → inventory 에 없음(E_150 은 극성 반전된 PARTIAL) → 제외, 대신 `sore_throat`(E_97)·`heartburn`(E_173)·`decreased_appetite`(E_32·E_161) 추가.
  - 어지럼 → `dizziness`(E_76). 실신 전 느낌(E_82 presyncope)은 pilot 밖 concept 으로 남김.

## 표현 출처 (provenance)
- DICTIONARY(train 쪽): 기존 MedMap 자원만 — terminology_ko.json(evidence_short label 과 구성 부분, evidence_questions), initial_evidence_ko.json(label·detail), question_labels_ko.json. 294개 표현.
- TEST(gold): `data/pilot_source_utterances.tsv`, **source_type = synthetic_paraphrase**(Claude 작성, 2026-10-08). existing_medmap 0, existing_patient_companion 0 (친구 저장소는 로컬에 없음 — 2026-10-04 사용자 결정으로 미반입).
- 제품 매퍼의 기존 평가 문장(exp/intake_mapper_v1*/)은 매퍼 튜닝·평가에 쓰였으므로 test 에 넣지 않았다.

## 문장 유형 (사용자 A–J + S)
| type | n |
|---|---|
| A | 22 |
| B | 33 |
| C | 91 |
| D | 25 |
| E | 19 |
| F | 21 |
| G | 20 |
| H | 14 |
| I | 7 |
| J | 17 |
| S | 5 |

A 짧은 일상 · B 자연 문장 · C 비정형/의성어 · D 증상+속성 · E 복수 증상 · F 부정 · G 과거/현재 · H 다른 사람 · I 애매 · J 매핑 불가 · S 철자 변형

## 품질 등급
| tier | n |
|---|---|
| A | 72 |
| B | 104 |
| C | 76 |
| D | 22 |

TIER_A 정답 명확 · TIER_B 정답 있으나 구어·애매 표현 · TIER_C 복수/부정/시점/타인/불확실 · TIER_D 한 concept 에 연결하면 안 됨(정답 = 없음)

concept 그룹별 문장 수: {'chills': 11, 'confusion': 10, 'cough': 14, 'decreased_appetite': 10, 'diarrhea': 12, 'dizziness': 12, 'dyspnea': 16, 'fatigue': 12, 'fever': 14, 'heartburn': 11, 'hematemesis': 10, 'hemoptysis': 10, 'limb_weakness': 12, 'loc': 12, 'nausea': 12, 'other_person': 10, 'pain': 16, 'palpitations': 12, 'sore_throat': 11, 'swelling': 12, 'unknown': 22, 'vomiting': 13}

## gold 형식 (`data/pilot_gold.csv`)
- `gold_mentions`: [{concept, status ∈ present/absent/historical/uncertain, subject ∈ patient/other}]. 환자 정답 = subject=patient 인 concept.
- `primary_concept` / `secondary_concepts` / `other_person_concepts` / `attributes`(concept 별 slot) / `should_link` / `ambiguity_flag` / `reason`.
- "쥐어짜는 느낌" 같은 양상은 class 가 아니라 `attributes.pain.quality`.

## 누수 방지
- 사전과 정규화 완전일치 또는 difflib ≥ 0.8 → 평가에서 제거: 1건 [['가만히 있어도 가슴 통증이 계속돼요', 'NEAR_DUPLICATE_OF_DICTIONARY:가만히 있어도 가슴 통증']]
- gold 내부 near-duplicate(≥ 0.85)가 dev/test 에 갈린 경우 test 로 이동: ['U018', 'U177']
- 정답 concept 의 사전 stem 이 문장에 그대로 있으면 `lexical_exposure=seen`(암기), 아니면 `novel`(일반화): seen 53 · novel 193 · 정답 없음 28. 결과는 둘을 분리해 보고한다.
- split: concept 그룹 안 원본 순서 index % 3 == 0 → dev, 나머지 test. threshold 는 dev 에서만 고른다.

## 정규화(과도한 규칙 금지)
공백·문장부호 제거, 사전 쪽 의문형 어미(-나요/-가요/-요 등) 제거, 명사형 어미(-ㅁ/-음) 제거 변형을 **추가**(원형도 유지 — '기침'의 ㅁ 받침 보호).
