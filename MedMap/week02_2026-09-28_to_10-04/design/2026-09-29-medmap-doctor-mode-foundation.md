# MedMap Doctor Mode Foundation — architecture/spec 초안

- 상태: **APPROVED rev4 (2026-09-30) — §11-6 결정 (B) 반영. 구현 진행.**
- 작성: 2026-09-29, 브랜치 `feat/doctor-mode-foundation`(worktree `~/medmap-worktrees/doctor-mode-foundation`, 기준 master `d2341b5`)
- 근거: 2026-09-29 사용자 방향 프롬프트("Patient Companion 보존 + Doctor MedMap 추가"), 기획 정본 `MedMap_최종방향_v5.md` §1–§6, repo 읽기 감사(§3)
- 이 문서의 "현재 상태" 서술은 전부 2026-09-29 repo 코드 기준이다. 과거 보고서 인용 아님.

---

## 1. 목적

MedMap의 최종 메인 제품은 **의사의 현재 진단(Working Diagnosis)을 계속 다시 확인하도록 돕는 의사용 진단 안전망(diagnostic safety-net prototype)**이다.
지금까지 만든 환자용 흐름은 버리지 않고 `Patient Companion / Intake Engine`으로 재정의한다. 그 역할은
"의사가 판단하는 데 필요한 환자 정보를 빠르고 정확하게 수집하는 것"이다.

첫 milestone `Doctor Mode Foundation`의 목적:
1. Patient Companion을 **동작·계약 그대로** 보존한다.
2. Patient/Doctor 역할을 **backend domain 투영 + frontend 진입점** 수준에서 분리한다.
3. 의사가 한 환자 세션을 열어 **이미 확정된 정보 → Working Diagnosis 입력(또는 건너뛰기) → 독립 모델 감별 후보 공개 → 후보를 구분할 IG 질문에 답 → 후보·질문 재계산** 루프를 도는 기본 Dashboard를 만든다.
   핵심 가치는 후보 목록 자체보다 **"후보들을 가장 잘 나누는 다음 정보"를 기존 Internal IG가 고르는 것**이다. 새 진단 알고리즘은 만들지 않는다(Diagnosis Engine + Internal IG + PatientState 재사용).
4. Episode·Timeline·Disease Knowledge Layer·Diagnosis Coverage가 나중에 붙을 **extension point**를 명시적인 "미지원" 상태로 둔다(가짜 데이터 없음).

## 2. Non-goals (이번 milestone에서 하지 않는다)

- Diagnosis Coverage·contradiction·unexplained finding·red flag·recovery prediction의 **실제 판단** (근거 지식층 없음, §9)
- LLM으로 질환 지식을 만들어 production fact처럼 쓰기
- 진단 엔진 재학습, `model_context` 추가, IG 표 교체, MAX_QUESTIONS 변경
- Mapper(`medmap/intake/`, frozen) 수정·파일 추가
- `PatientState`/`medmap-session-v1`/`medmap-turn-v1`/`medmap-answer-v1`/`medmap-clinical-summary-v1` 의미 변경
- 기존 7개 endpoint의 입력·출력·오류 의미 변경
- 환자 화면 재설계·삭제(환자 노출 축소는 §12 Phase P로 분리, 별도 승인)
- 서버 측 저장(DB), 계정·인증, EMR 연동, 외부 배포
- Episode/Timeline backend 구현 (구조만 문서화)
- TEST·VALIDATION·STEP16B/STEP17A HOLDOUT 접근

## 3. Current architecture (2026-09-29 repo 감사)

### 3-1. git
- master `d2341b5`(= `ebc854f` C 병합 + handoff v6). 미커밋: `.claude/MEMORY.md`, `.claude/memory/` 5파일, `exp/step17a_intake_start_validation/` — **건드리지 않음**.
- 다른 worktree: `research/intake-positive-error`(D, 다른 세션 소유 — 접근 금지), `feat/web-ui`(보류, 구 UI).

### 3-2. Backend (`medmap/`, Python, FastAPI, **stateless**)
| 모듈 | 역할 | Doctor Mode에서 |
|---|---|---|
| `patient_state.py` | `PatientState`(age, sex, initial_evidence, answers{id→Answer}, asked 순서), `AnswerStatus` 5종(UNASKED는 키 없음) | 읽기만 |
| `serialization.py` | `medmap-session-v1`·`medmap-turn-v1`·`medmap-answer-v1` 직렬화/검증, turn의 `diagnoses` = top3 `{name, probability}` | 읽기만 |
| `evidence.py`·`eligibility.py` | DDXPlus 223 evidence 카탈로그(E_134/E_152 제외), 부모 gate 자격 | 재사용 |
| `diagnosis.py` | STEP16B `model_k3/k5/k10.pkl` → 49질환 posterior·ranking | 재사용(재학습 없음) |
| `next_information.py` | 내부 IG(`AnswerLikelihoodTable`), `rank_questions(diagnoses, eligible)` = IG 내림차순·동점 번호순 | 재사용(read-only 호출) |
| `clinical_summary.py` | 세션 → 확정 정보 버킷 + top3 후보 + disclaimer(결정적, 저장 없음) | 버킷 로직 재사용 |
| `terminology.py` + `data/terminology_ko.json` | 질환 49·evidence·질문·값 한국어 정본 | 재사용 |
| `speech.py` | Whisper large-v3-turbo, 한국어 고정, lazy GPU | 무관 |
| `intake/` | 자연어 → evidence 매퍼 v1.2 (frozen) | 무관 |
| `api.py` | `/health`, `/v1/session/{start,answer,resume,summary}`, `/v1/intake/extract`, `/v1/stt/transcribe` (+ dist 서빙) | **변경 없음**, 새 router 추가만 |

