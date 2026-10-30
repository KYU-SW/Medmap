# EXP-SN-NBI-002 B0c 사전등록 (rev7) — LAB / BIOMARKER real-data availability & temporal feasibility

> rev7(2026-10-05, gate 7 NEEDS_FIX 반영, 실행 전): ① TEMPORALLY_UNCERTAIN을 stay 단위로 변경(+최소 stay 수) ② 입원/비입원 층 구간을 공개에서 봉인으로 이동(공개 37키) ③ 문구 정합(charttime 결측·PRE_T0_COLLECTED 범위·[K] 준용 치환·LAB_LINK_DEGENERATE 확장·UNCERTAIN 비적격·DEGENERATE 종료 상태) ④ §19 해석 제한 신설. 실데이터 실행 0회·환자 행 열람 0 그대로.

- 상위 실험: EXP-SN-NBI-002(NBI-B0). B0c 규칙의 원본은 manifest의 [C] window, [D] 정보 유형·가용 시각, [E] 연결, [G] 라벨, [H] pair 규칙, [I] class-blind, [J] 공개 최소화, [K] 실행·재실행·종료, [L] 누출 필드, [M] 수집 범위다. 이 문서는 그 규칙을 B0c 실행 수준으로 구체화하고, 새로 정한 항목에는 **(rev6 신규)**를 표시한다.
- 작성 시점 상태: B0a COMPLETE·VERIFIED(run 20261004_121905, protocol lock c724a06ffda3). B0c는 실데이터 실행 0회. labevents·admissions 환자 행 열람 0. 열람한 것은 d_labitems 사전(환자 정보 없음)과 파일 헤더뿐.
- 이 문서와 코드는 manifest deviation(rev6) + RG 재심사 RUN + 사용자 실행 승인 전에는 실행하지 않는다.

## 1. 목적 / 비목적
- 목적(단 하나): 사전 지정 lab/biomarker 정보 유형이 B0a와 같은 쌍 코호트(ACS–PE, ACS–PERI)의 ED 체류(T0 = ED intime 이후, outtime까지) 안에서 **결과가 저장된 기록(storetime)**으로 존재하는지, EHR 시각으로 정렬 가능한지 라벨과 거친 구간으로 기술한다.
- 비목적·금지: 검사 결과값(value·valuenum·flag·ref_range·comments) 사용, 양성/음성 판정, threshold, AUROC/AUPRC, sensitivity/specificity, odds ratio, 분류기, feature importance, class 간 차이 주장·검정, B1 실행, B0d(radiology) 분석, WD 이후 가용성 주장, 진단 유용성 주장.

## 2. 데이터와 무결성
| 파일 | 상태 | B0c 사용 |
|---|---|---|
| mimic-iv-ed-2.2.zip | sha256 d17bbf2e… (B0a와 동일) | 코호트(B0a 모듈 재사용) |
| mimic-iv-ecg-ext-icd…1.0.1.zip | sha256 4b99cac6… (B0a와 동일) | B0a 모듈이 같이 읽음(코호트 동일성 보장용, B0c 판정 미사용) |
| mimiciv_3.1/hosp/labevents.csv.gz | SHA_OK(PhysioNet SHA256SUMS) 2cd5e09b… | 허용 컬럼 subject_id·itemid·charttime·storetime만 |
| mimiciv_3.1/hosp/d_labitems.csv.gz | SHA_OK b7afdda7… | item 매핑(사전) |
| mimiciv_3.1/hosp/admissions.csv.gz | SHA_OK a9584ed8… | MEDICAL_RECORD_PRE_T0(subject_id·dischtime만) |
| mimiciv_3.1/hosp/patients.csv.gz | SHA_OK 4c7507de… | **미사용**(필요 컬럼 없음, dod는 누출 필드 [L]) |
| mimic-iv-ecg 1.0 machine_measurements·record_list·data_dictionary | SIZE_OK / SHA_NOT_AVAILABLE | 미사용(B0b) |
| mimic-iv-note 2.2 radiology·radiology_detail | SHA_OK | 미사용(B0d) |
| hosp diagnoses_icd·d_icd_diagnoses | **미보유** | manifest의 B0c 민감도 라벨(hosp 합집합, 판정 미사용)은 B0c에서 수행하지 않음 → B1 manifest로 이월 **(rev6 신규)** |
- 모든 입력 SHA는 러너(run_b0c.sh)와 스크립트 인자로 고정하고 실행 시 재검증한다. 하나라도 다르면 INVALID(sha_mismatch).

