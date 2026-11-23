# MedMap 52회차 독립 검증 보고서

- 검증자: 독립 검증 에이전트(실행 세션과 분리). 임상 전문가가 아니므로 의학적 정답은 판정하지 않음. 원문 근거 기준 "논쟁 가능" 항목은 모두 **전문가 검토 필요**.
- 검증일: 2026-11-21
- 쓰기 범위: `red-team/verifier/` 만 사용. 다른 파일은 수정하지 않음.

## 판정: **PARTIALLY_VERIFIED**

| 영역 | 판정 | 요약 |
|---|---|---|
| 해시·동결 | 부분 통과 | REF-R sha256 일치(efaa9cfe…). 입력·run_v1 해시 일치. methods_v1.py 는 run1 실패 뒤 수정·재해시(RUN_LOG·FREEZE 2행에 기록). **입력 파일 수정 시각 01:49:27 이 REF-R 동결 시각 01:48:04 보다 늦음 — 기록 없음, 변경 내용 확인 필요** |
| 수치 재계산 | 통과 | 216행(4층 × 9 λ × 6 방법) × 14필드 전부 일치, 불일치 0건 |
| 질문 재현율·정밀도 | 통과 | question_results 72행, summary 질문 지표 전부 일치 |
| 방법 B 재구현 | 통과 | 50/50 라벨, 50/50 원인 그룹, 50/50 관련 변수, 12/12 질문 집합 일치(질문 순서는 비교하지 않음) |
| LEVEL B 지침 원문 정합성 | 부분 통과 | 50항목 중 OK 22, TYPE C 후보 21, 인코딩 누락·비일관 5, 사례 사실 문제 2. 라벨이 바뀔 수 있는 항목 12 |
| 사례 사실 | 부분 통과 | 근거 없는 known 값 1건(CASE_07 on_glucose_lowering), 반대 증거가 있는 known 값 1건(CASE_07 sbp_ge130), 논쟁 가능한 분류 2건(AF·대동맥판 협착 → cvd) |
| "B=REF 100%" 의 의미 | 제한적 | REF-R 은 인코딩의 논리적 폐포와 같음(재구현 B = REF 50/50). 타당성 근거가 아니라 내적 일관성 확인 |
| B 대 C/D 우위 주장 | 미검증 | C·D 의 오류는 각각 1항목뿐이고, 두 항목 모두 검증자가 논쟁 가능으로 표시한 인코딩 선택에서 나옴 |

통과로 보지 않은 이유: 계산과 재현은 정확함. 그러나 성능 해석의 기준(REF-R)과 입력 인코딩에 원문 근거 문제가 있고, 방법 간 차이가 바로 그 논쟁 항목 위에 있음.

---

## 1. LEVEL B 지침 원문 정합성 감사

전체 항목별 표: `level_b_audit.csv` (50행, 원문 txt 줄 번호 포함). 중점 5개 질문:

