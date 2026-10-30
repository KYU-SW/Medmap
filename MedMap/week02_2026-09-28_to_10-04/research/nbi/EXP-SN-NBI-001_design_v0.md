# EXP-SN-NBI-001 설계 v0 — Next-Best-Information Safety-Net Feasibility

- 작성: 2026-10-03 00:1x KST, 13회차 세션
- 상태: DRAFT (분석·설계만). 브랜치·엔진·환자 단위 분석·학습·평가 데이터 접근 0
- 근거 범위: ck-v0 read-only 집계, MIMIC zip 파일 목록·CSV 헤더 1줄·README만 확인 (환자 행 0줄 열람)

---

## 1. git / worktree 상태 (2026-10-03 00:02 실측)

| 항목 | 값 |
|---|---|
| master | `fb2d7f0`, 미커밋 39건 = handoff·memory (관례상 미커밋, 건드리지 않음) |
| research/safety-net-core | `bf6dda0`, 미커밋 변경 0 |
| research/safety-net-rag | `a940847` (PAUSED) |
| research/safety-net-min | `1605d67` (BLOCK) |
| `*nbi*` 브랜치 | 없음 |
| `~/medmap-worktrees/safety-net-nbi` | 없음 → 이름 충돌 없음 |
| 디스크 | WSL `/` 664 GB 여유 (물리적으로는 C:), `/mnt/c` 205 GB 여유 |

## 2. EXP-SN-CORE-001 최종 상태 확인

- RG: RUN, lock `276ffd99bc95…`, 상태 OK, 바뀐 필드 0, deviation 24건
- ck-v0 SHA256SUMS 검증 통과, `ck_v0_sha256 = 56df424e…84ff38`
- precount: ACS~PE, ACS~PERI 모두 `NOT_EVALUABLE` (true=ACS 방향 U 가능 0)
- 평가 데이터 접근 0, 엔진 0, split 0 → 사용자 기술과 일치
- 숫자 대조: Stage 1 = 339 fact 중 TEST_RESULT 160 (47.2 %), ck-v0 = 216 중 99 (45.8 %) → 사용자 기술 "약 47 %"는 Stage 1 기준으로 일치

## 3. 새 branch/worktree 계획 (미생성, 승인 대기)

| 항목 | 제안 |
|---|---|
| branch | `research/safety-net-nbi` |
| 분기점 | **master `fb2d7f0`** (추천) |
| worktree | `~/medmap-worktrees/safety-net-nbi` |
| ck-v0 사용 | `docs/research/nbi/inputs/ck-v0/`에 복사본 + `SOURCE.md`(원본 `bf6dda0:docs/research/core/ck-v0/`, SHA256 대조 결과) |
| 커밋 | `git -c user.name=medmap -c user.email=<email> commit`, 이 브랜치에만 |

분기점 비교

| 후보 | 장점 | 단점 | 판정 |
|---|---|---|---|
| master `fb2d7f0` | 제품 기준 깨끗, CORE-001 RG 상태(`.research-guardian/experiments/EXP-SN-CORE-001`)와 분리 | ck-v0 복사 필요 | **추천** |
| `bf6dda0` | ck-v0가 이미 트리에 있음 | 종료된 실험의 manifest·lock·runner가 따라옴 → RG 혼동, "같은 ID 재개"로 오인될 위험 | 비추천 |

## 4. ck-v0 검사·측정 fact 재분류 (216 fact, read-only 집계)

원본 필드 `finding_kind` × `test_type` 집계 → 요청 분류로 재매핑

