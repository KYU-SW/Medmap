# MedMap v5-2A.1 보고서 — 검사 사건 단위 근거 그룹화·출처 추적

자동 생성(make_v5_2a1_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.

## 1. 알고리즘

v5-2A 비교 결과(무수정) → 원시 사용 수집(레거시 v4 방향 판단 그대로 + 원자 기준 입력) → 증거 ID→기록→명시 선언(사건·파생·완전 중복) 출처 해석(순환·사건 ID 충돌·부모 누락·뿌리 여러 개는 무효 → DEPENDENCY_UNKNOWN) → 그룹 키(가설·에피소드·사건·소견·관계)가 모두 같을 때만 묶음 → 같은 사건·같은 개념·다른 결과는 충돌 표시(제거 없음) → 정정본 공개 후 이전 판단은 정정 직전 시점 출력으로 SUPERSEDED_EVIDENCE 보존 → 보고 문장.

| 모듈 | 역할 |
|---|---|
| hybrid521/lineage.py | 선언 수집·사건 해석(순환·충돌·부분 출처 검출) |
| hybrid521/grouping.py | 원시 판단 수집, 그룹화, 개수 분리 |
| hybrid521/conflict.py | 동시 충돌, 정정·다단계 정정 |
| hybrid521/comparator.py | v5-2A 결과 연결, 그래프·평면표 공용 규칙 |
| hybrid521/graphs.py / flat.py | PatientGraph52 상속(중복 ID 거부·선언 이력·부분 출처 자리 노드) / 같은 선언 행 |
| hybrid521/report.py | 원시 판단과 그룹 분리 문장 |
| hybrid521/audit.py | v5-2A 레거시 중복 9건 읽기 전용 감사 |

## 2. 결과

- 사례 25개(CASE 01~20 + 경계 E01~E07), 평가 시점 24개
- 레거시 방향 원시 판단 39개 → 그룹 35개, 상태 {'DEPENDENCY_UNKNOWN': 10, 'DERIVED_FROM_SAME_EVENT': 8, 'DISTINCT_OBSERVATION': 12, 'EXACT_DUPLICATE': 1, 'SUPERSEDED_EVIDENCE': 4}
- 기준 입력 원시 8개 → 그룹 8개, 상태 {'DEPENDENCY_UNKNOWN': 2, 'DERIVED_FROM_SAME_EVENT': 2, 'DISTINCT_OBSERVATION': 4}
- 동시 충돌 1건(해결하지 않음) · 정정으로 대체된 원시 판단 보존 4개 · 출처 해석 문제 {'DERIVATION_CYCLE': 2, 'EVENT_ID_CONFLICT': 3, 'PARTIAL_PROVENANCE': 1}
- 원본에 없는 판단 주입: RAISED:SOURCE_NOT_FOUND: RAW:h_pe:PE-CTPA-NEGATIVE:EV:zzz:0 
- Graph vs Flat: 전체 24/24 · 그룹 24/24 · 선언 동일 23/23 (공용 규칙 — 구현 일관성일 뿐 의학적 정확도 아님)
- 레지스트리 37개 {'B': 22, 'C': 9, 'A': 6} 활성 0 · 실행 전후 SHA256 동일 True · 신규 방향 관계 0

## 3. v5-2A 레거시 중복 9건 감사

- 보고 9건 = 재구성 9행(일치 True). v5-2A 의 9 는 (사례 × 평가 시점 × 레거시 항목) 행 수 — 같은 판단이 여러 평가 시점에서 반복 집계됨
- 고유 원시 판단 5개, 같은 사건 그룹 2개 [['C06_same_result_repeated', 'CTPA-1', 'PE-CTPA-NEGATIVE'], ['C26_graph_flat_full', 'CTPA-1', 'PE-CTPA-NEGATIVE']]
- 분류: {'CONFIRMED_SAME_EVENT': 9, 'CONFIRMED_DISTINCT_EVENT': 0, 'DEPENDENCY_UNKNOWN': 0, 'CONFLICTING_EVENT_EVIDENCE': 0} — 근거는 v5-2A 합성 사례에 선언된 메타데이터(실제 EMR 사건 ID 아님)

## 4. 테스트·보존

| 묶음 | 실행 | 결과 |
|---|---|---|
| v5_2a1 | 27 | OK |
| v5_2a | 30 | OK |
| v5_1 | 32 | OK |
| v4 | 17 | OK |
| v3 | 28 | OK |
| v2 | 124 | OK |

- 기존 v1~v5-2A 파일 185개 체크섬: 변경 0 · 누락 0
- git: 전 20줄 → 후 21줄, 추가 ['?? exp/hybrid_reassessment_v5_2a1/'], 사라짐 []

## 5. 보고서 예시

### 근거 그룹 — C01_same_event_three_docs (as_of=7.0)

- h_pe: 레거시 방향 원시 판단 3개 · 그룹 1개 · 중복 연결 3개 · 종속 미확인 0개 · 충돌 그룹 0개 · 정정된 그룹 0개 / 기준 입력 원시 0개 · 그룹 0개
  - 폐색전증 약화 판단(레거시 v4, 미검증)이 3개 출력됐지만, 동일 검사 사건(CT001)에서 파생된 기록(d1, r1, s1)으로 확인돼 근거 그룹 1개로 표시했습니다. 원시 판단 3개와 출처는 모두 보존합니다.
- 그룹 수는 증거 강도·확률·통계적 독립 근거 수가 아닙니다. 레거시 판단은 LEGACY_V4_UNVALIDATED, 임상 성능 NOT_EVALUATED.

### 근거 그룹 — C09_after_correction (as_of=8.0)

- h_pe: 레거시 방향 원시 판단 2개 · 그룹 2개 · 중복 연결 0개 · 종속 미확인 0개 · 충돌 그룹 0개 · 정정된 그룹 1개 / 기준 입력 원시 0개 · 그룹 0개
  - 폐색전증 지지 판단(기록 r1)은 이후 정정 기록으로 대체됐습니다(SUPERSEDED_BY:['r1c'] at 7.0). 감사용으로 보존하며 현재 판단이 아닙니다.
- 그룹 수는 증거 강도·확률·통계적 독립 근거 수가 아닙니다. 레거시 판단은 LEGACY_V4_UNVALIDATED, 임상 성능 NOT_EVALUATED.


## 6. 발견·한계

- v5-2A 의 '9건'은 평가 시점별 반복 집계였음(고유 5개).
- v5-2A dependency.group_of 는 첫 부모만 따라가며 순환·사건 ID 충돌을 검출하지 않음. 같은 기록에 사건 ID 를 두 번 선언하면 그래프(첫 간선)와 평면표(마지막 선언)가 다르게 읽을 수 있음 → v5-2A 는 수정하지 않고, v5-2A.1 상속 클래스에서 평면 meta 를 '첫 사건·모든 파생'으로 맞추고 전체 선언은 lineage 에서 검사.
- v5-2A 그래프는 없는 부모 기록을 가리키는 파생 선언에서 KeyError → v5-2A.1 은 MISSING_SOURCE_RECORD 자리 노드로 보존.
- 테스트 작성 오류 1건: 그래프·평면표 평가 수 기대값을 27 로 잘못 계산 → 사례 정의상 24 로 정정(동작 기대값 변경 아님).
- 정정 이전 판단은 '정정 공개 직전 시점'의 레거시 출력으로 재구성(그 시점 다른 기록 영향 포함).
- 실제 EMR 의 사건 ID·파생 관계 가용성은 확인 필요. 그룹 수는 증거 강도·통계적 독립성 아님.
- 레거시 PE 판단 자체의 의학적 타당성은 미검증(LEGACY_V4_UNVALIDATED, 전문의 검토 전).

## 7. v5-2B 진입 조건

- ACS·MI 방향 관계·허혈 규칙, 심낭염 적용 조건(CRQ-06·07·09·10·11·15) 전문의 검토
- 방향 판단 집계 시 근거 그룹 단위 사용 여부(정책) 결정 — 현재는 표시만
- 실제 자료의 사건 ID 확보 방법 확인
