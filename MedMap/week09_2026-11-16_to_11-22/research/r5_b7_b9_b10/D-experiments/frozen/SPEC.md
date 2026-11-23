# SPEC — B7+B9+B10 통합 평가 사양 (SUBAGENT D, 실험 전 동결)

> **[합성]** 모든 조건 c0.., 행동 a0.., 효과·부담 수치, 시험 점, 선호 범위, 상호작용 규칙은 형식 검증용 가상 값이며 의학적 사실과 무관하다. "형식 충돌"은 입력 규칙상의 충돌일 뿐 의학적 금기가 아니다. 이 사양은 의학적 정확도를 다루지 않는다.
> 동결 시점에 후보 방법(Baseline A/B/B'/C, 변형 V) 코드는 **존재하지 않았다**. 동결 후 정답·사양은 수정하지 않는다(틀린 기대는 정정 메모로만).

## 1. 입력 (inputs/instances.json)
- 임상 변수 c_0..c_{k-1} ∈ {0,1}, 관측 obs_i ∈ {T, F, U(미확인)}. 의존성 deps: [a,b] = (c_a=1 → c_b=1).
- 가능 상태 S = {s : obs 와 일치, deps 만족}. 미확인 변수만 상태 키로 쓴다(예: `c0=1,c2=0`, 미확인 없으면 `-`).
- 지침 g: 적용 조건 app_g(리터럴 논리곱, 빈 것=항상), 선택지 options_g (options_g[0] = 1차 권고, 나머지 = 대체 행동). 지침 간 행동 id 는 겹치지 않음.
- 계획 p = 각 지침에서 선택지 하나씩 고른 벡터. **계획 번호 = itertools.product(options_0, options_1, ...) 순서.**
- 상태 s 에서 실현 집합 R(p,s) = {p_g : app_g(s)}.
- 규칙: `conflict`(a,b,cond): a,b ∈ R(p,s) 이고 cond(s) 이면 p 는 s 에서 허용 불가(형식 충돌). `compatible`(a,b): 양립 진술.
- 행동 a: effect(편익 기준값), pills, visits(치료 부담), trial = 시험 대상자 2차원 공변량 점 목록 또는 null(지식 없음).
- 환자 공변량 x(s) = (x0, x1_base + x1_delta·s[x1_var]); x1_var 가 미확인 변수이면 **같은 숨은 변수가 지침 적용·규칙 조건·근거 지지에 동시에 등장(공유 변수)**.
- 근거 상태 ev(a,s): trial=null → NOENTRY(지식 부족); x(s) ∈ conv(trial)(경계 포함) → OK(효과 정의); 아니면 OUT(효과 미정의, 근거 범위 밖).
- 값 벡터 v(p,s) = (Σ effect, −Σ pills, −Σ visits) — R(p,s) 의 모든 행동이 OK 일 때만 정의.
- 선호 W = {w ∈ 단체(3) : |w_i − center_i| ≤ r}. r=0 이면 점 선호. 효용 = v·w.

## 2. 상태별 라벨 L(s) (우선순위 순)
1. 허용 계획 집합 A(s)=∅ → `CONFLICT`
2. A(s) 안에 NOENTRY 행동을 포함한 계획이 있으면 → `KNOWLEDGE_GAP`
3. 아니고 OUT 행동을 포함한 계획이 있으면 → `EVIDENCE_GAP` (효과 미정의는 0 도, 금기도, 제외도 아님: 비교 불가)
4. 아니면 NO(s) = {p∈A : ∀w∈W ∀q∈A v_p·w ≥ v_q·w}, PO(s) = {p∈A : ∃w∈W ∀q∈A v_p·w ≥ v_q·w}.
   NO≠∅ → `CONFIRMED`(payload = NO 의 실현 집합들), 아니면 `PREF`(payload = PO 의 실현 집합들).

## 3. 상태 간 질의
- EWAS(∃w∀s): 모든 s 에서 L(s)∉{CONFLICT, KNOWLEDGE_GAP, EVIDENCE_GAP}, p∈A(s), 그리고 하나의 w 가 모든 s 에서 p 를 최적으로 만드는 계획 번호 집합.
- FSEW(∀s∃w): 같은 조건에서 ∀s p∈PO(s). RNEC: ∀s p∈NO(s). (FSEW ⊇ EWAS ⊇ RNEC)

## 4. 구성요소 라벨
- 지침 적용: 모든 s 에서 참 `CONFIRMED_APPLY` / 모두 거짓 `NOT_APPLY` / 섞임 `CONDITIONAL_APPLY`.
- 규칙(형식 탐지, 1차 권고 계획 기준): 모든 s 발동 `REAL` / 없음 `NONE` / 일부 `CONDITIONAL`; compatible 규칙은 `N/A`.

## 5. 최종 라벨 (출력 범주)
| 코드 | 범주 | 규칙 |
|---|---|---|
| NO_GROUND_TRUTH | 확정 불가(정답 없음·비교 불가) | 같은 쌍에 conflict 와 compatible 이 우선순위 없이 공존하고 두 지침이 어떤 s 에서 동시 적용 가능 |
| REAL_CONFLICT | 실제 충돌 | 모든 s 에서 CONFLICT |
| CONVERGED | 충돌 없음(수렴) | 모든 s 에서 같은 CONFIRMED payload 이고 모든 규칙 NONE |
| CONFIRMED_PLAN | 확정 적용 | 모든 s 에서 같은 CONFIRMED payload, 형식 충돌은 있었으나 대체로 해소 |
| PREFERENCE_DEPENDENT | 선호 의존 | 모든 s 에서 같은 PREF payload |
| EVIDENCE_SCOPE_INSUFFICIENT | 근거 범위 부족 | 모든 s 에서 EVIDENCE_GAP |
| KNOWLEDGE_GAP | 지식 부족 | 모든 s 에서 KNOWLEDGE_GAP |
| CONDITIONAL_CONFLICT | 조건부 충돌 | s 별로 다르고 일부 s 가 CONFLICT |
| CONDITIONAL_PLAN | 조건부 적용 | s 별로 다르고 모든 s 가 CONFIRMED |
| INFO_HOLD | 정보 부족 보류 | 그 밖에 s 별로 다름 |

## 6. 금지 출력 (방법별·인스턴스별 판정)
- F1 근거 없는 효과 확정: 정답 L(s)∈{EVIDENCE_GAP, KNOWLEDGE_GAP} 인 상태에서 방법이 CONFIRMED 또는 PREF(효과 값을 써서 비교) 주장.
- F2 선호 불명인데 단일 최적 확정: 정답 L(s)=PREF 인 상태에서 방법이 CONFIRMED 주장.
- F3 결측 무시 확정(결측=정상 계열): 정답 최종이 상태 의존(CONDITIONAL_CONFLICT/CONDITIONAL_PLAN/INFO_HOLD)인데 방법이 상태 무관 확정 라벨(CONVERGED/CONFIRMED_PLAN/REAL_CONFLICT) 출력.
- F4 시험 제외=금기: 정답 L(s)=EVIDENCE_GAP 인 상태에서 방법이 CONFLICT 주장하거나, OUT 계획을 허용 불가로 처리했음을 출력에 표시(방법이 `excluded_out_of_support` 를 보고).
- F5 형식 충돌=의학 금기: 출력 라벨 어휘에 금기 표현이 없도록 스키마로 보장(출력 문자열 검사, 기대값 0).

## 7. 손 사례 기대값 (GT 계산 전 설계 의도)
| 사례 | 현상 | 기대 최종 | 추가 기대 |
|---|---|---|---|
| A | 실제 충돌(대체 없음) | REAL_CONFLICT | |
| B | 겉보기 충돌 → 대체로 해소 | CONFIRMED_PLAN | payload {a0,a2} |
| C | 조건부 충돌(c0 미확인) | CONDITIONAL_CONFLICT | c0=1 CONFLICT |
| D | 선호 의존 | PREFERENCE_DEPENDENT | {a0},{a1} |
| E | 주변 범위 안·결합 볼록 껍질 밖 | EVIDENCE_SCOPE_INSUFFICIENT | |
| F | 시험 항목 없음 | KNOWLEDGE_GAP | |
| G | 공유 변수(적용 조건 + 지지 판정) | CONDITIONAL_PLAN | 모듈 분리(B') 는 과보수 가능 |
| H | 혼합 양화 ∃w∀s ≠ ∀s∃w | INFO_HOLD | EWAS=∅, FSEW={0} |
| I | G+H 세 요소 동시(같은 c0) | INFO_HOLD | EWAS=∅, FSEW={0} |
| J | 모순 규칙 | NO_GROUND_TRUTH | 정확도 계산에서 제외 |
| K | 수렴 | CONVERGED | |

## 8. 정답 생성 방법 (ground_truth.py)
전수 열거(상태) × 선호 polytope 정확 기하 × 근거 상태 정확 볼록 껍질. Fraction 정확 산술, scipy 미사용.
**지시와의 차이(의도적):** 지시는 "선호 polytope 꼭짓점"이었으나 ∃w 판정은 W 꼭짓점만으로는 부족하다(가능 최적 영역의 꼭짓점이 W 꼭짓점이 아닐 수 있음, 선행 B-jnp 조건 2). 그래서 ∀w 는 W 꼭짓점, ∃w 는 반평면 절단 후 비어 있지 않음(= 배열 꼭짓점 전수 검사와 동치)으로 판정한다. [수학적 검토]

## 9. 채점 규칙
- 비교 대상: NO_GROUND_TRUTH 인스턴스는 정확도에서 제외하고 별도 보고(범주 (5)).
- label_acc: 최종 라벨 일치.
- state_fn_acc(조건 논리 일치): 모든 s 에서 (kind, payload) 일치. 상태 개념이 없는 방법(A, C)은 모든 s 에 같은 출력을 낸 것으로 본다. **단일 계획만 출력하는 방법**은 그 실현 집합이 정답 payload 에 포함되면 payload 일치로 본다(동점 관대 규칙).
- full_acc: label_acc ∧ state_fn_acc.
- wrong_confirm: 방법 최종 ∈ {CONVERGED, CONFIRMED_PLAN, CONDITIONAL_PLAN} 인데 full 불일치.
- hold_set_acc(판단 보류 조건): {s : kind ≠ CONFIRMED} 집합 일치.
- gap_distinction: 정답 최종 ∈ {INFO_HOLD, EVIDENCE_SCOPE_INSUFFICIENT, KNOWLEDGE_GAP} 인 인스턴스에서 label_acc.
- ewas_acc / fsew_acc: 집합 일치(해당 출력을 내는 방법만).
- app_acc / rule_acc: 구성요소 라벨 전부 일치.
- 안정성(E5/E6/E7 family): 인접 수준 쌍에서 정답 출력 불변인데 방법 출력 변함(불필요 변동), 정답 변했는데 방법 불변(둔감).
- 시간: perf_counter, 메모리: tracemalloc peak(별도 패스).
- 가능 결과 분류: (1) A 실패·B 성공 (2) B·B' 모두 실패 (3) 성공하나 비용 큼 (4) 입력 지식 부족(KNOWLEDGE_GAP 가 정답 — 알고리즘 실패 아님) (5) 정답 없음(NO_GROUND_TRUTH — 비교 불가).

## 10. 생성기 조정 기록
초안 GT 분포(방법 코드 없음)를 보고 1회 조정: 시험 점 분포 폭 확대, p_entry 0.85→0.93, 선택지 수에 1 포함. 목적은 라벨 다양성(충돌·확정 범주 확보). 조정 전후 로그: logs/draft_gt.log, logs/draft_gt2.log.
