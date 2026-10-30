# EXP-SN-NBI-003 (NBI-B1) 사전등록 rev2 — ACS vs PE: Troponin / D-dimer 참조 표준 조건부 분리도의 후향 FEASIBILITY

> rev2(2026-10-06, 실행 전, gate 1 NEEDS_FIX 반영). rev1 대비 변경 사항:
> ① 주 CI를 재적합 bootstrap(B 1000, 복제 subject는 원 fold 유지)으로 바꿈
> ② lab 순위 특징을 baseline과 같은 척도로 표준화
> ③ 중도절단 값의 순위 배치, 단위 정규화, guard 값 범위 추가
> ④ estimand를 '참조 표준 조건부 분리도'로 명명하고 해석 제한·금지 표현을 사전 고정
> ⑤ 이월 항목 처분표 추가
> ⑥ 시험·변이 확장
>
> 실데이터 B1 집계 0회, 환자 행·lab 값 열람 0, B0 봉인 개봉 0. 세션이 본 것은 B0a·B0c·B0d 공개 출력, d_labitems 사전(B0c에서 고정), 파일 헤더, patients 공식 SHA뿐이다.

## 0. 기존 정의와의 관계
- 우선 적용(동결): EXP-SN-NBI-002 manifest
  - [H]: ACS–PE 확정. pair 전환 금지. 확보 n이 부족하면 underpowered/NOT_EVALUABLE로 처리한다.
  - [I]: B0 공개 출력만 설계에 쓴다. B0 봉인은 열지 않는다. 검사 시행 여부·순서는 입력으로 쓰지 않는다.
  - [L]: allowlist 기준.
  - subject 단위 split, subject당 첫 적격 stay.
- 이월 항목 처분표(결과 보기 전에 결정)

| 출처 | 항목 | 처분 | 사유 |
|---|---|---|---|
| NBI-001 설계 v0 §18 | B1 = VITAL(triage) + ECG | 미채택(충돌 보고) | 'F0 후 결정' 비동결 초안. ECG 시각은 B0a에서 TEMPORALLY_UNCERTAIN, ECG 내용(B0b) 미실행. 사용자 지시(2026-10-05) = Troponin·D-dimer. 활력은 baseline으로 사용 |
| NBI-001 v0 §17 / B0 설계 §18 | S0–S3 단계, ck-v0 점수 함수, A0 민감도 CF1/CF2/AB6 | 범위 밖 | 지식 기반 후보 순위 평가는 후속 단계 |
| NBI-002 [B] | B1용 반사실 WD(CORE 방식) | 미정의(WD 없음) | [B]가 'B1 manifest에서 정의'로 위임함. 이번 B1은 라벨 정의 쌍 코호트로만 감별 상황을 근사 |
| NBI-002 label_definition | 민감도 라벨: hosp 합집합(미보유), seq_num=1, seq_num 우선 배정, ACS 세부, PE septic·iatrogenic, I24.9 포함, lookback | NOT_RUN | 범위·다중성 통제. ACS 세부 구성은 봉인 기술(§8)로만 |
| NBI-002 label_definition | presentation-defined(주호소) 코호트 | NOT_RUN | chiefcomplaint 누출 필드, 키워드 사전 별도 설계 필요 |
| NBI-002 [L](22) | arrival_transport | 제외 | T0 정보지만 EMS 이송 = 중증도·의심 반영 가능, baseline 최소화 원칙 |
| NBI-002 [L] 밖 | triage pain | 제외 | T0 정보지만 결측·자유 기재 형식이 많고 숫자 변환 규칙을 따로 설계해야 함 → 보수적 제외([L] 항목 아님) |
| B0c §19 | NT-proBNP | NOT_RUN | 범위 통제(후속 후보) |