핵심 사실: **서버에는 세션 저장소가 없다.** 모든 요청은 클라이언트가 `medmap-session-v1` 스냅샷을 보내고 서버가 다시 계산한다.
환자 브라우저는 `sessionStorage['medmap.session']`에만 보관한다(시작 전 입력은 어디에도 저장 금지 — P2-4 계약).

### 3-3. Frontend (`medmap-web/`, React+Vite, 라우터 없음)
- `App.jsx`: `useMedmapSession().phase` 상태기계 `start → intake → consult → summary`, 단일 화면 트리.
- screens: `StartScreen`, `NaturalIntakeScreen`, `ConsultScreen`, `SummaryScreen` / components 10종 / `intake/startPlan.js`(bootstrap·rev3·START_INCOMPLETE) / `voice/` / `terminology/labels.js` + `generated/terminology_ko.json`.
- 테스트: vitest 217, e2e 6종(`natural-intake`, `flow-hardening`, `summary`, `voice-intake`, `english-audit`, `demo-https`). backend unittest 244(skip 3).

### 3-4. 데모 서빙
`scripts/demo_serve.sh` — 빌드된 dist + API same-origin, 자체 서명 HTTPS(8443), `--lan`은 사용자 직접 실행만.

## 4. Target architecture

```
[Patient Companion / Intake Engine]  ← 현재 기능 전부(변경 없음)
   자유 텍스트·STT → Mapper → 확인 → bootstrap(k3) → IG 질문 ≤3 → 요약
        │  medmap-session-v1 스냅샷 (명시적 전달, §7-3)
        ▼
[Doctor MedMap]  ← 이번 Foundation
   Patient Summary ─ Working Diagnosis ─ Independent Model Assessment ─ Next Information
   (extension slots, 전부 NOT_AVAILABLE) Timeline · Diagnosis Coverage · Unexplained · Alternatives · Turning Points · Visit · Recovery
        ▼
[Re-evaluation / diagnostic safety net]  ← Phase E 이후, Disease Knowledge Layer 필요
```

계층:
1. **Engine core** (기존, 불변): PatientState · DiagnosisEngine · NextInformationEngine · Catalog · Terminology.
2. **Domain projections** (신규 순수 함수 모듈): 같은 엔진 결과를 역할별로 투영한다. 기존 `clinical_summary`는 patient projection으로 그대로 둔다. 신규 `medmap/doctor_view.py` = doctor projection.
3. **API**: 기존 router 불변 + 신규 `/v1/doctor/*`.
4. **Frontend**: 환자 앱 트리 불변 + 별도 `DoctorApp` 트리. "환자 화면을 숨기면 의사용"이 아니라 **다른 컴포넌트·다른 데이터 계약**.

## 5. Patient vs Doctor 역할 분리

| 정보 | Patient Companion | Doctor Mode |
|---|---|---|
| 이해한 증상·확인 | O | O (구조화 evidence id + 한국어 라벨) |
| 추가 질문 | 기본 흐름: IG 1개씩 ≤3(보존) / 인계 흐름: 없음(intake까지만) | 인계 흐름: **의사가** IG 질문 1개씩 답변, ≤3 (기존 한도) |
| 진단 후보 | 기본 흐름: 현재 top3(보존, Phase P에서 재검토) → **2026-10-01 환자 화면 비노출로 변경(master `08cbbd3`)** / 인계 흐름: 표시 없음 | 독립 모델 감별 후보, **순서만**, 기본 상위 5 + [더 보기]로 최대 8(§6-2), WD 입력/건너뛰기 **후에만** 공개 |
| Working Diagnosis | 없음 | 입력/선택/건너뛰기 |
| 확률 %·신뢰도·IG bits | (기본 흐름 기존대로) → **2026-10-01 환자 화면 확률 비노출(API 응답은 불변)** | **표시하지 않음**. 확률은 서버 내부에서 순서·개수 결정에만 쓰고 응답에 넣지 않는다 |
| 연구 개념(k3, bootstrap, model_context_match) | 없음 | "모델 적용 조건" 한 줄로만 |
| transcript·원문·matched_text | 저장·로그 없음 | **받지도 않음** (세션 스냅샷에 없음) |
| Timeline/Coverage/Recovery | 없음 | 슬롯만(NOT_AVAILABLE) |

