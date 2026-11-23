# 공통 변수 연결·LEVEL 판정·비교 실험 사양 (메인 에이전트, 연결·실험 실행 전 동결)

- 작성: 2026-11-20 (동결 시각·sha256은 `PROTOCOL_FROZEN_v1.sha256.txt`)
- 입력(동결 시점에 이미 존재): `clinicaltrials/structured/trials.csv`, `clinicaltrials/structured/trial_conditions.csv` (Agent B, 무작위 표본 250시험), `shared-variables/CURATED_LABEL_RULES.csv` (메인이 openFDA 기준 라벨 원문과 직접 대조해 작성)
- openFDA 자동 추출(`label_conditions.csv`)은 사용 문장 정밀도 31.7%로 낮아 **실험에 쓰지 않는다**. 라벨 조건은 CURATED_LABEL_RULES만 사용한다.
- 진료지침은 이용 허가가 없어 쓰지 않는다. 이 실험은 "진료지침 충돌 평가"가 아니다.

## 1. 분석 단위와 분모
- 빈도 측정 단위: **약물–시험 쌍** (시험 t ∈ Agent B 무작위 표본 250건, 약물 d ∈ t의 `scope_drugs_in_interventions`).
- 약물 이름 정규화: `ARNI:lcz696|sacubitril|entresto` → sacubitril/valsartan, 나머지는 성분명. `NONE_MATCHED`, `ARB:angiotensin receptor blocker`(성분 미상), 기준 라벨이 없는 성분(candesartan, perindopril)은 쌍에서 제외하고 제외 수를 기록한다.
- (t, d) 중복 제거.
- 변수: eGFR, potassium, LVEF. 쌍마다 변수별로 LEVEL을 판정한다(분모 = 쌍×변수 = 쌍 수 × 3).

## 2. LEVEL 정의
- **LEVEL 1**: t에 변수 v의 적격성 행이 하나 이상 있고, d의 CURATED 규칙에 v가 하나 이상 등장(MONITOR_ONLY·UNKNOWN 포함).
- **LEVEL 2** (같은 환자 특성): LEVEL 1이면서
  - eGFR: t의 행 단위에 `1.73`이 명시되고 임계값 ≥ 10. 단위 `mL/min`만 있으면 CrCl과 구분 불가 → LEVEL 1에서 멈춤. 임계값 < 10은 크레아티닌 등 오추출로 보고 제외. 단위 UNKNOWN인 행은 같은 시험의 다른 eGFR 행에 `1.73`이 있고 임계값이 그 행과 같을 때만 사용.
  - potassium: 단위 mmol/L 또는 mEq/L (K⁺는 1가 이온이라 1 mmol/L = 1 mEq/L; 변환 근거 명시). 단위 UNKNOWN 행은 사용하지 않음.
  - LVEF: 단위 %.
  - d의 규칙이 v에 **수치 임계값**을 가짐(MONITOR_ONLY·UNKNOWN만 있으면 LEVEL 1에서 멈춤).
  - 시점: 시험 적격성(선별 시점)과 라벨 개시 규칙(치료 시작 전)은 모두 치료 전 상태라 호환으로 본다. 라벨의 '치료 중 지속' 규칙은 모형화하지 않는다.
  - 같은 시험·같은 변수에서 같은 방향의 서로 다른 경계가 두 개 이상이면 AMBIGUOUS → 원문 수작업 확인으로 해소되면 사용, 아니면 LEVEL 1에서 멈춤.
- **LEVEL 3** (같은 치료 판단): LEVEL 2이면서 라벨 규칙의 적응증 범위가 시험 맥락과 호환.
  - indication_scope `ALL`, `T2DM_ANY`: 호환
  - `HF`: 시험 conditions에 heart failure 계열 용어가 있을 때만
  - dapagliflozin·empagliflozin: 시험 conditions에 CKD/kidney 또는 heart failure 용어가 있으면 `CKD_HF_OTHER`, 없으면 `T2DM_GLYCEMIC` 규칙 사용
- **LEVEL 4** (공유하지 않으면 판정이 바뀜): LEVEL 3이면서 아래 3절 실험에서, 동결 격자의 어떤 환자 창(window)에서든 모듈 결합 결과가 결합 정식화 결과와 다르고, 그 차이가 '임상 의미 유형' 조합(아래 4절의 SPURIOUS_ALLOWED_OUT 또는 SPURIOUS_DISALLOWED_IN)을 포함.