## 1. 연구 질문 / estimand / 비목적
- 질문: ED 퇴원 ICD로 정의한 ACS–PE 후향 쌍 코호트에서, Troponin·D-dimer의 ED 도착 후 6 h 안 첫 결과값을 T0 baseline(나이·성별·triage 활력)에 더했을 때의 **참조 표준 조건부 분리도(label-conditioned separation)**를, 사전 정의 조건으로 정밀하게 추정할 수 있는가(retrospective FEASIBILITY).
- estimand 이름에 '참조 표준 조건부'를 붙인 이유: lab이 라벨 생성 경로에 들어 있다. MI 정의에 troponin이 포함되고, PE 진단 경로가 D-dimer → CTPA → I26이다. 그래서 측정 subset의 분리도는 생물학적 정보와 라벨 생성 관여도를 나눌 수 없다(§13).
- 분리해서 다루는 세 가지
  - A. 정보 가용성: 분석 B, 기술만
  - B. 측정된 경우의 분리도: 분석 A, 측정 subset 조건부
  - C. 임상의 선택 효과: 분석 B로 크기만 기술하고, 인과 보정은 하지 않음
- 비목적·금지: 임상 성능·오진 감소·의사 대비 우월성·NBI 추천 효과·prospective 성능·인과 효과, propensity 모형, threshold 이분화, hyperparameter 탐색, 다변량 ML, lab 자동 탐색, 영상·보고서·DICOM, ACS–PERI, B0 봉인 개봉, calibration·임상 운영점(이분화 금지라 보고하지 않음).

## 2. 코호트·라벨 (참조 표준 — 입력 금지)
- B0a 고정 compute()의 ACS~PE를 그대로 쓴다: 전 seq_num 코드표, MULTI 제외, subject당 첫 관련 stay, 제목 STOP.
- y = 1 PE / 0 ACS. 진단 코드·제목·seq_num·퇴원 정보는 특징에 넣지 않는다(시험·변이로 고정).
- 공개 출력의 pair status·cohort_pooled_bucket이 B0a·B0c·B0d 공개 출력의 ACS~PE와 다르면 INVALID(cohort_mismatch).
- 참조 표준의 한계: 판정위원회 없음, 판독자 간 일치도 없음, 청구 ICD.

## 3. 시간축
- T0 = ED intime. WD 시각은 없다고 가정하며 "WD 직후 추천 성능"으로 표현하지 않는다.
- baseline은 triage(도착 상태로 간주 — [B])·나이·성별이다.
- lab 적격은 B0c 동결 의미 그대로이며, 다음을 모두 만족해야 한다.
  - storetime ∈ [intime, min(intime + 6 h, outtime)], 양 끝 포함
  - charttime ≥ intime 또는 charttime 결측
  - [E] 겹침 배정 stay = 그 stay
- 결측 시각은 대체하지 않는다.
- 6 h는 manifest [C] W6이며 민감도 window는 없다. 근거: B0c 공개 시점 라벨 LATER_IN_STAY(첫 결과 중앙값 > 1 h)이고, 6 h는 ED 초기 평가 범위의 사전 상한이다.

## 4. 입력 allowlist ([L] 기준)
| 출처 | 허용 컬럼 | 용도 |
|---|---|---|
| ED triage | stay_id, temperature, heartrate, resprate, o2sat, sbp, dbp | baseline |
| hosp patients | subject_id, gender, anchor_age, anchor_year | 나이 = anchor_age + (intime 연도 − anchor_year), 성별 F = 1 |
| hosp labevents | subject_id, itemid, charttime, storetime, value, valuenum, valueuom | lab 첫 적격 결과 |
| hosp d_labitems | itemid, label, fluid | itemid 매핑 재검증 |
- 금지(코드·시험 고정)
  - chiefcomplaint([L](2)), acuity([L](3))
  - pain·arrival_transport(§0)
  - hadm_id([L](1)), disposition·dod([L](15)). outtime은 window 경계로만 쓴다.
  - anchor_year_group([L](25)), flag·ref_range·priority·comments([L](16)), 진단 코드([L](5))
  - radiology·영상 가용성, ECG 진단
  - 검사 시행 여부·순서·횟수([L](12), [I])
