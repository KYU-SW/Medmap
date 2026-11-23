# EXP-03-TIME 프로토콜 — 실제 MIMIC 시간정보 이용 가능성 정책(계획 단계)

- 작성 2026-11-03, 합성 테스트 실행 전 고정. 상위 `../PROTOCOL.md`(EXP-03 합성 단계)는 수정하지 않음 — 이 문서가 시간 정책을 **추가**. 변경은 끝 '변경 기록'에 날짜·이유와 함께 덧붙임.
- 상태: 계획. rg-plan 등록·rg-gate 판정·외부 사전등록 **없음**. 실제 환자 단위 counted run 없음.
- 진단 가설은 SIMULATED_WD 만. 최종·ED 진단 코드를 당시 의사 판단으로 쓰지 않음.

## 1. 출처별 시간 필드(공식 문서 2026-11-03 확인 + EXP-02 로컬 스키마)
| 원천(실제 사용 파일) | 필드 | 시각 의미(공식 문구 요지) | 등급 | 알 수 없는 것 | 주 분석(STRICT) | 민감도 분석 |
|---|---|---|---|---|---|---|
| MIMIC-IV-ED `triage.csv.gz` | (시각 열 없음) | "There is no time associated with triage observations"; 가장 가까운 근사 = `edstays.intime` | C_UNKNOWN | 실제 측정·완료·의사 확인 시각 | 사용 안 함(UNKNOWN_AVAILABILITY) | S1 TRIAGE_AT_INTIME_APPROX: intime 부터 이용 가능 가정(APPROX 표시) |
| MIMIC-IV-ED `edstays.csv.gz` | intime / outtime | ED 도착·퇴실 | A_DOCUMENTED(체류 경계) | — | 체류 창·체크포인트 경계 | 동일 |
| MIMIC-IV-ED `vitalsign.csv.gz` | charttime | "time at which the vital signs were charted" | C_LIMITED(기록 시각, 소급 기록 여부 불명) | 측정 시각·소급 기록 | 사용 안 함(EXP-02 도 미사용) | 이번 단계 비교 없음 |
| MIMIC-IV hosp `labevents.csv.gz` | charttime / storetime | charttime ≈ 검체 채취, "usually significantly earlier"; storetime = "made available in the laboratory system … when the information would have been available to care providers" | storetime = A_DOCUMENTED_AVAILABILITY | 의료진이 실제 본 시각 | storetime 사용, charttime 은 관찰 시각만 | 동일 |
| MIMIC-IV-Note `radiology.csv.gz` | charttime / storetime | charttime = 차트 시각, "not necessarily when the note was fully written"; storetime = DB 저장, "usually when the note was completed and signed" | storetime = B_CONSERVATIVE_PROXY(서명·저장 대리) | 예비 구두 보고 시각·실제 열람 시각·'usually' 예외 | storetime 을 보수적 대리 이용 시각으로 사용(PROXY 표시) | S2 STRICT_A_ONLY: 대리 시각 제외(영상 판독 미사용) |
| MIMIC-IV-Note `radiology_detail.csv.gz` | exam_name 등 | 시각 없음 | — | — | 검사 분류만 | 동일 |
| MIMIC-IV-ECG `machine_measurements.csv` | ecg_time, report_0–17 | 장비 내부 시계, "not synchronized with any external time source", "could be significantly out of sync"; report = 기계 생성 문구 | C_UNKNOWN(장비 시각) | 병원 시각과의 차이·판독 가용 시각 | 사용 안 함 | NOT_IDENTIFIABLE(보정 근거 없음 — 비교 만들지 않음) |
| MIMIC-IV-ECG 의사 판독문 | — | v1.0 미공개("will be made available … later"), 연결 정보만 | 해당 없음 | 전부 | 사용 안 함(자료 없음) | 해당 없음 |
| ECG-Ext-ICD `records_w_diag_icd10.csv` | ed_stay_id, ecg_time | ECG ↔ ED 체류 연결(파생) | 연결 키만 | ecg_time 동일 문제 | 체류 연결 참고만 | 동일 |
| MIMIC-IV-ED `vitalsign.rhythm` | rhythm(charttime) | ED 간호 리듬 기록 — ECG 모듈과 별개 | C_LIMITED | 측정·판독 주체 | 사용 안 함, ECG 와 합치지 않음 | 없음 |

