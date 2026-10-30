# NBI-B0 설계 v0 — Real-Data Information Availability & Temporal Feasibility

> **rev1 정정(2026-10-03, EXP-SN-NBI-002 gate-1 반영)**: 이 문서는 배경 자료이며 충돌 시 manifest 우선. §14의 "ED 라벨 vs ECG-Ext-ICD 라벨 교차 일치율"은 **폐기**(*_diag_* 미사용). §7 T0의 의미는 manifest [B] "ED 도착 기준 기록 여부(RECORDED_IN_STAY)"로 대체 — WD 이후 가용성은 B0에서 NOT_EVALUABLE. §6·§8의 IMAGING_CT_CHEST는 CTPA·CCTA·VQ로 분리, lab·영상 연결은 subject_id+시각(hadm_id 미사용). Cardiac Disease는 B0 실행 제외.

- 작성: 2026-10-03, 브랜치 `research/safety-net-nbi`
- 상태: DRAFT. RG 미제출, 환자 행 열람 0, 환자 단위 집계 0
- 확인 범위: 로컬 zip 파일 목록·CSV 헤더 1줄·README·LICENSE, PhysioNet 공개 문서
- 선행: EXP-SN-NBI-001 NBI-A0 = CONFORMANT, RG VERIFIED (커밋 `f16ea12`). A0 의미 = 사전등록 결정적 규칙 구현이 사전 계산값을 재현했다는 것뿐

---

## 1. A0 산출물 보존 (완료)

| 항목 | 위치 | 커밋 |
|---|---|---|
| 승인된 최초 실행 final log | `a0/logs/20261003_153828_final.log` (A0_FINAL CONFORMANT, rc1=rc2=0, SAME) | `f16ea12` (gitignore로 `-f` 추가) |
| precheck·run1·run2 log (종료코드 포함) | `a0/logs/20261003_153828_{precheck,run1,run2}.log` | `f16ea12` |
| run1·run2 출력 | `a0/out/run{1,2}/` (candidates, review, report[expected 비교 포함], NBI_A0_SHA256SUMS) | `f16ea12` |
| 검증 보고 | `.research-guardian/audits/EXP-SN-NBI-001/verify/20261003_154339_VERIFIED.md` | `f16ea12` |
| protocol lock | `.research-guardian/experiments/EXP-SN-NBI-001/protocol.lock.json` (b5e78f39df0e) | `f018b40` |
| 코드·입력·러너 SHA | `a0/A0_PINNED_SHA256SUMS`, manifest dataset_version, report.json inputs | `4a35ac5`·`f16ea12` |
| 제외 | `a0/__pycache__/`, `a0/tests/__pycache__/` (재현 무관 캐시) | — |

## 2. RG 구조 제안

| 안 | 내용 | 판정 |
|---|---|---|
| **EXP-SN-NBI-002 = B0**, EXP-SN-NBI-003 = B1 | 단계별 독립 manifest·lock·verify | **추천** — A0 lock은 VERIFIED로 닫힘, 같은 ID에 B0를 넣으면 lock 필드 deviation이 필요해 audit trail이 섞임 |
| EXP-SN-NBI-001 안에 B0 추가 | 한 ID | 비추천 — 동결 protocol(A0)과 다른 데이터·목적 |
| EXP-SN-NBI-001-B0 | 접미사 ID | 가능하나 rg.py ID 관례(EXP-xxx)와 다름 |

## 3. 다운로드·파일 상태 (2026-10-03 16:41 실측)

| 데이터셋 | 상태 | 위치 | 크기 |
|---|---|---|---|
| MIMIC-IV-ED 2.2 | 완료 | `C:\Users\<user>\Downloads\mimic-iv-ed-2.2.zip` | 121.9 MB |
| MIMIC-IV-Ext Cardiac Disease 1.0.0 | 완료 | 같은 폴더 | 27.2 MB |
| MIMIC-IV-ECG-Ext-ICD 1.0.1 | 완료 | 같은 폴더 | 37.4 MB (CSV 해제 시 338.9 MB) |
| MIMIC-IV-ECG 1.0 | **진행 중 4.62 / 33.80 GB (13 %)**, 평균 약 73 KB/s, curl.exe 실행 중 | `mimic-iv-ecg-1.0.zip.part` | — |
| MIMIC-IV 3.1 | **없음** (로컬 검색 0) | — | — |
| MIMIC-IV-Note 2.2 | **없음** | — | — |
| Symile-MIMIC 1.0.0 | **없음** | — | — |