분리 원칙: backend는 `doctor_view`가 **patient projection을 호출하지 않고** 엔진 core에서 직접 투영한다(한쪽 화면 수정이 다른 쪽을 바꾸지 않게). 공통 로직(확정 정보 버킷 분류)은 `clinical_summary`의 공개 함수를 **import만** 하고 복제하지 않는다.

## 6. Domain model

### 6-1. 기존 (불변)
- `PatientState`, `Answer`, `AnswerStatus`, `medmap-session-v1`, `Turn`, `DiagnosisResult`.

### 6-2. 신규 (Foundation)
```text
WorkingDiagnosis                          # 의사 입력. 서버 저장 없음, 요청 단위 값
  kind:  "CATALOG" | "OUT_OF_SCOPE"        # CATALOG = DDXPlus 49 class 중 하나
  code:  str | null                        # CATALOG 일 때 class key (예: "Bronchitis")
  label: str                               # 화면 표시명(CATALOG = terminology 한국어, OUT_OF_SCOPE = 의사 입력 문자열)
  # OUT_OF_SCOPE 는 모델이 아는 질환이 아니므로 어떤 비교·판단도 하지 않는다(에코만).

DoctorView  (schema "medmap-doctor-view-v1")  # 결정적 투영, 저장 없음
  schema_version
  patient_summary:        {age, sex, chief_complaint, confirmed_positive[], confirmed_negative[],
                           confirmed_values[], not_applicable[], unknown[], answered_questions_count}
  working_diagnosis:      {state:"PENDING"|"ENTERED"|"SKIPPED", value: WorkingDiagnosis | null}
  independent_assessment: PENDING 이면 {status:"LOCKED"} (후보를 응답에 아예 넣지 않음 — blind 는 서버에서 강제)
                          아니면 {status:"AVAILABLE", candidates:[{code, label_ko}] (순서만, 확률 없음),
                                  scope_ko:"DDXPlus 49개 질환 안에서만 고려합니다", model:{context:"k3"}}
  next_information:       PENDING 이면 {status:"LOCKED"}
                          아니면 {status:"QUESTION"|"BUDGET_REACHED"|"NONE_ELIGIBLE"|"UNSUPPORTED_SESSION_SHAPE",
                                  question: 기존 next_question 표현(presented 한국어, answer_type, 선택지) | null,
                                  questions_used, max_questions}
                          # 질문 선택 = 기존 NextInformationEngine(_run 경로) 그대로. 순위 목록·bits 비노출
  session:                갱신된 medmap-session-v1 (의사용 복사본에 저장)
  extensions:             {timeline, episode, diagnosis_coverage, unexplained_findings,
                           alternatives, turning_points, visit, recovery}
                          # 각각 {status:"NOT_AVAILABLE", reason:"<CODE>"} 고정
  disclaimer_ko
```
감별 후보 개수 규칙(rev3 사용자 결정 — 확률은 개수 결정에도 쓰지 않는다):
- 서버는 기존 `DiagnosisResult.ranking` 순서의 **상위 8개**(`DOCTOR_CANDIDATES_MAX = 8`)를 `{code, label_ko}`로만 반환한다. 누적확률·임계값 규칙 없음.
- UI는 기본 **상위 5개**(`DOCTOR_CANDIDATES_DEFAULT = 5`)를 순서대로 보이고, [더 보기]로 8개까지 펼친다. 확률·점수·순위 호칭 없음.
- 이 목록은 **표시 전용**이다. 다음 질문 선택(IG)은 화면에 보이는 subset이 아니라 기존 `_run` 경로의 전체 posterior(49질환)를 그대로 쓴다. doctor_view는 IG 입력을 만들거나 자르지 않는다.
- "목록에 없는 질환이 배제됐다는 뜻이 아닙니다" 고지 필수.
- 결정적: 같은 세션 → 같은 목록. 순서·동점 처리는 기존 ranking 그대로.

extension reason 코드: `EPISODE_BACKEND_MISSING`, `DISEASE_KNOWLEDGE_LAYER_MISSING`, `VISIT_INGESTION_MISSING`, `RECOVERY_MODEL_MISSING`. UI는 이 코드로 "아직 지원하지 않는 기능" 안내만 그린다.

### 6-3. 향후 (문서만, 구현 없음)
```text
Patient
 └─ IllnessEpisode (episode_id, opened_at, status)
      ├─ IntakeSession[]      = 기존 medmap-session-v1 스냅샷 (그대로 포함, 변환 없음)
      ├─ FollowUpSession[]
      ├─ Observation[]        (symptom_status: NEW|PRESENT|WORSENED|IMPROVED|RESOLVED|UNCHANGED|UNKNOWN, 체온, 사진 ref …)
      ├─ Visit[]              (working/final dx, 약, 검사, plan, 주의, follow-up)
      ├─ WorkingDiagnosisHistory[] (WorkingDiagnosis + 시각 + 근거 스냅샷 id)
      └─ RecoveryObservation[]
```
Session = 한 번의 interaction, Episode = 며칠~몇 주. Episode는 Session을 **감싸기만** 하고 Session 스키마를 바꾸지 않는다.