## 3. 코호트 / 분모
- B0a와 **완전히 동일**. 고정 B0a 모듈(b0a_availability.py sha 628d4ea7…)의 compute()를 그대로 호출해 같은 stay 제외·class 배정·MULTI·주 단위(subject당 쌍별 첫 관련 stay)·제목 키워드 STOP을 재사용한다.
- 동일성 확인: B0c 공개 출력의 쌍 상태·코호트 구간이 B0a 공개 출력(out/b0a/b0a_public.json sha 8434a874…)과 다르면 INVALID(cohort_mismatch_b0a).
- 분모 = n_pool(주 단위 a+b). 결과 기반 코호트(ED 퇴원 ICD)라는 편입 편향은 B0a와 같이 해석 제한에 남긴다. 코호트 선택에 쓴 진단 정보는 availability 판정 입력이 아니다.

## 4. 정보 유형과 item 매핑
| 정보 유형 | 역할 | 규칙(label 소문자 부분 문자열, fluid == 'Blood') | 고정 itemid |
|---|---|---|---|
| BIOMARKER_TROPONIN | **primary**, [H] ACS–PE 적격 입력 | troponin | 51002, 51003, 52642 |
| BIOMARKER_DDIMER | **primary**, [H] ACS–PE 적격 입력 | d-dimer | 50915, 51196, 52551 |
| BIOMARKER_CKMB | 보조(manifest [D] 사전등록), pair 규칙 미사용 | ck-mb · creatine kinase, mb · **isoenzyme mb (rev6 신규)** | 50908, 50911, 51580, 51595 |
| LAB_CRP_ESR | 보조(A0 PERI 'blood work', [D]), pair 규칙 미사용 | c-reactive protein · sedimentation · **high-sensitivity crp (rev6 신규)** | 50889, 51288, 51652 |
| MEDICAL_RECORD_PRE_T0 | 보조([D]) | admissions dischtime < intime(같은 subject) | — |
- 근거: 정보 유형 목록은 manifest [D]가 A0 NBI 후보(R2·R3 BIOMARKER, PERI blood work)에서 이미 사전등록한 것. 이 밖의 lab은 추가하지 않는다.
- **rev6 보완 2건**은 d_labitems 사전만 보고 정했다(환자 데이터·결과 미열람).
  - 51595 'Creatine Kinase, Isoenzyme MB'는 같은 분석물(CK-MB)인데 단어 순서 때문에 원 규칙이 놓친다.
  - 51652 'High-Sensitivity CRP'는 CRP 측정이며, gate 3 의료 심사 MINOR m7(hs-CRP B0c 이월)이 요구한 항목이다.
- 매핑 제외(사전 검토 근거):
  - Fibrin Degradation Products(51213, 52858): D-dimer와 다른 검사
  - Creatine Kinase(CK) total(50910): CK-MB 아님
  - Creatine Kinase Isoenzyme BB/MM: CK-MB 아님
  - fluid ≠ Blood 항목 전부
- 고정 방식: ITEMS(위 13개)를 코드에 고정한다. 실행 시 d_labitems에 규칙을 다시 적용해 ITEMS와 다르면 INVALID(item_map_mismatch). 매핑 산출물은 b0c/labitem_map.json(사전 내용, 건수 없음).
- 해석 제한: troponin 측정 세대(hs-cTn 여부)·POC 여부는 구분하지 않는다. Troponin I/T가 섞여 있다. hs-cTn 주장은 금지.
- 저장 원칙: labitem_map.json은 credentialed 데이터셋에서 나온 사전 내용이다. 연구 브랜치 로컬에만 두고 공개 저장소(~/medmap-github 등)로 내보내지 않는다.

