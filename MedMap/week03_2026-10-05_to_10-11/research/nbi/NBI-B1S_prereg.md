# EXP-SN-NBI-004 · NBI-B1S 사전등록 — B1 Troponin 51003 신호의 최소 민감도 진단

작성 2026-10-06 · rev2(RG gate 1 NEEDS_FIX 반영: 판정표 방향 조건·감쇠 CI 조건) · 실데이터 실행 전 고정 · LOCAL ONLY · 원천 실험 EXP-SN-NBI-003(B1, VERIFIED, commit 73048a5)

## 1. 목적
B1에서 관찰된 Troponin 51003 incremental separation(ΔAUROC +0.08, 95 % CI 0.06–0.11, 공개값)이
(A) MI 연관 라벨 의존(reference-standard entanglement)에 얼마나 민감한지,
(B) 측정 subset 선택이 관찰 가능한 baseline 특성과 얼마나 연관되는지를 후향적으로 진단한다.

## 2. 목적이 아닌 것
- B1 재실행·B1 결과 수정. B1 counted run(20261006_094224)은 그대로 정본.
- 참조 표준 얽힘 제거·bias 교정(propensity·IPW·matching·인과 모형 없음).
- 임상 유용성·추천 효과·오진 감소·인과 효과·미측정 환자 일반화·prospective 성능.
- 새 lab·D-dimer·새 baseline 특징·chief complaint·acuity·imaging·NLP·모형 탐색·hyperparameter 탐색.

## 3. 고정 원천(수정 없이 import)
- `../b1/b1_feasibility.py` (sha 07bcef30…, B1 pinned): `compute_b1`(코호트·라벨·lab 적격·baseline),
  `cell`(측정법 셀 분석), `oof`·`fold_auroc`·`boot_ci`·`strat_folds`(모형·split·bootstrap), 상수 N_MIN_B1 50,
  K 5, RIDGE 1.0, B 1000, seed 20261006, FEASIBLE 반폭 0.10, WINDOW 6 h.
- `../b0/b0a_availability.py` (sha 628d4ea7…): `ACS_SUB` ICD 코드 집합(B0a 이후 변경 없음).
- B1 공개 출력 `../b1/out/b1/b1_public.json` (sha 1137ab9d…): 재현 점검 기준.

## 4. ACS subtype 정의(새로 만들지 않음 — B0a `ACS_SUB` 그대로)
- MI형: STEMI(I21.0–I21.3, 410.0x–410.6x·410.8x 초회/미상), NSTEMI(I21.4, 410.7x), MI_UNSPEC(I21.9, 410.9x),
  SUBSEQUENT(I22) 중 1개 이상. UA 코드가 함께 있어도 MI형(MI 진단이 붙은 stay 이므로).
- UA형: UA 하위코드(I20.0, I25.110·700·710·720·730·750·760·790, 411.1)**만** 있고 MI 하위코드가 없는 ACS.
- UNASSIGNED: 위 어느 쪽도 아닌 ACS(코드 구조상 0 예상) — 분석 제외, 봉인 count.
- 단위: B1과 같은 subject당 첫 관련 ED stay 의 ED 퇴원 ICD. 입력(feature)으로 쓰지 않음.

## 5. A0 재현 점검(실행 무결성)
전체 ACS~PE 코호트의 51003 측정 subset 에서 B1과 같은 절차로 M0·M1 점추정(bootstrap 없음)을 다시 계산해
소수 2자리 auroc_m0·auroc_m1·delta 가 B1 공개값과 모두 같아야 한다. 코호트 구간·pair 상태도 B1 공개와 같아야 한다.
다르면 `INVALID reason=b1_reproduction_mismatch|b1_cohort_mismatch`(counted 아님, 결과 미생성).

## 6. TEST A — MI 연관 라벨 의존 민감도
- A1 = MI형 ACS vs PE, A2 = UA형 ACS vs PE. 각각 B1 `cell(TROPONIN, 51003)` 을 해당 subset 행에만 적용.
- 바뀌는 것은 ACS 쪽 행 제한뿐. baseline 8개·6 h·첫 적격 결과 규칙·subject 층화 5-fold(같은 해시 규칙을 subset 에
  다시 적용)·L2 로지스틱·fold 평균 AUROC·재적합 bootstrap(B 1000, 같은 seed)·N_MIN 50/class·FEASIBLE 반폭 0.10 동일.