## 7. API contracts

### 7-1. 기존 7개 endpoint — 변경 없음 (회귀 테스트로 고정)

### 7-2. 신규 (`medmap/api_doctor.py` APIRouter, `api.py`에는 `include_router` 한 줄만 추가)
```text
GET  /v1/doctor/diagnoses
  → {schema_version:"medmap-doctor-diagnoses-v1",
     diagnoses:[{code, label_ko}] (49, terminology 정본 순서 또는 한국어 가나다)}

POST /v1/doctor/view      # 읽기: 현재 세션의 의사용 투영
  body: {session: medmap-session-v1,
         working_diagnosis: {state:"PENDING"} | {state:"SKIPPED"}
                          | {state:"ENTERED", value:{kind:"CATALOG", code} | {kind:"OUT_OF_SCOPE", label}}}
  → medmap-doctor-view-v1

POST /v1/doctor/answer    # 쓰기: IG 질문에 의사가 답 → 재계산
  body: {session, working_diagnosis (ENTERED|SKIPPED 만; PENDING → 409 MEDMAP_WORKING_DIAGNOSIS_PENDING),
         answer: medmap-answer-v1 submission (기존 형식 그대로)}
  → medmap-doctor-view-v1 (갱신된 session 포함)

공통
  검증: session 은 기존 deserialize_session 그대로(같은 오류 코드).
        CATALOG code 가 49 class 밖 → 400 MEDMAP_INVALID_WORKING_DIAGNOSIS.
        OUT_OF_SCOPE label: 1–80자, 제어문자 금지, 로그에 남기지 않음.
  계산: 기존 api._run(state, model_context, submission) 를 **그대로 호출**(로직 복제 없음) → 같은 IG 질문 선택·같은 한도(MAX_QUESTIONS=3)
        ·같은 409 규칙(MEDMAP_UNEXPECTED_ANSWER 등). 그 결과 turn 을 doctor_view 가 투영:
          후보 = turn 의 DiagnosisResult ranking 상위 8 (확률 제거, 표시 전용 — IG 계산에 관여하지 않음)
          다음 질문 = turn.next_question 표현만(IG 값 제거)
        _run 이 private 이므로 api.py 에서 공개 함수로 노출하는 것은 **이름만 추가**(기존 함수 본문 불변).
  blind: working_diagnosis.state == PENDING 이면 후보·질문을 계산은 해도 응답에서 제외(LOCKED).
  working_diagnosis 는 Foundation 에서 에코만 한다. 후보와의 비교·순위·일치/불일치 판정을 반환하지 않는다.
```
- 둘 다 stateless, 서버 저장 없음. `LOG_PAYLOAD` 규칙 동일(OUT_OF_SCOPE label은 payload 로그에서도 제외).
- 오류 envelope은 기존 `{"error":{code,message,field}}` 그대로.

### 7-3. 환자 → 의사 데이터 전달 (결정: 같은 브라우저 인계, 서버 저장 없음 — rev4 §11-6 B)
- **인계 흐름(`#/handoff`)**: 자유 텍스트/음성 → 확인 → bootstrap → `/v1/session/start`(exact-k3)까지만. **자동 적용(settle) 없음.** 저장 `medmap.handoff.session` + `medmap.handoff.cache`. IG 질문은 환자에게 묻지 않는다.
- **Doctor 진입(`#/doctor`)**: `medmap.handoff.*`(없으면 기본 흐름 `medmap.session`)을 **읽기만** 해 사본 `medmap.doctor.session`/`medmap.doctor.cache`를 만든다. 의사 답변은 사본만 갱신. JSON 붙여넣기/파일 불러오기 지원.
- IG가 고른 질문이 사본 cache에 있으면 "환자가 이미 말한 내용"으로 보여주고, 의사가 확인해야만 answer로 반영(자동 제출 없음). 한도는 start 이후 IG 3문항 그대로.
- 기본 환자 흐름(해시 없음)은 **변경 없음**(자동 적용 포함). 기본 흐름을 끝까지 한 세션을 불러오면 `BUDGET_REACHED`.
- 휴대폰→의사 PC QR/코드 인계는 Episode/공유·인증 단계(Phase A).

## 8. Frontend flow