| 질문 | 원문 | 판정 |
|---|---|---|
| OA Sidebar 1 의 CVD·CKD NSAID 회피를 금기(contra)로 확정 | OA L954 "should **generally** be avoided in patients with or at risk for CVD, CKD"; 부록 I L7364 "Use with caution **or** avoid … renal impairment … known CVD, patients receiving anticoagulants" | **TYPE C 후보.** 원문은 상대적 회피·주의인데 인코딩은 절대 금기. 해당 항목: CASE_03 I3, CASE_05 I5, CASE_06 I2. 단 eGFR<30 회피(L956, "generally" 없음)는 금기로 둔 것이 원문과 맞음(CASE_04 I1). 세 사례 모두 다른 근거로 결론은 방어 가능(CVA+clopidogrel, at risk for CVD, warfarin+Celebrex 어지럼). 그래서 문제는 결론이 아니라 "확정"이라는 라벨 |
| SGLT2i 항목에 eGFR 하한 미인코딩 | DM L4707 금기/주의 "eGFR <20–30 (see labeling)"; DM L2962-2964 "evidence supports safety if eGFR is at least 20"; CKD L2923 "lowest eGFR for initiation … was 20" | **VA 원문과 불일치(조건 누락).** CKD 4기인 CASE_02 I4·CASE_04 I4, eGFR 18 시점이 있는 CASE_10 I4 에 해당. 라벨은 다른 미확인 변수 때문에 보류로 같지만, "eGFR≥20 인가" 질문이 B 질문 목록과 REF required_confirm 양쪽에서 빠짐. 질문 재현율 1.0 은 이 누락까지 공유한 결과 |
| CKD14 'unless intolerance' 를 미확인 시 보류 | CKD L2751-2754, L7311 "continuing therapy, unless there is drug intolerance or adverse event" | **해석 2가지 모두 가능 → 논쟁 가능.** 문형은 "기본 지속 + 예외(반증) 조건"으로 읽힘. 기록에 불내성이 없으면 지속(APPLY)으로 볼 수도 있음. 칼륨 미확인만으로 보류(CASE_02 I3, CASE_04 I5)한 것은 과도한 보류일 가능성. 같은 인코딩은 CASE_03 I4 의 CKD19 에는 원문에 없는 statin_intol 금기를 넣음(비대칭) |
| DM25 조건 처리 | DM L3147-3150 "**especially** those 65 years and older … **if** glycemic control can be achieved with other treatments" | **비일관.** CASE_01 I2·CASE_02 I5 는 age_ge65 를 필수 조건으로 넣어 원문보다 좁힘. CASE_08 I5 는 나이 조건이 없어 원문과 맞음. CASE_10 I1 은 "다른 치료로 조절 가능" 조건이 빠짐. "우선 선택"을 "기존 약 교체·중단"으로 넓힌 해석도 포함 |
| HTN4 'depending on patient characteristics and preferences' | HTN L1644-1646; L1693-1695 "frailty … orthostatic hypotension, and octogenarians/nonagenarians were excluded from clinical trials" | **TYPE C 후보 + 비일관.** 기립성 저혈압(시험 제외군 = 근거 적용범위 문제)을 P 금기로 바꿈. 80+/90+/허약(CASE_03·04·06·07)의 근거 범위(K)는 인코딩하지 않음. CASE_06 은 같은 사례 I1 에서 90세 근거 공백을 K 로 처리해 서로 맞지 않음. CASE_04 I6 은 기립성 금기 자체가 없음. "선호에 따라"인데 선호 변수가 있는 항목은 CASE_03/04 뿐 |

그 밖의 TYPE C·인코딩 후보(라벨 영향이 큰 순):

1. **CASE_04 I2(국소 NSAID)의 K 변수는 코퍼스 안에서 닫힘.** 같은 VA 묶음의 CKD CPG L7375 "Avoid NSAID use, including OTC and prescription (**oral/topical**), if possible". 지식 공백(K)이 아니라 다른 지침 원문을 대조하지 않은 것. REF HOLD[P,K] → NOT_APPLY 가능.
2. **CASE_08 I2(EDKA 후 SGLT2i)를 확정 금기로 둠.** VA DM 표는 DKA 를 주의사항(L4709)으로만 적음. CKD CPG L2917-2920 은 중증 질환 중 보류 후 "reinitiation … after an acute event has passed" 를 언급. 영구 금기는 사례 저자 Discussion 의 판단이고 VA 원문에는 없음. REF NOT_APPLY → HOLD[K] 가능.
3. **CASE_08 I4(MALA 후 metformin 재개).** CKD 모듈의 ">30"(L7307)만 적용하고 DM 표의 "do not initiate if eGFR <45"(L4643-4646)는 반영하지 않음. egfr_gt30=true 는 기저 eGFR 48 기준이고, AKI 회복 후 eGFR 은 원문에 없음. P 불확실성이 빠짐.
4. **CASE_09 I2(SGLT2i 시작).** 다른 모든 SGLT2i 항목과 달리 sglt2_contra 변수가 없음. 원문에는 약물 목록 자체가 없음. 동시 AKI 에 대해 CKD Box22(L7154)는 "SGLT2i 보류 고려"라고 함. REF 의 acceptable_confirm 에는 sglt2_contra 가 있지만 입력 변수에는 없음(내부 불일치).
5. **CASE_09 I3.** CKD 알고리즘 Box22 는 Box16(체액 상태)~Box20 을 배제한 뒤에 도달함. HF 악화·양측 흉수 환자에서 선행 조건을 생략한 채 이뇨제 보류를 확정함.
6. **CASE_13 I3.** 저자는 선택지 3개를 제시했고, CASE_13.json 도 "선호 없음 → Option 선택 불가"라고 기록함. 그런데 REF 는 APPLY 확정.
7. 경미한 것: CKD19 "initiation" 을 "유지"로 확장(CASE_01 I4, CASE_05 I1). DM9-10 "강화 = 자가혈당 측정 증가" 행동 정의(CASE_01 I3). 고령자 acetaminophen 2–3 g 문구(OA L7341)를 반영하지 않음(CASE_06 I3).

