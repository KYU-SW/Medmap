# EXP-03-TIME 프로토콜 v2 — 실제 MIMIC 시간정보 이용 가능성 정책(1차 gate 지적 반영 개정본)

- 작성 2026-11-03. 대상 RG 실험 EXP-MAI-003. 1차 gate(`.research-guardian/audits/EXP-MAI-003/gate/20261103_105726_NEEDS_FIX.md`) 지적 반영.
- v1(`../time_v1/PROTOCOL_TIME.md`·코드·테스트·결과) 보존 — 수정하지 않음. 시간 등급·정책 정의(v1 §1–§3)는 그대로 승계하고, `time_v1/time_policy.py` 를 수정 없이 import.
- 상태: 계획. 실제 MIMIC 실행 없음. 실행은 rg-gate RUN + 사용자 명시 승인 후 1회.
- post-hoc: 정책은 EXP-02 공개 시간 집계를 본 뒤 작성됨. 결과는 '정책 적용 결과 기술'이며 독립 검증이 아님.

## 1. 연구 범위·주장 한계
- 시스템 동작 기술. 질병 분류 정확도·실제 오진 탐지·실제 의사 판단 검증이 아님.
- 안전 조건 '위반 0'은 (A) 정책 정의상 보장되는 구현 불변식이 실행에서 깨지지 않았다는 회귀 검사, (B) 원 parquet 필드로 별도 계산한 허용 집합과 실제 사용 집합이 일치했다는 관찰이다. **자료 자체의 시각 정확성·귀속 정확성은 검증하지 않는다.**
- 누출은 "문서상 이용 가능 시각(lab storetime, 등급 A)·보수적 대리(radiology storetime, 등급 B) 가정하에서" 정의된다.
- 안전 위반 0을 rule-of-three 등 일반화 상한으로 해석하지 않는다(구조상 0 인 계층 A 포함, 선택 코호트).
- 사전 정의 셀은 전부 내부 정확 집계로 산출하고(공개는 §9-3 범위·VERIFIED 분만, 비공개 표 목록·공개 표 수 함께 보고, 비공개 칸 서술·추정 금지) 사후 선택 강조를 하지 않는다. 정책 간 우열 판정·유의성 검정 없음.

## 2. 체크포인트(고정)
- T0 = ED intime · T1 = min(intime + 180분, outtime) · T2 = outtime.
- T1 = T2 인 체류(체류 시간 ≤ 180분) 수를 보고(`stays.t1_equals_t2`).
- intime 또는 outtime 결측, 또는 outtime < intime 인 체류 = TIME_UNDEFINED: 체크포인트 평가 안 함(건수 보고), 귀속 창으로도 쓰지 않음. 이 체류에 키로 붙는 triage·ECG 는 `rows_on_time_undefined_stay`·`on_time_undefined_stay` 로 집계. 체류 제외가 아니라 '평가 불가'로 보고.
- 시점별 증거 = available_at ≤ T 인 기록(정책 허용 등급만). 관찰 시각(observed_at = charttime)은 귀속·역전 판정과 '시행됐으나 아직 미이용' 기술 집계에만 쓴다.

## 3. 고유 원본 기록 키·중복
| 원천 | 고유 키 | 단위 |
|---|---|---|
| hosp labevents | labevent_id | 검사 행 |
| note radiology | note_id | 판독 문서 |
| ECG machine_measurements | study_id | ECG 기록 |
| ED triage | stay_id(체류당 1행) | triage 행. 파생 증거(활력징후·주증상 키워드) 수는 별도 단위 |
- 키 결측 행 = `missing_key_rows`(미사용).
- 같은 키 여러 행: subject·charttime·storetime(ECG 는 ed_stay_id·ecg_time)이 모두 같으면 1행 유지(`dup_key_groups_identical`, 잉여 행 `dup_extra_rows`), 하나라도 다르면 그 키 전체를 미사용(`dup_key_groups_time_conflict`, 등급 C 취급). 원인 = '같은 키 다른 시각'.
- 행 대조 항등식: 입력 행 = 결측 키 + 고유 키 + 중복 잉여 행 / 유지 고유 = 귀속 + AMBIGUOUS + 미귀속.

## 4. 귀속(전역 1회)
- 고유 기록마다 한 번만 귀속한다(체류마다 반복 투입 금지). triage = stay_id, ECG = ed_stay_id(정수 정규화 후 매칭 건수 보고, dtype 기록), lab·radiology = 같은 subject 의 시각 정의 체류 중 charttime ∈ [intime, outtime].
- 두 체류 창에 들면 AMBIGUOUS(자동 선택 금지, 미사용), 어느 창에도 없으면 미귀속(미사용). hadm_id 로 합치지 않음.
- **연결 addendum = 가족 단위 귀속(2차 gate M-add-attr)**: §5 기준으로 연결된 addendum 은 자기 charttime 이 아니라 원 판독이 귀속된 체류로 귀속(stay 키로 전달). 원 판독이 AMBIGUOUS·미귀속이면 addendum 도 같은 상태(미사용). 자기 시각 귀속과 다른 경우 `linked_addendum_stay_ne_parent_stay`, 원 판독이 AMBIGUOUS·미귀속인 경우 `linked_addendum_parent_ambiguous_or_unattributed` 건수 공개. 계층 B 도 같은 규칙을 독립 구현.
- 한계: 판정은 코호트 체류끼리만 — 코호트 밖 ED 체류와 겹침은 감지 못함(NOT_VERIFIABLE). radiology charttime 은 '작성 시각이 아닐 수 있음'. 시각 불명(TIME_UNDEFINED) 체류의 창은 귀속에 쓰지 않으므로, 그 체류와 겹치는 기록은 AMBIGUOUS 로 잡히지 않고 인접 정의 체류에 귀속될 수 있음. intime 이전 채취 lab 은 미귀속. lab 분모는 MedMap 개념 itemid(LAB_NODE ∪ HIV) 한정 추출 — 전체 ED 검사 포함률 아님.