- 진입: 해시 경로 3개 — 없음(기존 환자 App, **바이트 단위로 같은 트리**) · `#/handoff`(인계용 환자 intake) · `#/doctor`(DoctorApp). 라우터 라이브러리 추가 없이 `main.jsx`에서 `location.hash`로 선택.
- `HandoffApp`: `StartScreen` → `NaturalIntakeScreen`(기존 컴포넌트·`useMedmapSession` 재사용) → start 성공 시 인계 완료 화면. consult/summary 화면으로 가지 않는다.
  `useMedmapSession` 수정 없이 가능한지 plan 단계에서 확인(불가하면 옵션 인자 1개 추가를 별도 승인 항목으로 보고).
- `DoctorApp` 상태기계: `load` → `wd`(Working Diagnosis 입력/건너뛰기, 후보·질문 LOCKED) → `review`(후보 공개 + IG 질문 답변 루프) → 한도 도달/질문 없음이면 루프 종료, 화면 유지.
- Dashboard 영역(위→아래, 모바일 1열 / 1280 2열):
  1. 환자 요약 — 나이·성별·주 증상·있음/없음/값/모름·답한 질문 수(환자 답/의사 답 구분은 프론트 표시 계층에서만, 세션 스키마 불변)
  2. Working Diagnosis — 49질환 검색 선택 + "목록에 없는 진단 직접 입력"(OUT_OF_SCOPE: "모델 지원 범위 밖이라 비교하지 않습니다") + [건너뛰기]. 입력 후 수정 가능, 단 이미 공개된 후보는 다시 숨기지 않음
  3. **현재 정보에서 독립 모델이 고려한 감별 후보** — 순서만, 확률·순위 호칭 없음, "DDXPlus 49개 질환 안에서만 고려합니다", "목록에 없는 질환이 배제됐다는 뜻이 아닙니다"
  4. **후보를 구분하기 위해 추가로 확인할 정보** — 기존 IG 질문 1개 + 답 버튼(기존 `QuestionPanel` 표현 재사용: 예/아니요/잘 모르겠어요 또는 값 선택). 답하면 `/v1/doctor/answer` → 3·4 갱신. "질문 N / 3"
  5. 준비 중 영역 — Timeline / Diagnosis Coverage / 설명이 부족한 정보 / 놓치기 쉬운 대안 / 진료 정보 / 회복 경과: 각 1줄 "아직 지원하지 않습니다(근거 데이터 준비 중)"
- 새 파일: `src/doctor/DoctorApp.jsx`, `src/doctor/useDoctorSession.js`, `src/doctor/sections/*.jsx`, `src/doctor/copy.js`, `src/handoff/HandoffApp.jsx`, `src/api/doctorClient.js`. 기존 파일 수정은 `main.jsx`(진입 분기)와 `api/client.js`(export 추가만).
- 디자인: 최종 UI redesign은 여전히 PAUSED. Foundation Dashboard는 기존 `plain.css` 수준 구조 화면으로 만들고, 시각 디자인은 redesign 단계에서 한다.
- 한국어 문구는 정본 terminology + 신규 문구는 `src/doctor/copy.js` 한 곳(하드코딩 번역 금지 원칙 유지 — 질환·질문 라벨은 정본에서만).

## 9. 지금 가능한 것 / Disease Knowledge Layer 없이는 불가능한 것

| 기능 | Foundation | 이유 |
|---|---|---|
| 확정 정보 표시 | **가능** | PatientState 그대로 |
| Working Diagnosis 입력 | **가능** | 49 class + OUT_OF_SCOPE |
| 독립 모델 감별 후보(순서만) | **가능(한계 표기)** | STEP16B 모델. 보정 미검증 → 확률 비노출. 49질환 범위 한정 |
| 후보를 구분할 다음 질문 + 답변 후 재계산 | **가능(검증 범위 안)** | 기존 `_run` 경로 그대로, 인계 흐름에서 질문 0→3 = STEP16B 검증 조건(k3 시작, IG ≤3)과 같음 |
| WD vs 모델 후보 "일치/불일치" | **하지 않음** | 사용자 결정. Phase E(Disease Knowledge Layer 이후) |
| Diagnosis Coverage / Unexplained finding | **불가** | 질환별 supporting/conflicting/important negative 지식 없음. STEP13B 외부 verifier NO_GO(AUROC 0.478) |
| 대안 진단 "놓치면 안 되는" | **불가** | severity·위험도 지식 없음 |
| 체온·사진·검사 등 NBI 2.0 | **불가** | DDXPlus에 해당 evidence·value 모델 없음 |
| Timeline / Temporal AI | **불가(Phase A–C)** | Episode 저장·시간 상태 없음, DDXPlus에 시간축 없음 |
| Recovery | **불가(Phase L–N)** | expected course 지식 없음 |

## 10. Clinical claim boundaries