RULES_v1.csv 의 paraphrase 자체(조건 → 행동 요약)는 23개 규칙 모두 원문 권고 문장과 의미상 맞음. 문제는 paraphrase 가 아니라 인코딩(applies/contra)에서 강도와 조건을 바꾼 데 있음. 인용 쪽 번호와 MGCDS 원본 대조는 이번 감사에서 확인하지 않음(**확인 필요**).

## 2. 사례 사실 감사

원문 대조: PPC S1 Table(`ppc/s002.txt`), PMC XML, `agentA_candidates/CASE_xx.json`.

| 사례 | known 값 | 원문 | 판정 |
|---|---|---|---|
| CASE_07 | on_glucose_lowering=true | PMC10359101 Table 2(약국 16종·집 28종 전체 대조표)에 혈당강하제 행이 없음. 본문은 "non-insulin dependent type 2 diabetes (HbA1c 5.2%)". CASE_07.json 도 "혈당강하제 이름 확인 필요"로 기록 | **근거 없음.** I1 "혈당강하 치료 강도 낮춤" APPLY 의 전제가 깨짐 |
| CASE_07 | sbp_ge130=true | 급성기 1회 169/60. 같은 Table 2 에서 irbesartan 중단 사유로 "blood pressure at goal with amlodipine and carvedilol" | **반대 증거 있음**(bp_valid 미확인으로 일부 흡수됨) |
| CASE_06 | cvd=true(AF) | AF 확인. NSAID 위험 맥락의 "CVD" 해당 여부는 논쟁 가능 | 라벨은 warfarin(부록 I) 때문에 불변 |
| CASE_05 | cvd=true(대동맥판 협착) | AS 확인. 해당 여부 논쟁 가능 | ckd=true 로 라벨 불변 |
| CASE_02/04 | egfr_lt30=true, dialysis=false | "Stage 4 CKD" 확인. 투석 아님은 4기 정의에서 추론 | 근거 있음 |
| CASE_03 | cvd=true, on_statin=false | CVA 확인. 약 10/10 나열에 스타틴 없음 | 근거 있음 |
| CASE_02 | high_comorb_low_func=true | 90+, ADL 도움, 문제 16개 | 추론, 근거 있음 |
| CASE_08 | egfr_gt30=true | 기저 48. 회복 후 수치 없음 | 재개 시점 기준으로는 미확인 |
| 선호 값 전체 | q_* known | S1 Table·본문 인용 모두 원문 문구 확인 | 일치. 단 확인된 선호 2건을 인코딩하지 않음: CASE_04 "Limit use of NSAIDs", CASE_07 q_fewer_meds(어느 항목에도 연결 안 됨). CASE_07 의 "약 단순화 동의"는 중복·만료약 폐기 맥락이므로 일반적 "약 줄이기" 선호로 넓힌 것도 해석임 |

## 3. REF-R 항목별 반대 검토(전문가 검토 필요)

