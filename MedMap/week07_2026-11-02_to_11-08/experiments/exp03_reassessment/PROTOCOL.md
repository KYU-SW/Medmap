# EXP-03 프로토콜 — Temporal Evidence & Diagnostic Reassessment Safety-Net (합성 단계)

- 작성: 2026-11-03, 구현·테스트 실행 전 고정. 이후 변경은 이 파일 끝 '변경 기록'에 날짜·이유와 함께 덧붙임(본문 수정 금지).
- 범위: 합성 시나리오만. 실제 환자 counted run 없음. 실제 MIMIC 은 시간정보 구조 집계(§12)만.
- 진단 가설은 전부 **SIMULATED_WD**(가상 의사 가설). 실제 working diagnosis 아님. 퇴원·ED 진단 코드·최종 CT 를 초기 가설로 쓰지 않음.

## 1. 연구 질문
- RQ1 새 증거 도착 시 가설 검토 상태가 사전 규칙대로 갱신되는가
- RQ2 결과 대기(PENDING)를 음성으로 취급하지 않는가
- RQ3 미래에 이용 가능해진 기록이 과거 시점 판단에 들어가지 않는가
- RQ4 명시적 모순(CONFLICT)과 정보 부족(INSUFFICIENT/UNKNOWN)을 구분하는가
- RQ5 재검토 알림이 근거 기록·증거 유형·이용 가능 시각·규칙 ID 를 추적 가능하게 갖는가
- RQ6 가설 변경·검사 결과 정정 시 상태와 알림이 일관되게 갱신되는가

## 2. 가설(시스템 동작 가설 — 임상 가설 아님)
- H1 제안 방식은 모든 합성 시나리오에서 미래정보 누출 0, 필수 상태 전이 100% 통과
- H2 기준선(단순 집계)은 이용 가능 시각·정정 이력 미반영으로 누출·정정 실패가 관찰됨(관찰 여부만 보고, 우월성 통계 주장 없음)

## 3. 입력·시간 정의
- 증거 필드: event_id · encounter_id · evidence_type · source_type · source_reference(필수, 빈 값 거부) · observed_at · recorded_at · available_at · evidence_status · uncertainty_status · concept · detail · revision_id · supersedes(정정 대상 event_id). superseded_by 는 시점별로 계산.
- 가설 이벤트: hypothesis_id · encounter_id · dx · set_at · provenance(SIMULATED_WD 고정) · action(SET/WITHDRAW).
- **이용 가능 규칙(P-AVAIL)**: 시점 T 에서 증거 사용 = available_at 이 있고 available_at ≤ T. available_at 없음 → 어떤 시점에도 사용 안 함(EXCLUDED_UNKNOWN_AVAILABILITY 로 셈). available_at < observed_at → 시각 역전, 사용 안 함(EXCLUDED_TIME_INVERSION). 영상 판독의 available_at = 판독 확인 시각(storetime 계열), 검사 시행 시각(charttime)으로 대체하지 않음.
- 정정: supersedes 가 있는 기록이 T 에 사용 가능하면 대상 기록은 T 부터 무효. 정정 기록이 아직 사용 불가면 원 기록 유지.
- 체류 격리: 타임라인은 encounter 1개. 다른 encounter_id 증거·가설은 추가 시 거부.

## 4. 증거 → 가설 관계 규칙(가설 'DX:Pulmonary embolism' = 급성 PE 가설에만 정의)
| 규칙 | 조건 | 관계 | 출처 성격 |
|---|---|---|---|
| R1 | CTPA 판독 ACUTE_POS(EXP-02 v3b) | SUPPORTS(결정 증거) | EXP-01b 그래프 CONCEPT:ctpa_filling_defect→PE(DisMech, 인용 없음) + v3b 추출 |
| R2 | CTPA 판독 NEGATIVE(명시적 전체 음성) | CONFLICTS(결정 증거) | 시스템 정의 규칙(가설 확인 검사의 명시적 음성) — 임상 검증 아님 |
| R3 | CTPA 판독 CHRONIC_OR_PERSISTENT | NOT_CONFIRM_ACUTE(급성 미확인, 'PE 없음' 아님) | v3b 분류 |
| R4 | CTPA 판독 UNCERTAIN(의심·배제 불가·부분 음성·과거력·품질 제한) | UNKNOWN | v3b 분류 |
| R5 | CTPA 판독 NO_MENTION(의뢰 사유에만 등장 포함) | UNKNOWN | v3b 분류 |
| R6 | CTPA 의뢰 있음 + 사용 가능한 해당 판독 없음 | PENDING | 시스템 정의 |
| R7 | 증상·활력 POSITIVE, 그래프에 concept→가설 SUGGESTS 간선 | SUPPORTS(약한 증거, 문헌 연관) | EXP-01b 그래프 |
| R8 | 증상·활력 NEGATIVE | NO_EFFECT(음성은 모순 아님, 가설 유지) | EXP-01b 원칙 |
| R9 | 그래프 간선 없는 concept(D-dimer·트로포닌 T 등) | NO_KNOWLEDGE(지지·모순·배제 모두 아님) | EXP-01b 그래프 |
- 가설이 PE 가 아니면 CTPA 규칙 R1–R6 미적용(NOT_DEFINED), R7–R9 는 해당 가설 간선으로 동일 적용.