## 5. 가용성 정의 (시각 기준 사전 고정)
- **가용 시각 = storetime**(결과 저장 시각, manifest [D]). charttime(채취 시각)은 보조 판정에만 쓴다. 결과를 본 뒤 기준 시각을 바꾸지 않는다.
- 연결([E]): subject_id ∧ storetime ∈ window. hadm_id는 쓰지 않는다(귀가 환자 제외 = 결과 조건부 선택 방지).
  - 같은 subject의 stay가 겹치면, 사건 시각 이전(≤)에 intime이 있는 stay 중 intime이 가장 늦은 stay에 배정한다.
- 주 window W_STAY = [intime, outtime], 양 끝 포함. outtime 이후는 가용으로 세지 않는다(disposition 교란 차단, [C]).
- 한 stay·유형에 대한 판정
  - **기록됨(AVAILABLE 집계에 포함)**: storetime ∈ W_STAY ∧ 그 stay에 배정 ∧ (charttime ≥ intime 또는 charttime 결측 — 결측이면 가용으로 셈, rev7 명시).
  - **PRE_T0_COLLECTED**: charttime < intime ∧ storetime ∈ W_STAY ∧ 그 stay에 배정(rev7 범위 정합). 가용으로 세지 않고 봉인 집계만 한다.
  - storetime 결측: 가용으로 세지 않는다. 체류 중 채취(charttime ∈ W_STAY) 사건 기준으로 결측 건수를 봉인한다.
  - 봉인 전용 서술(판정 미사용): storetime ∈ [intime−24h, intime)인 stay 수, storetime ∈ (outtime, outtime+24h]인 stay 수(ED 이후 입원 중 결과 포함), W1·W3·W6 window별 기록 stay 수, itemid별 기록 stay 수(측정법 구성).
- MEDICAL_RECORD_PRE_T0: 같은 subject의 admissions 중 dischtime < 해당 stay intime인 기록이 있으면 '있음'. 입원 기록만 보며 외래 기록은 수집 범위 밖이다([M]).

## 6. 라벨과 시점 클래스
- 쌍 상태: class a 또는 b가 0이면 NOT_EVALUABLE(모든 라벨 NOT_EVALUABLE).
- lab 4종 라벨(순서대로 적용)
  1. NOT_EVALUABLE(쌍 평가 불가)
  2. **TEMPORALLY_UNCERTAIN (rev7, stay 단위)**: 체류 중 채취 사건(charttime ∈ W_STAY, 배정 stay)이 있는 pooled stay 중, 그 유형의 storetime이 전부 결측인 stay의 비율 ≥ 0.5 **∧** 그런 stay 수 ≥ Q_MIN(30). 시각을 정렬할 수 없으므로 가용으로 판정하지 않는다. 분모는 manifest unit_of_analysis와 같은 주 단위 stay다. 0.5·Q_MIN은 사전 고정이며 민감도 분석은 금지한다(rev6의 사건 단위 비율은 gate 7 통계 MAJOR로 폐기: 반복 채혈 소수 stay가 라벨을 좌우).
  3. NOT_AVAILABLE_IN_DATA: pooled 기록 stay 0
  4. RECORDED_IN_STAY_AVAILABLE: class a·b 각각 기록 stay ≥ N_MIN(30)
  5. RECORDED_IN_STAY_PARTIAL: 그 외
- PRE_T0 기록 라벨: NOT_EVALUABLE / NOT_AVAILABLE_IN_DATA / PRE_T0_RECORD_AVAILABLE(각 class ≥ 30) / PRE_T0_RECORD_PARTIAL
- 시점 클래스(공개, 판정·pair 규칙 미사용)
  - EARLY_ROUTINE_POSSIBLE: pooled 첫 storetime 지연 중앙값 ≤ 1 h(반올림 전 값)
  - LATER_IN_STAY: 중앙값 > 1 h
  - INSUFFICIENT_N: 지연 값 < Q_MIN 30
  - TEMPORALLY_UNCERTAIN: 위 2번 규칙에 해당
  - NOT_EVALUABLE: 쌍 평가 불가
  - PRE_T0는 NOT_APPLICABLE
- 금지 표현: "WD 이후 이용 가능". EARLY_ROUTINE_POSSIBLE은 "WD 형성 전 또는 동시에 생성됐을 수 있는 정보"라는 뜻일 뿐이다.