## 5. 영상 유형·CTA 판정·addendum
- CTA = exam_name(대문자) 이 'CTA CHEST' 로 시작. PE 프로토콜 여부는 확인 안 됨(대동맥 CTA 등 포함 → confounder). 그 외 영상 = OTHER(증거 미투입, 참고 집계), exam_name 결측 = UNKNOWN_TYPE(증거 미투입). 주 지표는 CTA, 전체 영상 집계는 참고로 분리.
- addendum: note_type 'AR'. 연결 = radiology_detail 의 parent_note_id(자식→부모)와 addendum_note_id(부모→자식)가 **양방향으로 일치**하고, 자식이 AR 이고, 부모가 추출에 있고, 자식의 부모가 하나이고, 부모·자식 subject_id 가 같을 때만(다른 환자 연결 = `link_subject_mismatch`, 연결 안 함). 공식 문서는 "부모 보고–addendum 연결이 표에 있다"만 명시(필드 방향 의미는 확인 필요) → 양방향 요구로 보수 처리, 한 방향만 있는 쌍 수를 보고.
- 연결된 addendum 의 유형: 자기 exam_name, 없으면 부모 exam_name.
- 연결 addendum 중 v3b 결정적 분류(ACUTE_POS·NEGATIVE·CHRONIC_OR_PERSISTENT·UNCERTAIN)만 자기 이용 가능 시점부터 직전 가족 구성원(부모 또는 앞선 addendum, storetime 순 사슬)을 대체(supersedes). NO_MENTION addendum 은 증거 미투입(짧은 addendum 이 원 판독을 지워 AL2 오알림을 만드는 것 방지).
- **§5-1 addendum 시간 순서 규칙(2026-11-03, 실행 전 사전 등록, 7번째 기록 심사 지적 M-add-order 대응)**: 연결 addendum 중 결정적 분류인 것에 적용. (1) 원 판독의 시각이 불명확(storetime·charttime 결측 또는 storetime < charttime) → `addendum_order_undeterminable_excluded`. (2) addendum storetime < 원 판독 storetime → `addendum_stored_before_parent_excluded`. (3) addendum charttime < 원 판독 charttime → `addendum_charted_before_parent_excluded`. 해당 addendum 은 증거에 넣지 않고 대체 관계도 만들지 않으며 건수만 내부 집계한다(세부 기록 표, 외부 공개 제외). 원 판독은 자기 시각 그대로 유효 — 과거 상태를 소급 수정하지 않음. 같은 시각은 '이른 시각' 아님. 자기 시각이 부적격인 addendum(시각 결측·역전)은 기존 경로(등급 C, 미사용). 계층 B 가 같은 규칙을 독립 구현해 건수 대조. 이 규칙으로 reassess.py(동결·무수정)의 StopIteration 경로에 도달하지 않음. 실제 빈도는 미확인.
- 연결 없는 AR = 별도 판독 증거 + `ADDENDUM_UNLINKED` 표시.
- 대체 대상이 그 체류 타임라인에 없으면(가족 귀속 뒤 남는 경우 = 원 판독 비입력) 연결 없이 별도 증거(`CORRECTION_TARGET_NOT_IN_TIMELINE`). 원 판독 시각 부적격이면 §5-1 로 제외(2026-11-03 변경).
- 한계: 미연결 AR(한 방향 연결·부모 둘 이상·부모 추출 없음·다른 환자 연결)은 부모를 모르므로 자기 charttime 으로 귀속된 단독 판독 증거 — 이전 방문 CTA 의 addendum 이 현재 체류에 들어올 수 있음. 규모 = 사전 지정 기술 집계 `stays_with_unlinked_AR_effective`(T 시점 유효 증거에 미연결 AR 이 있는 체류 + 환자).
- 정정 전 시점 상태는 바뀌지 않는다(addendum available_at 이전에는 원 판독 유효).
- 기술 집계(사전 지정): 대체 쌍의 (직전 구성원 분류 → addendum 분류) 건수 `replace_pair:*`, NO_MENTION 미투입 addendum 의 원 판독 분류별 건수 `nomention_addendum_parent_class:*`(ACUTE_POS 원 판독 = 놓친 철회 가능성). UNCERTAIN addendum 도 사전 규칙상 대체(유지) — 해석 시 이 표로 규모 확인.
- v3b 는 addendum 문서에서 검증되지 않음(AR 본문에 원 보고 전문이 들어 있는지는 확인 필요) — confounder.
- 판독 분류 = EXP-02 동결 v3b(읽기 전용). v3b 는 Ext-PE(PE 프로토콜 판독)에서 개발 — 비PE 프로토콜 CTA 에 적용하는 도메인 차이 confounder.

