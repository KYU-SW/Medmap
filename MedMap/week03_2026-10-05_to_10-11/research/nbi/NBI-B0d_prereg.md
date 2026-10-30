# EXP-SN-NBI-002 B0d 사전등록 (rev8) — IMAGING / RADIOLOGY study·report availability & temporal feasibility

> rev8(2026-10-05, 실행 전): B0d 최초 사전등록. 실데이터 집계 실행 0회. 보고서 본문(text) 열람 0. 코호트 연결 집계 0.
> 세션이 본 것: PhysioNet 공식 SHA256SUMS 대조, 두 파일 헤더(컬럼명), 공개 문서(mimic.mit.edu radiology·radiology_detail 페이지),
> radiology_detail의 exam_name·cpt_code·exam_code 정찰 어휘(코호트·class·시각·건수 없음, note ≥ 11 ∧ subject ≥ 11인 이름만),
> field_name별 RR/AR 비율(전체 데이터, 코호트 무관).

- 상위 실험: EXP-SN-NBI-002(NBI-B0). 원본 규칙은 manifest [C] window, [D] 정보 유형, [E] 연결, [G] 라벨, [H] pair 규칙, [I] class-blind, [J] 공개 최소화, [K] 실행·재실행·종료, [L] 누출 필드, [M] 수집 범위다. 이 문서는 B0d 실행 수준으로 구체화하고, manifest [D]의 B0d 정의를 바꾸는 항목은 **(rev8 변경)**으로 표시한다. 충돌 시 manifest [O] 우선.
- 상태: B0a COMPLETE·VERIFIED(run 20261004_121905). B0c COMPLETE·VERIFIED(run 20261005_153323, 공개 SHA bde70d78…, [H] ACS–PE ELIGIBLE 확정).
- 이 문서와 코드는 manifest deviation(rev8) + RG 재심사 RUN + 사용자 실행 승인 전에는 실행하지 않는다.

## 1. 목적 / 비목적
- 목적(단 하나): ACS–PE(주)·ACS–pericarditis(보조) 쌍 코호트에서, 사전 지정 흉부 영상 개념의 **검사 사건(STUDY)**과 **판독 서명(REPORT)**이 MIMIC 후향 데이터에 존재하고 ED 체류 시간축(T0 = ED intime ~ outtime)에 연결 가능한지 라벨과 거친 구간으로 기술한다.
- MedMap v1 영상 경로의 범위: 검사 종류 + 시행(기록) 시각 + 판독 서명 시각까지만. 원본 영상·DICOM·PACS 연동·영상 AI·판독문 NLP는 범위 밖이다.
- 비목적·금지: 보고서 본문·indication·impression·소견 사용, PE/ACS/심낭삼출 양성·음성 추출, NLP·LLM 판독 해석·embedding/RAG, 영상 분석, 분류기, AUROC/AUPRC, sensitivity/specificity, accuracy, odds ratio, class 간 차이 주장·검정, B1 실행, 실제 병원 연동 가능성 주장, WD 이후 가용성 주장.

## 2. 데이터와 무결성
| 파일 | 상태 | B0d 사용 |
|---|---|---|
| mimic-iv-note 2.2 note/radiology.csv.gz | SHA_OK(PhysioNet SHA256SUMS 재계산 일치) 2c09bc76… | 허용 컬럼 note_id·subject_id·note_type·charttime·storetime만(text·hadm_id·note_seq 미참조) |
| mimic-iv-note 2.2 note/radiology_detail.csv.gz | SHA_OK 9d3f6c44… | 허용 컬럼 note_id·field_name·field_value, field_name == 'exam_name' 행만 |
| mimic-iv-ed-2.2.zip / ECG-Ext-ICD zip | B0a와 동일 SHA | 코호트(B0a 모듈 재사용) |
| out/b0a/b0a_public.json · out/b0c/b0c_public.json | 8434a874… · bde70d78… | 코호트 동일성 대조만 |
| hosp labevents·d_labitems·admissions·patients | 보유 | **미사용** |
| ECG machine_measurements·record_list | 보유 | 미사용(B0b) |
- 모든 입력 SHA는 러너(run_b0d.sh)·스크립트 인자로 고정하고 실행 시 재검증한다. 하나라도 다르면 INVALID(sha_mismatch).
- 스키마(헤더, 확인함): radiology = note_id, subject_id, hadm_id, note_type, note_seq, charttime, storetime, text. radiology_detail = note_id, subject_id, field_name, field_value, field_ordinal. field_name 어휘 = addendum_note_id, cpt_code, exam_code, exam_name, parent_note_id.
- 공개 문서 정의(mimic.mit.edu): charttime = "the time at which the note was charted — usually the most relevant time for interpreting the content", storetime = "the time at which the note was stored in the database. This is usually when the note was completed and signed." note_type = RR(판독문)·AR(addendum).
- 데이터 구조 확인(전체 데이터, 코호트 무관): exam_name·exam_code·cpt_code·addendum_note_id는 RR 판독문에만, parent_note_id는 AR에만 있다.