PhysioNet 공개 문서 기준: MIMIC-IV-ECG의 `machine_measurements.csv`(174.2 MB)·`record_list.csv`(67.1 MB)는 개별 다운로드 가능 → B0·B1의 ECG 구조화 정보에는 33.8 GB zip 불필요 (waveform만 zip 필요).

## 4. 데이터 사용 원칙 (DUA·LLM)

| 근거 | 내용 |
|---|---|
| 3개 zip의 LICENSE.txt | PhysioNet Credentialed Health Data License 1.5.0 — 3항 "will not share access to PhysioNet restricted data with anyone else", 2항 신원 노출 방지, 8항 논문 코드 공개 |
| PhysioNet 공지 2025-09-24 "Use of MIMIC Data with Large Language Models and Online Services" | 서드파티 LLM으로 전송은 DUA 금지 대상; 사용 시 zero data retention·학습 미사용·사람 검토 없음 확인 필요; 로컬 LLM 권장 |
| 이 세션(Claude Code) | 이 계정의 zero data retention 적용 여부 **확인 필요** → 충족 안 된 것으로 간주 |

**결론: LOCAL SCRIPT ONLY.** Claude 세션에 들어오는 것은 schema·컬럼명·코드·집계(소표본 억제 적용)만.

- 로컬 스크립트 출력 = 집계 JSON/CSV만, stdout은 판정 1줄
- 예외 발생 시 traceback(행 값 포함 가능)은 로컬 비공개 로그에만 쓰고 stdout에는 예외 타입만
- 출력 guard: ID 형식(8자리 subject_id·hadm_id·stay_id 등), 날짜·시각 문자열, note 텍스트 흔적이 있으면 출력 파일을 격리하고 INVALID
- 소표본 억제(제안): 1–10 건은 `<11`로 표기 (PhysioNet 강제 규정 여부 확인 필요, 보수적 선택)
- 원본 데이터 위치(제안): `~/<restricted>/mimic/` (git·worktree 밖, `chmod 700`, WSL ext4; 주의 — WSL `/`는 물리적으로 C:)

## 5. 스키마 인벤토리 (헤더·README 수준)

| 데이터셋 / 파일 | 컬럼 | 시각 필드 | 비고 |
|---|---|---|---|
| ED `edstays` | subject_id, hadm_id, stay_id, intime, outtime, gender, race, arrival_transport, disposition | intime, outtime | hadm_id 존재 = 입원 (누출) |
| ED `triage` | subject_id, stay_id, temperature, heartrate, resprate, o2sat, sbp, dbp, pain, acuity, chiefcomplaint | **없음** | README: "collected at the time of triage", 도착 직후 |
| ED `vitalsign` | subject_id, stay_id, charttime, temperature, heartrate, resprate, o2sat, sbp, dbp, rhythm, pain | charttime | 체류 전체 시계열 |
| ED `diagnosis` | subject_id, stay_id, seq_num, icd_code, icd_version, icd_title | 없음 | 퇴원 후 코더 부여, 최대 9개 — 참조 표준 후보, 입력 금지 |
| ED `medrecon` / `pyxis` | 투약 이력 / ED 투약 분배 | charttime | pyxis(ED 투약)는 의심 진단 반영 → 입력 금지 |
| ECG-Ext-ICD `records_w_diag_icd10.csv` | file_name, study_id, subject_id, ecg_time, ed_stay_id, ed_hadm_id, hosp_hadm_id, ed_diag_ed, ed_diag_hosp, hosp_diag_hosp, all_diag_hosp, all_diag_all, gender, age, anchor_year, anchor_age, dod, ecg_no_within_stay, ecg_taken_in_ed, ecg_taken_in_hosp, ecg_taken_in_ed_or_hosp, fold, strat_fold | ecg_time | 진단 = 퇴원 코딩; ECG–stay 연결은 시각 비교로 생성 |
| MIMIC-IV-ECG `machine_measurements.csv` (미보유) | subject_id, study_id, cart_id, ecg_time, rr_interval, qrs_onset, qrs_end, …, bandwidth, filtering, report_0..report_17 | ecg_time | **ECG 시각 = 기기 내부 시계, MIMIC-IV 시각과 크게 어긋날 수 있음**(공식 문서) |
| Cardiac Disease `heart_diagnoses.csv` | note_id, subject_id, hadm_id, note_type, …, HPI, physical_exam, chief_complaint, invasions, X-ray, CT, Ultrasound, CATH, ECG, MRI, reports | charttime(퇴원요약) | 퇴원요약 유래 → T0 입력 금지 |
| Cardiac Disease `heart_labevents_*` | hadm_id, specimen_id, charttime, storetime, value, valuenum, …, label, fluid, category, examination_group | charttime, storetime | 입원 + 결과 기반 코호트 |
| MIMIC-IV hosp `labevents` (미보유) | 공식 문서: ED·외래 검사도 일부 포함 | charttime, storetime | troponin·D-dimer 출처 |
| MIMIC-IV-Note `radiology` (미보유) | note_id, subject_id, hadm_id, note_type, charttime, storetime, text | charttime, storetime | 영상 결과 텍스트; indication 문구 누출 |