## 6. 지표(전부 코드가 직접 산출)
- 원천별: 입력 행·결측 키·고유 키·중복(동일/충돌)·유지·귀속·AMBIGUOUS·미귀속, 영상 유형·귀속 유형·v3b 분류·연결·addendum 처리 수, ECG 매칭, triage 행·파생 증거 수.
- 정책별 flag(OK·POST_ED·UNKNOWN_AVAILABILITY·TIME_CONFLICT·NOT_IDENTIFIABLE·EXCLUDED_BY_POLICY·APPROX_INTIME)·등급(A·B·C)을 원천별로. 등급 C 입력 후보 수 vs 사용 수.
- 정책 P·시점 T 사용: 원천별 사용 고유 기록 수 · PROXY 사용 증거 수 · APPROX 사용 증거 수 · triage 파생 증거 사용 수 · 증거 있는 체류 수 + 고유 환자 수.
- **포함률** = (정책 P 에서 T 까지 사용된 고유 기록) / (평가 체류에 귀속된 고유 기록, 정책 무관). 분모: lab = 귀속 고유 labevent_id, rad = 귀속 CTA 입력 문서(연결 NO_MENTION addendum 제외), triage = 파생 증거 있는 triage 행, ecg = 귀속 고유 study_id. 합산(pooled) = 네 분모 합. 체류 포함률 = 증거 있는 체류 / 평가 체류.
- **정책 간 포함률 차이** = `rate_diff_vs_STRICT[P][T][원천|pooled]` = 비율(P) − 비율(STRICT), 반올림 전 정확값으로 계산 후 4자리(코드 직접 산출). 어느 쪽이 마스킹·분모 0 이면 '계산 불가'. pooled 는 단위 혼합 참고값(해석은 원천별 우선).
- 기술 집계: observed ≤ T < available 인 기록 수, 시행됐으나 판독 미이용 CTA 가 있는 체류 수(MIMIC 에 의뢰 시각이 없어 PENDING 은 생성되지 않음 — 이 상태는 INSUFFICIENT 로 집계됨).
- 요약 상태 분포(체류 + 환자) · AL1·AL2 체류 + 환자 · 상태 변화: T0→T2 비교와 '어느 시점이든 변화'를 분리 · 알림 변화도 같은 두 정의.
- **대응 교차표(2차 gate S-paired-construct)**: 범주 = 요약 상태 + 근거 — NO_HYPOTHESIS · CONFLICT_R2 · SUPPORTED_R1 · SUPPORTED_R7(결정 증거 없이 R7 지지) · INSUFFICIENT_R3 · INSUFFICIENT_NO_DECISIVE · UNKNOWN_R4R5 · PENDING. 결정 상태 = {CONFLICT_R2, SUPPORTED_R1}. 시점별 STRICT 범주(행) × S1 또는 S2 범주(열), 같은 체류(체류 + 환자). `decisive_lost` = 행 ∈ 결정 ∧ 열 ∉ 결정 칸 합, `decisive_gained` = 반대 방향 합 — 둘 다 보고, 방향 판정 없음. 정책별 범주 분포도 보고. 요약 상태·알림이 다른 체류 수(+환자).
- 출처: REJECTED_NO_SOURCE, CORRECTION_TARGET_NOT_IN_TIMELINE.
- 단위 분리(2026-11-04): 원천별 고유 기록 수 · 기록이 연결된 체류 수(`stays_with_records`) · 환자 수(`patients_with_records`)를 따로 산출(내부 집계, 계층 B 대조). 같은 기록을 체류마다 다시 세지 않음.
- 재현: EXP-01b 그래프 지식 파일 버전(graph_kb_sources: SHA·커밋·데이터 버전만) · 코드 SHA-256(time_v2 코드 전체 + 관계 파일 + 이 문서 + time_v1/time_policy.py + reassess.py + ct_bridge.py + EXP-02 5개 + exp01b 상위 .py 전부), 입력 SHA-256(parquet 4개 + radiology_detail), python·pandas·numpy·pyarrow 버전, 프로토콜 버전.