## 3. 코호트 / 분모
- B0a·B0c와 **완전히 동일**. 고정 B0a 모듈(b0a_availability.py 628d4ea7…)의 compute()를 그대로 호출한다(stay 제외·class 배정·MULTI·주 단위·제목 키워드 STOP 재사용). 새 코호트 코드 없음.
- 동일성 확인: B0d 공개 출력의 쌍 상태·코호트 구간이 B0a 공개 출력 **및** B0c 공개 출력과 다르면 INVALID(cohort_mismatch).
- 분모 = n_pool(주 단위 a+b, 두 층·두 개념 공통). B0c와 같은 의미다(denominator semantics 차이 없음).

## 4. 영상 개념과 매핑 (rev8 변경)
### 4-1. 정찰과 결정 근거
- 정찰(b0d_exam_vocab.py → b0d/exam_vocab.json): radiology_detail에서 넓은 키워드(ct·cta·chest·thora·pulm·lung·embol·angio·v/q·ventilat·perfusion·coronar·cardiac·heart)에 걸리는 exam_name 153개(억제 0개), 이름별 함께 나온 cpt_code·exam_code(각각 note ≥ 11). 코호트·class·시각·건수는 쓰지 않았다.
- 확인된 사실 1: **진단 CT·CTA exam_name에는 cpt_code가 없다**(cpt는 시술·IR 계열에만). manifest [D]의 'cpt 71275' 경로는 이 데이터에서 작동하지 않는다.
- 확인된 사실 2: **PE 전용 이름(pulmonary·PE protocol·embol 계열 CTA)이 어휘에 없다**. 'embol'은 색전술(시술)에만 있다. 흉부 CTA 이름은 'CTA CHEST', 'CTA CHEST W&W/O C&RECONS, NON-CORONARY' 두 개뿐이다.
- 결론: 메타데이터만으로는 CTPA(PE protocol)를 대동맥 CTA 등 다른 흉부 CTA와 구분할 수 없다. 본문의 indication·impression으로 구분하는 것은 누출(clinician suspicion·결과)이므로 금지한다. → manifest [D]의 IMAGING_CTPA를 **IMAGING_CTA_CHEST('CTPA와 호환되는 흉부 CTA, PE 특이성 없음')**로 대체한다.
- V/Q: 정찰 키워드(v/q·ventilat·perfusion·lung)에 V/Q 이름이 없다 → B0d에서 실행하지 않음(NOT_RUN — 어휘 없음; 'NOT_AVAILABLE'로 보고하지 않음, 핵의학 보고서가 이 테이블 밖일 수 있음).
- IMAGING_CCTA·IMAGING_CXR(manifest [D] 사전등록): **B0d에서 실행하지 않음(NOT_RUN — 범위 축소)**. 사유: 사용자 지시(2026-10-05) v1 영상 경로를 CTPA·흉부 CT로 한정. 코호트·결과를 보기 전 결정. B1 manifest에서 필요 시 별도 사전등록.
- IMAGING_ECHO: manifest [D] 사전 기대(NOT_EVALUABLE, TTE는 radiology에 없을 가능성)대로 B0d 미실행.