## 7. 공개 출력 계약 (out/b0c/b0c_public.json, 37키 고정: expected_schema_b0c.json, rev7)
- 쌍별 공개 항목
  - pair_status, cohort_pooled_bucket(B0a와 같은 구간)
  - labels(5개 유형)
  - pooled_share_bin(5개): 10 %p 구간 0_10…90_100
  - timing(5개)
  - (rev7) 입원/비입원 층 구간은 **공개하지 않는다**. 입원 여부가 class와 강하게 연관된 쌍(예: ACS~PERI)에서는 층 구간이 class별 기록 비율의 대리값이 되어 [I] class-blind 원칙과 [L](1)을 우회하기 때문이다(gate 7 통계 MAJOR). manifest [M]의 층 보고는 봉인 층 집계로 충족한다.
  - pair_rule_inputs.acs_pe_eligibility
- 전체: pair_decision.b1_primary_pair
- 구간 공개 조건: pooled 분모 ≥ SHARE_MIN_POOL 100이고 쌍이 평가 가능해야 한다. 아니면 WITHHELD.
- guard: 모든 공개 leaf 값은 허용 어휘 문자열이어야 한다. 숫자나 자유 문자열이면 쓰지 않고 INVALID.
- meta: SHA·상수만 담는다(guard 대상 밖, 코드로 고정한 값).
- 공개하지 않는 것: exact count, class별 값, window별 값, 지연 수치, itemid별 값, storetime 결측 수, PRE_T0_COLLECTED 수, 입원/비입원 층 크기와 층별 기록 수·비율, 쌍 간 차집합.

## 8. 봉인 출력 (로컬 제한 폴더 nbi_b0c/sealed/b0c_sealed.json, SHA만 공개)
- 담는 값: 쌍별 n_a·n_b·n_pool·입원/비입원 층 크기(입원 = edstays hadm_id 존재, B0a와 같은 정의), 유형별 pooled·a·b·a_admitted·b_admitted·층별 기록 수, W1·W3·W6 a·b, storetime 결측·존재 사건 수와 채취 stay·전부 결측 stay 수, PRE_T0_COLLECTED·pre-24h·post-ED-24h stay 수, itemid별 기록 stay 수, 지연 분위수, 시점 라벨
- 개봉 규칙은 manifest [I]와 같다(EXP-SN-NBI-003 protocol lock 이후에만, deviation + SHA 재검증 + 사용자 로컬 개봉).
- Claude 접근 차단: 기존 permissions.deny(Read·Edit·Bash 봉인 경로)를 그대로 적용한다.

## 9. B1 pair 규칙 적용 ([H] 그대로)
- ACS–PE 적격: BIOMARKER_TROPONIN 또는 BIOMARKER_DDIMER가 RECORDED_IN_STAY_AVAILABLE이면 ELIGIBLE이고, b1_primary_pair = ACS~PE로 확정한다.
  - 둘 다 아니면 PENDING_DATA_B0D(CTPA 대기)다. CTPA가 아직 판정되지 않아 비적격 확정은 불가능하다.
  - 쌍이 NOT_EVALUABLE이어도 같다.
- PARTIAL·TEMPORALLY_UNCERTAIN은 적격 근거가 아니다. [H]의 '판정됨·비적격' 상태에 TEMPORALLY_UNCERTAIN을 포함한다(rev7 명시).
- 해석 제한([H]): 라벨로 정의한 코호트라 ED I21 ↔ troponin, ED I26 ↔ D-dimer/CTPA 관계가 기계적으로 높아질 수 있다. ELIGIBLE은 "B1을 시작할 정보 유형이 기록돼 있다"는 뜻일 뿐이다. 판별 정보의 존재나 충분성을 뜻하지 않는다. B1 '확보 n'의 정의는 B1 preregistration에서 정한다.

## 10. 중단(abort) 조건 — 공개 출력 없이 counted=no
- exit 7: 러너에 인자를 넣음
- exit 6: cd 실패
- exit 4: 출력(out/b0c 또는 봉인 폴더)이 이미 있음
- exit 5: 고정 SHA 불일치(B0C_PINNED_SHA256SUMS, 9개 파일)
- exit 2(INVALID)
  - preflight: 입력 SHA 불일치, item_map_mismatch
  - data: schema_mismatch(53키), output_guard, cohort_mismatch_b0a, 예외(traceback은 비공개 로그로만)
