# MedMap Doctor Mode Foundation — implementation plan

- 상태: **APPROVED rev2 (2026-09-30, Task 5 = 결정 B). 진행 중.**
- spec: `docs/superpowers/specs/2026-09-29-medmap-doctor-mode-foundation.md` (APPROVED rev3)
- 브랜치/worktree: `feat/doctor-mode-foundation` @ `~/medmap-worktrees/doctor-mode-foundation` (기준 master `d2341b5`)
- 방식: Task 단위 TDD(RED → GREEN), Task마다 커밋, 큰 Task 뒤 code-reviewer(opus) 리뷰. 완료 시 merge-ready 보고 후 **중단**(master merge는 사용자 명령 시에만).
- 커밋: `git -c user.name=medmap -c user.email=<email> commit` + Co-Authored-By 줄.

## 자원 계획 (병행 세션 고려)

| 작업 | 자원 | 예상 | 실행 방식 |
|---|---|---|---|
| backend unittest 전체(모델 3개 로딩) | CPU, RAM ~1–2 GB | 수 분 | `nohup` + `ram_guard.sh 90%`, 로그 `logs/doctor_*` |
| vitest | CPU | 1분 내외 | 포그라운드 가능(2분 초과 시 nohup) |
| e2e(텍스트 계열) | CPU, uvicorn 1 + headless chromium 1 | 수 분 | uvicorn `--port 8010` + dist 서빙(`MEDMAP_SERVE_WEB_DIST`), `MEDMAP_WEB=http://127.0.0.1:8010` |
| 음성 e2e | **GPU** | — | `~/scripts/wait_for_resources.sh --check` OK일 때만, WAIT면 생략하고 "미실행" 보고 |

- **포트 8000은 다른 프로젝트(changUp)가 사용 중** → vite dev proxy(8000 고정)는 쓰지 않고, e2e는 8010 dist 서빙으로 돈다. `vite.config.js`는 수정하지 않는다.
- GPU 사용 작업 없음(음성 e2e 제외). 모든 서버는 ps로 실제 PID 확인 후 kill, `pkill -f` 금지.
- 매 Task 시작 전 `free -h`(RAM 90% 상한), 병행 세션 프로세스 확인.

---

## Task 0. worktree 준비 + 기준선

1. read-only symlink(HANDOFF §3 관례):
   `ln -s ~/medmap/data data` · `ln -s ~/medmap/exp/step16b_next_information_validation/model_k{3,5,10}.pkl exp/step16b_next_information_validation/`
   (`ig_table_step16b_train.npz`는 추적 파일인지 `git ls-files`로 확인, 아니면 같은 방식 symlink)
2. `cd medmap-web && npm ci --prefer-offline --no-audit --no-fund` → `git diff --stat package-lock.json` 0 확인.
3. 기준선(변경 전): backend `~/ai_env/bin/python -m unittest discover -s tests` → **244 OK(skip 3)** 기대 · `npx vitest run` → **217** 기대 · `npm run build` OK. 숫자가 다르면 멈추고 보고(기준선이 다르면 이후 비교 무효).
4. spec rev3 + 이 plan 커밋: `docs: Doctor Mode Foundation spec rev3 + implementation plan`.

## Task 1. `medmap/doctor_view.py` — 순수 투영 (backend)

책임: 기존 `_run` 결과(turn payload)와 같은 상태의 `DiagnosisResult`를 받아 `medmap-doctor-view-v1` dict를 만든다. **엔진·IG를 호출하지 않는다**(입력만 투영).