- 보고: 각 셀 status, n 구간, M0·M1 AUROC, ΔAUROC, 95 % CI, lab 단독 AUROC(B1과 같은 방향 고정).
- A1 과 A2 의 차이에 대한 검정·p 값 없음(기술적 비교).

### TEST A 판정 규칙(반올림 전 봉인 값, 위에서부터 첫 일치)
| 순서 | 조건 | interpretation | reason |
|---|---|---|---|
| 1 | A2 status ∉ {FEASIBLE, EVALUABLE_IMPRECISE} | REFERENCE_SENSITIVITY_NOT_EVALUABLE | UA_INSUFFICIENT_DATA / UA_NOT_EVALUABLE_UNIT / UA_NOT_EVALUABLE_MODEL |
| 2 | A1 status ∉ {FEASIBLE, EVALUABLE_IMPRECISE} | REFERENCE_SENSITIVITY_NOT_EVALUABLE | MI_NOT_EVALUABLE |
| 3 | (A1 lab 단독 AUROC − 0.5) × (A2 lab 단독 AUROC − 0.5) ≤ 0 (lab 방향이 A1 과 반대 또는 0.5) | REFERENCE_SENSITIVITY_NOT_EVALUABLE | UA_DIRECTION_REVERSED |
| 4 | A2 Δ CI 하한 > 0 | SIGNAL_PERSISTS_BEYOND_MI_SUBTYPE | UA_CI_ABOVE_ZERO |
| 5 | A1 Δ CI 하한 ≤ 0 | REFERENCE_SENSITIVITY_NOT_EVALUABLE | MI_CI_NOT_ABOVE_ZERO |
| 6 | A2 status ≠ FEASIBLE(반폭 > 0.10) | REFERENCE_SENSITIVITY_NOT_EVALUABLE | UA_IMPRECISE |
| 7 | Δ(A2) > 0.5 × Δ(A1) | REFERENCE_SENSITIVITY_NOT_EVALUABLE(결론 미정) | UA_NOT_ATTENUATED |
| 8 | A2 Δ CI 상한 ≥ Δ(A1) 점추정 | REFERENCE_SENSITIVITY_NOT_EVALUABLE(결론 미정) | UA_ATTENUATION_UNRESOLVED |
| 9 | 그 외(Δ(A2) ≤ 0.5 × Δ(A1) ∧ A2 CI 상한 < Δ(A1) ∧ A2 CI 가 0 포함) | SIGNAL_MOSTLY_REFERENCE_DEPENDENT | UA_ATTENUATED |

- 규칙 3 근거: M1 은 lab 계수 부호를 학습하므로 Δ 는 방향과 무관하게 양수다. UA 는 정의상 troponin 비상승 ACS 라
  UA vs PE 에서 'troponin 높을수록 PE' 반대 방향 분리가 생길 수 있고, 이는 B1 신호의 유지가 아니라 UA 라벨 정의가 만든 분리다.
- 규칙 8 근거: 감쇠 라벨은 A2 CI 가 A1 점추정을 배제할 때만(규칙 4 의 CI 요구와 대칭). 검정·p 값 아님.
- 라벨 이름은 사용자 지정 어휘를 유지한다. 단 SIGNAL_PERSISTS_BEYOND_MI_SUBTYPE 은 'UA subset 에서도 같은 방향의
  0 아닌 incremental separation' 만 뜻하고 크기 유지·참조 표준 독립성을 뜻하지 않는다. SIGNAL_MOSTLY_REFERENCE_DEPENDENT
  는 'UA subset 에서 감쇠' 만 뜻하며 참조 표준 의존과 범위 제한(spectrum)·표본 차이를 구분하지 못한다.
  UA_NOT_ATTENUATED·UA_ATTENUATION_UNRESOLVED 는 '평가 불가' 가 아니라 '결론 미정' 으로 서술한다.