### 4-2. 고정 규칙 (b0d_exam_map.py → b0d/exam_map.json, b0d_availability.py RULES·EXAMS)
| 개념 | 규칙(exam_name 대문자 접두) | 고정 exam_name |
|---|---|---|
| IMAGING_CTA_CHEST | `^CTA CHEST\b` | CTA CHEST · CTA CHEST W&W/O C&RECONS, NON-CORONARY |
| IMAGING_CHEST_CT | `^CT CHEST\b` | CT CHEST W&W/O C · CT CHEST W/CONTRAST · CT CHEST W/CONTRAST W/ONC TABLE · CT CHEST W/O CONTRAST |
- 두 개념은 서로소다(같은 판독문에 두 이름이 함께 있으면 두 개념 모두에 센다 — 복합 검사).
- 제외(exam_map.json excluded_by_reason): 관상동맥 CTA·심장 CT/MR(CORONARY_OR_CARDIAC), 폐암 검진 저선량 CT·LCS 추적(LUNG_CANCER_SCREENING — 'F/U DIAGNOSTIC CT CHEST … LCS'는 접두가 달라 규칙 밖), 흉부 X선·투시(CHEST_RADIOGRAPH_OR_FLUORO), CT 유도 시술·생검·배액·색전술(PROCEDURE_OR_GUIDANCE), MR/MRA/초음파(MR_OR_US), 머리·복부·골반·척추·사지·경부·CTA 머리·경부·복부 등 다른 부위 CT(OTHER_CT_BODY_REGION), 'CT TRACHEA'(기도 전용 프로토콜), 'CT LUNG/MEDIASTINAL BX'(시술).
- 매핑에 쓰지 않는 것: 보고서 본문, indication, impression, cpt_code, exam_code, 환자·class별 빈도.
- 고정 방식: 실행 시 radiology_detail 전체 exam_name에 RULES를 다시 적용해 EXAMS와 다르면 INVALID(exam_map_mismatch). 매핑 산출물 exam_map.json·exam_vocab.json은 credentialed 데이터에서 나온 기관 검사명 어휘다 — 연구 브랜치 로컬에만 두고 공개 저장소로 내보내지 않는다(labitem_map.json과 같은 규칙).

## 5. 두 층의 정의 (rev8 변경 — manifest [D]의 'storetime 단일 가용 시각 + CHARTTIME_ONLY 표기'를 대체)
- 사건 = 개념에 매핑된 **RR 판독문 1건**. AR(addendum)은 쓰지 않는다(봉인에 건너뛴 수만 기록). radiology 테이블 행 자체가 판독문이므로 '검사는 있으나 판독문 행이 없는' 사건은 이 데이터에서 관찰할 수 없다 → 두 층은 '판독문 존재'가 아니라 **시각**으로 구분한다.
- 연결([E]): subject_id ∧ 시각 ∈ window. hadm_id 미사용. 같은 subject의 겹치는 stay는 사건 시각 이전(≤) intime 중 가장 늦은 stay에 배정. W_STAY = [intime, outtime] 양 끝 포함.
- **STUDY 층(검사 사건 기록)**: charttime ∈ W_STAY ∧ charttime 기준 배정 stay. charttime은 '기록 시각'이며 실제 촬영 시각으로 검증되지 않은 대리값이다.
- **REPORT 층(판독 서명)**: storetime ∈ W_STAY ∧ storetime 기준 배정 stay ∧ (charttime ≥ intime 또는 charttime 결측). 뜻 = 'ED 체류 중 판독이 서명·저장되었다'. 예비 판독(prelim) 시각은 데이터에 없으므로 실제 임상 가용 시점보다 늦을 수 있다(보수적).
- PRE_T0_STUDY(봉인): charttime < intime ∧ storetime ∈ W_STAY — REPORT 가용으로 세지 않음.
- REPORT_AFTER_ED(봉인): charttime ∈ W_STAY ∧ storetime > outtime — 체류 중 검사, ED 이탈 후 서명.
- 시각 결측
  - STUDY 층 불확실: storetime 기준으로 체류 중인 판독문이 있는 stay 중, 그 개념 사건의 charttime이 전부 결측인 stay 비율 ≥ 0.5 ∧ 그런 stay 수 ≥ Q_MIN(30) → TEMPORALLY_UNCERTAIN.
  - REPORT 층 불확실: charttime 기준으로 체류 중 검사가 있는 stay 중, storetime이 전부 결측인 stay 비율 ≥ 0.5 ∧ 그런 stay 수 ≥ Q_MIN → TEMPORALLY_UNCERTAIN.
  - 두 층 모두 결측 시각을 다른 층 시각으로 **대체하지 않는다**. 0.5·Q_MIN은 B0c rev7과 같은 사전 고정 상수이며 민감도 분석은 금지한다.