## 7. 안전 검사 2계층·중단
- **계층 A(구현 불변식 — 정책 강제로 0, 실증 근거 아님)**: assess(전체,T) == assess(T 까지,T) · 관계·알림의 available_at ≤ T · 정책 밖 등급 C 사용 0 · 체류 간 증거 0 · 출처 없음 0 · 전역 귀속과 체류 빌드 귀속 불일치 0 · addendum 가족 동시 유효 0.
- **계층 B(독립 데이터 감사 — 원 parquet 필드로 별도 경로, 관찰 0)**: `independent_audit.py` 가 파이프라인 모듈을 import 하지 않고 pandas 병합으로 체류×정책×T 허용 집합을 다시 계산해 사용 집합과 대조(초과·누락 둘 다) · 사용 기록 available_at == 원 storetime(lab·rad) / == intime(S1 triage) · 같은 subject · 전역 원 키 다중 체류 사용 0 · ECG 사용 0 · triage 는 S1 에서만, S1 에서는 파생 증거 전부 사용 · 입력 행·귀속 집계를 파이프라인과 대조 + 항등식.
- 공유 입력(독립 계산 아님): v3b 분류 결과, triage 파생 증거 수(EXP-02 어댑터). `A_source_reference_untraceable`(출처 문자열이 원 기록 가명 키로 추적됨)은 파이프라인 가명표로 계산하므로 계층 A. addendum 대체 정확성은 A(가족 동시 유효)로만 검사. 공개 건수 linked_addendum_stay_ne_parent_stay·linked_addendum_parent_ambiguous_or_unattributed 는 파이프라인 집계(B 는 그 결과인 귀속·AMBIGUOUS·CTA 입력만 대조). 계층 B 대조 범위: lab·radiology = 입력 행·결측 키·고유 키·중복·유지·귀속·AMBIGUOUS·미귀속·연결·CTA 입력 + 항등식, ECG = matched, triage = 대조 없음(S1 완전성만).
- 키 dtype 공통 오류 방어: lab·radiology 귀속 0 또는 ECG 매칭 0(입력 행 > 0)이면 ABORT(`B_zero_match_guard_*`). 입력 키 dtype 을 공개 JSON 에 기록.
- 검증 불가(NOT_VERIFIABLE, 공개 JSON 에 명시): 실제 열람 시각, storetime 'usually' 예외·예비 구두 보고, 코호트 밖 체류 겹침, lab storetime 이 실제 이용 시각과 다른 경우.
- 누출 검사 범위: 세 정책 모두(하나라도 위반 시 ABORT).
- 중단: 어느 계층이든 위반 1건 이상 → 즉시 중단, ABORT JSON(위반 항목 이름·건수만), 종료 코드 3. 코드 SHA 가 gate 동결 목록과 다르면 데이터 읽기 전 ABORT. 예외 → 단계·오류 유형 이름만 출력(메시지·traceback 비출력), 종료 코드 4. 로그 확인은 `DONE`/`ABORT` 고정 토큰 grep 으로만.

## 8. 보안·식별자
- 내부 키 = 실행마다 새 salt 로 만든 HMAC-SHA256 16자 가명(`lab:…`·`rad:…`·`ecg:…`·`triage:…`), salt 비저장. 원 note_id(subject_id 포함)·labevent_id·stay_id 는 예외 메시지·출처 문자열·이벤트 id 에 들어가지 않음.
- 출력 = 공개 집계 JSON 1개(또는 ABORT JSON). 체류별 결과 파일은 v2 에서 만들지 않음(v1 초안의 '봉인 체류별 결과' 정식 제외).
- Ext-PE: extract_v2 radiology 와 Ext-PE 문서가 겹침(EXP-02 공개 집계 9,580). Ext-PE 라벨 미연결·정확도 미산출·Ext-PE CSV join 금지 → TEST 재평가 아님.

## 9. 공개 마스킹
- 1–9 → '<10'. 공개 항등식 묶음 안에 마스킹 칸이 하나뿐이면 다음 작은 양수 칸도 가림(MASKED_COMPLEMENT), 전 출력에 걸쳐 한 번에 반복 적용(전역). 묶음(과잉 포함 허용): 체류 블록 · 원천별 행 대조(입력·결측·고유·잉여, 고유·유지·시각 충돌, 유지·귀속·AMBIGUOUS·미귀속, ECG 유지·키 없음·코호트 밖·시각 불명·매칭) · 영상 유형·note_type·귀속 유형·분류·연결·대체 쌍 · 같은 양(분모 ↔ 기록 집계) · 정책별 원천 flag 합·등급 합 = 분모 · C 입력 = 등급 C · 원천 사용 + pooled · PROXY = rad 사용 · APPROX = triage 사용 = C 사용 · 상태·범주 합 = 평가 체류 · 요약 상태 = 범주 합 · 교차표 행 = STRICT 범주, 열 = 비교 정책 범주 · 상이 체류 = **요약 상태가 다른** 칸의 합(SUPPORTED_R1↔R7, INSUFFICIENT_R3↔무결정 칸 제외 — 정확한 항등식 묶음, 비대각 전체 묶음은 과잉 포함으로 함께 둠) · 결정 상실·획득 = 해당 칸 합 · 정책·시점 간 정의상 같은 양(lab 사용 세 정책 동일, rad 사용 STRICT = S1, S1 triage 사용 T0 = T1 = T2, lab flag·등급·C 입력 세 정책 동일) — **같은 양은 2칸 사슬 묶음으로 표현**해 한 칸이라도 가려지면 같은 양의 모든 칸이 가려지게 함. 일반 규칙(5차 gate): 모든 원천의 같은 flag·등급·C 입력 칸과 같은 원천·같은 T 의 사용 칸·PROXY 칸은 세 정책 사슬, 정책별 triage 사용은 T0–T2 사슬, APPROX·triage 파생 증거·C 사용은 사슬(정의상 다른 칸은 더 가릴 뿐). 과잉 포함 묶음은 정확한 항등식 묶음이 함께 있을 때만 허용. 체류 칸이 가려지면 짝 환자 칸도 가림.
- 마스킹 칸이 들어간 비율·차이·분모 0 비율 = '계산 불가'.
- 잔여 위험(명시): 여러 묶음을 연립해 푸는 역산 차단은 보장하지 않음(1단계 보완). 공개 대상은 기록·체류 건수이며 개인 속성 아님.