## 5. 가설 단위 요약 상태(증거별 관계는 보존, 요약은 별도 계산)
1. 가설 없음 → NO_HYPOTHESIS
2. 사용 가능한 결정 증거(R1–R5)가 있으면: R2 있음 → CONFLICT / 아니면 R1 있음 → SUPPORTED / 아니면 R3 있음 → INSUFFICIENT(chronic_only) / 아니면 UNKNOWN
3. 결정 증거 없음 + R6 → PENDING
4. 결정 증거 없음 + R7 → SUPPORTED(decisive=False)
5. 그 외 → INSUFFICIENT
- 함께 보고하는 플래그: support · conflict · pending · unknown · chronic_only · decisive.

## 6. 재검토 알림(REVIEW_NEEDED) — 시점 T 의 함수(체크포인트 간격과 무관)
- AL1 NEW_CONFLICT: 현재 가설에 대해 사용 가능·유효한 R2 증거마다 1건
- AL2 SUPPORT_RETRACTED: 현재 가설의 R1 증거가 정정으로 무효가 되고, 정정 기록의 관계가 SUPPORTS 가 아님
- 알림 필수 필드: hypothesis_id · rule · evidence event_id · source_reference · evidence_type · available_at. 하나라도 없으면 생성 안 함.
- 세션 로그: 연속 체크포인트 사이 새로 생긴 알림 / 사라진 알림 + 사유(HYPOTHESIS_CHANGED · RESOLVED_BY_CORRECTION · OTHER).
- 정보 부족·대기·불확실·만성만 은 알림을 만들지 않음.

## 7. 성공·실패 기준(합성 테스트 합격선 — 실제 환자 성능 아님)
- 미래정보 누출 0 · 근거 없는 확정 판정 0 · 미확인(PENDING/UNKNOWN/NO_MENTION) 음성 오분류 0 · 출처 누락 0 · 필수 상태 전이 100%
- 결함 주입 7종 전부 테스트가 실패로 검출(대조 사본 통과 전제)

## 8. 비교
- PROPOSED: 이 프로토콜 구현
- BASELINE-N(새 비교 대상, 기존 구현 아님): 시간 = observed_at(검사 시행 시각), 정정 이력 무시(모든 판독 유효), 의뢰 대기 무시(음성으로도 쓰지 않음), 판독 분류 → ACUTE_POS 지지 / NEGATIVE 모순 / 그 외 무영향. 일부러 고장 낸 부분 없음 — '이용 가능 시각·출처 구분 없는 단순 집계' 정의 그대로.
- BASELINE-E(기존 구현): EXP-01b `ReasoningSession` + `assess_working_dx`(observed=검사 시각, recorded=이용 가능 시각, 정정=supersedes). 요약 매핑: conflicting 경로 → CONFLICT, supporting 경로 → SUPPORTED, 그 외 INSUFFICIENT. 알림 개념 없음 → conflicting 경로를 알림으로 간주.
- 세 방식 모두 같은 시나리오·같은 기대 출력.

## 9. 제외 조건
- available_at 없음·시각 역전 증거(집계만), 다른 encounter 증거(거부)

## 10. 테스트 방법
- 시나리오 CASE A–L + 보조(C2 과거력, C3 출처 없음, C4 다른 체류, C5 이용 시각 없음, A2 D-dimer 음성): 각 체크포인트 기대 요약·알림 규칙 집합을 시나리오 파일에 고정 → 자동 비교
- 누출: 모든 시나리오·체크포인트에서 assess(전체 기록, T) == assess(T 까지 사용 가능한 기록만, T)
- v3b 연결: 같은 합성 판독문을 v2·v3b(EXP-02 동결 코드, 읽기 전용 import)로 분류해 증거로 넣고 차이 기록
- 결함 주입: 대조 사본 + 7개 변이(미래 결과 삽입 · PENDING→NEGATIVE · 출처 제거 · 가설 이력 누락 · 만성→급성 · 정정 무시 · 체류 혼합)

## 11. 해석 한계
- 합성 규칙에 대한 정합성 검증일 뿐, 의학적 타당성·실제 오진 탐지·임상 안전성 검증 아님. R2 등 규칙은 시스템 정의이며 임상 지침 검증 아님.

## 12. 실제 MIMIC 시간정보 적합성(집계만)
- EXP-02 봉인 추출(extract_v2_20261030_1139) 로컬 스크립트로: 판독·검사의 시행/확인 시각 결측률, 역전, 지연 분위수, ED 체류 연결 가능 비율. 원문·식별자 비출력. 실제 WD 없음 → 알림의 의학적 정오 채점 안 함.

## 변경 기록
- (없음)