## 6. NBI 후보 ↔ MIMIC 출처 매핑

| A0 후보 (pair) | 정보 유형 | 데이터셋 | 파일·필드 | 시각 | 구조화 | T0 이후 | 누출 위험 | 현재 보유 |
|---|---|---|---|---|---|---|---|---|
| ECG ST·Q·PR 소견 (ACS–PERI R1), ECG (R3) | ECG | MIMIC-IV-ECG | machine_measurements report_0..17·측정값 | ecg_time (**시계 불일치**) | 구조화+기계 판독문 | UNCERTAIN | MEDIUM (시각 정렬) | 아니오 |
| ECG 시행 여부·시각 | ECG | ECG-Ext-ICD | ecg_time, ed_stay_id, ecg_taken_in_ed | ecg_time | 구조화 | UNCERTAIN | HIGH(시행 여부 = 의심 반영) | **예** |
| 마찰음 (A1b2-0016) | PHYSICAL_EXAM | Cardiac Disease physical_exam | 퇴원요약 텍스트 | 없음 | 텍스트 | NO | HIGH | 예(사용 금지) |
| troponin (ACS R3) | BIOMARKER | MIMIC-IV hosp labevents | itemid(d_labitems), valuenum | storetime(결과 가용) | 구조화 | YES 예상 | MEDIUM(주문 = 의심) | 아니오 |
| D-dimer (PE R3) | BIOMARKER | 동일 | 동일 | storetime | 구조화 | YES 예상 | MEDIUM | 아니오 |
| CTPA·CT angiography (ACS–PE R2) | IMAGING | MIMIC-IV-Note radiology | text (결과), charttime/storetime | storetime | 텍스트 | YES 예상 | HIGH(indication 'r/o PE', NLP 필요) | 아니오 |
| 심초음파·흉부 X선 (R3) | IMAGING | radiology | 동일 | 동일 | 텍스트 | YES 예상 | HIGH | 아니오 |
| 활력 (SpO2·HR·BP; A0 SUPPORTING context) | VITAL_SIGN | ED triage / vitalsign | 구조화 | triage 없음 / charttime | 구조화 | triage = T0 시점 | LOW–MEDIUM | **예** |
| 이전 CAD 검사 기록 (A1b2-0012) | MEDICAL_RECORD | hosp 과거 입원 | intime 이전만 | — | 구조화 | T0 이전 | MEDIUM | 아니오 |

## 7. T0 후보와 bias

| 후보 | 정의 | 장점 | bias·문제 | 판정 |
|---|---|---|---|---|
| T0-a ED 도착 | edstays.intime | 전 stay에 존재, 검사 이전 | WD 미형성 시점; triage 정보 시각 없음(도착 근사) | **주 후보** |
| T0-b triage 완료 | 시각 컬럼 없음 | — | 측정 불가 | 불가 |
| T0-c 첫 ECG 직전 | ecg_time | 의사 평가 근사 | ECG 시계 불일치, ECG 시행 = 의심 반영 | 비추천 |
| T0-d 첫 lab 채취 | labevents charttime | — | 주문 = 의심(confounding by indication) | 비추천 |
| T0-e 입원 시점 | admittime | — | 입원 결정 = 결과 반영, ED 귀가 환자 제외 | 금지 |