- 중복: 같은 stay·개념의 여러 판독문은 stay 1개로 세고, 첫 시각 = 가장 이른 값.
- 봉인 전용 서술(판정 미사용): W1·W3·W6 window별 기록 stay 수, charttime ∈ [intime−24h, intime)·(outtime, outtime+24h] stay 수, 판독 지연(storetime − charttime, 체류 중 검사 사건) 분위수, 입원/비입원 층별 기록 수.

## 6. 라벨과 시점 클래스 (B0c와 같은 어휘·순서)
- 쌍 상태: class a 또는 b가 0이면 NOT_EVALUABLE(모든 라벨 NOT_EVALUABLE).
- 4개 유형(IMAGING_CTA_CHEST_STUDY, IMAGING_CTA_CHEST_REPORT, IMAGING_CHEST_CT_STUDY, IMAGING_CHEST_CT_REPORT) 라벨, 순서대로
  1. NOT_EVALUABLE
  2. TEMPORALLY_UNCERTAIN(§5 규칙)
  3. NOT_AVAILABLE_IN_DATA: pooled 기록 stay 0
  4. RECORDED_IN_STAY_AVAILABLE: class a·b 각각 기록 stay ≥ N_MIN(30)
  5. RECORDED_IN_STAY_PARTIAL: 그 외
- 시점 클래스(공개, 판정 미사용): 층별 첫 시각(STUDY = charttime, REPORT = storetime)의 intime 대비 지연 중앙값 ≤ 1 h(반올림 전)이면 EARLY_ROUTINE_POSSIBLE, > 1 h이면 LATER_IN_STAY, 지연 값 < Q_MIN이면 INSUFFICIENT_N, 라벨이 UNCERTAIN이면 TEMPORALLY_UNCERTAIN, 쌍 평가 불가면 NOT_EVALUABLE. STUDY와 REPORT 시각은 섞지 않는다.
- 금지 표현: "WD 이후 이용 가능", "CTPA 시행"(개념은 흉부 CTA), "PE 평가 완료".

## 7. 공개 출력 계약 (out/b0d/b0d_public.json, 28키 고정: expected_schema_b0d.json)
- 쌍별: pair_status, cohort_pooled_bucket(B0a와 같은 구간), labels(4), pooled_share_bin(4, 10 %p 구간), timing(4) = 14키 × 2쌍.
- pair_decision·pair_rule_inputs 키 없음(§9).
- 구간 공개 조건: n_pool ≥ SHARE_MIN_POOL 100 ∧ 쌍 평가 가능. 아니면 WITHHELD.
- guard: 모든 공개 leaf = 허용 어휘 문자열. 숫자·자유 문자열이면 쓰지 않고 INVALID(output_guard).
- meta: SHA·상수·시각 정의 문자열만(guard 대상 밖, 코드 고정 값).
- 공개하지 않는 것: exact count, class별 값, window별 값, 지연·판독 지연 수치, 결측 수, PRE_T0_STUDY·REPORT_AFTER_ED 수, 입원/비입원 층, AR 수, exam_name별 값.

## 8. 봉인 출력 (로컬 제한 폴더 nbi_b0d/sealed/b0d_sealed.json, SHA만 공개)
- 쌍별 n_a·n_b·n_pool·층 크기, 유형별 pooled·a·b·층별·window별 기록 수, 시각 결측·존재 사건 수와 확인 stay·전부 결측 stay 수, PRE_T0_STUDY·REPORT_AFTER_ED·±24 h stay 수, 판독 지연 분위수, 지연 분위수, 시점 라벨, AR 건너뛴 수.
- 개봉 규칙 = manifest [I](EXP-SN-NBI-003 protocol lock 이후, deviation + SHA 재검증 + 사용자 로컬 개봉). Claude 접근 차단은 기존 permissions.deny 그대로.

## 9. B1 pair 규칙과의 관계
- [H]의 ACS–PE 적격은 B0c(TROPONIN·DDIMER AVAILABLE)로 이미 확정됐다(b1_primary_pair = ACS~PE). B0d 결과는 [H] 결정을 바꾸지 않고 입력도 아니다.
- [H] 문구의 IMAGING_CTPA는 IMAGING_CTA_CHEST로 **대체하지 않는다**(PE 특이성 없음). B1 설계에서 영상 정보를 쓸지는 B1 manifest가 정한다([I]: B1은 검사 시행 여부·순서를 입력으로 쓰지 않음).