- 금지(UI·문서·커밋 메시지): "오진을 잡았습니다", "현재 진단이 틀렸습니다", "이 질병이 확실합니다", "MedMap이 오진을 예방합니다", "최종 진단", "확정 진단", "불일치 확정", "진단 오류".
- 허용: "현재 진단을 다시 확인하는 데 참고할 정보", "추가 확인이 필요한 정보", "독립 모델 평가에서 고려된 후보", "현재 입력을 기반으로 한 진료 참고 정보", "diagnostic safety-net prototype".
- 모든 Doctor 화면 하단 고정 문구: "합성 데이터(DDXPlus)로 학습한 연구용 프로토타입입니다. 실제 환자 데이터로 검증되지 않았으며 진단 결과가 아닙니다."
- 금지 표현은 테스트로 강제(§14 claim lint).

## 11. Semantic 결정 (사용자, 2026-09-29~30)

1. **환자→의사 전달** = 같은 브라우저 인계, 서버 저장 없음, 시연용 JSON 붙여넣기/파일 불러오기. QR/코드 인계는 Episode/공유·인증 단계로.
2. **WD와 모델 후보** = Blind. WD 입력 또는 건너뛰기 전에는 후보·질문을 서버 응답에서 제외. 비교·불일치 판정 없음.
3. **확률** = 표시하지 않음. 감별 후보는 모델 순서로만, 숫자 확률·신뢰도 비노출. 가치의 중심은 IG가 고르는 "후보를 구분할 다음 질문"과 답변 후 재계산.
4. **질문 한도** = 인계 흐름에서 환자는 intake(start)까지만, IG 질문은 의사 화면에서 기존 한도 3 안에서. 기본 환자 흐름은 보존.
5. **후보 개수**(rev3) = 기본 상위 5, [더 보기]로 최대 8. 누적확률 기준 폐기(보정 미검증). 표시 subset은 IG 범위를 제한하지 않는다(§6-2).

6. **(rev4 결정: B) 인계 흐름은 자동 적용 없이 cache 보존 → IG가 선택했을 때 "환자가 이미 말한 내용"으로 제시, 의사 확인 후에만 answer 반영.** exact-k3 이후 IG 최대 3문항(STEP16B) 그대로. 기본 환자 흐름의 자동 적용은 불변.
   - 인계 흐름은 `useMedmapSession`을 쓰지 않는 별도 hook(`useHandoffSession`)으로 `/v1/session/start`만 호출(`settle` 없음). 저장: `medmap.handoff.session` + `medmap.handoff.cache`(cache 형식은 기존 `sanitizeCache` 그대로 `{evidence_id, status}`, 원문 없음).
   - Doctor 사본: `medmap.doctor.session` + `medmap.doctor.cache`. 인계 원본은 읽기만. cache 항목은 의사가 해당 질문에 답하면 사본 cache에서만 제거.
   - 검토 기록(아래는 결정 전 분석):
   - 사용자 요구: 환자 자유입력·bootstrap evidence는 전부 보존, Doctor 질문 N/3은 Doctor 진입 후 IG가 새로 고른 질문만 센다. session-v1·`/session/start`·`/session/answer` 불변, 한도 6 금지, STEP16B 범위 유지.
   - 코드 확인 결과(2026-09-30):
     a. `start()`의 자동 적용은 `settle()` → 기존 `POST /v1/session/answer`다. 적용되는 것은 **IG가 방금 제안한 질문**에 대해 intake cache(`medmap.intakeCache`, 환자가 말했지만 start에 못 넣은 binary 답)가 일치할 때뿐이며, 결과는 세션의 `answers`·`asked_question_ids`에 일반 답과 **구분 없이** 기록된다(설계 문서 §7-4 "자동 반영도 질문 예산 1개를 씀").
     b. `_run`의 한도는 `questions_used = n_additional − k`(세션 상태에서 계산, `tests/test_api.py::test_23`). 엔진은 `MAX_QUESTIONS − used`만큼만 질문을 고른다.
     c. STEP16B 3Q = **exact-k3 start state 이후 IG가 순차로 고른 질문 3개**(답은 환자 기록에서). 자동 적용된 질문도 IG가 고른 질문이므로 이 정의상 IG 3Q 중 하나다.
   - 결론: 자동 적용 j개 뒤에 Doctor가 "새로" 3개를 더 물으면 start 이후 IG 질문이 j+3개(최대 6)가 되어 **STEP16B 검증 범위(3Q)를 넘는다.** 이것은 한도를 늘리는 것과 같은 효과이고, Doctor 카운터만 따로 두어도 `_run` 한도(세션 상태 기반)와 충돌해 `_run`을 우회하거나 세션 계약을 바꿔야 한다 → **구현하지 않고 보고.**
   - 참고 사실: cache 중 IG가 제안하지 않은 evidence는 현재도 PatientState에 들어가지 않는다(exact-k3 start 계약 때문). "환자 evidence 전부 PatientState에 보존"도 현 계약상 불가능하며, Doctor 사본에는 세션 + cache를 **함께 복사**해 보존하는 것까지만 가능.
   - 검증 범위 안의 대안(결정 필요):
     (A) 한도는 start 이후 IG 3개 그대로, **표시만 분리**: "환자 말로 이미 확인된 IG 질문 j개" / "의사가 확인한 질문 k개", j+k ≤ 3.
     (B) 인계 흐름에서 자동 적용을 하지 않고(`settle` 미사용) 세션을 used=0으로 넘김 → Doctor 루프에서 IG가 cache에 있는 질문을 고르면 "환자가 이미 말한 내용"으로 제시·확인 후 반영. 한도는 동일하게 3(환자 말로 채운 것도 1개로 셈). 환자 원 입력은 버리지 않음.
     (C) Doctor 새 질문 3개를 별도로 보장 = 새 검증 필요(사전등록·fresh split, 연구 트랙). Foundation 범위 밖.