| 항목 | REF | 검증자 의견 | 방향 |
|---|---|---|---|
| CASE_07 I1 | APPLY | 혈당강하제 복용 근거 없음 | 성급한 확정 |
| CASE_13 I3 | APPLY | 선택지 3개, 선호 없음 | 성급한 확정 |
| CASE_08 I2 | NOT_APPLY | VA 원문에 영구 금기 없음 | 성급한 확정 |
| CASE_03 I3 / CASE_05 I5 | NOT_APPLY | "generally avoided" 의 확정 금기화 | 성급한 확정(결론은 방어 가능) |
| CASE_09 I3 | APPLY | 알고리즘 선행 조건 생략 | 성급한 확정 |
| CASE_02 I1 | SDM_CONFLICT | 이미 신장내과 진료 중인지 미상 | 성급한 확정 가능 |
| CASE_10 I1 | APPLY | DM25 조건 누락(결론은 강함) | 경미 |
| CASE_02 I3 / CASE_04 I5 | HOLD[P] | 'unless' 를 반증 조건으로 읽으면 지속 | 과도한 보류 |
| CASE_04 I2 | HOLD[P,K] | CKD CPG 가 국소 NSAID 회피를 명시 | 과도한 보류(K 부적절) |
| CASE_07 I3 | HOLD[P] | 원문에 "BP at goal" | 논쟁 가능 |
| CASE_09 I2 | HOLD[Q] | P(현재 사용·금기·AKI) 누락 | 원인 집합 과소 |
| CASE_08 I4 | HOLD[K] | 회복 후 eGFR·45 기준(P) 누락 | 원인 집합 과소 |
| CASE_03 I1, CASE_06 I4 | HOLD[P] | 고령·허약 근거 범위(K) 누락 | 원인 집합 과소 |
| CASE_10 I4 | HOLD[P] | 시점 미지정(eGFR 18 이면 근거 하한 미만) | 모호 |

## 4. 수치 독립 재계산

- 스크립트: `recompute.py`(메인 코드 import 없음). 결과: `recompute.csv`, `recompute_mismatches.txt`(0건).
- 분류 정의(검증자 독립 정의): REF 확정 & 출력 동일 = CC, REF 확정 & 출력 HOLD = UD, REF 확정 & 다른 확정 = WC, REF HOLD & 출력 HOLD = AD, REF HOLD & 출력 확정 = WC. item_results 의 ref/out 이 REF_R_v1.json·method_outputs.json 과 같은지도 대조함(300행 일치).
- λ=(5,1) 결과(summary.csv 와 전부 일치):

| 층 | N | U_ref | B: U / S | A: U / S | C: U / S | D: U / S | ALL_HOLD U | GUIDELINE_ONLY U |
|---|---|---|---|---|---|---|---|---|
| ALL | 50 | 0.0 | 1.0 / 1.0 | −2.0 / −2.0 | 0.88 / 0.88 | 0.88 / 0.88 | 0.0 | −2.12 |
| REAL_WITH_PREF | 31 | 0.2903 | 1.0 / 1.0 | −2.871 / −4.4545 | 1.0 / 1.0 | 1.0 / 1.0 | 0.2903 | −3.0645 |
| REAL_NO_PREF | 12 | −0.1667 | 1.0 / 1.0 | −1.5 / −1.1429 | 0.5 / 0.5714 | 0.5 / 0.5714 | −0.1667 | −1.5 |
| GUIDELINE_VIGNETTE | 7 | 1.0 | 1.0 / NA | 1.0 / NA | 1.0 / NA | 1.0 / NA | −1.0 | 1.0 |

- 질문(ALL): 재현율 B 1.0, C 0.9231, D 1.0, ALL_HOLD 1.0. 정밀도 B·C·D 1.0, ALL_HOLD 0.9677. 일치.

## 5. 방법 B 독립 재구현

- `reimpl_B.py` 는 methods_v1.py 를 보지 않고 작성함(대조 후 C/D 해석을 위해 methods_v1.py 를 읽음). 출력: `reimpl_B_output.json`, `reimpl_B_compare.csv`, `reimpl_B_stdout.txt`.
- 결과: 라벨 50/50, 원인 그룹 50/50, 관련 변수 50/50, 질문 집합 12/12 일치. 재구현 B 도 REF 와 라벨 50/50, HOLD 원인 25/25 일치.
- 의미: B 의 계산은 명세대로 동작함. 동시에 REF-R 은 이 인코딩에 같은 폐포 규칙을 적용한 결과와 구별되지 않음(6절).

## 6. 순환성·편향 판정