## 9-2. 공개 집계 보호 구조 개정(2026-11-03, 7번째 정식 gate 전) — §9 를 대체(§9 는 1단계로 유지)
- **변경 전 정책**: §9 — 1–9 '<10' + 사람이 찾은 항등식 묶음에 1단계 보완 마스킹. 공개 대상 = 사전 정의 셀 전부.
- **변경 이유**: 1~5차 gate(+ 기록되지 않은 6차 심사)에서 매번 새 역산 경로(합·차이·같은 양·필드 간 합)가 지적됨 — 관계를 사람이 하나씩 추가하는 방식으로는 끝나지 않음. 지적 목록은 TRACKING_GATE1.md.
- **변경 후 정책(보수적)**:
  1. INTERNAL_AGGREGATES = 정확 집계(모든 사전 정의 셀·비율, 환자 수 포함) → 봉인 영역(`--internal-out`, `/home/<user>/medmap_exp02_sealed/` 아래만, 권한 700/600)에만 저장. 공개 가림이 연구 계산을 바꾸지 않음. 세션은 실제 자료 실행 결과를 열지 않음.
  2. PUBLIC_AGGREGATES = (1단계) §9 heuristic 보완 → (2단계) 환자 수 정책: 평가 체류 전체 환자 1칸만 공개, 나머지 환자 칸 PUBLIC_WITHHELD(집합·중복 관계는 선형 검증 범위 밖) → (3단계) 독립 검증기 역산 검사 → FAILED·NOT_VERIFIABLE 칸이 속한 표(또는 같은 관계 성분의 가장 세부 표)를 통째로 PUBLIC_WITHHELD → 처음부터 재검사, VERIFIED 까지 반복. 끝까지 검증 안 되면 전 자료 표 비공개.
  3. 공개 우선순위: T1 전체 요약(체류·원천 핵심 행 대조·분모·사용·상태·알림·변화·대응 요약) → T2 병합 범주(flags_merged: 시각상 사용 가능 / 퇴실 후 / 미사용) → T3 세부(flag·등급·C 입력·범주·8×8 교차표·세부 기록 집계). 같은 실패 성분이면 세부부터 비공개.
  4. 비율·차이는 분자·분모(출처 비율)가 공개 정수일 때만 공개(`ratio_sources` 로 출처 선언), 아니면 '계산 불가'.
  5. 실제 공개 파일을 다시 읽어 재검사 — VERIFIED 가 아니면 공개 파일 삭제·ABORT(공개 0).
- **독립 검증기**(`disclosure_verifier.py`): 보호 코드·묶음 G 를 import 하지 않음(테스트로 확인). 관계 = `relation_discovery_v2.py` 가 무작위 합성 자료(`synth_random_v2.py`, 실제 MIMIC 아님) 약 2,000개를 파이프라인 정확 집계로 돌려 찾은 (a) 상수 칸, (b) 선형 등식(정확 분수 RREF, 전 자료 정수 검증), (c) 쌍별 부등식 x_i ≤ x_j(이행적 축약). 실행 시 이번 자료 정확값에서 참인 관계만 사용(거짓 관계는 공격자 지식 아님, 우연히 참인 관계는 남김 = 보수적).
- **검사 범위**: 미지수 = 공개 숫자가 아닌 관계 범위의 모든 칸('<10' [1,9], MASKED_COMPLEMENT [10,∞), PUBLIC_WITHHELD·누락 [0,∞)). 선형계획 최소·최대 → 정수 범위가 [1,9] 안이고 후보 < 5 이면 FAILED. 관계 범위 밖 숫자·상수 불일치·허용 밖 환자 칸·출처 없는 소수·관계 모순 → NOT_VERIFIABLE(공개하지 않음). 판정 = VERIFIED(정해진 범위에서 위험 미검출) / FAILED / NOT_VERIFIABLE — NOT_VERIFIABLE 을 PASS 로 바꾸지 않음.
- **검증 불가 처리**: 검증 범위 밖이면 해당 표 비공개. 비공개 사유는 일반 문구만(어느 칸·값 때문인지 비공개, 내부 기록에만).
- **남은 위험(명시)**: 3개 이상 칸의 부등식·비선형 관계·LP 완화의 정수 간극은 미검사 · 관계는 합성 자료 기반(실제 자료에만 있는 우연한 관계 미검사) · 과거 공개 EXP-02 집계와의 결합 미검사(이미 공개된 값은 되돌릴 수 없음 — 이번 보고서에서 추가 노출 방지만) · 재검증은 내부 정확 집계 접근 권한자만 재현 가능 · 공개 표가 비공개됐다는 사실 자체는 '그 표에 작은 칸이 있었다'는 정보를 줌(값 아님).
- **연구 지표와 공개 분리**: 모든 지표 계산·성공 판정은 내부 정확 집계로 수행. 공개 축소는 계산 결과를 바꾸지 않음. 내부 집계는 삭제·덮어쓰기 금지.
- 이 개정은 개인정보 보호(공개 방식) 변경이며, 시간 정책·진단 안전망 기능 정의는 바꾸지 않음.

