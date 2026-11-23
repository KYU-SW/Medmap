# 공통 데이터 구조 (구현: `hybrid/schema.py`, `hybrid/temporal.py`)

## DiagnosisAssertion
`assertion_id, encounter_id, diagnosis_label, concept_id, subtype, status, asserted_by, asserted_at, certainty, basis_evidence_ids, provenance, supersedes`
- status: CONFIRMED / WORKING / DIFFERENTIAL / RULED_OUT / HISTORICAL / PATIENT_REPORTED / UNKNOWN
- asserted_by: PHYSICIAN / EMR_RECORD / PATIENT / MODEL_EXTRACTED / DATASET_ANNOTATION / SIMULATED / UNKNOWN
- 같은 병명이라도 상태·주체·시각이 다르면 다른 진술. 이전 진술은 `supersedes` 로 보존.

## EvidenceItem
`evidence_id, encounter_id, kind, text, polarity, experiencer, concept_id, uncertainty, observed_at, recorded_at, available_at, reviewed_at, provenance, supersedes`
- polarity: PRESENT / ABSENT / VALUE_ONLY / NOT_ASSESSED / UNKNOWN. **NOT_ASSESSED ≠ ABSENT**.
- 시각 4개를 분리: 시행·기록·이용 가능·의사 확인. `available_at` 없으면 어느 시점에도 사용 안 함.
- concept_id 는 연결 근거가 있을 때만. 추정 금지.

## Provenance
`source_type, source_ref, data_class, text_span, extractor, extractor_version, physician_confirmed`. data_class: SYNTHETIC / PUBLIC_OPEN / RESTRICTED. 출처 없으면 생성 거부.

## 검사 상태(TestEvent → TestStatus)
ORDER·COLLECT·RESULT·REVIEW·CANCEL·CORRECT 사건에서 as_of 상태 계산: NOT_ORDERED / ORDERED / PENDING / RESULT_AVAILABLE / REVIEWED / CANCELLED / UNKNOWN.
- 사건 기록이 없으면 UNKNOWN. 정정 결과는 다시 RESULT_AVAILABLE(재확인 필요).
- 추천 판단에 필요한 후속 필드(설계): 판단 변경 가능성, 위험·금기, 적용 지침, 근거 없음 = NOT_EVALUABLE. 중복 판정은 상태만 보고 의학적 재검사 필요성은 판단하지 않음.

## Reasoner 계약
입력 `ReasonerInput(item_id, case_id, hypothesis, evidence, context_summary, prior_evidence, as_of, data_class)` → 출력 `ReasonerOutput(item_id, reasoner, status, effect, grade, reason_code, citations, claims, used_evidence_ids, flags)`
- status: ANSWERED / ABSTAIN / NOT_IMPLEMENTED. 기권·미구현은 판단값을 가질 수 없음.
- effect: SUPPORT / WEAKEN / CONTRADICTION / NO_CLEAR_EFFECT / UNCERTAIN / INSUFFICIENT_EVIDENCE / NOT_APPLICABLE.
- grade: -2~+2. 근거가 등급을 정의할 때만. 효과에서 임의 환산 금지.

## 지식 관계 v2 (`hybrid/knowledge.py`)
관계: HAS_FINDING, HAS_RISK_FACTOR, EVALUATED_BY, SUPPORTS_HYPOTHESIS, WEAKENS_HYPOTHESIS, DIFFERENTIAL_OF, REQUIRES_CONTEXT, EVIDENCE_FROM, HAS_SUBTYPE, HAS_CONTRAINDICATION, HAS_UNCERTAINTY.
필드: 주체·객체, 출처 종류·위치·버전, 원문 인용, 적용 조건, 예외, 근거 수준, 검토 상태(PROPOSED / SOURCE_QUOTE_CHECKED / CLINICIAN_REVIEWED / RETIRED).
- 방향 관계는 인용·적용 조건 필수, ONTOLOGY·COOCCURRENCE 출처 거부, PROPOSED 는 추론에 미사용.
- 기존 EXP-01b 간선은 방향 근거가 아니라 HAS_FINDING 후보로 읽기만 함. **의학 관계 내용은 이번에 하나도 추가하지 않았다.**

## 표준 용어 후보와 사용 조건
| 표준 | 확인 상태 |
|---|---|
| LOINC | 무료, 라이선스 동의 필요(검색 확인) |
| SNOMED CT | 회원국·제휴 라이선스 필요. 한국 회원 여부·조건 **확인 필요** |
| HPO, NCI Thesaurus, ICD-O, ICD-10 | 이번 공식 페이지에서 조건 확인 실패 → **확인 필요**, 사용 전 재확인 |
| HL7 FHIR | 구조 참고만. 라이선스 원문 **확인 필요** |
| UMLS | 기존 프로젝트 규칙: 문자열 공개 저장소 금지 |