```python
DOCTOR_VIEW_SCHEMA_VERSION = "medmap-doctor-view-v1"
DOCTOR_CANDIDATES_MAX = 8          # 표시 전용. IG 입력과 무관
WD_STATES = ("PENDING", "ENTERED", "SKIPPED")
EXTENSION_REASONS = {"timeline": "EPISODE_BACKEND_MISSING", "episode": "EPISODE_BACKEND_MISSING",
                     "diagnosis_coverage": "DISEASE_KNOWLEDGE_LAYER_MISSING",
                     "unexplained_findings": "DISEASE_KNOWLEDGE_LAYER_MISSING",
                     "alternatives": "DISEASE_KNOWLEDGE_LAYER_MISSING",
                     "turning_points": "EPISODE_BACKEND_MISSING",
                     "visit": "VISIT_INGESTION_MISSING", "recovery": "RECOVERY_MODEL_MISSING"}

def parse_working_diagnosis(raw, disease_classes) -> dict          # 검증 + 정규화, 실패 시 ValueError("MEDMAP_INVALID_WORKING_DIAGNOSIS")
def build_doctor_view(*, turn_payload, diagnoses, working_diagnosis, catalog, labels) -> dict
```
- `patient_summary`: `clinical_summary.build_clinical_summary`의 버킷을 **import해서 호출**하고 필요한 키만 골라 담는다(`diagnosis_candidates`·`disclaimer` 제외). 로직 복제 없음.
- `independent_assessment`: PENDING → `{"status": "LOCKED"}`. 아니면 `diagnoses.ranking[:8]` → `[{code, label_ko}]`, 확률 키 없음, `scope_ko`, `model:{context}`.
- `next_information`: PENDING → LOCKED. 아니면 `turn_payload["next_question"]`에서 IG 값 등 수치 키를 제거한 표현 + `stop_reason` 매핑(`MAX_QUESTIONS`→`BUDGET_REACHED`, `NO_ELIGIBLE_QUESTION`→`NONE_ELIGIBLE`, `UNSUPPORTED_SESSION_SHAPE` 그대로) + `questions_used`, `max_questions`.
- `session`: `turn_payload["session"]` 그대로.
- 테스트 `tests/test_doctor_view.py` (RED 먼저, 모델 로딩 없이 합성 DiagnosisResult/payload fixture로):
  - PENDING이면 `candidates`·`question` 키 자체가 없음
  - 응답 전체 재귀 탐색: `probability`, `information_gain`, `posterior`, 숫자 float 값 **0개**
  - 후보 순서 = ranking 순서, 최대 8, 49 class 밖 WD → ValueError, OUT_OF_SCOPE label 길이·제어문자 검증
  - patient_summary 버킷이 같은 입력의 `build_clinical_summary`와 동일
  - extensions 8개 전부 `NOT_AVAILABLE` + 정해진 reason
  - 결정성(같은 입력 2회 → 동일 dict)

## Task 2. `medmap/api_doctor.py` + `api.py` 연결 (backend)

- `api.py` 변경(본문 불변, 추가만): 파일 끝에 `from .api_doctor import router as _doctor_router; app.include_router(_doctor_router)` 및 공개 별칭 `run_session = _run`, `restore_session = _restore`, `registry = _registry`. (순환 import 방지를 위해 `api_doctor`는 함수 안에서 `from . import api` 지연 import)
- endpoints:
  - `GET /v1/doctor/diagnoses` → 49개 `{code, label_ko}` (terminology 정본, 모델 class 순서)
  - `POST /v1/doctor/view` `{session, working_diagnosis}` → `restore_session` → `run_session(state, ctx)` → 같은 결과 상태로 `registry().engine(ctx, 0).diagnosis.diagnose(state_after)` → `build_doctor_view`
  - `POST /v1/doctor/answer` `{session, working_diagnosis, submission}` → PENDING이면 409 `MEDMAP_WORKING_DIAGNOSIS_PENDING` → `run_session(state, ctx, submission)` → 위와 같음
  - 오류는 기존 `ApiError` envelope 재사용. OUT_OF_SCOPE label은 로그 미기록(LOG_PAYLOAD 경로에서도 제외).
- 테스트 `tests/test_doctor_api.py` (TestClient, 모델 1회 로딩):
  - **동일성**: 같은 session·submission으로 `/v1/session/answer`와 `/v1/doctor/answer`를 호출 → `session`, `next_question.question_id`, `stop_reason` 동일 (3턴 연속)
  - **후보 subset이 IG를 제한하지 않음**: `/doctor/view` 응답의 다음 질문 = `/session/resume`의 다음 질문 (여러 seed 세션), 그리고 doctor 후보 상위 3 이름 = resume 응답 `diagnoses` 3개 이름(같은 posterior 사용 증명)
  - PENDING view → 후보·질문 LOCKED, PENDING answer → 409, 3문항 후 `BUDGET_REACHED`, 잘못된 WD → 400, 잘못된 session → 기존 오류 코드
  - 기존 endpoint 회귀: `/v1/session/start`·`/answer`·`/resume`·`/summary` 응답 키 집합 스냅샷 불변
  - 응답 JSON 문자열에 `probability` 부재

## Task 3. 프론트 API·문구 (`medmap-web`)

