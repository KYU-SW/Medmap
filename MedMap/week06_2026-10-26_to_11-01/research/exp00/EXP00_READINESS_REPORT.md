# EXP-00 데이터·실험 준비 감사 보고서 (2026-10-26)

표기: **[사실]** 파일·코드로 확인 · **[문헌]** 논문·데이터 문서 근거 · **[가설]** · **[제안]** 미검증

## 1. 최종 판정: **CONDITIONAL**

- EXP-01·EXP-04: **실행 준비 가능**(DDXPlus·기존 코드 로컬 확인). 단 RG 사전등록·gate 전.
- EXP-02·EXP-03: **조건부** — MIMIC hosp `diagnoses_icd`·discharge note 미보유, 증상 구조화 선행 필요.
- EXP-05: **조건부** — RL 라이브러리 미설치(설치 승인 필요), RAG 코퍼스 재사용성 확인 필요.
- EXP-06: **선행 의존**.
- 이번 단계에서 모델 우수성 주장 없음. 학습·기존 실험 재실행 0.

## 2. 실제 보유 데이터(요약 — 숫자 정본은 `outputs/data_assets_generated.md`)

| 데이터 | 보유 | 읽기 검증 | 정답 라벨 | 접근·라이선스 |
|---|---|---|---|---|
| DDXPlus en/fr | 있음 | train 전체 집계, validate/test 미개봉 | PATHOLOGY + DIFFERENTIAL(합성) | CC-BY **[문헌]** |
| MIMIC-IV 3.1 hosp | patients·admissions·d_labitems·labevents **4개만** | 헤더 + 50행 열 개수 일치 | 없음(`diagnoses_icd` 없음) | PhysioNet credentialed DUA |
| MIMIC-IV-Note 2.2 | radiology·radiology_detail | 동일 | 없음 | 동일 |
| MIMIC-IV-ED 2.2 (zip) | 있음 | zip 내 6개 csv.gz 헤더·열 일치 | ED `diagnosis` ICD | 동일 |
| MIMIC-IV-ECG 1.0 | record_list·machine_measurements(파형 없음) | 동일 | — | 동일 |
| ECG-Ext-ICD 1.0.1 (zip) | 있음 | 동일 | `ed_diag_*`, `all_diag_hosp`(ECG 연결 stay) | 동일 |
| MIMIC-IV-Ext-Cardiac-Disease 1.0.0 (zip) | 있음 | 동일 | `heart_diagnoses_all(_true)` ICD — 정의 **확인 필요** | 동일 |
| HPO 2026-09-01 | 있음 | JSON 파싱 | — | HPO 라이선스 |
| UMLS 2026AA | MRCONSO·MRREL·MRSTY·MRSAB | 파일 목록만(문자열 미출력) | — | UMLS 라이선스, 외부 전송 금지 |
| SNOMED CT INT 20260901 | Snapshot | 행 수만 | — | Affiliate, 외부 전송 금지 |
| HSDN · OptimusKG · DisMech · 질환 프로필 | 있음 | parquet 메타 | — | 각 출처 |
| MIMIC-IV-Ext-DiReCT · Ext-PE · Ext-Note-Extract · EHRNote-ChatQA | **없음** | — | — | 미보유로 표시 |

**[사실]** DDXPlus EVIDENCES 에는 명시적 음성 토큰이 없다 → "음성"은 시뮬레이터 규약(물었고 미기재).
**[사실]** DDXPlus 공식 validate 는 STEP14·15·16A 에서 반복 사용, 공식 test 는 STEP13B 에서 1회 개봉 → 새 실험의 선택·최종 평가에 쓰지 않음.
**[문헌]** DDXPlus 환자는 `release_conditions.json` 지식표로 생성됨 → 이 표를 질환 그래프로 쓰면 순환.

## 3. 재사용할 코드