| NBI 분류 | 원본 조합 | fact 수 |
|---|---|---|
| ECG | TEST_RESULT·ECG 53 + OTHER·ECG 6 | 59 |
| IMAGING | TEST_RESULT·IMAGING 26 + OTHER·IMAGING 7 | 33 |
| BIOMARKER (troponin·D-dimer·CK-MB) | TEST_RESULT·BIOMARKER 20 + OTHER·BIOMARKER 3 | 23 |
| LAB (비바이오마커 일반검사) | 별도 test_type 없음 ("blood work" 1건은 BIOMARKER로 기록) | 0 (구분 불가) |
| PHYSICAL_EXAM | EXAM_SIGN·None 14 + EXAM_SIGN·PHYSICAL_EXAM 1 + OTHER·PHYSICAL_EXAM 1 | 16 |
| VITAL | EXAM_SIGN·VITALS 1 (+ 텍스트상 hypoxia·tachycardia 등은 다른 kind로 기록됨) | 1 (텍스트 재분류 시 증가, 재분류 규칙 필요) |
| QUESTION (병력·위험인자·인구학) | SYMPTOM_HISTORY 43 + RISK_FACTOR 18 + DEMOGRAPHIC 2 | 63 |
| MEDICAL_RECORD | OTHER·RECORDS 1 | 1 |
| OTHER | OTHER·None 20 | 20 |

질환별 relation 분포 (fact 단위)

| 대상 | SUPPORTING | TEST_REQUIRED | IMPORTANT_NEGATIVE | POORLY_EXPLAINED | DIFFERENTIATING | OVERLAPPING | OUT_OF_SCOPE |
|---|---|---|---|---|---|---|---|
| ACS | 57 | 15 | 5 (전부 검사) | 7 (병력·진찰) | — | — | 17 |
| PE | 60 | 12 | 2 (PERC·심초음파) | 1 (영상) | — | — | 1 |
| PERI | 14 | 8 | 0 | 1 (ECG) | — | — | 1 |
| ACS~PE | — | 2 (CT) | — | — | **0** | 2 | — |
| ACS~PERI | — | 1 (ECG) | — | — | 5 | 5 | — |

주의

- `finding_kind`와 `test_type`가 일관되지 않은 행 존재 (예: hypoxia·tachycardia가 VITALS가 아님) → VITAL 재분류는 텍스트 해석이 들어가므로 규칙 고정 필요
- 위 재분류는 **새 fact 생성 아님**, 기존 필드 재매핑만

## 5. ACS–PE에서 history-only가 부족한 정확한 이유

1. **쌍 수준 DIFFERENTIATING fact 0건** — corpus 18문서 안에 "ACS와 PE를 가르는 소견" 문장 자체가 없음
2. **PE 쪽 POORLY_EXPLAINED 병력 0건** — "PE로 설명 안 되는 소견" 근거 없음 → true=ACS·WD=PE 방향 U_pos 0
3. **PE IMPORTANT_NEGATIVE 2건 모두 병력 아님** — PERC 전부 음성(복합 기준, OTHER) · 심초음파 RV 부담 부재(IMAGING) → U_neg 0
4. **OVERLAPPING 2건** = angina-like chest pain, elevated D-dimer → 병력·검사 모두 겹침 근거
5. **관측 공간** — DDXPlus 223문항에 ECG·troponin·D-dimer·영상·활력징후 문항 0 (§50-6)
6. 쌍 수준 근거의 형태는 TEST_REQUIRED뿐: "CT angiography for differential diagnosis of ACS vs PE"(A1b1-0149), "multislice CT for PE after ACS ruled out"(A1b1-0160), 둘 다 SRC-0001 (2025 Brazilian chest pain guideline)

결론: history-only 부족 = 지식 부재 + 관측 공간 부재의 이중 원인. 검사 관측 공간을 추가해도 **쌍 수준 판별 fact는 여전히 0** → 질환별 SUPPORTING fact 조합으로 판별 신호를 만들려면 "한쪽만 지지 = 판별"이라는 추론 규칙이 필요(=출처 밖 가정). 사전등록에서 명시·제한 필요

## 6. ACS–PE source-grounded NBI 후보 (ck-v0 fact만)