- `src/api/doctorClient.js`: `getDoctorDiagnoses()`, `getDoctorView({session, workingDiagnosis})`, `submitDoctorAnswer({session, workingDiagnosis, questionId, kind, value})`. `client.js`의 `request`/`post`를 **export 추가만** 해서 재사용(기존 함수 불변).
- `src/doctor/copy.js`: Doctor 전용 문구 한 곳. 필수 문구:
  - "현재 정보에서 독립 모델이 고려한 감별 후보" / "DDXPlus 49개 질환 안에서만 고려합니다" / "목록에 없는 질환이 배제됐다는 뜻이 아닙니다"
  - "후보를 구분하기 위해 추가로 확인할 정보"
  - 하단 고정: "합성 데이터(DDXPlus)로 학습한 연구용 프로토타입입니다. 실제 환자 데이터로 검증되지 않았으며 진단 결과가 아닙니다."
  - 준비 중 영역 문구, OUT_OF_SCOPE 문구 "모델 지원 범위 밖이라 비교하지 않습니다"
- 질환·질문·값 라벨은 terminology 정본(서버 응답 `label_ko`/기존 `labels.js`)만 사용. 하드코딩 번역 금지.
- 테스트: client 요청 형태(mock fetch), copy에 spec §10 금지 표현 0건.

## Task 4. DoctorApp (`src/doctor/**`)

- `useDoctorSession.js`: 진입 소스 우선순위는 Task 5 참고(`medmap.doctor.*` → `medmap.handoff.*` 복사 → `medmap.session` 복사 → `load` 상태 JSON 붙여넣기/파일). 원본 키에는 쓰지 않음. 상태 `load → wd → review`. WD 상태·값은 메모리 + `medmap.doctor.wd`(새로고침 복원용). pending ref·request id 세대 가드(늦은 응답 폐기, 메모리 `stale-async-response` 교훈).
- 섹션 컴포넌트:
  - `PatientSummarySection`, `WorkingDiagnosisSection`(검색 선택 49 + 직접 입력 + [건너뛰기]; 공개 후 수정 가능, 다시 숨기지 않음)
  - `CandidatesSection`(기본 5, [더 보기] → 8, 번호·%·"1위" 없음, 고지 2줄)
  - `NextInformationSection`(기존 `QuestionPanel` 재사용, "질문 N / 3", BUDGET_REACHED/NONE_ELIGIBLE 안내)
  - `ComingSoonSection`(extensions 8개 → 6줄 안내)
  - `SessionImport`(붙여넣기/파일, 파싱 실패·서버 4xx 문구)
- 스타일: 기존 `plain.css`에 `.doctor*` 클래스 추가만(디자인 PAUSED — 구조 화면 수준, 390/1280 깨짐 없음).
- 테스트(vitest, mock api):
  - WD 전: 후보·질문 DOM 없음(blind) / 건너뛰기·입력 후 공개
  - 후보 5개 → [더 보기] → 8개, 화면 텍스트에 `%`·숫자 확률 없음
  - 답변 → `submitDoctorAnswer` 호출 → 후보·질문 갱신, 3회 후 BUDGET_REACHED
  - `medmap.session` 원본이 doctor 동작 후에도 바이트 동일
  - 잘못된 JSON·4xx·네트워크 오류 문구, 늦은 응답 폐기

## Task 5. 인계 흐름 + 진입 분기 (rev2 — 결정 B)

- `src/handoff/useHandoffSession.js`(신규, 기존 `useMedmapSession` **수정·사용 안 함**): `health`, `begin`, `extract`(기존 `api.extractIntake`), `start(intake, cache, intakeHistory)` = `api.startSession(intake)`만 호출 — **`settle`/자동 적용 없음**. 성공 시 `medmap.handoff.session`(응답 session) + `medmap.handoff.cache`(기존 `sanitizeCache` 결과) 저장. 시작 전 입력은 어디에도 저장하지 않음(P2-4 계약 동일). `reset`은 두 키 삭제.
- `src/handoff/HandoffApp.jsx`: 기존 `StartScreen` + `NaturalIntakeScreen` 재사용 → start 성공 시 인계 완료 화면("의사에게 전달할 준비가 됐습니다" + [의사 화면 열기] → `#/doctor`). 새로고침 시 저장된 handoff session이 있으면 완료 화면. IG 질문 화면 없음.
- Doctor 연동(Task 4 보완): `useDoctorSession`이 진입 시 `medmap.doctor.session` → 없으면 `medmap.handoff.session`+`medmap.handoff.cache`를 **복사**(원본 불변) → 없으면 `medmap.session`(기본 흐름 세션, cache 없음) → 없으면 load 화면.
  - IG가 제안한 `question_id`가 사본 cache에 있으면 `NextInformationSection`이 "환자가 이미 말한 내용: 예/아니요"를 함께 보여준다. **자동 제출 없음.** 의사가 [이 답으로 확인] 또는 다른 답을 눌러야 `/v1/doctor/answer` 제출. 제출 성공 후 사본 cache에서 그 항목 제거.
  - 질문 수 표시는 기존 `questions_used / max_questions`(start 이후 IG 질문 수 = STEP16B 3Q)와 같다. 인계 흐름에서는 start 직후 0이므로 전부 의사 확인 질문이다.