- exit 3: STOP_TITLE(B0a와 같은 제목 키워드 검사)
- 봉인 쓰기는 모든 검사를 통과한 뒤에만 한다(검사 → 봉인 → 공개 순서).

## 11. 퇴화·재실행·종료 규칙
- manifest [K] rev4·rev5의 (a)~(i)를 B0c에 그대로 적용한다. 대상은 B0C_FINAL 로그다.
  - 산출물 전부 보존
  - 재실행은 합성 회귀 테스트로 구현 결함을 입증한 경우에만
  - 결함 미입증이면 최초 승인 실행을 최종으로 확정
  - INVALIDATED_BY_IMPLEMENTATION_BUG → FINAL_COUNTED_RUN_CANDIDATE
  - ENVIRONMENTAL_ABORT
  - counted 보류는 1회 조사·종결 deviation으로 종결
  - fixture 출처 제한
- B0c 퇴화 조건 **(rev6 신규)**
  - (1) B0a 퇴화 조건(두 쌍 NOT_EVALUABLE ∧ LT_100)은 cohort_mismatch_b0a 검사 때문에 B0c에서 생길 수 없다.
  - (2) **LAB_LINK_DEGENERATE**: 두 쌍에서 lab 4종 8칸이 모두 {NOT_AVAILABLE_IN_DATA, TEMPORALLY_UNCERTAIN}에 속하면(rev7 확장) 연결 결함(subject_id 형식, 경로, 시각 형식)을 의심한다. [K](a)·(h)의 DEGENERATE와 같이 처리한다(1회 조사 → A/B 종결).
- [K] 준용 시 바꿔 읽을 것(rev7 명시): (h)(1) 고정 시험 = tests/test_b0c.py·tests/mutation_b0c.py. (h) 종결 기한 사건 = 다음 RG 재심사·B0d deviation·B1 manifest 착수 중 가장 이른 시점 전. 재실행 경로의 /rg-verify 대상 = 원 경로 logs/와 deviation에 고정한 재실행 경로의 *_b0c_final.log 전부.
- 종료 상태(rev7, gate 6 이월 반영): 결함 미입증으로 확정된 B0c DEGENERATE(LAB_LINK_DEGENERATE 포함)는 B0 전체 종료 판정에서 'NOT_EVALUABLE 명시 종료'로 취급한다.
- 재실행 사유가 아닌 것: coverage가 낮음, ELIGIBLE이 안 나옴, TEMPORALLY_UNCERTAIN, 기대와 다름, 다른 timestamp·itemid·threshold를 쓰고 싶음.
- /rg-verify 대조
  - 원 경로와 deviation에 고정한 재실행 경로의 B0C_FINAL 중, 재분류되지 않은 counted=yes 실행이 정확히 1개
  - precheck runner_sha256 = run_b0c.sh 고정값
  - 공개 meta SHA 일치: 입력 5개, schema, script, b0a 모듈, B0a 공개, sealed
  - 공개 leaf 전부 허용 어휘
  - LAB_LINK_DEGENERATE였다면 종결 deviation이 있을 것

## 12. 완료(success) 기준
- B0C_FINAL verdict=COMPLETE ∧ rc 0 ∧ counted=yes
- 37키(rev7), 허용 어휘, sealed SHA가 meta에 기록됨
- 코호트가 B0a와 일치
- 중단 조건 없음, LAB_LINK_DEGENERATE 아님
- COMPLETE의 뜻은 "사전 지정 lab 정보 유형의 ED 체류 중 결과 저장 기록 여부와 시각 정렬 가능성을 라벨·거친 구간으로 기술했다"까지다.

## 13. NOT_EVALUABLE
- 쌍 단위: class a 또는 b가 0이면 해당 쌍의 모든 유형이 NOT_EVALUABLE이다.
- 유형 단위: TEMPORALLY_UNCERTAIN은 "시각 정렬 불가"라는 protocol 결과이며, 그대로 보고한다.