S0(T0 상태) 입력 후보 = 나이·성별(anchor), triage 활력·pain. chiefcomplaint·acuity는 기본 제외(누출), 민감도 분석으로만 검토. B0는 WD를 정의하지 않음(가용성만); WD는 B1에서 CORE 방식 반사실 부여 후보.

## 8. 참조 표준·코호트 정의 후보

| 항목 | 제안 |
|---|---|
| 진단 출처 (주) | ED `diagnosis` (ED 퇴원 ICD, 귀가 환자 포함) |
| 진단 출처 (보조) | hosp `diagnoses_icd` (입원 시, MIMIC-IV 3.1 필요), ECG-Ext-ICD `ed_diag_ed`로 교차 확인 |
| ACS | STEMI/NSTEMI + unstable angina 묶음 (ICD-10 I21·I22·I20.0 계열, ICD-9 410·411.1 계열 — **코드표는 공식 사전과 대조 후 고정, 확인 필요**). 세부 라벨 보존, 분리는 민감도 분석만 |
| PE | ICD-10 I26 계열, ICD-9 415.1 계열 (확인 필요) |
| 심낭염 | ICD-10 I30 계열, ICD-9 420 계열 (확인 필요; 심낭삼출 단독 등 경계 코드 처리 사전 결정) |
| 위치 | 주: stay의 모든 seq_num / 민감도: seq_num=1 |
| rule-out 코드 | "의심 후 배제" 계열 관찰 코드·증상 코드(흉통 등)는 truth 아님 |
| 공존 | ACS+PE, ACS+PERI 동시 코드 → BOTH 군, pairwise 주 분석 제외(집계만) |
| 반복 방문 | B0: subject당 stay 수 분포 집계; B1: subject 단위 split, 분석은 subject당 첫 적격 stay(사전 고정) |
| 코호트 방식 | 주: 라벨 정의 코호트(쌍의 한쪽 진단 stay) — 결과 기반 선택(spectrum bias) 공개; 보조: 주호소 사전 사전(질환명 제외 단어) 기반 표현 정의 코호트 |
| Cardiac Disease | B0 스키마 대조·가용성 교차 확인만, B1 주 코호트 금지 |

## 9. 누출(leakage) 필드 목록

이전 RG 기록 4개 (필수):
1. hadm_id·ed_hadm_id·hosp_hadm_id 존재 자체 = 입원 여부
2. chiefcomplaint 자유텍스트 내 의심 진단명
3. acuity = 임상의 판단·downstream 결정 반영
4. Cardiac Disease = 결과 기반 코호트 선택

추가 (A0 manifest [N]·설계 §13·이번 확인):
5. ED `diagnosis`, ECG-Ext-ICD `*_diag_*`, hosp `diagnoses_icd` — 참조 전용
6. disposition, outtime, dod
7. ECG-Ext-ICD fold·strat_fold (라벨 층화)
8. 검사 시행 여부 자체: ecg_taken_in_ed, lab 주문 존재, 영상 존재
9. 영상 판독 indication 문구('r/o PE', 'eval for PE')
10. pyxis ED 투약(항응고제·항혈소판·니트로글리세린 등) — 의심 진단 반영
11. Cardiac Disease HPI·physical_exam·X-ray·CT·ECG·reports·HPI.json·RAG_data (퇴원요약 유래)
12. 입원 후 시술 코드(관상동맥 시술 등), heart_procedures
13. labevents flag·comments (해석 텍스트)
14. ECG ecg_time 시계 불일치 → 'T0 이후' 판정 오류
15. MEDICAL_RECORD는 intime 이전 기록만

## 10. B0 집계 출력 스키마

출력 = `b0/out/b0_availability.json` + `.csv` (ID·날짜 없음)

| 컬럼 | 설명 |
|---|---|
| pair | ACS~PE / ACS~PERI |
| cohort_def | label_defined / presentation_defined |
| class_group | pooled / a / b / both (class별 행 포함 여부는 결정 필요 — §16) |
| information_candidate | ECG_any, ECG_machine_report, troponin, D-dimer, CT_PA_report, echo_report, CXR_report, vitals_triage, vitals_series |
| source_grounded | A0 role (R1/R2/R3/context) |
| mimic_source | 데이터셋·파일 |
| timestamp_available | YES/NO |
| window | ED_stay / 0–1h / 0–3h / 0–6h / 0–24h (전부 보고, 선택 없음) |
| n_cohort, n_with_info, pct | 소표본 억제 적용 |
| n_pre_T0, n_post_T0, n_time_uncertain | |
| delay_quantiles_h | p25/p50/p75 (시간 단위, 0.5h 반올림) |
| leakage_risk | LOW/MEDIUM/HIGH (사전 고정표) |