## 10. 중단(abort) 조건 — 공개 출력 없이 counted=no
- launch_b0d.sh: 7 인자, 6 cd 실패, 8 자원 미충족(wait_for_resources --check --no-gpu ≠ OK — 실행 시작 안 함), 4 이미 실행(marker 또는 out/b0d 존재), 9 시작 실패
- run_b0d.sh: 7 인자, 6 cd 실패, 4 출력 존재(out/b0d 또는 봉인 폴더), 5 고정 SHA 불일치(B0D_PINNED_SHA256SUMS 11개)
- b0d_availability.py exit 2(INVALID): preflight — sha_mismatch, exam_map_mismatch; data — schema_mismatch(28키), output_guard, cohort_mismatch(B0a·B0c), 예외(traceback은 비공개 로그로만)
- exit 3: STOP_TITLE(B0a와 같은 제목 키워드 검사)
- 쓰기 순서: 모든 검사 통과 → 봉인 → 공개.

## 11. 퇴화·재실행·종료 규칙
- manifest [K] rev4·rev5 (a)~(i)를 B0D_FINAL에 그대로 준용한다(산출물 전부 보존, 결함 입증 시에만 재실행, 미입증이면 최초 승인 실행 확정, INVALIDATED_BY_IMPLEMENTATION_BUG → FINAL_COUNTED_RUN_CANDIDATE, ENVIRONMENTAL_ABORT, counted 보류는 1회 조사·종결 deviation, fixture 출처 제한).
- 준용 치환: (h)(1) 고정 시험 = tests/test_b0d.py·tests/mutation_b0d.py. (h) 종결 기한 = 다음 RG 재심사·B1 manifest 착수 중 이른 시점 전. /rg-verify 대상 = 원 logs/와 deviation 고정 재실행 경로의 *_b0d_final.log 전부.
- **IMAGING_LINK_DEGENERATE**: 두 쌍에서 4유형 8칸이 모두 {NOT_AVAILABLE_IN_DATA, TEMPORALLY_UNCERTAIN} → 연결 결함 의심(note_id 형식·시각 형식·경로) → [K](a)·(h) DEGENERATE와 같이 처리. 결함 미입증이면 B0 전체 종료 판정에서 NOT_EVALUABLE 명시 종료.
- 재실행 사유가 아닌 것: coverage 낮음, CTA 적음, 기대와 다름, 매핑을 넓히고 싶음(예: 본문으로 CTPA 구분), threshold·window·pair 변경 희망, charttime/storetime 역할 교체 희망.
- 실행기의 marker(logs/b0d_launch.marker)는 삭제하지 않는다. 정당한 재실행은 [K](e)대로 새 run ID·새 출력 경로·새 SHA로 고정한 러너·실행기에서만.

## 12. 완료(success) 기준
- B0D_FINAL verdict=COMPLETE ∧ rc 0 ∧ counted=yes ∧ 공개 키 = expected_schema_b0d.json(28) ∧ 허용 어휘 ∧ 봉인 SHA meta 기록 ∧ 코호트 B0a·B0c 일치 ∧ IMAGING_LINK_DEGENERATE 아님 ∧ ram_guard 로그가 logs/ram_guard_b0d.log(절대경로)에 있음.
- 뜻: "사전 지정 흉부 영상 개념(흉부 CTA·흉부 CT)의 판독문 기록 시각(charttime)과 서명 시각(storetime)이 ED 체류 시간축 안에 있는지 라벨·거친 구간으로 기술했다"까지.

## 13. NOT_EVALUABLE
- 쌍: class a 또는 b가 0이면 모든 유형 NOT_EVALUABLE.
- 유형: TEMPORALLY_UNCERTAIN은 시각 정렬 불가라는 protocol 결과로 그대로 보고.
- 개념 수준 NOT_RUN(보고서 서술, 공개 키 아님): CTPA 전용 개념(메타데이터로 식별 불가), V/Q(어휘 없음), CCTA·CXR(범위 축소), ECHO(사전 기대).

