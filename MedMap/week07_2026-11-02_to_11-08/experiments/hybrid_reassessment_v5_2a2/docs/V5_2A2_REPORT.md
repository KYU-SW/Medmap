# MedMap v5-2A.2 보고서 — 검사 사건별 정정 귀속과 시간 일관성

자동 생성(make_v5_2a2_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.

## 1. 재현한 문제(PHASE 1)

- 경로: hybrid521/comparator.py `compare521` — 정정된 기록마다 `th = superseded_at - EPS` 로 `_v52(pg, th, mode)` 를 다시 불러 환자 전체 상태로 이전 판단을 재계산.
- 최소 반례(C02): 사건 버전 CT001@E1:C1:V1(기록 r1)의 공개 시점 판단 10.0 → ['WEAKEN', ''], 유효 구간 안 판단 [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], 문맥 출처 ['n1', 'n2'].
- v5-2A.1 은 이 버전의 이전 판단을 [(11.999999, 'PE-CTPA-NEGATIVE', 'INSUFFICIENT_EVIDENCE')] 하나로 보고(정정 직전 환자 전체 상태 재계산) → 공개 이후 추가된 문맥 기록(문맥 출처 참조)의 영향이 CT 판독 이력에 섞이고 공개 당시 판단은 사라짐. 같은 구간에 공개된 트로포닌(OBS:t11)은 PE 레거시 판단의 문맥 출처가 아님.

## 2. 세 결과 계약

| 결과 | 내용 | 표시 |
|---|---|---|
| EVENT_VERSION_HISTORY | 사건(명시 lineage+supersedes)별 판독 버전, 버전 기록에 직접 귀속되는 원시 판단만, 유효 구간 안 시점별 관측 | 구간 안 판단 변화 시 문맥 출처 표시 |
| PATIENT_AS_OF_HISTORY | 공개 시각마다 v5-2A.1 비교(무수정) 요약, 새 기록·정정 기록·판단 변화와 원인 | 원인: EVENT_VERSION_CHANGED / PATIENT_CONTEXT_CHANGED / ATTRIBUTION_UNRESOLVED |
| CORRECTION_ONLY_COUNTERFACTUAL | 입력 이력 재생, 사건의 한 버전만 남기고 T_ref 에서 같은 평가기 | COUNTERFACTUAL_REPLAY · NOT_HISTORICAL_OBSERVATION · NOT_CAUSAL_PROOF, 고정 문맥 동일성 검사 |

## 3. 결과

- 사례 함수 20개 + 단위 검사 3개(C18·C19·C27), 시점 스냅샷 84개, 사건 22개, 버전 38개
- 버전 상태: {'ACTIVE': 75, 'NOT_YET_AVAILABLE': 77, 'SUPERSEDED': 23} · 사건 상태: {'CONFLICTING_EVENT_EVIDENCE_HOLD': 2, 'NO_ACTIVE_VERSION': 30, 'SINGLE_ACTIVE_VERSION': 71}
- 유효 구간 안 판단이 바뀐 버전 판단 5건: [('C02_other_result_between', 'CT001@E1:C1:V1', 'PE-CTPA-NEGATIVE', [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], ['n1', 'n2']), ('C04_patient_vs_event_differ', 'CT001@E1:C1:V1', 'PE-CTPA-NEGATIVE', [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], ['n1', 'n2']), ('C05_other_test_kept', 'CT001@E1:C1:V1', 'PE-CTPA-NEGATIVE', [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], ['n1', 'n2']), ('C06_counterfactual_ct_only', 'CT001@E1:C1:V1', 'PE-CTPA-NEGATIVE', [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], ['n1', 'n2']), ('C17_multi_context_dependency', 'CT001@E1:C1:V1', 'PE-CTPA-NEGATIVE', [['WEAKEN', ''], ['INSUFFICIENT_EVIDENCE', 'DIRECTIONAL_PATH_CONFLICT']], ['n1', 'n2'])]
- 사건 미연결: {'UNRESOLVED_EVENT_LINK': 30, 'INVALID_EVENT_METADATA': 2} · 귀속 상태: {'ATTRIBUTION_UNRESOLVED': 14, 'DIRECT': 20, 'DIRECT_WITH_CONTEXT_DEPENDENCY': 56}
- 환자 전체 이력 판단 변화 원인: {'ATTRIBUTION_UNRESOLVED': 3, 'EVENT_VERSION_CHANGED': 47, 'PATIENT_CONTEXT_CHANGED': 8}
- 가상 비교 15건(수행 15, 고정 문맥 동일 15, 출력 차이 있음 15, 주입 버전 사용 4)
- Graph vs Flat: 20/20 전체 동일, 영역별 {'EVENT_VERSION_HISTORY': 20, 'PATIENT_AS_OF_HISTORY': 20, 'CORRECTION_ONLY_COUNTERFACTUAL': 20, 'v5_2a1_compat': 20} (공용 규칙 — 의학적 정확도 아님)
- 레지스트리 37개 활성 0 · 신규 방향 관계 0

## 4. 테스트·보존

| 묶음 | 실행 | 결과 |
|---|---|---|
| v5_2a2 | 30 | OK |
| v5_2a1 | 27 | OK |
| v5_2a | 30 | OK |
| v5_1 | 32 | OK |
| v4 | 17 | OK |
| v3 | 28 | OK |
| v2 | 124 | OK |

- 기존 v1~v5-2A.1 파일 205개 체크섬: 변경 0 · 누락 0
- git: 전 22줄 → 후 23줄, 추가 ['?? exp/hybrid_reassessment_v5_2a2/'], 사라짐 []

## 5. 보고서 예시(C02)

### C02_other_result_between

**A. 검사 사건별 판독 이력(직접 귀속 판단만)**
- 사건 CT001@E1: 상태 (12.5, 'SINGLE_ACTIVE_VERSION')
  - CT001@E1:C1:V1 기록 r1 공개 10.0 정정 12.0
    - PE-CTPA-NEGATIVE: 공개 시점(10.0) 약화 → 유효 구간 안 변화 ['약화', '근거 부족(DIRECTIONAL_PATH_CONFLICT)'] (문맥 출처 ['n1', 'n2'])
  - CT001@E1:C1:V2 기록 r1c 공개 12.0 정정 None
    - PE-CTPA-POSITIVE: 공개 시점(12.0) 근거 부족(DIRECTIONAL_PATH_CONFLICT)
- 사건 LAB-T11@E1: 상태 (12.5, 'SINGLE_ACTIVE_VERSION')
  - LAB-T11@E1:C1:V1 기록 OBS:t11 공개 11.0 정정 None

**B. 환자 전체 as_of 이력(그 시점 전체 정보 기준)**
- as_of 1.0: 판단 []
- as_of 10.0: 판단 [('PE-CTPA-NEGATIVE', '약화')] · 새 기록 ['r1'] · 정정 [] · 변화 원인 ['EVENT_VERSION_CHANGED']
- as_of 11.0: 판단 [('PE-CTPA-NEGATIVE', '근거 부족(DIRECTIONAL_PATH_CONFLICT)')] · 새 기록 ['OBS:t11', 'n2'] · 정정 [] · 변화 원인 ['EVENT_VERSION_CHANGED', 'PATIENT_CONTEXT_CHANGED']
- as_of 11.5: 판단 [('PE-CTPA-NEGATIVE', '근거 부족(DIRECTIONAL_PATH_CONFLICT)')] · 새 기록 [] · 정정 [] · 변화 원인 []
- as_of 12.0: 판단 [('PE-CTPA-POSITIVE', '근거 부족(DIRECTIONAL_PATH_CONFLICT)')] · 새 기록 ['r1c'] · 정정 ['r1'] · 변화 원인 ['EVENT_VERSION_CHANGED']
- as_of 12.5: 판단 [('PE-CTPA-POSITIVE', '근거 부족(DIRECTIONAL_PATH_CONFLICT)')] · 새 기록 [] · 정정 [] · 변화 원인 []

**C. 정정만 바꾼 가상 비교(COUNTERFACTUAL_REPLAY · NOT_HISTORICAL_OBSERVATION · NOT_CAUSAL_PROOF)**
- CT001@E1 CT001@E1:C1:V1→CT001@E1:C1:V2 @T_ref=12.5: 고정 문맥 동일 True, 차이 [('PE-CTPA-NEGATIVE', 'CHANGED_EVENT_VERSION', '근거 부족(DIRECTIONAL_PATH_CONFLICT)', '없음'), ('PE-CTPA-POSITIVE', 'CHANGED_EVENT_VERSION', '없음', '근거 부족(DIRECTIONAL_PATH_CONFLICT)')]. 동일한 기록 문맥을 고정하고 이 사건의 판독 버전만 바꿨을 때 추론 엔진 출력이 달라졌습니다. 실제 과거 판단·실제 진단 변경·인과 증명이 아닙니다.


## 6. 발견·한계

- [결함·수정] v4 `add_record` 는 없는 기록을 정정 대상으로 받으면 docs·그래프 노드를 먼저 넣은 뒤 KeyError → 그래프에는 남고 평면표에는 없어 결과 불일치(C20 첫 실행에서 발견). v4 는 수정하지 않고 v5-2A.2 입력 계층에서 상태 변경 전 거부. 회귀 테스트 1개는 발견 후 추가(사전 고정 기대값 아님).
- [표시 수정] 사건 ID 없이 명시 정정만 있는 경우(C13) 판단 소멸은 '원인 미확인', 정정본 판단은 '사건 연결 없는 새 기록(문맥 변화)'으로 엇갈리게 표시되던 것을 둘 다 ATTRIBUTION_UNRESOLVED(명시 정정 확인·사건 연결 없음)로 통일 — 첫 산출물 검토 중 발견, 테스트 기대값 변경 없음.
- v4 입력 API 로는 supersedes 순환을 만들 수 없음(정정 대상이 먼저 있어야 함) → C19 는 출처 행 단위 검사로만 확인.
- 문맥 출처는 v4 결정 트리가 참조한 사실 키의 출처 기록(키가 없으면 facts_used 전체를 상한으로 사용).
- 가상 비교는 교체 버전에서 파생된 고정 문맥 기록이 있으면 수행하지 않음(문맥 고정 불가).
- T_ref 이후 공개된 버전은 공개 시각을 T_ref 로 당겨 주입 — INJECTED 로 표시.
- 레거시 PE 판단의 의학적 타당성, 검사 전 확률 충돌 처리 규칙(v4)은 미검증.

## 7. 다음 단계에 미치는 영향 / v5-2B 진입 조건

- 구조 보완은 여기서 종료 가능: 사건 이력·환자 이력·가상 비교가 분리돼, 의학 관계 검토 결과를 넣어도 정정·문맥 영향이 섞이지 않음.
- 남은 핵심은 의학 내용: PE 레거시 관계의 적용 조건(검사 전 확률 충돌 시 처리 등), ACS·MI 방향 관계와 허혈 근거 규칙, 심낭염 적용 조건 — 전문의 검토(CRQ-06·07·09·10·11·15).
- 방향 판단 집계를 근거 그룹 단위로 할지, 문맥 의존 판단을 어떻게 보고할지 정책 결정 필요.