- 활력 범위 밖 값은 결측으로 처리한다: temperature 90–110 °F, HR 20–250, RR 4–60, SpO2 50–100, SBP 40–300, DBP 20–200.

## 5. Lab 후보·측정법·값·단위
- 후보는 B0c 동결 itemid만 쓴다. 실행 시 d_labitems로 다시 계산해 다르면 INVALID(item_map_mismatch).
  - TROPONIN: 51002(Troponin I), 51003(Troponin T), 52642(Troponin I)
  - DDIMER: 50915, 51196, 52551
- 제외: CK-MB, CRP/ESR, NT-proBNP.
- **측정법(itemid)별로만 분석하고 합치지 않는다.**
  - subject의 측정법은 첫 적격 결과의 itemid다. 이 배정은 임상 흐름(그 시점 주문 패턴)에 따른 선택이다(§13).
  - 반복 측정은 첫 적격 1개만 쓴다. 정렬: storetime → charttime → itemid → 파일 순서.
  - 첫 결과가 사용 불가여도 이후 결과로 대체하지 않는다. 이후 사용 가능 결과가 있는 subject 수는 봉인한다.
- 값 해석
  - valuenum이 숫자 → MEASURED_NUMERIC
  - valuenum 결측 ∧ value가 `<b`·`<=b`·`>b`·`>=b`(기호 앞뒤 공백 허용) → MEASURED_CENSORED
    - 순위 배치: `<`는 그 측정법의 모든 측정값 아래, `>`는 모든 측정값 위. 같은 쪽 경계값끼리는 b 순서.
    - 순위 기반 분석만 하므로 값을 대입하지 않는다.
  - 그 외 → MEASURED_UNUSABLE
- 단위
  - 비교 전 정규화: 공백 제거·소문자.
  - 정규화 단위가 빈칸이면 UNIT_MISSING(제외)이다.
  - 한 측정법 안에 정규화 단위가 2개 이상이면 NOT_EVALUABLE_UNIT이다(변환 없음).
  - FEU/DDU 차이나 측정 세대(hs 여부)가 단위 문자열에 드러나지 않으면 검출할 수 없다(§13).
  - 봉인: 원 단위·정규화 단위 목록, 셀별 censored 수·서로 다른 경계값 수.

## 6. Missingness·측정 선택 (분석 B, 기술)
- subject × 개념 상태(배타)
  - 첫 적격 결과가 있으면: MEASURED_NUMERIC / MEASURED_CENSORED / MEASURED_UNUSABLE / UNIT_MISSING
  - 없으면: TIME_MISSING(storetime 결측 ∧ charttime ∈ window) → TIME_INELIGIBLE → NOT_MEASURED
- **미측정은 정상이 아니고 0도 아니다.** 분석 A에서 제외한다.
- 공개
  - class별 측정 비율 10 %p 구간: 분모 = class n, n < 100이면 WITHHELD
  - 데이터 품질 문제(UNUSABLE + UNIT_MISSING + TIME_MISSING) pooled 구간: 분모 = 사건 있는 subject, < 100이면 WITHHELD
- 봉인: 측정 subset과 미측정 subset의 baseline 평균·결측(선택 효과 크기), class별 baseline 분포(Table 1 재료).
- 해석: class별 측정 비율 차이는 임상의 선택과 수집 범위의 결과다. 정보 가치가 아니다.

## 7. 주 분석 (분석 A, 측정법 셀별)
- 대상: 해당 측정법의 사용 가능 측정 subject.
- 모형(고정): L2 로지스틱(RIDGE 1.0, 절편 제외), IRLS
  - M0 = baseline 8개(학습 fold 중앙값 대치 → 학습 fold 평균·SD 표준화)
  - M1 = M0 + lab 순위 특징. 순위는 학습 fold 경험분포 백분위이고, baseline과 같이 학습 fold 평균·SD로 표준화한다(같은 RIDGE 척도 — rev2).
  - 시험 행은 변환만 받는다(적합에 쓰지 않음).