## 9-3. 공개 보호 2차 개정(2026-11-03, 마지막 기록 gate 20261103_173120 지적 대응 — gate 재심 없이 코드·합성 시험까지만) — §9-2 의 관계·공개 범위 부분을 대체
- **상태**: 재심사 없음, 승인 아님. EXP-MAI-003 은 NEEDS_FIX·UNLOCKED 그대로. 실제 MIMIC 미실행.
- **관계 출처 변경**: 합성 자료에서 찾은 관계를 규칙으로 쓰지 않는다. 관계 = `disclosure_schema.py` 가 §2–§6·time_v1 정의·reassess.py 규칙에서 선언한 등식·쌍별 부등식·다항 부등식(Σc·x ≤ 0)·정의상 0 칸·외부 공개값 칸. 파일 `disclosure_relations/relations_v3_schema.json`(`build_relations_v3.py` 생성). `relations_v2.json` 은 보존·미사용.
- **합성 자료의 역할(`synth_random_v2.py`)**: (1) 선언 대조 — 합성 전부에서 거짓이면 생성 실패. (2) 상수 칸 분류 — 정의상 0(`constant`, 공격자 지식) / 생성기 미도달(`generator_constant`, 공격자 지식 아님, 실제 값이 다르면 그 칸 비공개). (3) 빈틈 대조 — 합성 영공간 관계 중 선언 span 밖 = `untrusted_cells`(공개 금지). 쌍별 부등식 중 선언으로 설명 안 되는 것은 규칙으로 쓰지 않고 건수만 `coverage_report`.
- **거짓 관계 처리**: 이번 자료에서 거짓인 선언 관계·상수 → 지우고 통과시키지 않고 그 칸 전부 NOT_VERIFIABLE → 표 비공개(첫 검증 전). '이번 자료에서 참인 관계만 쓰면 보수적'이라는 §9-2 서술은 폐기.
- **FAILED 규칙**: 공개 정수 1–9 = FAILED. 정수 범위 [lo, hi] 에서 hi ≥ 1, lo ≤ 9, 1 이상 후보 수(hi − max(lo,1) + 1) < 5 = FAILED(0 포함 범위·9 걸친 범위 포함). 값 5 는 정책 선택('<10' 후보 9개의 절반 미만이면 실패). 실행 후 변경 금지.
- **외부 결합**: `EXTERNAL_MAP` 의 EXP-02 공개값(체류·환자·lab·radiology·ecg 행 수)은 이번 공개본과 무관하게 공격자 지식. 값은 EXP-02 공개 파일에서 읽음. 이번 입력과 다르면 결합 모형 불성립 → 전 자료 표 비공개. 내부 칸 `patients_without_evaluable_stay` 추가(공개 안 함) → 코호트 환자 − 평가 환자 역산 차단. 평가 체류가 가려지면 평가 환자도 가림. 정의가 달라 선형 관계로 넣을 수 없는 공개 집계(시간 감사 CTA 행 수, Ext-PE 등)와 겹칠 수 있는 칸(영상 유형 등)은 공개 범위에서 제외.
- **공개 범위**: T1 요약·T2 병합 범주만 후보. T3 세부(flag·등급·C 입력·범주·8×8 교차표·세부 기록 집계)는 검증 결과와 무관하게 외부 공개 제외. 이 표들의 §6 지표는 내부 정확 집계로만 산출. 공개 숫자 최대화는 목표가 아님. 공개 표가 0개여도 비공개는 실패 아님 — 공개 표 수·비공개 표 목록을 보고.
- **내부 집계**: 덮어쓰기 거부, 권한 700/600. 공개 파일은 임시 이름으로 쓰고 재검사 통과 후 공개 이름으로 교체. EXP-02 동결 추출 폴더를 `--internal-out` 으로 지정 금지.
- **남은 위험(명시)**: (a) 선언 완전성 보장 없음 — 합성이 드러내지 못한 구조적 관계는 놓칠 수 있음. (b) 선언으로 설명 안 되는 합성 쌍별 부등식 다수는 대부분 소규모 자료 우연으로 보나 전수 검토 안 함. (c) 생성기 미도달 칸은 실제 값이 0 이면 공개되며 관계 검사가 약함. (d) LP 완화의 정수 간극·비선형 관계·표에 없는 작은 합 미검사. (e) 최종 재검사는 같은 검증기의 재적용. (f) 재검증은 내부 정확 집계 접근자만 가능. (g) EXP-02 외 공개 집계와의 결합은 범위 제외로만 대응. (h) 비공개 사실 자체가 '작은 칸이 있었다'는 정보를 줌.
- **정수 재확인(2026-11-04)**: LP 로 통과한 뒤 최종 판정에서 상한 40 이하 칸을 정수 계획(`milp`)으로 재확인, 풀지 못하면 NOT_VERIFIABLE. 남은 위험 (d) 의 정수 간극은 상한 40 초과 범위로 줄어듦.
- **이미 공개된 시간 감사(`mimic_time_audit_public.json`)**: 실행 시 EXP-02 공개값과 일치 확인(불일치 시 실행 거부). 정의가 달라(체류 창 중복 사건·행 단위) 선형 관계로 넣지 않고, 겹칠 수 있는 세부 칸(영상 유형·flag·등급)은 공개 범위에서 제외.
- **결함 주입 범위**: X5 는 §9-2 환자 정책 탓에 동치였으나 평가 체류↔평가 환자 짝 추가 후 재평가(결과는 TRACKING 기록). 생존 결함은 PASS 로 처리하지 않고 기록.