| 후보 | information_type | 근거 fact (relation) | 판별 근거 성격 | 주의 |
|---|---|---|---|---|
| CT angiography / CTPA | IMAGING | A1b1-0149 (ACS~PE TEST_REQUIRED), A1b1-0150·A1b2-0111 (PE TR), A1b2-0097 (PE SUP: 충만결손) | **쌍 수준 근거 유일** | 결과는 PE 확진형, ACS 쪽 결과 근거 아님 |
| D-dimer | BIOMARKER | A1b1-0068·0111 (PE TR, 저·중간 검사전 확률), A1b2-0118 (PE SUP) | 조건부 rule-out 정보 | **A1b2-0090: elevated D-dimer = ACS~PE OVERLAPPING** → 상승 자체는 판별 근거 아님 |
| Troponin (hs-cTn) | BIOMARKER | ACS TR 6건, SUP 6건, IN 4건 | ACS 지지·배제 | **PE에서의 troponin fact 0** → "troponin 상승 = ACS 쪽" 해석은 출처 밖 가정 |
| 12-lead ECG | ECG | ACS SUP 다수(ST 상승/하강, T파), PE SUP(동성빈맥, S1Q3T3, RBBB, V1–V4 T파역위, qR V1, 심방성 빈맥) | 질환별 지지 | **PE SUP에 "inferolateral ST elevation or depression"(A1b2-0116), "T-wave inversion V1–V4"(A1b2-0117)** → ACS ECG 소견과 겹침, ECG 판별력은 corpus상 불명확 |
| 활력징후 (SpO2, HR, BP) | VITAL_SIGN | PE SUP: hypoxia(A1b2-0074), hypoxaemia(A1b2-0121), tachycardia(A1b2-0084), 혈역학 불안정(A1b1-0075) | PE 지지 | ACS 쪽 활력 fact 없음 → 판별은 비대칭 가정 필요 |
| 심초음파 | IMAGING | ACS: RWMA(A1b1-0138), PE: RV 부담·McConnell·60/60 | 질환별 지지 | MIMIC-IV-ED에서 시점 관측 불가 (아래 §8) |
| 흉부 X선 | IMAGING | PE SUP(A1b1-0089, Westermark, Hampton) | PE 지지 | 민감도 정보 없음 |
| V/Q scan | IMAGING | PE TR·SUP | PE 지지 | MIMIC 관측 여부 확인 필요 |

## 7. ACS–pericarditis source-grounded NBI 후보

| 후보 | information_type | 근거 fact | 판별 근거 성격 | 주의 |
|---|---|---|---|---|
| ECG ST 모양 | ECG | A1b3-0044 convex ST↑ (DIFF favors ACS), A1b3-0045 concave ST↑ (DIFF favors PERI) | **쌍 수준 DIFFERENTIATING** | 모두 SRC-0010 단일 문헌 |
| ECG PR 하강 | ECG | A1b3-0047 (DIFF favors PERI), A1b3-0027 (PERI SUP) | 쌍 수준 | **충돌: A1b3-0033 "PR-segment displacement in any lead" = ACS SUP** |
| ECG Q파 | ECG | A1b3-0046 (DIFF favors ACS) | 쌍 수준 | **충돌: A1b3-0030 Q waves = ACS~PERI OVERLAPPING** (같은 문헌) |
| 마찰음 | PHYSICAL_EXAM | A1b2-0016 (DIFF favors PERI), A1b2-0014 (ACS POORLY_EXPLAINED), A1b3-0024 (PERI SUP) | 쌍 수준 | MIMIC 구조화 변수 없음 (퇴원요약 진찰 텍스트만) |
| 심초음파·흉부X선 | IMAGING | A1b1-0145, A1b3-0017 (PERI TR) | 검사 필요성만 | 결과 판별 fact 없음 |
| CK-MB | BIOMARKER | A1b3-0031 OVERLAPPING | 판별 근거 아님 | 후보 제외 대상 |

판정: **쌍 수준 판별 fact가 실제로 있는 쌍 = ACS–PERI (ECG)**. ACS–PE는 TEST_REQUIRED(CT)만 쌍 수준

## 8. NBI 후보 ↔ MIMIC 연결 (스키마·README 수준, 환자 행 미열람)