표본 부족이면 cohort 를 넓히거나 N_MIN 을 낮추지 않고 그대로 종료한다.

## 7. TEST B — 측정 선택 진단
- 대상: B1 ACS~PE 코호트 전체(subject 1행). 결과변수 M = 1 ⇔ 첫 적격 Troponin 결과가 51003 이고 사용 가능
  (B1 51003 셀 분모와 같은 정의). M 은 진단 분류기의 특징이 아니라 이 진단의 결과변수일 뿐.
  M = 0 에는 미측정·다른 assay(51002·52642) 첫 결과·6 h 창 밖·시각 결측·사용 불가·단위 결측이 섞인다 → 결과 문장은
  "임상의 측정 선택" 이 아니라 "51003 분석 subset 소속(검사 주문 + 시각 적격 + 사용 가능)" 으로 쓴다.
- 입력: B1 baseline 8개(나이·여성·triage 활력 6개)만. 진단·ICD·chief complaint·acuity·disposition·다른 lab·imaging·미래 정보 금지.
- 모형·split·CI: B1 `oof`·`strat_folds`(M 층화)·`fold_auroc`·`boot_ci`(B 1000) 그대로.
- 주 지표: pooled 측정 선택 AUROC + 95 % CI. 보조: ACS 내·PE 내 같은 지표(class 차이에 의한 혼입을 분리해 보기 위함).
  각 집단에서 측정·미측정 어느 쪽이든 < 50 이면 INSUFFICIENT_DATA.
- 판정: AUROC ≥ 0.60 ∧ CI 하한 > 0.50 → SELECTION_SIGNAL_PRESENT, 아니면 SELECTION_SIGNAL_WEAK_OR_UNRESOLVED.
  WEAK 여도 '선택 편향 없음' 이라고 쓰지 않는다(미관측 교란 가능).
  해석 근거는 within_acs·within_pe 를 pooled 와 같은 비중으로 제시한다. pooled 는 baseline 의 class 예측력 × class별
  측정률 차이가 섞이므로, pooled 만 PRESENT 이면 class 혼입 가능성을 병기한다. 대표본에서 CI 하한 > 0.50 은 거의
  자동이므로 실질 기준은 AUROC ≥ 0.60(관례적 '약한 이상' 판별 경계, 결과 전 고정).
- class별 51003 측정 비율: 10 %p 구간(A.share_bin), class n < 100 이면 WITHHELD.

## 8. 음성 대조(1회, 구현 sanity)
51003 측정 subset(전체 ACS~PE) 안에서 lab 값을 seed 20261007 로 한 번 섞고 점추정 Δ 만 계산.
|Δ| ≤ 0.02 → NC_PASS, 아니면 NC_FLAG(보고만, 중단 아님). 참조 표준 bias 를 다루는 검사가 아님. 반복 permutation 없음.
1회 섞기라 귀무 분포를 특징짓지 못하고 큰 구현 오류만 잡는다 — NC_PASS 를 'bias 없음'·'신호 검증' 으로 서술 금지.

## 9. 공개·봉인
- 공개(39키, `expected_schema_b1s.json`): status 어휘, n 구간(LT_50 …), 10 %p 구간, 소수 2자리 AUROC·Δ·CI,
  판정 라벨. 키·값 guard 위반·스키마 불일치면 INVALID.
- 봉인(`~/<restricted>/nbi_b1s/sealed/b1s_sealed.json`, repository 밖): subtype별 exact count, MI+UA 동반 수,
  exact 지표·fold count·bootstrap 실패 수, 선택 진단 exact count. 환자 단위 예측은 저장하지 않음.
- 금지 출력: subject_id·stay_id·hadm_id·환자 행·raw lab 값·exact timestamp·exact class count.