1. **B=REF 100% 가 의미하는 것:** (a) B 구현이 명세대로 맞음. (b) REF 작성자가 인코딩된 applies/contra/prefs 를 "미확인 변수가 판단을 바꾸면 보류"라는 규칙으로 일관되게 읽었음.
2. **의미하지 않는 것:** 임상적 타당성, 지침 해석의 정확성, 다른 인코더·임상의가 같은 REF 를 쓸 것이라는 점. 원인 집합까지 50/50 같다는 것은 REF 가 독립 판단이 아니라 인코딩의 함수라는 강한 신호임. 입력 파일이 REF 동결 83초 뒤에 수정된 점(기록 없음)도 같은 방향의 우려. 결과를 보기 전이지만 REF 에 맞춰 입력을 조정했을 가능성을 배제할 수 없음(**확인 필요**).
3. **A 의 −2.0 은 설계상 정해진 값:** A 는 보류 개념이 없으므로 REF 보류 25개가 전부 WC 가 됨. U 는 REF 보류 비율과 λW 로 계산될 뿐 경험적 발견이 아님.
4. **C·D 와의 차이는 각 1항목이고, 둘 다 논쟁 가능한 인코딩 선택 위에 있음:**
   - C 의 유일한 WC = CASE_09 I2. 이 항목에만 sglt2_contra 가 빠져서 applies/contra 가 완전히 알려진 상태가 되고, C 의 "미확인 선호 = 기본값 수용" 규칙이 APPLY 를 냄. 다른 SGLT2i 항목처럼 sglt2_contra 를 넣었다면 C 는 Kleene 평가에서 HOLD 를 냄(methods_v1.py run_C 논리상). 그러면 라벨 기준 B=C.
   - D 의 유일한 WC = CASE_08 I4. 인코더가 만든 K 변수 k_metformin_after_mala_safe(default=true) 하나가 차이의 전부. 회복 후 eGFR 을 P 변수로 인코딩했다면 D 도 HOLD 를 냄. 그러면 라벨 기준 B=D.
   - 따라서 "B 가 C/D 보다 낫다"는 라벨 수준 결론은 인코딩 선택 2개에 달려 있음. B 의 고유한 기여로 남는 것은 원인 그룹(P/Q/K) 귀속과 K 를 질문 대상에서 빼는 것인데, 이것도 K 변수를 정의한 사람이 REF 작성자와 같음.
5. **민감도(`sensitivity_altref.csv`):** run2 출력은 그대로 두고 REF 의 논쟁 항목만 대안 판독으로 바꿈. 단일 변경(CASE_07 I1→HOLD 또는 CASE_08 I2→HOLD)만으로 B 의 U 가 1.0→0.88 이 되고, C/D 는 0.76. 6개 변경을 모두 적용하면 B 0.52, C/D 0.40, A −2.12. 순위(B ≥ C=D ≫ A)는 유지되지만, 크기는 REF 판독에 크게 좌우됨. 대안 판독은 정답이 아니라 예시임.

## 7. 권고(실행 세션 대상, 검증 판정 완화 아님)

1. REF 동결 후 입력이 수정된 이유와 diff 를 RUN_LOG 에 기록.
2. CASE_07 on_glucose_lowering 근거를 재확인하고, 없으면 미확인으로 바꿈.
3. SGLT2i eGFR≥20 조건, CKD14 해석, OA Sidebar "generally" 처리, CASE_04 국소 NSAID(CKD L7375), CASE_08 I2/I4, CASE_09 I2 sglt2_contra 를 임상 전문가에게 검토받음.
4. B 대 C/D 비교는 "인코딩 의존" 한계를 명시하기 전까지 우위 주장으로 쓰지 않음. 독립 인코더·독립 REF(가능하면 임상의)로 재평가.

## 산출물

- `VERIFICATION_REPORT.md`(이 문서)
- `level_b_audit.csv` + 생성 스크립트 `make_level_b_audit.py`
- `recompute.py`, `recompute.csv`, `recompute_mismatches.txt`
- `reimpl_B.py`, `reimpl_B_output.json`, `reimpl_B_compare.csv`, `reimpl_B_stdout.txt`
- `sensitivity_altref.py`, `sensitivity_altref.csv`