- `src/main.jsx`: `#/doctor` → `DoctorApp`, `#/handoff` → `HandoffApp`, 그 외 → 기존 `App`. `hashchange` 시 리마운트.
- 테스트:
  - 인계: start 후 `submitAnswer` 호출 **0회**(자동 적용 없음), 저장 키가 `medmap.handoff.session`·`medmap.handoff.cache`뿐, `medmap.session`·`medmap.intakeCache` 미작성, 완료 화면·링크, 새로고침 복원
  - Doctor: cache 적중 질문에 "환자가 이미 말한 내용" 표시 + 제출 전 API 호출 0, 확인 후 제출·cache 항목 제거, 인계 원본 키 바이트 불변
  - 기본 흐름: 기존 integration 테스트(자동 적용 포함) 그대로 green — 해시 없음 → 기존 `App`

## Task 6. e2e + 감사

- `e2e/doctor-mode.e2e.mjs`(텍스트만, GPU 불필요, 390/1280):
  1. `#/handoff` → 설명 입력(추가 증상을 말해 cache가 생기는 문장 포함) → bootstrap → 인계 완료, 자동 적용 0
  2. `#/doctor` → 후보 DOM 없음 확인 → cache 적중 시 "환자가 이미 말한 내용" 표시 확인(적중 여부는 seed에 따라 다르므로 적중 사례를 찾는 문장을 e2e 작성 시 API로 먼저 확인) → [건너뛰기] → 후보 5 → [더 보기] 8 → 질문 답 반복 → BUDGET_REACHED 또는 NONE_ELIGIBLE
  3. WD 직접 입력(OUT_OF_SCOPE) 경로 1회, 49 선택 경로 1회
  4. 화면 전체 텍스트에 `%`·금지 표현 0, 결과 `logs/doctor_mode_e2e.json`, 성공 `DOCTOR_E2E_OK`
- `english-audit.e2e.mjs`: 경로 목록에 handoff·doctor 추가(기존 WALKS 로직 재사용, 새 판정 규칙 추가 없음).
- claim lint: `src/doctor/**`·`src/handoff/**`·`dist` 문자열에서 금지 표현 검색. **대조군**: 금지어를 넣은 임시 fixture로 검사기가 실제로 실패하는지 먼저 확인(메모리 `verify-the-verifier`).
- 실행: `npm run build` → `MEDMAP_SERVE_WEB_DIST=medmap-web/dist nohup ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8010` + ram_guard → e2e는 `MEDMAP_WEB=http://127.0.0.1:8010`.

## Task 7. 전체 검증 + 리뷰 + merge-ready

1. backend 전체(기준 244 + 신규) · vitest 전체(217 + 신규) · build · e2e 텍스트 5종 + doctor + english audit — 전부 로그 파일로 남기고 숫자는 로그에서 인용.
2. 음성 e2e: GPU `--check` OK일 때만. WAIT면 "미실행(GPU 경합)"으로 보고.
3. `git diff master --stat`으로 기존 파일 변경이 화이트리스트(`api.py` 추가만, `main.jsx`, `client.js` export, `plain.css` 추가) 안인지 확인. `api.py` diff가 추가 줄만인지 확인.
4. code-reviewer(opus) whole-branch 리뷰 → CHANGES_REQUIRED면 수정 후 재리뷰.
5. 서버 종료(ps로 PID 확인) · 포트 확인 · 프로젝트 메모리 기록 · merge-ready 보고 후 **중단**.

## 완료 기준

- 기존 테스트 전부 green, 기존 endpoint 응답 키 불변, 해시 없는 환자 흐름 불변.
- Doctor 응답·화면에 확률/점수 0, WD 전 후보·질문 0(서버 강제).
- `/doctor/answer` ≡ `/session/answer` (session·다음 질문·stop_reason) — 테스트로 증명.
- 금지 표현 0(대조군 확인된 검사기로).
- 실행 안 한 검증은 "미실행"으로 보고, 숫자 조작 없음.

## 범위 밖 (이 plan에서 하지 않음)

환자 화면 노출 축소(Phase P) · Episode/Timeline · Disease Knowledge Layer · WD 비교/판정 · 서버 저장 · 인증 · 시각 디자인(redesign PAUSED 유지) · 매퍼/엔진/IG/MAX_QUESTIONS 변경.