## 10. 실행·중단·재실행
- 유일한 실행 명령: `bash /home/<user>/medmap-worktrees/safety-net-nbi/docs/research/nbi/b1s/launch_b1s.sh` (인자 금지).
- launcher: 자원 점검(`--no-gpu`) → marker 원자적 생성 → nohup runner → ram_guard 90 %.
- runner: 출력 존재 시 4, pinned SHA 불일치 5, 인자 7. python: 입력 SHA·item map·재현·스키마·guard 불일치 시 INVALID(2).
- counted run = `out/b1s/b1s_public.json` 생성. 정확히 1회. 결과와 무관하게 재실행 금지.
  ENVIRONMENT_ABORT·IMPLEMENTATION_ABORT(공개 출력 미생성)만 원인 기록 + deviation + 사용자 승인 후 재시도 가능.
  봉인 디렉터리가 생성된 뒤 공개 출력 전에 중단되면(counted=no) 봉인 디렉터리는 열람 없이 사용자가 이름을 바꿔 보존
  (`sealed` → `sealed_aborted_<ts>`)한 뒤에만 재시도한다(runner 가 exit 4 로 막으므로).

## 11. 해석 한계(결과에 반드시 병기)
- 이 분석은 "MI-associated label dependence 에 대한 sensitivity analysis" 이다. 참조 표준 얽힘을 제거하지 않는다.
- UA 진단 자체도 troponin 결과(음성 확인)와 독립적이지 않다 — UA형은 "troponin 이 상승하지 않은 ACS" 로 선택된
  집단일 수 있어 A2 Δ 는 과소 또는 과대 어느 쪽으로도 왜곡될 수 있다.
- A1·A2 는 PE 군을 공유하므로 독립 비교가 아니다. 두 CI 의 겹침으로 차이를 해석하지 않는다. CI 는 다중성 보정 없음.
- UA 정의 자체가 troponin 결과에 의존하므로 어떤 TEST A 라벨도 참조 표준 독립성을 뜻하지 않는다.
- ED 퇴원 ICD 의 UA 는 확정 진단이 아니라 'rule-out ACS' 임시 진단일 수 있어 비ACS 흉통이 섞인 이질적 집단일 수 있다.
- B0a ACS 정의는 I21.A1(type 2 MI)·I24.x·ICD-9 410.x2 를 제외하므로 MI형은 사실상 type 1 계열 MI 이다.
- TEST B 의 AUROC 가 낮아도 미관측 교란·임상의 판단에 의한 선택이 없다는 뜻이 아니다.
- 단일 기관(MIMIC-IV), 후향, ED 퇴원 ICD 라벨, 측정 subset 한정.

## 12. 금지 주장
"Troponin NBI 가 임상적으로 유용하다", "MedMap 이 Troponin 을 잘 추천한다", "검사하면 진단이 좋아진다",
"참조 표준 bias 를 제거했다", "선택 편향이 없다", 인과·prospective·미측정 환자 일반화 주장.
최대 허용 문장: "B1에서 관찰된 Troponin 51003 incremental separation 이 MI-associated reference-standard
dependence 에 얼마나 민감한지, 그리고 measured-subset selection 이 관찰 가능한 baseline 특성과 얼마나 연관되는지
후향적으로 평가했다."

## 13. 시험(실데이터 미사용)
합성 14건(`tests/test_b1s.py`): subtype 분리·MI+UA 동반 처리, subset 누수·subject 단위 split, 측정 결과변수 규칙,
선택 모형 baseline-only, 선택 진단 INSUFFICIENT 경로, UA 표본 부족, B1 cell 과 같은 규칙, 재현 점검,
판정표 14경우(방향 반전 2·감쇠 CI 미확정 2 포함), 음성 대조, guard·스키마, 결정적 출력·exact count 비노출, 1회 실행 guard·중단.
최소 변이 8종 전부 KILLED(방향 조건 제거·감쇠 CI 조건 제거 포함). runner·launcher 경로 12/12 PASS.

## 14. 예상 시간·자원
CPU 전용, 표준 라이브러리. B1 실측 약 25분(51003 셀 + baseline bootstrap). B1S = 데이터 적재 + A1·A2 셀 2개 +
선택 bootstrap 3개 → 약 40–70분 예상. RAM: B1과 같은 적재 구조.