## 3. 비교 실험 (합성 환자 창 × 실제 문서 조건)
- 합성 환자: 변수 v의 값이 창 [c−h, c+h] 안 어딘가로 미확인. 격자(동결):
  - eGFR: c = 10..90 (간격 1), h = 5
  - potassium: c = 3.5..6.0 (간격 0.05), h = 0.2
  - LVEF: c = 10..70 (간격 1), h = 5
- 라벨 모듈 L(x): CURATED 규칙의 구간 상태. 경계 포함 규칙은 파일의 lower_incl / upper_excl 그대로. 예외: `>` 표기 규칙(FINE-K1, FINE-K2, EPLE-K)은 하한 미포함.
- 근거 모듈 E(x): 시험 적격 구간 안이면 IN, 밖이면 OUT (적격성 = 지지 영역의 상한일 뿐이라는 한계 명시. 실제 등록자 분포는 기초특성 6/122시험만 있어 사용하지 않음).
- **Baseline A (모듈 결합)**: 창 안에서 SL = {L(x)}, SE = {E(x)}를 각각 계산 후 곱집합 M = SL × SE.
- **Baseline B (결합 정식화)**: 창을 L·E의 모든 경계로 분할해 조각마다 (L, E)를 평가한 집합 J. (경계값 자체를 한 점 조각으로 포함.) 이것이 계산 정답이다(정확 열거).
- 독립 검증: J를 조밀 표본(eGFR 0.01 간격, K 0.001, LVEF 0.01)으로 다시 계산해 일치 확인.

## 4. 출력 범주와 지표
- allowed형: ALLOWED, ALLOWED_DOSE_ADJ, ALLOWED_DOSE_LIMIT, ALLOWED_MONITOR. 불가형: CONTRAINDICATED, INIT_NOT_RECOMMENDED, NOT_RECOMMENDED, DO_NOT_INITIATE. UNKNOWN.
- 범주(집합 S에 대해):
  - `OK_IN`: 모든 조합이 (allowed형, IN)
  - `OK_OUT_EVIDENCE_GAP`: 모든 조합이 (allowed형, OUT) — 근거 범위 밖(금기 아님)
  - `NOT_INITIATE`: 모든 조합의 라벨이 불가형
  - `LABEL_UNKNOWN`: 라벨 UNKNOWN 포함
  - `HOLD`: 그 외 혼합(추가 확인 필요)
- 지표:
  - 차이 창 수: M ≠ J
  - 가짜 조합: M − J. 유형 `SPURIOUS_ALLOWED_OUT`(불필요한 근거 범위 경고), `SPURIOUS_DISALLOWED_IN`, 기타
  - 범주 변화: category(M) ≠ category(J)
  - 잘못된 확정: category(M) ∈ {OK_IN, OK_OUT_EVIDENCE_GAP, NOT_INITIATE}인데 category(J)와 다름
  - 불필요한 보류: category(J) ≠ HOLD인데 category(M) = HOLD
- **2차 분석(B7형, 약물 간 공유)**: 같은 시험에 eGFR 규칙을 가진 약물이 둘 이상이면, 두 라벨 모듈의 곱집합 vs 결합 집합을 같은 격자로 비교(가짜 조합 수).
- **3차 분석(라벨 내부)**: 같은 라벨의 사용 규칙과 `TRIALS_ENROLLED_RANGE` 문장의 공유 구조(약물별 1건).
- B9(선호): 실제 선호 자료가 없어 이 파일럿에서는 실행하지 않는다(NOT_RUN). 이전 합성 실험 결과로 대체하지 않는다.

## 5. 판정 기준(결과 보기 전 고정)
- 결론 1(정보 공유 구조 + 모듈 손실 확인, 기존 결합으로 해결): LEVEL 4 쌍이 1개 이상 실제 문서로 설명되고, 결합 정식화가 차이를 모두 해소.
- 결론 2(공통 변수는 있으나 손실 거의 없음): LEVEL 1~3은 있으나 LEVEL 4 = 0.
- 결론 3(판단 불가): LEVEL 2 판정에 필요한 단위·문맥이 대부분 UNKNOWN.
- 결론 4(기존 결합으로도 해결 안 됨): 결합 정식화 J가 조밀 표본 검증과 불일치하거나 계산 불가인 사례가 실제 조건에서 발생.
- 빈도 수치만으로 계속/중단을 자동 결정하지 않는다.