| 데이터셋 | 상태 | 실제 확인한 파일·컬럼 | NBI 역할 | 시간 정보 |
|---|---|---|---|---|
| MIMIC-IV-ED 2.2 | 완료 (zip) | `edstays`(intime, outtime, hadm_id, disposition), `triage`(temperature, heartrate, resprate, o2sat, sbp, dbp, pain, acuity, chiefcomplaint), `vitalsign`(charttime, …, rhythm), `diagnosis`(ICD, 퇴원 후 코딩), `medrecon`, `pyxis` | **T0** = intime + triage 활력 + 주호소(자유텍스트) · VITAL 후보 | triage 행에 시각 컬럼 없음 → intime 근사 (확인 필요) |
| MIMIC-IV-ECG-Ext-ICD 1.0.1 | 완료 | `records_w_diag_icd10.csv`: file_name, study_id, subject_id, **ecg_time**, ed_stay_id, ed_hadm_id, hosp_hadm_id, ed_diag_ed, ed_diag_hosp, hosp_diag_hosp, all_diag_*, age, gender, dod, ecg_no_within_stay, ecg_taken_in_ed, **fold, strat_fold** | ECG 시각·ED stay 연결, 진단 라벨(**참조용만**) | ecg_time 있음 |
| MIMIC-IV-ECG 1.0 | 진행 중 (512.9 MB / 33.80 GB) | 미확인 | ECG 기계 측정·기계 판독문 (구조화 ECG 후보) | 확인 필요 |
| MIMIC-IV-Ext Cardiac Disease 1.0.0 | 완료 | `heart_diagnoses.csv`(퇴원요약 유래 HPI, physical_exam, chief_complaint, X-ray, CT, Ultrasound, CATH, ECG, MRI, **reports=ECG 기계 판독**), `heart_labevents_*`(charttime, storetime, label, examination_group), `heart_diagnoses_all(_true)`, `heart_procedures` | 입원 코호트 lab·영상 텍스트 | lab은 charttime/storetime 있음 · **영상·HPI·진찰은 퇴원요약 발췌 → 시점 없음** |
| MIMIC-IV-Note 2.2 | 예정 | — | radiology report(CTPA·CXR·심초음파 결과 텍스트) | 확인 필요 |
| MIMIC-IV 3.1 | 예정 | — | hosp `labevents`(troponin·D-dimer 전체), `diagnoses_icd`, `admissions` | 확인 필요 |
| Symile-MIMIC 1.0.0 | 예정 | — | ECG + CXR + lab 묶음 | 이번 pilot 불필요 판단 |

후보별 연결

| NBI 후보 | 연결 가능 위치 | 현재 다운로드만으로 |
|---|---|---|
| 활력 (SpO2·HR·BP) | ED `triage`, `vitalsign` | **가능** |
| ECG 시행 여부·시각 | ECG-Ext-ICD `ecg_time`, `ecg_taken_in_ed` | **가능** |
| ECG 내용 (ST·Q·PR·S1Q3T3·RBBB) | MIMIC-IV-ECG 기계 측정/판독, Cardiac Disease `reports` | 부분 (Cardiac Disease는 입원 코호트·시점 불명) |
| Troponin·D-dimer | MIMIC-IV hosp `labevents`, Cardiac Disease `heart_labevents_*` | 부분 (Cardiac Disease 코호트 정의 README에 없음 → PE 포함 여부 확인 필요) |
| CTPA·CXR·심초음파 결과 | MIMIC-IV-Note radiology | **불가** (미다운로드) |
| 마찰음 등 진찰 | Cardiac Disease `physical_exam`(퇴원요약) | 시점 누출 위험 → T0 입력 불가 |
| 최종 진단 (참조 표준) | ED `diagnosis`, ECG-Ext-ICD 진단 컬럼, hosp `diagnoses_icd` | 가능 (참조용만) |

## 9. 현재 다운로드로 가능한 것 / 추가 필요