향후 Disease Knowledge Layer가 생기면 이 감별 후보 루프 위에 Working Diagnosis Validation · Diagnosis Coverage · Unexplained Findings · Missed Alternative Detection을 **추가 레이어**로 얹는다(루프 자체는 바꾸지 않음).

## 11-1. 구현 반영 기록 (2026-09-30, 리뷰 후)

- `patient_summary`는 `answered_questions`(목록)와 `questions_used`를 그대로 담는다(§6-2 초안의 `answered_questions_count` 대신 — 화면이 목록 길이로 개수를 표시).
- 고정 disclaimer는 응답 키(`disclaimer_ko`)가 아니라 Doctor 화면 문구(`src/doctor/copy.js` `prototypeNotice`)로 둔다.
- 화면 영어 노출 0 규칙 때문에 `scope_ko`·하단 고지에서 "DDXPlus"를 빼고 "모델이 학습한 49개 질환", "합성 데이터"로 표기한다.
- `/v1/doctor/answer` 본문 키는 기존 `/session/answer`와 같은 `submission`(§7-2 초안의 `answer` 대신).
- 이전 환자 방지: 인계는 start 성공마다 새 식별자 `medmap.handoff.id`를 쓴다(같은 입력이면 세션 JSON이 같으므로). Doctor 사본은 `medmap.doctor.seen`(사본을 만들 때의 인계 식별자·환자 세션 원문)을 기록하고, 진입 시 바뀌었으면 사본 대신 새 원본을 연다. Doctor는 인계·환자 키에 쓰지 않는다. 한계: 기본 환자 흐름(`medmap.session`)은 식별자가 없어(그 hook 불변) 같은 입력 반복 시 구분되지 않는다.
- 인계 저장 실패 시 완료 화면으로 넘기지 않고 안내한다(이전 상담이 열리는 것 방지).
- "환자가 이미 말한 내용"은 YES_NO 질문에만 표시(기존 `cachedAnswerFor`와 같은 조건).
- (2026-10-02) 제품 정체성 v5 정렬: 이 Foundation은 진단 안전망의 **기반**이며, WD Validation·Coverage·Unexplained·Missed Alternative·Recovery Deviation은 미구현·미검증(`PRODUCT.md`). 환자가 확인했지만 start에 들어가지 못한 소견(cache)의 Doctor 화면 **표시**는 별도 변경(feat/v5-alignment, 표시만·자동 적용 없음)

## 12. Roadmap (Foundation 이후, 각 phase 별도 spec·승인)

| Phase | 내용 | 선행 조건 |
|---|---|---|
| P | 환자 화면 노출 축소(raw 확률·항상 top3 제거, 누를 것 줄이기) — **부분 완료 2026-10-01: 후보·확률 제거(`08cbbd3`)**, 누를 것 줄이기는 남음 | 사용자 승인, redesign과 묶음 |
| A | Illness Episode (서버 저장소·공유·인증·QR 인계 설계 포함) | 사용자 승인 |
| B | Patient Timeline | A |
| C | Temporal Symptom AI (NEW…UNKNOWN 상태 추출) | B, 새 평가셋 사전등록 |
| D | **Disease Knowledge Layer** (provenance 필수, 사람 검수, 출처 없는 fact 금지) | 별도 연구 트랙 |
| E | Working Diagnosis Validation | D |
| F | Diagnosis Coverage | D, E |
| G | Unexplained Finding Detection | D, F, 새 사전등록·fresh split |
| H | Blind Independent Second Opinion (Foundation blind 게이트를 확장: WD 이력·공개 시점 기록) | Foundation, A |
| I | Missed Alternative Detection | D(severity) |
| J | Next-Best-Information 2.0 (질문 외 정보원) | D, 새 데이터 |
| K | Diagnostic Turning Point | B, 세션 이력 |
| L | Visit ingestion | A |
| M–N | Recovery Model / Deviation | D(expected course), L |
| O | 최종 Doctor Dashboard + redesign | 위 전부 |

## 13. Backwards compatibility / migration