| 자산 | 위치 | 재사용 |
|---|---|---|
| 질환 후보 모델(MODEL_k3/5/10) | `~/medmap/exp/step16b_next_information_validation/*.pkl`, `medmap/diagnosis.py` | Baseline A 그대로 |
| 정보이득 질문 | `medmap/next_information.py`, `ig_table_step16b_train.npz` | Baseline A + 우도표 재사용 |
| 분할 규칙·시뮬레이터 | `s16b_core.py` (`split_key`, `is_holdout`, `make_view`, `Semantics`) | import 재사용 |
| 답변 상태·eligibility | `medmap/patient_state.py`, `medmap/eligibility.py` | 상태 규약 근거 |
| 의사 화면 WD | `medmap/doctor_view.py`, `api_doctor.py` | EXP-01 PC 의 제품 연결점(연구 단계에서는 미연결) |
| 근거→UMLS/HPO 매핑 | `exp/step8_mapping/` (EXACT 62 · PARTIAL 105 · COMPOSITE 55 · FAIL 1) | 외부 지식 그래프 연결 |
| HSDN 질환·증상 간선 | `exp/step10_hsdn/` (49질환 중 외부 간선 38) | Baseline C 외부 지식 팔 후보 |
| 한국어 NLU·개념 검색 | `~/medmap-worktrees/symptom-ontology/exp/step20~30` | 환자 입력 쪽(이번 범위 밖). STEP30 공식 REGRESSION |
| MIMIC 시간 정렬·가용성 | `~/medmap-worktrees/safety-net-nbi/docs/research/nbi/` (A0·B0a·B0c·B0d·B1·B1S, 모두 VERIFIED) | EXP-02 storetime 규약·Troponin/D-dimer 가용성. **수정·재실행 금지** |
| 그래프 스키마 초안 | `exp/main_ai/common/evidence_graph.py` (이번 신규) | EXP-01 PB·PC 규칙 층 |

## 4. 추천 구조

**E: 공유 그래프 + 규칙 층 + 탐색 뷰** — 상세 `graph_design.md`.
근거: 질환·검사 노드 공유(복제 없음), AND/OR 규칙, 5상태 관측, append-only + as_of, source 단위 중복 방지, 가지치기는 하위 작업 비활성만. 이 원칙들은 가상 데이터 단위 테스트 11개로 **스키마 수준에서만** 확인 **[사실]**. 실제 데이터 성능은 미검증.

## 5. 실행 계획 — `experiment_plan.md`(EXP-01~06 각 12항목), `exp01_predesign.md`

## 6. EXP-01 첫 구현 단계 — `exp01_predesign.md` §7, Codex 프롬프트 `codex_prompt_exp01.md`

## 7. 생성 파일·Git

- worktree `~/medmap-worktrees/main-ai`, 브랜치 `research/main-ai-exp00`(master `977877f` 에서 분기), **미커밋**.
- 위치 변경 이유: 지시안의 `experiments/main_ai/` 대신 기존 프로젝트 관례 `exp/` 를 따라 `exp/main_ai/` 사용.
- master·제품 코드·원본 데이터·다른 worktree 수정 없음.

## 8. 수행한 검증 / 미검증

| 항목 | 상태 |
|---|---|
| DDXPlus train 전체 파싱·집계 | 수행 |
| DDXPlus validate/test | 존재·크기만(의도적 미개봉) |
| MIMIC 각 파일 헤더 + 앞 50행 열 개수 | 수행(값 미출력) |
| MIMIC 파일 전체 무결성(SHA) | **이번 미수행** — 2026-10-05 다운로드 시 SHA 대조 기록(handoff)만 있음 |
| MIMIC 행 수·코호트 크기 | 미수행 |
| HPO 파싱, SNOMED 행 수, parquet 메타 | 수행 |
| UMLS 파일 읽기 | 파일 목록만 |
| 그래프 스키마 단위 테스트 | 11/11 통과, 변이 6/6 검출 |
| EXP-01 모델·지표 구현 | 미구현 |
| 자원 추정(시간·RAM) | 미측정 추정 |
| cardiac-ext 라벨 정의, 추가 데이터 라이선스 | 확인 필요 |

## 9. 해결 방향(문제별)

| 문제 | 방향 |
|---|---|
| MIMIC 입원 진단 라벨 없음 | `hosp/diagnoses_icd`·`d_icd_diagnoses` 추가 다운로드(같은 자격, 무료지만 다운로드 사전 승인 규칙) |
| 원문 기반 진단 추론 라벨 없음 | MIMIC-IV-Ext-DiReCT 신청·다운로드(승인 필요) |
| DDXPlus 에 의사 WD 없음 | 정답/그럴듯한 오답/무작위 WD 세 조건 시뮬레이션, 오답 조건 안전 지표로 채택 판단 |
| DDXPlus 에 임상 필수 조건 없음 | 합성 규칙 시나리오로 가지치기 안전성 별도 평가, 의료적 배제로 해석 금지 |
| 검사 시행 선택 편향(MIMIC) | 시행 여부 특징 금지 또는 선택 모델 병행 보고(B1S 결과 참조) |
| RG 미활성(이 worktree) | EXP-01 착수 전 `.research-guardian` 활성 + rg-plan/gate |