| 구분 | 내용 |
|---|---|
| 지금 가능 (환자 데이터 불필요) | NBI-A 전체 (ck-v0 기반 후보표·스키마·provenance 검사) |
| 지금 가능 (RG 후, 집계만) | ED 코호트 T0 정의, 활력 관측률, ECG 시행 시각 정렬, 쌍별 코호트 크기 집계 |
| 추가 필요 | ECG 내용 → MIMIC-IV-ECG (기계 측정 파일만 개별 다운로드 가능 여부 확인 필요), troponin·D-dimer 전체 → MIMIC-IV 3.1 hosp, 영상 결과 → MIMIC-IV-Note |
| 불필요 (이번 pilot) | Symile-MIMIC, raw waveform, CXR 이미지 |

## 10. NBI-A / NBI-B 분리 설계

### NBI-A: Selection Feasibility (환자 데이터 0)

- 입력: (WD, alternative, 관측된 정보 집합) 조합 — 실제 환자 아님, 정보 상태 격자
- 처리: ck-v0 fact만으로 결정론적 규칙 적용 (LLM 판단 0)
  - HISTORY_INSUFFICIENT 판정 규칙: 현재 관측 정보 유형 안에서 쌍·방향별 U 가능 evidence = 0 (CORE-001 precount 식 재사용)
  - 후보 생성: 해당 쌍·방향에서 fact가 존재하는 information_type별 후보, 이미 관측된 유형 제외
- 출력: `NextInformationCandidate` 목록 + provenance (fact_id·quote·source_id·unit_id)
- 검증 대상: (1) provenance 100 % 기계 대조 (2) 독립 검증자 판정 (B 방식, 격리 CLI — **과금·사용량 한도 사전 승인 필요**) (3) 각 후보의 MIMIC 관측 가능성 매핑 (4) 정보 상태별 결과가 고정 목록과 다른지
- 핵심 한계 사전 공개: ck-v0 고정이면 NBI-K 출력은 쌍·관측상태의 함수 → 사실상 사전 정의 목록(B3)과 같아질 수 있음. NBI-A의 의미 = "목록을 출처로 정당화할 수 있는가" + "이미 있는 정보를 다시 추천하지 않는가"

### NBI-B: Information Gain in Real Data (별도 RG gate 이후)

- 코호트: MIMIC-IV-ED stay 중 참조 진단이 쌍의 한쪽인 stay (참조 = 퇴원 ICD, 정의는 사전등록)
- WD: MIMIC에 T0 시점 의사 WD 기록 없음 → CORE-001과 같은 **반사실 WD** (true=a 사례에 WD=w 부여) 방식 제안 (결정 필요)
- 정보 단계: T0 (triage) → T0+ECG → T0+ECG+biomarker → (+영상, 데이터 확보 시)
- 점수: ck-v0 매핑 규칙 기반 점수 (학습 모델 아님). 학습 로지스틱은 참조 상한으로만 별도 보고 여부를 사전 결정
- 주 비교: 같은 사례에서 단계별 쌍 판별력 변화

## 11. NextInformationCandidate schema (v0)