## 14. 실행 (RG RUN + 사용자 승인 후 정확히 1회)
```
cd /home/<user>/medmap-worktrees/safety-net-nbi && mkdir -p docs/research/nbi/b0/logs && RG_EXP=EXP-SN-NBI-002 nohup bash docs/research/nbi/b0/run_b0c.sh > docs/research/nbi/b0/logs/nohup_b0c.log 2>&1 & JOB=$!; echo "PID: $JOB"; nohup bash ~/scripts/ram_guard.sh "$JOB" 90 60 docs/research/nbi/b0/logs/ram_guard_b0c.log > /dev/null 2>&1 &
```
- 실행 전에 `~/scripts/wait_for_resources.sh --check --no-gpu`(CPU 전용)로 자원과 디스크를 점검한다.
- 예상 시간: labevents 2.6 GB를 /mnt/c에서 스트리밍하므로 수십 분 수준으로 추정한다(실측 전, 확인 필요).
- 메모리: 대상 itemid·코호트 subject 사건만 보관하므로 작다.

## 15. 고정(freeze) 방식
- 고정 SHA 목록(B0C_PINNED_SHA256SUMS): b0c_availability.py, b0a_availability.py(import), expected_schema_b0c.json, b0c_labitem_map.py, b0c/labitem_map.json, tests/test_b0c.py, tests/mutation_b0c.py, tests/test_b0a.py(Gen import), tests/fixtures/cms_icd_titles.json
- 러너 run_b0c.sh에 PINNED·schema·입력 SHA를 하드코딩한다.
- manifest rev6 deviation에 이 문서의 SHA와 러너 SHA를 기록한다. RG RUN 시 protocol lock이 갱신된다.
- 시험(rev7): 합성 fixture 31 tests OK, 변이 20/20 KILLED(stay 단위 UNCERTAIN·경계 0.5·최소 stay 수·층 공개 변이 추가), 러너 실패 경로 3종(인자 7, 변조 5, 출력 존재 4; scratch 사본, HOME 교체, 실데이터 도달 전)

## 16. 개인정보 / 잔여 위험
- B0a [J]와 같은 원칙을 적용한다.
  - LOCAL ONLY
  - 환자 행·ID·환자별 시각·결과값을 세션이나 외부로 내보내지 않는다.
  - stdout은 판정 1줄
  - traceback은 비공개 로그로만 남긴다.
- 잔여 추론 범위(rev7): B0a에서 열거한 범위(라벨 하한 30, 비율 10 %p 구간, n_pool ≥ 100)와 같다. 층 구간을 공개하지 않으므로 gate 7에서 열거된 입원 비율 추정(4유형 조합 시 폭 약 0.04)과 입원≈class 쌍의 class 비율 대리 노출은 없어진다. B0c 공개 + B0a 공개 조합의 새 역산 경로는 lab 유형별 pooled 구간·라벨 하한뿐이다.
- lab 결과값 컬럼은 csv 파서가 행 단위로 잠시 거칠 뿐 보관하거나 참조하지 않는다. 허용 컬럼 테스트와 변이 테스트로 고정했다.

## 17. 기대 주장 (COMPLETE일 때만)
- 허용: "MIMIC-IV-ED·hosp 단일 기관 후향 데이터에서, ED 퇴원 ICD로 정의한 쌍 코호트(편입 편향 있음)에 대해, 사전 지정 lab 정보 유형(troponin, D-dimer, CK-MB, CRP/ESR)의 ED 체류 중 결과 저장 기록 여부와 시점 해석 라벨을 기술했다."
- 금지: 진단 유용성, 판별력, threshold, hs-cTn 성능, WD 이후 가용성, 임상 권고, 오진 감소, class 간 검사 시행 차이(봉인)