- 기존 7 endpoint·4 schema·환자 UI 트리·startPlan 규칙·매퍼·모델 파일 **무변경**. 변경 파일 화이트리스트: `medmap/api.py`(include_router 1줄 + `_run`/`_restore` 공개 별칭 추가, 본문 불변), `medmap-web/src/main.jsx`(진입 분기), 필요 시 `medmap-web/src/api/client.js`(export 추가만). `useMedmapSession.js` 변경이 필요하면 별도 승인.
- 신규 파일만 추가: `medmap/doctor_view.py`, `medmap/api_doctor.py`, `tests/test_doctor_*.py`, `medmap-web/src/doctor/**`, `medmap-web/src/handoff/**`, `medmap-web/e2e/doctor-mode.e2e.mjs`.
- 데이터 migration 없음(서버 저장 없음). Episode 도입 시에도 `medmap-session-v1`은 포함만 한다.
- 병합: 전용 worktree에서 구현 → 검증 → merge-ready 보고 후 중단. master merge는 사용자 명령 시에만.

## 14. Test plan

- Backend: 기존 244 green 유지 + `test_doctor_view.py`(결정성, 버킷이 clinical_summary와 동일, **응답 어디에도 probability/IG 키 없음**, PENDING이면 후보·질문 키 부재, 후보 최대 8·순서가 ranking과 동일, **IG 질문이 후보 subset과 무관함**(ranking 9위 이하 질환에만 영향 주는 상태에서도 `/session/answer`와 같은 질문), WD 검증·에코, extensions 전부 NOT_AVAILABLE, OUT_OF_SCOPE 로그 미기록) + `test_doctor_api.py`(`/doctor/answer`의 다음 질문·session이 같은 입력의 `/session/answer`와 **동일**함을 대조 — 로직 동일성 증명, PENDING answer 409, 한도 3 → BUDGET_REACHED, 오류 envelope, 기존 endpoint 응답 스냅샷 불변).
- Frontend: vitest 217 green 유지 + `src/doctor/**`·`src/handoff/**` 단위(blind: WD 전 후보 DOM 부재, 확률 문자열 `%` 부재, 답변→재계산, 환자 원본 `medmap.session` 불변, 잘못된 JSON) + `main.jsx` 분기(해시 없음 → 기존 App 동일).
- e2e: 기존 텍스트 계열 5종 green + `doctor-mode.e2e.mjs`(`#/handoff` intake → start → `#/doctor` → WD 건너뛰기/입력 → 후보 공개 → 질문 3개 답 → BUDGET_REACHED, 390/1280) + english audit를 handoff·doctor 경로까지 확장.
- Claim lint: 빌드 산출물·`src/doctor/**` 문자열에서 §10 금지 표현 0건(대조군: 금지어를 넣은 fixture가 실패하는지 먼저 확인).
- 음성 e2e: GPU `--check` OK일 때만(Doctor Mode는 STT 무관, 회귀 확인용).
- 자원: 전부 CPU·수 분 이내. 모델 로드 RAM ≈ 기존 API 수준. 긴 실행 없음.

## 15. Security / privacy

- 서버 저장 없음 유지. Doctor view도 요청 단위 계산 후 버린다.
- transcript·원문·matched_text는 세션 스냅샷에 없으므로 Doctor 경로로 전달될 수 없다(구조적 보장).
- 인증 없음 → Foundation은 **로컬 시연 전용**. `--lan`에서도 `#/doctor`는 같은 브라우저 저장본/붙여넣은 JSON만 보여준다. 실제 배포는 인증·권한 설계 전 금지.
- OUT_OF_SCOPE WD 문자열은 로그 금지.

## 16. Risks

| 위험 | 대응 |
|---|---|
| 모델 후보를 의사가 "AI 판정"으로 읽음(anchoring·자동화 편향) | 서버 강제 blind, 고정 disclaimer, 순위·확률 비노출 |
| 상위 5/8 목록이 "나머지 배제"로 읽힘 | 고지 문구 필수 |
| 표시 subset이 IG 입력으로 새어 들어감 | doctor_view는 `_run` 결과를 투영만, 동일성 대조 테스트 |
| 의사가 환자 대신 답해 환자 보고와 의사 확인이 섞임 | 세션 스키마 불변이라 구분 정보는 프론트 표시에만 — 영구 구분은 Episode/Observation(Phase A)에서 설계 |
| 인계 흐름 추가가 기존 환자 흐름을 건드림 | 별도 해시 경로 + 기존 해시 없음 경로 회귀 테스트, `useMedmapSession` 변경 시 별도 승인 |
| 49 class 밖 WD가 대부분일 수 있음(실제 임상) | OUT_OF_SCOPE 명시, 비교 안 함 |
| 인증 없는 LAN 노출 | 로컬 시연 한정, `--lan` 사용자 실행 규칙 유지 |
| 환자/의사 로직이 섞여 한쪽 수정이 다른 쪽을 깸 | 투영 모듈 분리 + 기존 응답 스냅샷 회귀 테스트 |
| 병행 세션·GPU 경합 | 구현은 CPU만, worktree 격리, `wait_for_resources` 확인 |