| 필드 | 타입 | 설명 |
|---|---|---|
| candidate_id | str | `NIC-<pair>-<n>` |
| wd / alternative | enum | 질환 코드 |
| direction | str | `true=a|WD=w` (CORE-001과 동일 표기) |
| information_type | enum | QUESTION, PHYSICAL_EXAM, VITAL_SIGN, ECG, LAB, BIOMARKER, IMAGING, MEDICAL_RECORD, OTHER |
| subtype | str | 예: `ECG_ST_MORPHOLOGY`, `BIOMARKER_D_DIMER`, `IMAGING_CTPA` |
| target_variable | str | 관측 대상 (예: "concave ST elevation") — fact 문구 그대로 |
| candidate_role | enum | SOURCE_SUPPORTED_DISCRIMINATOR / NEXT_INFORMATION_CANDIDATE / ADDITIONAL_INFORMATION_NEEDED |
| rationale_relation | enum | DIFFERENTIATING, TEST_REQUIRED, SUPPORTING, IMPORTANT_NEGATIVE, POORLY_EXPLAINED |
| fact_ids | list | ck-v0 fact_id (1개 이상 필수) |
| source_id / source_location | str | SRC-xxxx / unit_id |
| quote_sha256 | str | 인용문 해시 (ck-v0 원문과 기계 대조) |
| provenance_status | enum | CKV0_VERIFIED / CORPUS_ONLY_UNVERIFIED / REJECTED |
| conflicts | list | 같은 대상에 반대 방향 fact (예: Q파 DIFF vs OVERLAPPING) |
| medmap_observable | bool | 현재 MedMap 입력으로 관측 가능 여부 |
| mimic_available | enum | YES / PARTIAL / NO / UNKNOWN |
| mimic_dataset / mimic_table_or_modality | str | 예: `mimic-iv-ed/triage.o2sat` |
| requires_new_test | bool | |
| already_available_possible | bool | 이미 시행됐을 수 있는 정보 (재추천 방지용) |
| research_only | bool | 항상 true (이번 트랙) |
| review_status | enum | DRAFT / MACHINE_PASS / VERIFIER_ACCEPT / VERIFIER_REJECT |

금지 어휘: REQUIRED_TEST, "반드시", "권고"

## 12. SafetyNetReview 확장안

```
SafetyNetReview
  status: CONSISTENT | HISTORY_INSUFFICIENT | REVIEW_SUGGESTED | OUT_OF_SCOPE | ABSTAIN
  information_state: [관측된 information_type 목록 + 시점 Tn]
  supporting_findings[]
  unexplained_findings[]
  possible_conflicts[]
  overlapping_alternatives[]
  next_information_candidates[]: NextInformationCandidate (상위 k개, k 사전등록)
  re_review_trigger: 새 정보 도착 시 재계산 여부
  provenance_summary: fact_id 목록
```

- HISTORY_INSUFFICIENT 조건: 쌍·방향 U 가능 = 0 ∧ 비병력 정보 유형에 fact ≥ 1
- ABSTAIN 조건: 비병력 정보 유형에도 fact 0 (= 출처로 다음 정보도 못 고름)
- 제품 반영 0 (Doctor UI NOT_AVAILABLE 유지)

## 13. Time-zero / leakage 방지 계획

| 시점 | 정의 후보 | 출처 |
|---|---|---|
| T0 | ED `intime` + triage 활력·주호소·나이·성별 | MIMIC-IV-ED |
| T1 | 첫 ECG `ecg_time` (≥ intime) | ECG-Ext-ICD / MIMIC-IV-ECG |
| T2 | 첫 troponin·D-dimer **결과 시각 = storetime** (charttime 아님) | MIMIC-IV hosp labevents |
| T3 | 영상 판독 시각 | MIMIC-IV-Note radiology |
| 참조 | 퇴원 ICD | ED diagnosis / hosp diagnoses_icd — 입력 금지 |

누출 차단 규칙

- 퇴원요약 유래 필드 전부 입력 금지 (Cardiac Disease `HPI`, `physical_exam`, `X-ray`, `CT`, `ECG` 섹션, `HPI.json`, `RAG_data*`) — 사후 작성, 진단 언급 가능
- ED `diagnosis`, ECG-Ext-ICD `*_diag_*`, `dod`, `disposition`, `outtime` 입력 금지
- 검사 **시행 여부** 자체가 의사 의심을 반영 (confounding by indication) → 결과값과 시행 여부를 분리 보고, 시행 여부를 점수 입력으로 쓰지 않음
- 정보 단계별 시간 창 (예: intime 후 X시간) 사전 고정, 창 밖 정보 제외
- subject 단위 split, 반복 방문은 첫 stay만 또는 subject 묶음 (사전 고정)
- ECG-Ext-ICD 내장 `fold`는 그 데이터셋 목적 기준 → 사용 여부 사전 결정
- **PhysioNet 자격 데이터 처리 원칙**: 환자 단위 텍스트·행을 LLM(Claude 세션·격리 CLI 포함)에 넣지 않음. 로컬 스크립트가 집계만 출력. PhysioNet의 LLM 사용 정책 문구는 확인 필요 — 확인 전 환자 행 열람 금지 유지