- split: subject 5-fold, class 층화(class 안 sha256("EXP-SN-NBI-003|subject_id") 순서, 순번 mod 5). 결정적이다.
  - salt는 1개다. 분할 자체의 변동(합성에서 Δ SD 약 0.011–0.017, 50/class)은 CI에 반영되지 않는다(§13).
- **주 지표: ΔAUROC = fold 평균 OOF AUROC(M1) − fold 평균 OOF AUROC(M0)**
  - fold 평균을 쓰는 이유: pooled OOF는 fold 간 절편 차이로 정보 없는 모형에서 0.5 아래로 편향된다(시험 고정).
- **95 % CI = 재적합 bootstrap(rev2)**
  - B = 1000, seed 20261006
  - 반복마다 class 층화 subject 재표집 → **복제 subject는 원래 fold를 유지**(재분할 금지, 누출 방지) → M0·M1 재적합 → fold 평균 Δ(paired, 같은 재표집) → 백분위 2.5·97.5
  - 실패 반복이 1 %를 넘으면 NOT_EVALUABLE_MODEL
  - 근거: gate 1 통계 시뮬레이션에서 OOF 고정 bootstrap의 포함률은 0.85–0.87이었고, 재적합 bootstrap은 0.96–0.99였다.
- 보조(기술)
  - AUROC(M0), AUROC(M1)
  - 값 단독 AUROC: 원값 순위, "높을수록 PE" 방향 고정, 모형·CI 없음, 사후 방향 반전 금지
  - 전체 코호트 baseline AUROC + 같은 CI
- 사전 지정 비교: (P1) baseline vs + Troponin(측정법별), (P2) baseline vs + D-dimer(측정법별). 조합 모형은 하지 않는다.
- 검정·p 값은 없다. CI는 보정하지 않은 95 % 7개(6셀 + baseline)이며 정밀도 기술용이다. 전부 보고하고 선택 보고는 금지한다.
- 실행 시간(합성 실측, 2026-10-06): M0 + M1 OOF 1회 기준
  - class 당 500명 0.33 s → B 1000이면 셀당 약 6분
  - 1500명 0.94 s → 약 16분
  - 3000명 2.14 s → 약 36분
  - 여기에 labevents 스트리밍(약 5분)이 더해진다. 전체는 수십 분~2시간 이내로 추정한다(nohup·ram_guard).

## 8. 판정 (사전 고정, 반올림 전 값)
- 셀 판정 순서
  1. NOT_EVALUABLE_PAIR
  2. NOT_EVALUABLE_UNIT
  3. INSUFFICIENT_DATA: min(class별 측정 n) < 50
  4. NOT_EVALUABLE_MODEL: 학습 fold 단일 class, IRLS 미수렴, bootstrap 실패 > 1 %
  5. FEASIBLE: ΔAUROC 95 % CI 반폭 ≤ 0.10
  6. EVALUABLE_IMPRECISE: 그 외
- N_MIN 50은 **진입 문턱**이다(단일 AUROC Hanley–McNeil: AUROC 0.75, 50/50에서 반폭 ≈ 0.10). FEASIBLE은 실측 재적합 CI로 따로 판정한다. ΔAUROC 반폭은 두 모형의 상관에 따라 달라 50/50에서도 0.10을 넘을 수 있다.
  - 이것이 [H]·[I]의 'B1 확보 n' 정의다: 측정법별 class 당 사용 가능 측정 subject 수의 최솟값. 봉인을 열기 전에 정의했으며, B0 봉인은 열지 않는다.