## 14. 실행 (RG RUN + 사용자 승인 후 정확히 1회)
```
bash /home/<user>/medmap-worktrees/safety-net-nbi/docs/research/nbi/b0/launch_b0d.sh
```
- 인자 없음, 이 한 줄만 사전등록된 명령이다. 실행기가 자원 점검 → marker → nohup 러너 → ram_guard(90 %)를 모두 절대경로로 처리한다(cwd·cd·& 무관). 환경변수 B0D_RESOURCE_CHECK·B0D_RAM_GUARD는 시험 전용이며 실제 실행에서 설정하지 않는다(실행기 출력 첫 줄의 resource_check와 ram_guard 로그 위치로 /rg-verify 대조).
- 로그: logs/<ts>_b0d_{precheck,run,final}.log, logs/nohup_b0d.log, logs/ram_guard_b0d.log, logs/b0d_launch.marker/launch(pid·ts).
- 예상 시간: radiology.csv.gz 782 MB를 /mnt/c에서 csv 파싱(본문 필드는 파서 통과만) — 수 분~수십 분 추정(실측 전, 확인 필요). 메모리: 매핑된 note_id 집합과 코호트 subject 사건만 보관.

## 15. 고정(freeze) 방식
- B0D_PINNED_SHA256SUMS(11개): b0d_availability.py, b0a_availability.py, expected_schema_b0d.json, b0d_exam_map.py, b0d_exam_vocab.py, b0d/exam_map.json, b0d/exam_vocab.json, tests/test_b0d.py, tests/mutation_b0d.py, tests/test_b0a.py, tests/fixtures/cms_icd_titles.json.
- run_b0d.sh에 PINNED·schema·입력 SHA 하드코딩, precheck 로그에 runner·launcher SHA 기록. manifest rev8 deviation에 이 문서·러너·실행기 SHA 기록. RG RUN 시 protocol lock 갱신.
- 시험(rev8): 합성 32 tests OK, 변이 28/28 KILLED, 러너 실패 경로(인자 7, 출력 존재 4, 변조 5 — 제한 폴더 미생성), 실행기 경로(인자 7, 자원 미충족 8 — marker 미생성, 정상 시작 0 — /tmp에서 `&`로 시작해도 로그·marker·ram_guard 로그가 b0/logs 절대경로에 생성·중첩 경로 0, 두 번째 시작 4). 모두 scratch 사본·HOME 교체, 실데이터 도달 전.

## 16. 개인정보 / 누출 / 잔여 위험
- LOCAL ONLY. 환자 행·ID·환자별 시각·보고서 본문을 세션·외부로 내보내지 않는다. stdout 판정 1줄, traceback은 비공개 로그로만.
- 보고서 본문: csv 파서가 행 단위로 지나갈 뿐 보관·참조하지 않는다(RAD_ALLOW 시험, 본문 내용을 바꿔도 출력 동일 시험, text_column_read 변이 KILLED).
- 누출 점검(STEP 6)
  - indication·진단 문구·impression·최종 진단: 사용 안 함(본문 미참조, 개념은 exam_name만).
  - exam_name 자체의 정보: 'W/ONC TABLE'(종양 추적)·'NON-CORONARY' 같은 프로토콜 문구는 개념 배정에만 쓰고 공개·B1 입력에 쓰지 않는다([L](7) 확장).
  - 검사 시행 자체 = 의사 의심(confounding by indication) — 흉부 CTA 시행은 PE·대동맥 박리 의심의 결과다. B0d는 기록 존재만 기술하며, B1은 검사 시행 여부·순서를 입력으로 쓰지 않는다([I]).
  - 결과·class 기반 매핑: 없음 — 정찰은 코호트·class·시각 없이 어휘만.
- 잔여 추론 범위: B0c와 같은 구조(라벨 하한 30, 10 %p 구간, n_pool ≥ 100). STUDY·REPORT 구간 차이는 'ED 이탈 후 서명' pooled 비율을 10 %p 폭 수준으로 드러낼 수 있다(class 무관, pooled) — 허용 범위로 사전 공개. class별 값·작은 셀은 없음(공격 fixture: PE 1–10 변화 → 공개 동일).
- 세션이 본 정찰 어휘(기관 검사명 153개, 건수 없음)는 환자 정보가 아닌 검사 카탈로그 문자열이지만 credentialed 데이터 파생물이다 — 반출 금지(§4-2).