## 10. 실행 자원·시간 추정
- 합성 규모 시험(`bench_v2.py`, 실제 자료 아님)으로 추정 후 manifest 에 기록. 판독 원문은 CT 계열·exam 결측 문서만 필터 로드, 분류 후 즉시 해제. 실행 = nohup + ram_guard 90%, OMP/OPENBLAS/MKL_NUM_THREADS=1.

## 11. 테스트·결함 주입
- 공개 보호(2026-11-03 개정): `tests/test_disclosure_v2.py` — 합성 역산 공격(전체−부분, 행 합, 열 합, 교차표, 정책 간 차이, 정확·반올림 비율, 차이 출처, 여러 표 연쇄, 집단 중첩 부등식, 여러 작은 칸 동시, 비공개 칸의 다른 표 경유 복원, 여러 시점, 분모 재사용, 요약↔세부), NOT_VERIFIABLE ≠ PASS, 정상 대조군, 검증기 독립성(import 검사), 보호 단계, 끝단(공개 파일 재검증·보호 우회 → ABORT·heuristic 만 → ABORT). 결함 D1–D7(검증기 비율 규칙·범위 검사·부등식·후보 수, 보호 비공개 무력화, 환자 정책, 공개 파일 재검사 해제).
- 2차 개정(§5-1·§9-3): `tests/test_disclosure_v3.py` — 거짓 관계·상수, 0 포함 범위, 1–9 직접 공개, EXP-02 공개값 결합, 공개 범위, addendum 시간 순서, 내부 집계 보존, 합성 끝단 공격. `fault_v2.py` 에 D8–D21·O1–O5 추가.
- `tests/test_v2.py`: 합성 parquet(`tests/fixture_v2.py`, 가짜 MIMIC 형식 ID) 정확값 표(실행 전 고정).
- `fault_v2.py`: run 스크립트 포함 전체 경로 결함 주입 — 요구 13종(F01–F13, F10·F11 은 a/b 2종씩) + 추가 F14·F15 + 검사기 약화 X1–X11. 대조(CONTROL) OK + 결함마다 FAILED 이어야 통과, 결함별 발동 위반 이름 기록.
- seed: 결정적 집계라 의미 없음(0 기록은 형식상).
- 코드 동결 절차(2026-11-04 변경): 전체 검증을 마친 코드로 **gate 전** `--write-code-sha outputs/CODE_SHA256_<시각>.json`(자료 읽지 않음, 덮어쓰기 거부), 그 파일 SHA 를 manifest `code_sha_manifest_sha256` 에 기록 → reviewer 는 동결된 코드를 심사 → 본실행은 `--code-sha-manifest` 필수(불일치 시 데이터 읽기 전 ABORT).

## 12. 실제 실행 관문·1회 실행·사후 검증(2026-11-04)
- **권한 구분**: 코드 변경 기록(`deviations.yaml`, `rg.py` 가 항상 status APPROVED 로 기록) ≠ 연구 계획 ≠ rg-gate 통과 ≠ 실행 승인. deviation 은 변경 기록일 뿐 실행 권한이 아니며, 실행 경로는 deviations.yaml 을 읽지 않는다.
- **관문**(`gate_authorization`, 자료를 읽기 전): review_status = RUN · 마지막 gate 판정 = RUN·보고서 존재 · protocol.lock 존재·`rg.py check` OK · 동결 코드 목록 SHA = manifest 기록값. 하나라도 어긋나면 실행 거부. 추가로 `--i-have-user-approval`·`--rad-detail`·`--code-sha-manifest`·`--internal-out` 필수.
- **1회 실행**: 관문 통과 직후 `outputs/EXP_MAI_003_COUNTED_RUN_USED` 를 O_EXCL 로 생성. 이미 있으면 거부. 실행이 실패·중단돼도 표지를 지우지 않으며 재실행하지 않는다(실패 보고).
- **결과 위치**: 공개 = `outputs/real_run_<시각>/`(공개 JSON + RUN_RECORD.json: SHA·이름만), 내부 = `/home/<user>/medmap_exp02_sealed/exp03_time_v2_internal_<시각>/`(권한 700/600, 세션·reviewer 미열람, 덮어쓰기 거부).
- **사후 검증**(`verify_counted_run.py`, 로컬 실행, 재실행 없음, 값·식별자 비출력): 실행 횟수·표지 · 코드 SHA(동결=현재=공개 기록) · 입력 SHA · 프로토콜 버전 · 출력 SHA · 원 parquet 에서 분모 재계산 대조(체류·환자·고유 기록·중복·귀속·연결, 독립 감사 모듈) · stay_id 유일·체류당 환자 1명 · §6 정의 항등식(정책별 합) · 공개값 = 내부값·토큰 일치·1–9 없음·세부 표 비공개·비율 재계산 · 공개 파일 재검증(정수 재확인 포함) · 식별자 패턴 없음 · EXP-01 FINAL SHA·표지·EXP-02 동결·봉인 권한 · gate 관문 재확인. 결과 `outputs/real_run_<시각>/VERIFY_<시각>.json`. 누출·체류 혼합 감사(계층 A·B)는 실행 중 판정이라 여기서는 기록만 확인(재계산 안 함 — 한계).
- **/rg-verify**: `experiment-verifier` 가 manifest·lock·공개 JSON·RUN_RECORD·VERIFY JSON·로그 토큰을 대조. 봉인 내부 집계·원 parquet·판독 원문은 읽지 않는다. 그래서 내부값 대조는 로컬 스크립트 결과를 근거로 함(한계 명시).
- **세션 공개 범위**: 세션은 공개 JSON·VERIFY JSON 만 읽음. 세부 표(§9-3 T3)의 값은 세션 보고에도 쓰지 않음.