추가 집계: 쌍별 class 크기, BOTH 군 크기, subject당 stay 수 분포(1/2/3–5/6+), 입원 비율(누출 확인용), 결측 조합 패턴(정보 유형 존재 조합별 n).

금지: AUROC, 민감도·특이도, WD 탐지율, 모델, 임계 튜닝, 특징값 분포(검사 결과값), 환자 단위 행.

## 11. B0 manifest 초안 (EXP-SN-NBI-002)

```yaml
experiment_id: EXP-SN-NBI-002
title: NBI-B0 real-data information availability and temporal feasibility (MIMIC, local-only, aggregate-only)
research_question: >-
  A0 NBI 후보(ECG, troponin, D-dimer, CTPA/영상, 활력)가 MIMIC 후향 데이터에서
  T0(ED 도착) 이후 시간 정렬 가능한 형태로 존재하는가? 판별 성능은 묻지 않는다.
hypothesis: 없음(기술 연구). 판정 = 사전등록 가용성 표 산출 + 중단 조건 미발생
dataset: MIMIC-IV-ED 2.2, MIMIC-IV-ECG-Ext-ICD 1.0.1 (+ 확보 시 MIMIC-IV 3.1 hosp, MIMIC-IV-Note 2.2 radiology, MIMIC-IV-ECG machine_measurements)
dataset_version: zip·파일 SHA256 (추출 시 고정)
data_modality: structured EHR, ECG metadata (waveform 없음), radiology text(존재 여부·시각만, 내용 NLP 없음)
unit_of_analysis: ED stay (집계), subject 중복은 별도 집계
label_definition: §8 (ICD 코드표 고정 필요)
split_strategy: 없음(B0); B1은 subject 단위
primary_metric: pair × candidate × window 가용 비율과 T0 이후 비율 (count/%)
success_criterion: 가용성 표 완성 + 출력 guard 통과 + 중단 조건 0 (수치 임계 없음 — B1에서 고정)
failure_criterion: §17 중단 조건
expected_claim: "MIMIC에서 A0 후보 정보의 존재·시점 분포를 집계했다" (판별력·임상 유효성 주장 없음)
potential_confounders: §9, confounding by indication, MNAR, ECG 시계 불일치, 결과 기반 코호트
```

## 12. B0 로컬 스크립트 계획

| 파일 | 역할 | 실행 |
|---|---|---|
| `b0/extract_minimal.sh` | zip에서 필요한 파일만 `~/<restricted>/mimic/`로 해제, SHA 목록 생성, chmod 700 | 사용자 승인 후 |
| `b0/b0_availability.py` | 로컬 join(ID는 메모리 내부만), 집계·소표본 억제·출력 guard, stdout 1줄 | RG RUN + 승인 후 |
| `b0/tests/` | 합성 fixture(가짜 ID·시각)로 guard·억제·window 계산 시험 | 개발 중 |
| `b0/expected_schema.json` | 출력 컬럼·행 키 사전 고정 | gate 전 |

원칙: 실제 데이터 개발 실행 금지(합성 fixture만), pandas 메모리 상한(RAM 90 % 규칙, labevents는 청크 처리), 장시간이면 nohup + ram_guard.

## 13. 최소 압축 해제 목록과 디스크

| 파일 | 크기(압축/해제) | B0 용도 |
|---|---|---|
| ED edstays, triage, vitalsign, diagnosis (.csv.gz 그대로) | 약 57.6 MB | T0·활력·참조 라벨 |
| ECG-Ext-ICD records_w_diag_icd10.csv | 338.9 MB | ECG 시행·시각, 라벨 교차 |
| (확보 후) MIMIC-IV-ECG machine_measurements.csv, record_list.csv | 174.2 + 67.1 MB | ECG 구조화 소견 |
| (확보 후) MIMIC-IV hosp labevents, d_labitems, diagnoses_icd, d_icd_diagnoses, admissions, patients | 확인 필요 (labevents 수 GB 예상, 확인 필요) | troponin·D-dimer, 입원 진단 |
| (확보 후) MIMIC-IV-Note radiology(+detail) | 확인 필요 | 영상 존재·시각 |
| 불필요 | ED medrecon·pyxis, Cardiac Disease 전체, ECG waveform zip, Symile | — |

