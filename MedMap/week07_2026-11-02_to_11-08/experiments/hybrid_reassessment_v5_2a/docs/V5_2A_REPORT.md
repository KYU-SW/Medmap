# MedMap v5-2A 보고서 — 다질환 근거 비교 엔진

자동 생성(make_v5_2a_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.

## 1. 구현 알고리즘

환자 기록 → v4/v5-1 추출(개념·수치·ECG) → 가설 등록(출처·의사 확인 분리) → 그래프 순회 또는 평면표 필터로 같은 입력 수집 → v5-1 기준 사실 함수·eval5/eval_kofn 으로 가설별 조건 평가 → 미확정 이유 분류 → 증거 연결 4단계 → 명시 메타데이터 기반 중복·종속 → 공통·차별·미연결 분류 → 비교 결과·보고서.

| 모듈 | 역할 | 재사용 |
|---|---|---|
| hybrid52/hypotheses.py | 가설 출처·의사 확인·WD 1개/에피소드·자동 생성 금지 | v5-1 MultiHypothesis |
| hybrid52/dependency.py | EXACT_DUPLICATE/DERIVED/DISTINCT/UNKNOWN, 중복 그룹, 같은 사건 값 불일치 | — (신규, 명시 메타데이터만) |
| hybrid52/criteria.py | 가설별 조건 행, 부족 정보 7분류, v5-1 분류와 일치 검사 | v5-1 criterion_facts_*, eval5, eval_kofn, combine_evidence, v1 test_status |
| hybrid52/evidence_linker.py | 연결 4단계, 미연결 소견 분류(A~F) | v3 link_status, v5-1 v5_override |
| hybrid52/comparator.py | 그래프·평면표 공용 비교 | v5-1 evaluate_common |
| hybrid52/graphs.py | PatientGraph5 상속, 메타데이터·검사 종류 노드, 순회 수집, 비교 부분그래프 | v4 PatientGraph(as_of·정정·에피소드), v4 Reasoner(레거시 PE) |
| hybrid52/flat.py | 같은 정보를 행 필터로 수집 | v5-1 rows_of |
| hybrid52/report.py | 한국어 비교 보고서 | — |

## 2. 결과 요약

- 사례: CASE 01~28 (28개, 평가 시점 32개), 조건 행 241개
- 조건 결과 분포: {'CONFLICT': 2, 'FALSE': 10, 'NOT_EVALUATED_NO_VERIFIED_RULE': 34, 'TRUE': 74, 'UNKNOWN': 121}
- 부족 정보 분류: {'CONFLICTING_INFORMATION': 1, 'MISSING_INFORMATION': 80, 'NO_VERIFIED_RULE': 34, 'PENDING_RESULT': 8, 'SEE_COMPONENT_CRITERIA': 33, 'UNRESOLVED_EPISODE': 1}
- 종속 상태: {'DEPENDENCY_UNKNOWN': 21, 'DERIVED_FROM_SAME_SOURCE': 114, 'DISTINCT_OBSERVATION': 25} · 중복 그룹 6 · 같은 사건 값 불일치 1 · 공통 소견 10
- 미연결·미평가 분류: {'DIAGNOSIS_MENTION_NOT_FINDING': 6, 'EXCLUDED_KNOWN_MISLINK': 10, 'LINKED_CONCEPT_NO_VERIFIED_RULE': 9, 'RESULT_NOT_YET_AVAILABLE': 6, 'TEST_NAME_MENTION_ONLY': 12, 'UNMAPPED_FINDING': 5, 'UNRESOLVED_EPISODE': 1, 'UNSUPPORTED_EXTRACTION': 30}
- Graph vs Flat: 32/32 동일(공용 평가 함수 — 구현 일관성 확인일 뿐 임상 정확도 아님)
- v5-1 분류와 기준 상태 불일치: 0건 · v5-2A SUPPORT/WEAKEN ID: 0건 · 신규 활성 방향 관계: 0건
- 레지스트리: 후보 37개, 그룹 {'B': 22, 'C': 9, 'A': 6}, 활성 0, 실행 전후 SHA256 동일 True

## 3. 테스트·보존

| 묶음 | 실행 | 결과 |
|---|---|---|
| v5_2a | 30 | OK |
| v5_1 | 32 | OK |
| v4 | 17 | OK |
| v3 | 28 | OK |
| v2 | 124 | OK |

- 기존 v1~v5-1(+v5-0) 파일 165개 체크섬: 변경 0 · 누락 0
- git 상태: 작업 전 18줄 → 후 19줄, 이번 작업으로 추가: ['?? exp/hybrid_reassessment_v5_2a/'], 사라진 줄: []

## 4. 발견한 문제

- 레거시 v4 PE 는 같은 CTPA 결과의 반복 서술을 각각 판단함: 중복 그룹에 속한 레거시 항목 9개(예: [('C06_same_result_repeated', 'EV:r1:0', 'DUP:EVT:CTPA-1:1'), ('C06_same_result_repeated', 'EV:s1:1', 'DUP:EVT:CTPA-1:1'), ('C06_same_result_repeated', 'EV:d1:0', 'DUP:EVT:CTPA-1:1')]). v4 는 수정하지 않고 v5-2A 에서 duplicate_group_id 로 표시만 함.
- v3 추출은 ECG 기록의 'ECG' 단어 자체를 UNSUPPORTED_TEST_OR_PROCEDURE 로 남김 → UNSUPPORTED_EXTRACTION 으로 분류됨(소견 아님).
- 구현 중 결함: hybrid52/criteria.py 가 v1 모듈을 v4 경로 설정 전에 import 하면 실패(뮤테이션 검사용 별도 실행에서 발견, 정상 실행 경로는 import 순서상 통과하고 있었음) → 패키지 __init__ 에서 v4 graphs 를 먼저 import 하도록 수정.

## 5. 비교 보고서 예시(CASE 01)

### 다질환 비교 — C01_three_hypotheses (as_of=5.0)

- 환자: SYN-C01 · Working Diagnosis: h_pe · 가설 간 배타 관계: 가정하지 않음
- 임상적 판단: NOT_EVALUATED · 신규 방향 관계: 0건

#### h_acs — V5:DX:ACS (의사 추가 가설, 의사 확인 UNCONFIRMED, 에피소드 E1)
- 방향 관계: NO_VERIFIED_DIRECTIONAL_RELATION · 연결 증거 2개 · 원본 기록 OBS:t0, OBS:t1
  - INJ_ABOVE_SEX_SPECIFIC_URL: 충족 (출처 OBS:t0, OBS:t1)
  - INJ_RISE_OR_FALL_REPORTED: 미확인 (출처 -) · 이유: MISSING_INFORMATION
  - ACUTE_INJURY_RESEARCH: 미확인 (출처 OBS:t0, OBS:t1)
  - ACS_DIAGNOSTIC_CRITERIA: 검증 규칙 없음 (출처 -) · 이유: NO_VERIFIED_RULE
  - 연구용 분류 V5:STATE:ACUTE_MYOCARDIAL_INJURY: UNDETERMINED_UNKNOWN — RESEARCH_ONLY_NOT_VALIDATED, 방향 NOT_DERIVED

#### h_pe — DX:Pulmonary embolism (의사 Working Diagnosis, 의사 확인 UNCONFIRMED, 에피소드 E1)
- 방향 관계: LEGACY_V4_UNVALIDATED · 연결 증거 0개 · 원본 기록 없음
  - PE_V5_CRITERIA: 검증 규칙 없음 (출처 -) · 이유: NO_VERIFIED_RULE
  - 레거시 v4: [] — LEGACY_V4_UNVALIDATED(전문의 검토 전, v5 검증 결과 아님)

#### h_peri — DX:Pericarditis (의사 추가 가설, 의사 확인 UNCONFIRMED, 에피소드 E1)
- 방향 관계: NO_VERIFIED_DIRECTIONAL_RELATION · 연결 증거 4개 · 원본 기록 e1, n1
  - CLINICAL_PRESENTATION: 충족 (출처 EV:n1:0)
  - PERI_RUB: 충족 (출처 EV:n1:1)
  - PERI_ECG: 충족 (출처 ECG:e1:0, ECG:e1:1)
  - PERI_CRP: 미확인 (출처 -) · 이유: MISSING_INFORMATION
  - PERI_EFFUSION: 미확인 (출처 -) · 이유: MISSING_INFORMATION
  - PERI_CMR: 미확인 (출처 -) · 이유: MISSING_INFORMATION
  - PERI_ADDITIONAL_AT_LEAST_2: 충족 (출처 ECG:e1:0, ECG:e1:1, EV:n1:1)
  - 연구용 분류 DX:Pericarditis: DEFINITE — RESEARCH_ONLY_NOT_VALIDATED, 방향 NOT_DERIVED(지침 등급을 SUPPORT/WEAKEN 으로 바꾸지 않음)

- 공통 소견(SHARED_FINDING, 지지 의미 없음): 없음
- 중복 증거 그룹: 없음
- 정보 없음: h_acs:INJ_RISE_OR_FALL_REPORTED, h_peri:PERI_CRP, h_peri:PERI_EFFUSION, h_peri:PERI_CMR
- 검증 규칙 없음: h_acs:ACS_DIAGNOSTIC_CRITERIA, h_pe:PE_V5_CRITERIA
- 미연결·미평가 [EXCLUDED_KNOWN_MISLINK]: EV:e1:0
- 미연결·미평가 [UNSUPPORTED_EXTRACTION]: EV:e1:1

한계: 합성 사례 기반 기술 검증. 임상 성능 NOT_EVALUATED. / 신규 진단 방향(SUPPORT/WEAKEN) 관계 0건 — 가설 간 우열·확률·순위 없음. / 심낭염·심근손상 기준은 연구용(RESEARCH_ONLY_NOT_VALIDATED). 기준 충족 ≠ 확진. / PE 판단은 v4 레거시(LEGACY_V4_UNVALIDATED). 전문의 검토 전. / 중복·종속은 명시 메타데이터만 사용. 메타데이터 없으면 DEPENDENCY_UNKNOWN. / 추출 범위는 v3·v5-1 사전·정규식 한계를 그대로 가짐(UNSUPPORTED_EXTRACTION 로 표시).


## 6. 한계·미검증

- 신규 진단 방향 관계 0 — 가설 간 우열·확률·순위 없음. 임상 성능 NOT_EVALUATED.
- 심낭염(ESC 2025 Table 4)·급성 심근손상(UDMI5 Box 1) 기준은 연구용. CRQ-10·11·15(심낭염), CRQ-06·07·09(MI) 전문의 검토 전.
- ACS·MI 진단 기준(허혈 근거 포함)은 NO_VERIFIED_RULE. PE 는 LEGACY_V4_UNVALIDATED.
- 중복·종속은 명시 메타데이터가 있을 때만 판정. 실제 EMR 의 사건 ID 가용성은 확인 필요.
- 검사 종류→기준 연결표(TEST_FEEDS)는 v5-1 기준 함수 입력 구조를 옮긴 것(의학 관계 아님).
- 추출 범위는 v3·v5-1 사전·정규식 한계 그대로(예: 진단명 외 증상 다수 미추출).

## 7. v5-2B 진입 조건

- ACS·MI 검증 가능한 방향 관계와 허혈 근거 규칙(전문의 검토)
- 심낭염 기준 적용 조건(CRQ-10·11·15) 확정
- PE 레거시 관계의 위험 조건 해석 재검토 및 반복 서술 중복 계산 정책
- 다질환 비교 결과의 임상 평가 기준 정의