## 변경 기록
- 2026-11-03 v2 작성(1차 gate 지적 반영). v1 무수정.
- 2026-11-03 2차 gate(20261103_115323_NEEDS_FIX) 반영: 연결 addendum 가족 귀속(§4), 대체 쌍·NO_MENTION 원 판독 분류표(§5), 포함률 차이 코드 산출·교차표 범주 = 상태+근거·결정 상실/획득(§6), 계층 이름 정리·dtype 방어(§7), 전역 보완 마스킹·환자 칸 연동·잔여 위험 명시(§9), 코드 SHA 동결 절차·필수화(§11). 실행 결과 미관찰(실제 자료 미실행).
- 2026-11-03 v1 문서 정정 기록(v1 파일은 보존·무수정): time_v1/PROTOCOL_TIME.md §7 의 `tests/test_time_faults.py` 는 존재하지 않음 — 실제 결함 주입 = `time_v1/fault_time.py`(1차 gate MINOR).
- 2026-11-03 3차 개정 중 합성 규모 시험에서 다른 환자 addendum 연결이 가족 귀속으로 환자 간 이동 가능함을 발견(안전 검사 ABORT) → 연결 조건에 같은 subject 추가(deviation 23, 실행 전).
- 2026-11-03 3차 gate(20261103_152143_NEEDS_FIX) 반영: 상이 체류 정확 항등식 묶음·정책/시점 간 같은 양 묶음(§9), 미연결 AR 한계·유효 체류 수 사전 지정(§5), 계층 B 목록 정리·linked_addendum 건수 비대조 명시(§7), §5 문구 정정. 실행 결과 미관찰.
- 2026-11-03 4차 gate(20261103_153500_NEEDS_FIX) 반영: 같은 양 묶음을 2칸 사슬로 교체(3칸 묶음은 보완이 2칸에서 멈춰 역산 가능), lab 등급·C 입력 사슬 추가(§9). 실행 결과 미관찰.
- 2026-11-03 5차 gate(20261103_154503_NEEDS_FIX) 반영: 같은 양 사슬을 일반 규칙(모든 원천 flag·등급·C 입력·사용 칸 세 정책)으로 확장, graph_kb_sources 기록(§6·§9). 실행 결과 미관찰.
- 2026-11-03 공개 집계 보호 구조 개정(§9-2) — 사용자 지시: 반복 재심사 중단·근본 원인 해결·정식 gate 1회. 6차 심사는 reviewer 실행 후 기록 명령이 사용자 거부로 미실행(공식 기록 없음). 관계 발견 중 발견한 독립 감사 빈 표 처리 결함 2건·영상 키 결측 처리 결함 1건 수정(계산 결과 영향 없음, 비정상 종료 방지). addendum 이 원 판독보다 먼저 저장되면 reassess.py 가 비정상 종료하는 문제는 미해결(시간 정책 범위 — 별도 결정 필요). 실행 결과 미관찰.
- 2026-11-03 공개 보호 2차 개정(§5-1·§9-3) — 사용자 지시: 7차 재심사·실제 MIMIC 미승인, 지적 결함 수정 후 종료. 스키마 선언 관계로 교체, 거짓 관계 칸 비공개, 0 포함 범위·1–9 직접 검출, EXP-02 공개값 결합, T3 외부 공개 제외, addendum 시간 순서 제외 규칙. 기존 심사 기록 수정 없음·승인 아님. 실행 결과 미관찰(실제 자료 미실행).
- 2026-11-04 사용자 지시(남은 결함 일괄 해결 후 gate 1회, 통과 시 실제 실행 1회): §12 관문·1회 실행·사후 검증 추가, 코드 동결을 gate 전으로 이동, 기록·체류·환자 단위 분리, 정수 재확인, 시간 감사 대조, 생성기 구성비 다양화, 실제 입력 문자열 시각 열 대응. 실행 결과 미관찰.