## 17. 기대 주장 (COMPLETE일 때만)
- 허용: "MIMIC-IV-ED·Note 단일 기관 후향 데이터, ED 퇴원 ICD로 정의한 쌍 코호트(편입 편향 있음)에서, 사전 지정 흉부 영상 개념(흉부 CTA — PE 특이성 없음, 흉부 CT)의 판독문 기록 시각과 서명 시각이 ED 체류 시간축 안에 있는지 사전 고정 라벨과 pooled 거친 구간으로 기술했다."
- 금지: CTPA 가용성(개념이 CTPA가 아님), PE 진단 성능, 영상의 판별력, 임상 유용성, WD 이후 가용성, 예비 판독 시점, 실제 병원(EMR·RIS·PACS·FHIR·DICOMweb) 연동 가능성, 오진 감소, class 간 검사 시행 차이(봉인).

## 18. 자기감사(self-audit, STEP 17)
| 항목 | 판정 | 근거 |
|---|---|---|
| 원본 영상 분석 | 없음 | DICOM·픽셀·PACS 코드 없음 |
| 보고서 결과를 진단 feature로 사용 | 없음 | 본문 미참조(RAD_ALLOW, 변이 KILLED, 본문 변화 무관 시험) |
| indication 누출 | 없음 | 본문 미참조 |
| final diagnosis 누출 | 해석 제한으로 공개 | 코호트는 ED 퇴원 ICD(B0a와 같음), 판정 입력 아님 |
| B1 분석 혼입 | 없음 | pair_decision 키 없음, 성능 지표 없음 |
| class prediction | 없음 | 모델·확률 없음 |
| raw report 출력 가능성 | 차단 | 본문 미보관, stdout 1줄, guard·schema |
| exact count 공개 | 없음 | 모든 count 봉인, 구간은 n ≥ 100 |
| 결과 보고 매핑 변경 | 없음 | 정찰은 코호트·class·시각 없음, 실행 시 exam_map_mismatch 검사 |
| temporal threshold 사전 고정 | 예 | N_MIN·Q_MIN·0.5·1 h 상수(B0c와 같음) |
| study/report 혼합 | 없음 | 층 분리, 결측 시각 대체 금지, layers_merged·report_uses_charttime·study_uses_storetime 변이 KILLED |
| 병원 연동 과장 | 금지 문구 사전 고정 | §17 |
| 운영(B0c 로그 경로 사고) | 재발 방지 | 실행기 절대경로, cwd 무관 시험 |
| 확인 필요 | — | ED 귀가 환자의 radiology 수록 범위([M]), charttime이 실제 촬영 시각에 얼마나 가까운지, 실행 시간 실측 전 |

## 19. 해석 제한 (사전 고정 보고 문구)
- 흉부 CTA ≠ CTPA: PE protocol·대동맥 protocol을 메타데이터로 구분할 수 없다. 흉부 CTA 기록은 'PE 평가가 이루어졌다'를 뜻하지 않는다.
- 시각: charttime은 기록 시각(촬영 시각 대리, 검증 안 됨), storetime은 최종 서명 시각(예비 판독보다 늦음). REPORT 층 AVAILABLE은 'ED 체류 중 서명된 판독문이 있다'일 뿐, 의사가 그때 판독을 보았음을 뜻하지 않는다.
- 참조 표준 구조: ED I26은 대부분 CTA/V/Q 확인을 거친 사례라 PE class의 흉부 CTA 기록률은 정의상 높을 수 있다(verification bias). ACS class의 흉부 CTA는 대동맥 박리 감별 등 다른 의심을 반영한다(confounding by indication).
- 수집 범위: radiology 테이블이 ED만 거친 환자의 판독문을 얼마나 포함하는지, 외부 병원 영상은 포함하지 않는지 공개 출력으로 알 수 없다. 기록 없음 ≠ 미시행([M]).
- 체류 절단: outtime 이후 서명은 REPORT 가용으로 세지 않는다(봉인 REPORT_AFTER_ED로만 기술). 짧은 체류 class는 차등 절단될 수 있다.
- 단일 기관·기관 고유 검사명: 다른 병원 검사명·코드 체계로 일반화하지 않는다.
- 제품 관계: "MIMIC에 판독문 기록이 있다"는 "실제 병원에서 MedMap이 실시간으로 가져올 수 있다"가 아니다.