## 2. 주 분석 정책 STRICT_AVAILABLE_TIME
1. 시각 필드를 observed_at · charted_at · signed_or_stored_at · available_at 로 분리 보존. available_at 은 등급 A(문서상 이용 가능 시각) 또는 B(보수적 대리)에서만 채움, 그 외 None.
2. 사용 = time_grade ∈ {A_DOCUMENTED_AVAILABILITY, B_CONSERVATIVE_PROXY} 이고 available_at ≤ 시점 T. B 사용 증거는 결과·알림에 `PROXY` 표시.
3. 시간 없음 → UNKNOWN_AVAILABILITY · signed_or_stored < observed(역전) → TIME_CONFLICT · 둘 다 사용 안 함. ED 도착·CT 시행 시각으로 대체 금지.
4. triage: 주 분석 미사용(T0 자동 투입 없음). 'triage 후 스냅샷'도 완료 시각 확인으로 주장하지 않음.
5. ECG 장비 시각만 있는 파형·기계 판독: 미사용. 파형 획득·기계 해석·의사 판독을 별개 기록 유형으로 구분(합치지 않음).
6. 영상: storetime = B 대리. 결측·역전 → 제외, ED 퇴실 후 저장 → 해당 ED 체크포인트에서는 아직 미이용(POST_ED 표시), 이후 시점으로만.
7. 증거 상태 혼동 금지: PENDING(의뢰·결과 미이용) · UNKNOWN(판정 불가) · NEGATIVE(명시 음성) · 급성/만성 · CONFLICT · INSUFFICIENT. 급성 PE 명시 음성은 PE 가설에만 관계(R2) — 다른 질환 가설에는 NOT_DEFINED.
8. 시간 확정성 등급: A_DOCUMENTED_AVAILABILITY / B_CONSERVATIVE_PROXY / C_UNKNOWN_OR_CONFLICT. 존재하지 않는 시각 생성 금지.
9. 주 분석과 민감도 분석 결과를 섞어 하나의 지표로 보고하지 않음. 어떤 지표도 임상 오진 탐지 성능이 아님.

### 정책 재정렬(지시 3-B 대응)
- 지시 초안의 RADIOLOGY_SIGNED_PROXY(대리 시각 사용)는 STRICT 가 이미 영상 storetime 을 B 대리로 쓰므로 **STRICT 에 통합**하고, 반대 방향 민감도 **S2 STRICT_A_ONLY**(대리 제외)를 둔다. 이유: 판독 서명 전 정보가 시스템에 있다고 볼 근거가 없어 storetime 은 이용 시각을 앞당기지 않는 쪽(누출 방지 방향)의 대리값. 단 'usually' 예외·예비 보고 가능성 때문에 A 와 구분.

## 3. 민감도 분석(사전 명시)
- S1 TRIAGE_AT_INTIME_APPROX: STRICT + triage 를 edstays.intime 부터 이용 가능 가정. 모든 결과에 APPROX 표시.
- S2 STRICT_A_ONLY: STRICT − B 대리(영상 판독 미사용).
- ECG: 모든 정책에서 NOT_IDENTIFIABLE — 임의 시각 추정 비교를 만들지 않음.
- 비교 지표: 정책별 사용 가능 증거 건수·비율, 시간 불명 제외율, ED 퇴실 전 이용 가능 비율, (합성) 상태·알림 변화 건수. 임상 참·거짓 경고율 없음.

## 4. 체류 귀속·기록 처리
- ED 표(triage·vitalsign)는 stay_id 로, ECG 는 ed_stay_id 로 귀속. 검사·영상은 subject_id + [intime, outtime] 창. 한 기록이 두 체류 창에 동시에 들면 AMBIGUOUS_STAY(제외), 어느 창에도 없으면 미귀속. hadm_id 만으로 판독·체류를 합치지 않음.
- 퇴실 후 이용 가능: ED 체크포인트(T ≤ outtime)에서는 미사용, POST_ED 집계.
- 정정: 명시적 연결(supersedes)이 있을 때만 이전 기록 무효. MIMIC radiology addendum(note_type AR)은 원 보고와의 연결 방법이 공식 문서에 없음 → 별도 증거(자동 대체 없음), 연결 근거 확인 전 정정으로 처리하지 않음.
- 중복 event_id 거부, 출처 없는 기록 거부.
- 누출 정의: 시점 T 의 판단에 available_at > T 인 기록 내용이나 등급 C 기록이(주 분석에서) 반영되는 경우.

## 5. 분석 단위·분모(후속 실제 집계 계획 — 이번 미실행)
- 문서(판독)·검사 결과(행)·ECG 기록·ED 체류·환자. 각 지표에 단위 명시.
- 같은 환자의 여러 체류: 체류 단위 집계 + 환자 수 병기, 부트스트랩 시 환자 단위 군집.
- 수집 항목: 자료 유형별 분모·등급별 건수 · 시각 누락·역전·충돌·중복 · AMBIGUOUS_STAY · POST_ED · STRICT vs S1 vs S2 포함률 차이 · (SIMULATED_WD 주입 시) 정책별 상태·알림 변경 건수.
- 안전 조건(합성·실제 공통): 주 분석 누출 0, 출처 누락 0, 등급 C 증거 주 분석 사용 0.

## 6. 독립성·규칙 변경
- 시간 정책은 EXP-02 공개 집계(시간 결측·역전 등)를 이미 본 뒤 작성 — 실제 자료 집계는 '정책 적용 결과 기술'이지 독립 검증 아님.
- 규칙 변경 시 새 버전(time_v2…)·새 승인, 이전 결과 보존.

## 7. 합성 테스트(이 폴더 tests/)
- `test_time_policy.py`: 정상 사례 TP01–TP17(정책·질의 시점·기대·이유를 사례 표에 고정).
- `test_time_faults.py` + `fault_time.py`: 결함 주입(별도 보고).

## 변경 기록
- (없음)