## 14. Baseline 후보 (미확정)

| ID | 정의 | MIMIC 적용성 |
|---|---|---|
| B0 | 항상 다음 질문 | MIMIC에 DDXPlus 문항 응답 없음 → 적용 불가, NBI-A 정보 상태 격자에서만 |
| B1 | 기존 IG next-question (IG3) | 동일 — DDXPlus 관측 공간 전용 → NBI-B 직접 비교 불가 (사전 공개 필요) |
| B2 | 항상 가장 흔한 검사 유형 | 가능 (빈도는 코호트 집계 후 고정 → 집계 순서 주의) |
| B3 | 쌍별 사전 정의 목록 (출처 무관 고정 목록) | 가능 — NBI-K와 차이가 작을 수 있음 (§10 한계) |
| B4 | T0 정보만 (추가 정보 없음) | NBI-B의 정보 이득 기준선 |
| NBI-K | ck-v0 기반 정보 상태 조건부 후보 | |

## 15. 주 평가 지표 후보

| 단계 | 지표 | 비고 |
|---|---|---|
| NBI-A | provenance 기계 대조 통과율 | 100 % 미만이면 후보 제외 |
| NBI-A | 독립 검증자 ACCEPT율, kappa | 격리 CLI 필요 → 과금 승인 |
| NBI-A | 후보 수 / 쌍·방향 (D: 과잉 추천) | |
| NBI-A | 이미 관측된 유형 재추천률 (E) | 0 이어야 함 |
| NBI-A | 병력만으로 U 가능 > 0인 상태에서 검사 후보 출력률 (F) | |
| NBI-B | 단계별 쌍 판별 AUROC 변화 (ΔAUROC, subject 단위 bootstrap CI) | 주 지표 후보 |
| NBI-B | 후보 정보의 실제 가용률 (B: 시간 창 안 관측 비율) | |
| NBI-B | 같은 위양성률에서 반사실 WD 재검토 신호 추가 탐지 | CORE-001 지표 계승 후보 |

임계값 없음 — 사전등록에서 표본 크기 확인 후 고정 (PROVISIONAL_METHOD_THRESHOLD)

## 16. 예상 confounder

- confounding by indication: 검사 시행 = 의사 의심 (D-dimer 시행 자체가 PE 의심 신호)
- 결측 비무작위 (MNAR): 검사 미시행 환자의 결과 부재
- 참조 진단 잡음: 청구용 ICD, ED 진단과 입원 진단 불일치, 비주진단 코드
- STEMI 경로 선택 편향 (바로 시술 → lab·영상 시점 짧음)
- 증상 발생 시각 부재 → troponin 시간 의존 fact(>3 h) 적용 불가
- 비특이 troponin 상승 (PE·신기능 저하 등) — ck-v0에 PE troponin fact 없음
- 반복 방문 환자
- 단일 기관·시대 (기계 ECG 판독 알고리즘 버전)
- 입원 환자만 lab이 있는 데이터 (Cardiac Disease) → 선택 편향
- 같은 회사 LLM이 지식 추출·검증 (CORE-001 한계 계승)

## 17. RG preregistration 고정 필수 항목

1. 쌍 (primary/secondary)과 방향 정의
2. 사용 지식 = ck-v0 SHA `56df424e…`만, 새 fact 금지, 재분류 규칙 (VITAL 등 텍스트 재매핑 포함)
3. "한쪽만 지지 = 판별" 추론 허용 여부 (ACS–PE의 핵심 쟁점)
4. HISTORY_INSUFFICIENT·ABSTAIN 판정식
5. 후보 순위·k
6. T0·T1·T2·T3 정의와 시간 창, storetime 사용
7. 코호트 포함·제외, 참조 진단 ICD 코드 목록과 우선순위 (seq_num)
8. 반사실 WD 방식 여부
9. 입력 금지 필드 목록 (§13)
10. split 단위 (subject), 반복 방문 처리, 내장 fold 사용 여부
11. 점수 함수 (ck-v0 매핑 규칙), 학습 모델 사용 여부
12. 주 지표·보조 지표·통계 검정·bootstrap 단위·다중비교
13. NOT_EVALUABLE 사전 조건 (예: 쌍별 최소 n, 모달리티 관측률 하한) — 숫자는 F0 집계 후
14. 실행 단계별 사용자 승인 지점
15. 자격 데이터 처리 원칙 (LLM 비전송, 집계만 출력)

