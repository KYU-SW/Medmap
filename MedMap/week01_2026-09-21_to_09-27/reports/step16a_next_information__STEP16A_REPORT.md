# STEP16A RUN1 결과 보고 (2026-09-22)

## Validity
- 사전등록 SHA 검증: MD 31b30117… / JSON e260afd5… 일치(부록 A는 별도 파일 `00_STEP16A_PREREGISTRATION_APPENDIX_A.md`로 분리해 본문 SHA 보존)
- TEST reads 0 / VALIDATION opens 1 (`s16_run.py`, 로그 'VALIDATION opened once 132448'; `s16_finalize.py`는 저장 CSV만 사용) / frozen 변경 0(run 후 재검증) / 입력 무결성 유지
- hidden reads before selection: 구조적 보장(reveal()은 chosen[] 확정 후 호출) — 단 **in-process 카운터는 느린 bootstrap 단계(4,595 s)에서 프로세스를 종료해 유실**, 산출물로 재도출 불가 → strict audit **PASS_WITH_NOTE**
- 알려진 Primary 매핑 한계(Pain 과매핑·E_14 누락) 유지, 매핑 보정 0
- 원 프로세스 종료 사유: paired_boot의 환자별 pandas 루프(~25분/쌍). 05/06/07은 이미 기록됨. 08~12는 동일 규칙(1000회·seed 42·환자 클러스터)의 벡터화 구현으로 생성

## Eligibility (config 9개 합산 행 수)
| ALL | PILOT_TRUE | PILOT_PAIR | PROFILE_REACHABLE | SIMULATABLE | Primary wrong N | Primary correct(harm) N |
|---|---|---|---|---|---|---|
| 1,192,032 | 286,902 | 60,975 | 59,520 | 58,078 | 30,863 | 27,215 |
- config별 primary wrong N: {'k10_s42': 3545, 'k10_s43': 3502, 'k10_s44': 3466, 'k3_s42': 3416, 'k3_s43': 3364, 'k3_s44': 3402, 'k5_s42': 3389, 'k5_s43': 3412, 'k5_s44': 3367} (환자 클러스터 11,331명)

## Initial accuracy (ALL VALIDATION, 새 뷰 프로토콜 — 무작위 질문·대부분 음성이라 Step2+3의 0.91~0.99와 다름)
- k3 0.4225/0.4216/0.4241 · k5 0.4538/0.452/0.4547 · k10 0.5258/0.5242/0.5266 · pooled 0.4673 · truth top2 0.6169 · top3 0.7021; primary 모집단 초기 정확도 0.4686 → **recovery headroom이 큼(오답 53%)**

## RECOVERY@1Q — PRIMARY (COMMON_POOL, paired, 오답 30,863)
| selector | recovery | C→W(1Q) | net acc |
|---|---|---|---|
| RANDOM | 0.1104 | 0.0435 | +0.0383 |
| INTERNAL_IG | 0.2164 | 0.0331 | +0.0995 |
| PROFILE_FACT_ONLY | 0.1289 | 0.0301 | +0.0544 |
- PROFILE − RANDOM: +0.0185 [+0.0129, +0.0250] · PROFILE − IG: -0.0875 [-0.0934, -0.0815] · IG − RANDOM: +0.1061 [+0.0997, +0.1127]

## RECOVERY@3Q (secondary trajectory)
| selector | recovery | C→W(3Q) | net acc | abstain | mean Q |
|---|---|---|---|---|---|
| RANDOM | 0.1874 | 0.0393 | +0.0812 | 0.441 | 2.26 |
| INTERNAL_IG | 0.2704 | 0.0455 | +0.1224 | 0.493 | 2.12 |
| PROFILE_FACT_ONLY | 0.2479 | 0.0459 | +0.1102 | 0.444 | 2.32 |
- PROFILE − RANDOM: +0.0604 [+0.0565, +0.0648] · PROFILE − IG: -0.0225 [-0.0248, -0.0203]

## Secondary
| selector | 1Q recovery | 3Q recovery | 1Q C→W | 1Q vs RANDOM | 1Q vs IG |
|---|---|---|---|---|---|
| PROFILE_IG_HYBRID | 0.2164 | 0.2704 | 0.0331 | — | +0.0000 [+0.0000, +0.0000] |
| PROFILE_WITH_CURATED_PAIR_AUDIT | 0.1831 | 0.2289 | 0.0296 | +0.0727 [+0.0651, +0.0814] | -0.0333 [-0.0417, -0.0246] |
| PROFILE_ONE_SIDED_SENSITIVITY | 0.1147 | 0.2636 | 0.0326 | +0.0043 [-0.0013, +0.0106] | — |
| INTERNAL_IG_FULL | 0.3561 | 0.7982 | 0.0242 | +0.3111 [+0.3015, +0.3213] | +0.1396 [+0.1281, +0.1507] |
| RANDOM_FULL | 0.0450 | 0.0884 | 0.0320 | — | — |
- PROFILE_IG_HYBRID − IG = 0.0000: 이 실행에서 Primary INTERNAL_IG는 COMMON_POOL에서 동작하므로 Hybrid(프로필 지원 후보 중 IG 최대)와 **정의상 동일**. IG의 자유 pool 결과는 INTERNAL_IG_FULL 행.