- FEASIBLE 규칙의 성질(사전 공개)
  - 정밀도 기준이다. 정보가 없는 lab(Δ ≈ 0, M1 ≈ M0)은 CI가 좁아 대개 FEASIBLE이 된다.
  - 정보가 강할수록 CI가 넓어져 EVALUABLE_IMPRECISE가 될 수 있다(효과 크기에 대해 단조롭지 않음).
  - 따라서 **FEASIBLE·IMPRECISE는 정보 가치의 크기나 유무를 뜻하지 않는다.**
- 개념 상태: FEASIBLE(셀 1개라도) > EVALUABLE > INSUFFICIENT_DATA > NOT_EVALUABLE. 셀 최댓값 요약이다. **개념 상태를 특정 셀 Δ와 묶어 인용하지 않는다.**
- baseline 상태: 같은 반폭 기준, 전체 코호트, N_MIN 50/class.

## 9. 공개 출력 (out/b1/b1_public.json, 68키 고정: expected_schema_b1.json)
- 구성
  - pair: status, cohort_pooled_bucket
  - baseline: status, auroc, ci_lo, ci_hi
  - 개념 × {status, measurement.{acs_measured_bin, pe_measured_bin, data_quality_issue_bin}, assays.<itemid>.{status, n_bucket_acs, n_bucket_pe, auroc_m0, auroc_m1, delta, delta_ci_lo, delta_ci_hi, auroc_value_only}}
- guard(rev2): 키별로 허용 값을 검사한다.
  - status·구간 키: 해당 어휘만
  - 지표 키: WITHHELD, 또는 소수 2자리 문자열이면서 범위 안(AUROC [0, 1], Δ [−1, 1])
  - 위반 시 쓰지 않고 INVALID(output_guard)
- 봉인(로컬 제한 폴더 nbi_b1/sealed/b1_sealed.json, SHA만 공개)
  - exact n, class별 상태 수
  - 단위 목록·censored 수·경계값 수
  - 전체 자리 지표·CI·bootstrap 실패 수, fold별 class 수
  - troponin 셀의 ACS 세부(STEMI·NSTEMI·MI_UNSPEC·SUBSEQUENT·UA) 구성
  - class별·측정/미측정 baseline 요약
  - 이후 사용 가능 결과 수
- **환자 단위 예측·값은 저장하지 않는다.**
- 잔여 추론(사전 공개): 2자리 AUROC·n 구간으로 class 수를 정할 수 없다. 측정 구간의 WITHHELD 여부는 class n이 100 이상인지를 드러낸다(허용). 작은 셀(< 50)은 숨긴다(공격 시험). 역산 값은 후속 설계에 쓰지 않는다.

## 10. 중단·재실행·종료
- 실행기 launch_b1.sh: 7 / 6 / 8 자원 미충족 / 4 이미 실행 / 9
  - marker/launch에 자원 점검 줄·도구 경로·override 여부를 기록한다.
- 러너 run_b1.sh: 7 / 6 / 4 출력 존재 / 5 고정 SHA 불일치(B1_PINNED_SHA256SUMS 10개)
- 스크립트 exit 2
  - preflight: sha_mismatch(입력 5 + schema + B0 공개 3), item_map_mismatch
  - data: schema_mismatch, output_guard, cohort_mismatch, 예외(비공개 로그)
- exit 3 STOP_TITLE. 쓰기 순서: 모든 검사 → 봉인 → 공개.
- 재실행: EXP-SN-NBI-002 [K] rev4/rev5 (a)~(i)를 B1_FINAL에 준용한다.
  - 결함 입증 시에만 재실행한다. 결과 불만·INSUFFICIENT·IMPRECISE·Δ 작음·window·N_MIN·모형·측정법·단위 규칙 변경 희망은 재실행 사유가 아니다.
  - 고정 시험 = tests/test_b1.py·mutation_b1.py·runner_paths_b1.py
  - 모든 재시도는 새 실행기 경로·SHA로 한다(marker 삭제 금지).
  - B1 DEGENERATE = 쌍 NOT_EVALUABLE 또는 6셀 모두 NOT_EVALUABLE_* → 1회 조사·종결.