현재 보유분 B0 디스크: 약 0.4 GB. 전체 B0(확보 후): 약 1 GB + hosp·note(확인 필요). WSL `/` 여유 664 GB(물리 C: 여유 205 GB).

## 14. 현재 데이터만으로 가능한 B0 범위

- T0-a 정의, 쌍별 라벨 코호트 크기·BOTH 군·subject 중복 구조 (ED diagnosis)
- 활력 가용성·시각 (triage, vitalsign)
- ECG 시행 여부·ecg_time 분포(시계 불일치 주의, UNCERTAIN 표기)
- ED 라벨 vs ECG-Ext-ICD 라벨 교차 일치율(집계)

## 15. 추가 다운로드 후 가능한 범위

| 필요 데이터 | 가능해지는 것 |
|---|---|
| MIMIC-IV-ECG machine_measurements (개별 다운로드 174 MB) | ECG 소견(ST·Q·PR 판독문·측정값) 가용성 |
| MIMIC-IV 3.1 hosp | troponin·D-dimer 가용성·storetime 지연, 입원 진단 교차 |
| MIMIC-IV-Note radiology | CTPA·심초음파·CXR 보고서 존재·시각 |

## 16. 결정이 필요한 항목 (gate 제출 전)

1. RG ID: EXP-SN-NBI-002 (추천)
2. class별 가용성 행 포함 여부 — MNAR·confounding by indication 평가에 필요하지만 결과 조건부 집계임. 추천: 포함(검사 결과값 없이 존재 여부만), 사전등록
3. B1 primary pair 결정 규칙 — 추천: 고정 우선순위 ACS–PE > ACS–PERI, B0 중단 조건(정보 유형 전부 T0 이후 가용 0, 시간 정렬 불가)에 걸릴 때만 다음 쌍. 최소 n은 B1 manifest에서 검정력 계산으로 고정
4. ZDR 미확인 상태 유지 → local-only 원칙 고정
5. 소표본 억제 기준(<11)

## 17. B0 중단 조건

- DUA·LLM 원칙 위반 가능성(환자 행·ID·시각·note가 세션 출력에 나타남) → 즉시 중단, 출력 격리, 보고
- 출력 guard 실패 → INVALID, 재실행 전 deviation·재심사
- 참조 라벨 정의 불가(코드표 확정 불가) → 중단
- 쌍 라벨 코호트 0 → 해당 쌍 NOT_EVALUABLE
- T0 이후 정보가 모든 비병력 유형에서 0 → 해당 쌍 NOT_EVALUABLE
- 필수 정보가 누출 필드로만 존재 → 해당 후보 NOT_EVALUABLE
- RAM 90 % 초과(ram_guard) → 중단

## 18. B1 진입 조건

- B0 RG VERIFIED
- 쌍 × 정보 유형 × window 가용성 표 존재, ECG 시각 정렬 처리 방법 확정
- B1 manifest(EXP-SN-NBI-003)에 고정: primary pair(§16-3 규칙), 최소 n(검정력), S0–S3 단계, 반사실 WD, subject split, MNAR·confounding by indication·test-ordering bias 분석, 입력 allowlist, A0 민감도(CF1/CF2/AB6) 반영 — ECG discriminator는 연구 후보이며 의학적 truth 아님
- RG RUN 후에만 실행

---

출처: PhysioNet "Use of MIMIC Data with Large Language Models and Online Services" (2025-09-24, https://physionet.org/news/post/llm-responsible-use/), MIMIC-IV-ECG 1.0 문서 (https://physionet.org/content/mimic-iv-ecg/1.0/), MIMIC-IV-ECG-Ext-ICD 1.0.1 문서 (https://physionet.org/content/mimic-iv-ecg-ext-icd-labels/1.0.1/), MIMIC-IV 3.1 문서 (https://physionet.org/content/mimiciv/3.1/), MIMIC-IV-Note 2.2 문서 (https://physionet.org/content/mimic-iv-note/2.2/), 로컬 zip LICENSE.txt·README.