## Coverage
- Profile abstention: 1Q 0.000(COMMON 비어있지 않은 모집단 정의상), 3Q 0.444 · 후보 수: COMMON 평균 3.289, FULL 평균 203.49 · 관측 불가 프로필 feature(`09_unobservable_information_opportunities.csv`): 5건

## 대표 사례 (`11_error_case_examples.csv`, 결정적 순서: k10_s42 오름차순)
- recovered: Chronic rhinosinusitis(정답)인데 top1 Acute rhinosinusitis → E_91 발열 질문 후 정정 (id 1008·1393·1447)
- not_recovered: Acute otitis media→Viral pharyngitis/laryngitis pair에 E_91 질문(정답이 후보 쌍 밖) (id 7); Chronic rhinosinusitis vs Viral pharyngitis에 E_91 (id 95); Acute laryngitis vs Viral pharyngitis에 E_212 쉰목소리 질문했으나 미정정 (id 213)
- harmed: Acute laryngitis(정답)→E_91 후 Chronic rhinosinusitis로 이탈 (id 796); Viral pharyngitis→COPD 악화 쌍에 E_91 (id 7138); Acute laryngitis→E_212 후 이탈 (id 7968)

## 판정 근거
1. 같은 COMMON_POOL에서 PROFILE_FACT_ONLY > RANDOM (+0.0185, CI [+0.013,+0.025]; 3Q +0.060) — 프로필 우선순위가 무작위보다 낫다는 신호는 있음.
2. 그러나 PROFILE_FACT_ONLY < INTERNAL_IG (−0.0875, CI [−0.093,−0.082]; 3Q −0.0225) 이고 Hybrid는 IG와 동일(+0) → 사전등록 §20 경계: FACT_ONLY와 Hybrid 모두 IG 대비 신호 없음 → 프로필 기반 질문 선택의 **추가 가치는 약함**.
3. 수기 pair audit(secondary) 0.183은 IG 0.216에 근접 — 병목이 개념 자체보다 **기계 매핑 품질**(Pain 과매핑·E_14 누락)임을 시사하나 Secondary라 Primary 결론을 바꾸지 못함.
4. 가장 큰 효과는 INTERNAL_IG_FULL(1Q 0.356 → 3Q 0.798, Random_FULL 0.045/0.088): TRAIN 내부 통계 기반 질문 선택은 3문항으로 오답의 80%를 정정. 다만 이는 DDXPlus 내부 지식이며 외부 프로필 축의 결론과 별개.
5. harm: 모든 selector가 정답 케이스를 3~4% 뒤집음(1Q). Profile이 가장 낮음(0.030).

## 판정: **STEP16A_PROFILE_NO_GO** — 다음 단계: **STOP_PROFILE_QUESTION_ENGINE**
(사전등록 §20 규칙에 따른 판정. 대안 해석: curated 결과와 Profile>Random을 근거로 IMPROVE_SELECTOR(매핑 품질 개선 후 재시험)도 가능하나, 이는 Secondary 근거이므로 Primary 판정에 쓰지 않음)

## 한계
- 새 뷰 프로토콜은 초기 정확도 0.42~0.53으로 낮아 headroom이 크며, 결과는 이 설정에 종속
- 10질환 pilot: PILOT_PAIR 60,975 뷰(전체의 5.1%), 상위 오답쌍(부비동염·후두염/인두염·협심증)이 지배
- Profile 후보 pool 평균 3.3개 vs FULL 203개 — 프로필이 답할 수 있는 질문 자체가 적음
- audit 카운터 유실(구조적 보장으로 대체), Random 3Q는 50 draw 유지·FULL 변형은 10 draw

## 파일
01(사전등록 3)·02 예측 1,192,032행·03 eligibility·04/04b/04c/04d·05 Q1·06 Q3·07 metrics·08 bootstrap·09 unobservable·10 audit·11 examples·12 summary·s16_run.py·s16_finalize.py·로그 logs/step16a_run1_*.log