## 11. 성공(완료) 기준
- B1_FINAL verdict=COMPLETE ∧ rc 0 ∧ counted=yes ∧ 68키·guard ∧ 봉인 SHA meta ∧ 코호트 B0a·B0c·B0d 일치 ∧ logs/ram_guard_b1.log ∧ marker override=none.
- 뜻: "Troponin·D-dimer 측정법별 참조 표준 조건부 분리도를 사전 정의 조건으로 추정할 수 있었는지(또는 없었는지) 기술했다"까지. FEASIBLE·EVALUABLE_IMPRECISE·INSUFFICIENT_DATA·NOT_EVALUABLE은 모두 정상 결과다.

## 12. 실행 (RG RUN + 사용자 승인 후 정확히 1회)
```
bash /home/<user>/medmap-worktrees/safety-net-nbi/docs/research/nbi/b1/launch_b1.sh
```

## 13. 해석 제한 (사전 고정 보고 문구)
- **참조 표준 오염 — troponin**
  - ACS의 MI는 정의상 troponin 상승을 포함하고, UA는 troponin 음성이다(incorporation bias).
  - troponin이 상승한 PE에 I21.4가 함께 코딩되면 MULTI로 빠진다. 그래서 PE class에는 troponin 음성 PE가 상대적으로 많이 남고 분리도가 위로 부풀려진다.
  - **troponin–ACS/PE 분리를 정보 가치로 해석하지 않는다.**
- **참조 표준 오염 — D-dimer**
  - ED의 PE 진단 경로는 D-dimer 양성 → CTPA → I26이다. D-dimer 음성이면 PE 진단이 나오지 않는다. ACS군의 D-dimer는 PE 배제 수단이었다.
  - 그래서 차등 검증으로 분리도가 위로 편향된다.
  - 고위험 PE는 D-dimer 없이 CTPA로 가므로, PE 측정 subset은 사전확률이 낮은 쪽으로 치우친다.
  - **D-dimer–PE 분리를 정보 가치로 해석하지 않는다.**
- **제품 이전 불가**
  - (a) MedMap 추천이 작동할 대상은 아직 검사를 받지 않은 환자다. B1은 이미 주문된 측정 subset만 본다. 측정 subset의 Δ를 미측정 집단으로 옮길 수 없다.
  - (b) 라벨은 ED 퇴원 ICD다. 'ED에서 놓친 PE'는 PE class에 들어오지 않는다. 안전망의 yield·놓친 진단 탐지에 대한 정보는 0이다.
  - (c) baseline은 의도적으로 최소다(chiefcomplaint·acuity·pain·병력·ECG·Wells/HEART 없음). 그래서 Δ는 실제 임상 증분 정보보다 클 수 있다.
- **금지 표현**
  - "Troponin/D-dimer가 ACS와 PE를 구분한다"
  - "MedMap이 D-dimer를 추천하면 PE를 잡는다"
  - "TROPONIN FEASIBLE = troponin이 유용하다"
  - "ΔAUROC = 추천 효과"
  - "CI가 0을 제외하므로 정보가 있다·유의하다"
  - "WD 이후 이용 가능"
  - "임상적으로 검증됨"
- **FEASIBLE 인용 규칙**: 공개 status FEASIBLE·개념 FEASIBLE을 인용할 때는 반드시 "정밀도 기준(CI 반폭 ≤ 0.10) 충족일 뿐, 정보 가치·임상 유용성 아님" 캡션을 함께 쓴다.
- **선택·spectrum**
  - 라벨 정의 코호트, MULTI 제외, 측정법 = 첫 결과 itemid(주문 패턴 선택), 첫 결과가 사용 불가면 제외.
  - outtime 상한 때문에 cath lab 직행 STEMI 등 짧은 체류 ACS는 결과가 outtime 뒤에 저장되어 troponin 측정 subset에서 빠질 수 있다(STEMI 비중 감소).
  - 외부 병원 검사·전원은 수록되지 않는다.