## 18. 가장 작은 실행 가능 pilot

| 단계 | 범위 | 환자 데이터 | 추천 |
|---|---|---|---|
| **NBI-A0** | ACS–PE + ACS–PERI, ck-v0만, 결정론적 후보표 + provenance 기계 대조 | 0 | **1순위** |
| NBI-F0 | MIMIC-IV-ED + ECG-Ext-ICD로 쌍별 stay 수·ECG/활력 관측률·시간 정렬 가능률 **집계만** (결과×특징 교차표 0) | 집계만, RG 후 | 2순위 |
| NBI-B1 | 1 pair + 2 modality: **VITAL(triage) + ECG** | RG RUN 후 | F0 후 결정 |

pair 선택 근거 (사전 판단, 데이터 미열람)

- 출처 강도: ACS–PERI (ECG DIFFERENTIATING 5건) > ACS–PE (쌍 수준 = CT TEST_REQUIRED만)
- 사용자 지정 primary: ACS–PE
- ACS–PE + VITAL + ECG는 "한쪽만 지지" 추론 의존, ACS–PERI + ECG는 쌍 수준 fact 직접 사용
- 결정은 사용자 몫 (NBI-A0는 두 쌍 모두 포함하므로 지금 결정 불필요)

## 19. 성공 시 제품 통합 단계 (별도 승인)

1. `SafetyNetReview.next_information_candidates` 백엔드 필드 (표시 없음, 로그만)
2. Doctor UI 연구용 플래그 뒤 "추가 정보 후보" 표시 (NOT_AVAILABLE 기본 유지)
3. IG(질문)와 NBI(검사)를 같은 "다음 정보" 목록으로 통합 — IG max-3 계약 불변
4. 새 정보 입력 → Safety-Net 재계산 흐름
5. 임상 전문가 검토 전 문구 제한 (NEXT_INFORMATION_CANDIDATE)

## 20. 실패 / NOT_EVALUABLE 시 선택지

| 상황 | 선택지 |
|---|---|
| NBI-A에서 쌍 수준 근거 부족 (ACS–PE) | ACS–PERI 단독 진행 / ACS–PE는 "TEST_REQUIRED 기반 정보 필요 알림"만 (판별 주장 없음) |
| provenance 검증 실패 다수 | ck-v0 범위 한계로 기록, 새 fact 작성 protocol은 별도 실험 ID |
| F0에서 쌍별 표본 부족 | 쌍 변경 (사전 집계 기준으로만), 다른 데이터 검토 |
| ECG 내용 데이터 확보 불가 | VITAL 단독 pilot 또는 Cardiac Disease `reports` 사용 (입원 코호트 한계 공개) |
| NBI-B에서 정보 이득 없음 | 음성 결과 보존, 제품 통합 없음, Safety-Net은 history 범위 ABSTAIN 표시로 축소 |

---

## 확인 필요 목록

- MIMIC-IV-ED triage 행의 실제 기록 시각 (intime 근사 타당성)
- Cardiac Disease 코호트 포함 기준 (README에 없음) — PE·pericarditis 포함 여부
- MIMIC-IV-ECG 안 기계 측정 파일만 개별 다운로드 가능 여부·크기
- PhysioNet의 자격 데이터 LLM 사용 정책 문구
- 압축 해제 위치 (C: 79 % 사용, WSL `/`도 물리적으로 C:)
- MIMIC lab 중 ED 체류 중 채취분의 hadm_id 연결 방식