## 18. 자기감사(self-audit, RG 제출 전)
| 항목 | 판정 | 근거 |
|---|---|---|
| B1 성능분석 혼입 | 없음 | 성능 지표·모델 코드 없음 |
| 진단 가치 계산 | 없음 | class 간 비교·검정 없음, class별 값은 봉인 |
| 실제 lab 값 사용 | 없음 | LAB_ALLOW 4개 컬럼, 테스트·변이 value_column_read KILLED |
| 결과 기반 item 선택 | 없음 | rev6 보완 2건은 사전(dictionary)만 보고 결정, 환자 데이터 미열람 |
| 후행 진단 누출 | 해석 제한으로 공개 | 코호트는 ED 퇴원 ICD(편입 편향), availability 판정 입력 아님 |
| 시점 주장 강도 | 제한 | storetime 기준, WD 이후 주장 금지, 결측 다수면 UNCERTAIN |
| 개인정보 누출 | 차단 | 어휘 guard, 37키 schema(rev7, 층 구간 봉인), 공격 fixture(1–10 변화 → 공개 동일) |
| small-cell exact count | 비공개 | 모든 count 봉인, 구간은 n ≥ 100에서만 |
| B0a 코호트 일관성 | 보장 | 같은 모듈 호출 + cohort_mismatch_b0a 검사 |
| NOT_EVALUABLE 경로 | 있음 | 쌍 0 class, UNCERTAIN, LAB_LINK_DEGENERATE |
| 실행 횟수·재실행 규칙 | 고정 | [K] (a)~(i) 준용, counted 규칙 |
| 확인 필요 | — | labevents가 ED 귀가 환자 lab을 얼마나 포함하는지는 실행 전에 알 수 없어 층 구간으로만 보고한다([M]). 실행 시간 실측 전. |

## 19. 해석 제한 (rev7 신설, gate 7 의료·설계 MINOR 반영 — 판정 규칙 불변, 보고 문구 사전 고정)
- 측정법 구성: CK-MB에는 계산값(50908 index·51580 calculated)과 전기영동 isoenzyme(51595)이 섞여 있다. LAB_CRP_ESR은 CRP(hs-CRP 포함)와 ESR(Westergren 약 1 h)을 합친 유형이라 시점 라벨이 두 검사의 혼합이다. troponin I/T 혼재, 측정 세대(hs 여부)·POC 미구분. d_labitems에 POC 표기 troponin이 없으므로 ED POC 결과가 labevents에 없으면 troponin 가용성은 과소 추정될 수 있다.
- 체류 절단: 가용은 outtime까지만 센다. 짧은 체류(예: cath lab 직행 STEMI)는 ED 채취 결과가 outtime 뒤에 저장되어 빠질 수 있고, 입원 대기가 긴 class는 기회가 많다 → class 간 차등 절단 가능. 봉인 post-ED 24 h 집계로만 기술한다.
- 수집 범위: hosp labevents가 ED만 거친(귀가) 환자의 ED lab을 얼마나 포함하는지 B0c 공개 출력으로는 알 수 없다. 기록 없음은 '미시행'과 '수집 범위 밖'을 구분하지 못한다(manifest [M]). 층별 기록은 봉인에만 있다.
- 참조 표준 구조: ED I21은 정의상 troponin 상승을 포함하고 UA는 정의상 troponin 음성이다(incorporation bias). ED I26은 CTPA/V/Q 확인을 거친 경우다(verification bias). D-dimer는 사전확률이 낮을 때 주로 시행된다(confounding by indication). 따라서 [H] ELIGIBLE은 정보 유형 기록의 존재일 뿐이며, B1에서 troponin·D-dimer의 존재·시점을 입력으로 쓸 경우의 처리는 B1 manifest 필수 항목이다.
- MEDICAL_RECORD_PRE_T0의 실제 정의: '같은 subject의 이 기관 이전 입원 기록 존재(dischtime < intime)'뿐이다. 기록 내용이 T0에 활용 가능했는지, 외래 기록은 담지 않는다. 관찰 유형 입원이 섞일 수 있고, 데이터 시작에 가까운 stay는 되돌아볼 기간이 짧다(좌측 절단). 공개 보고 때 라벨명보다 이 정의 문장을 먼저 쓴다.
- 범위 밖 후보: NT-proBNP·Myoglobin·Lactate는 [D] 목록 밖이라 B0c에 추가하지 않는다. NT-proBNP(PE 위험층화)는 B1 manifest 검토 후보로만 기록한다. ED-only 동일 질환 직전 입원(유병 사례) lookback 민감도는 diagnoses_icd 미보유로 B1 manifest로 이월한다(potential_confounders의 'lookback 민감도는 B0c' 문구를 B1 이월로 정정).
- 반출 금지: b0c/labitem_map.json과 tests/test_b0c.py의 사전 fixture는 credentialed 사전 내용을 담는다. 공개 저장소 내보내기(전체 push·브랜치 병합 포함) 체크리스트에서 이 두 파일과 그 git 이력을 제외한다.