- **시점**
  - 첫 결과만 쓴다. 연속 측정 변화량(delta troponin)과 증상 발현 후 경과 시간은 반영되지 않는다. 조기 내원 MI는 첫 값이 음성일 수 있어 이 부분은 분리도를 과소 추정하는 방향이다(incorporation과 반대 방향).
  - storetime 기준 6 h, WD·triage 시각 없음.
- **측정법**
  - troponin I/T·세대(hs 여부) 미구분(측정법별 분리로 완화).
  - POC 결과는 labevents에 없을 수 있어 누락될 수 있다.
  - D-dimer FEU/DDU는 단위 문자열에 드러날 때만 구분된다.
- **통계**
  - CI는 재적합 bootstrap이지만 salt 1개 분할 변동은 반영되지 않는다.
  - 보정하지 않은 95 % CI 7개다.
  - 값 단독 AUROC에는 CI가 없다.
  - 내부 OOF만 했다(외부 검증 없음). 단일 기관·청구 ICD.

## 14. 자기감사
| 항목 | 판정 | 근거 |
|---|---|---|
| 최종 진단 누출 | 차단 | y만 사용, allowlist, label_in_features 변이 KILLED, 상수 baseline → 정확히 0.5 시험 |
| 퇴원·입원·주호소·중증도 | 차단 | 컬럼 미읽음, 정적·변이 시험 |
| 검사 시행 여부를 입력으로 | 없음 | 측정 subset 조건, 분석 B 기술만 |
| 늦은 정보 | 차단 | 6 h·outtime·도착 전 채취 제외·[E] 배정, window·pre_arrival·no_assignment·time_missing 변이 KILLED |
| 측정법 혼합·단위 | 차단·정규화 | assays_pooled·no_unit_check·unit_not_normalized 변이 KILLED |
| 미측정 = 정상 | 없음 | not_measured_as_zero 변이 KILLED |
| 중도절단 | 순위 배치 | censored_* 변이 KILLED |
| threshold·튜닝 | 없음 | 연속 순위, RIDGE·B·반폭 상수 소스 고정 시험 |
| split·전처리 누출 | 차단 | train_on_test·prep_fit_on_all·ecdf_on_all·boot_refolds_replicates 변이 KILLED, 시험 행 독립 시험 |
| CI | 재적합·paired·층화 | boot_unpaired·boot_unstratified·ci_80 변이 KILLED |
| 결과 기반 선택 | 없음 | 첫 적격 결과, 6셀 + baseline 전부 보고 |
| 공개 exact count | 없음 | 키별 guard·범위, expose_exact_n·guard_no_range 변이 KILLED, small-cell 공격 시험 |
| 제품·임상 과장 | 금지 문구 사전 고정 | §13 |
| B0 봉인 | 미개봉 | — |
| 확인 필요 | — | 측정법별 실제 n·단위·censored 비율(실행 전 미상), D-dimer FEU/DDU, 실행 시간 |

## 15. 고정
- B1_PINNED_SHA256SUMS(10): b1_feasibility.py, ../b0/b0a_availability.py, ../b0/b0c_availability.py, expected_schema_b1.json, tests/test_b1.py, tests/mutation_b1.py, tests/runner_paths_b1.py, ../b0/tests/test_b0a.py, ../b0/tests/test_b0c.py, ../b0/tests/fixtures/cms_icd_titles.json
- 러너에 PINNED·schema·입력·B0 공개 SHA를 하드코딩한다. precheck 로그에 runner·launcher SHA를 남긴다.
- 시험(rev2): 합성 46 OK, 변이 48/48 KILLED(동치 변이 1종 제외, 사유 주석), 러너·실행기 경로 12/12 PASS(아래 manifest 기록).
- 반출 금지: itemid·사전 파생 내용은 공개 저장소로 내보내지 않는다.
