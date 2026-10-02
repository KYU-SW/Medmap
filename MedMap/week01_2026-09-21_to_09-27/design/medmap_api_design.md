# MedMap API 설계 (v1)

> **역사 문서(2026-10-02 표기)**: 작성 당시 계약 기록. 현재 제품 정본은 `PRODUCT.md`(v5 정렬). 이후 STT·자연어 intake·Doctor 화면·인계가 추가됐다.

작성 2026-09-23 · **개정 2026-09-23(사용자 검토 반영, 구현본 `medmap/api.py` 와 일치)**.
기준: `docs/medmap_engine_contract.md`, `medmap/`.

개정 요지: 질문 진행 횟수를 클라이언트가 보내지 않고 **복원된 `PatientState` 에서 서버가 계산**하며,
`max_questions` 는 **서버 설정값**(기본 3)으로 고정한다. 요청 본문에서 두 필드를 제거했다.

---

## 1. 목적

기존 제품 엔진(`medmap/`)을 HTTP JSON 으로 감싸, UI/앱이 파이썬을 직접 호출하지 않고도 같은 계약으로 쓰게 한다.

```
HTTP JSON 요청 → medmap 엔진 호출 → 기존 JSON 계약(medmap-turn-v1) 응답
```

API 는 **진단 로직을 새로 만들지 않는다.** 진단 계산·질문 자격·정보이득·질문 선택·한국어 표현·답변 검증·세션 직렬화는
전부 엔진(`DiagnosisEngine`, `QuestionEligibility`, `NextInformationEngine`, `QuestionPresenter`, `medmap.serialization`)이 담당한다.

## 2. 범위

포함: `/health`, 세션 시작·답변·재개 3개 endpoint, 오류 매핑, 모델 1회 로딩, 로깅·CORS 정책, 테스트 계획.

**Non-goals (이번 v1 에서 만들지 않음)**: 로그인·회원가입, DB·Firebase, 사용자 프로필/진료기록 저장, STT, 파일 업로드,
관리자/의사 페이지, WebSocket,(※ STT·의사 페이지·WebSocket은 이후 추가됨 — `PRODUCT.md`) 외부 LLM 호출, Profile 기반 selector, 모델 학습 endpoint, debug endpoint, 성능 최적화·분산 서버.

## 3. 아키텍처 — stateless

- 서버는 진단 세션을 **저장하지 않는다.** 클라이언트가 매 요청에 `medmap-session-v1` 을 보내고, 서버는 새 세션 JSON 을 응답에 돌려준다.
- 세션의 source of truth 는 `PatientState` 하나. posterior·top3·next_question·IG 는 요청마다 재계산되는 파생값이며 저장하지 않는다.
- 요청 처리 흐름(세 endpoint 공통):

```
요청 JSON
  → deserialize_session(...) 또는 PatientState.new(...)   # 복원·검증
  → NextInformationEngine.start(state) [/ .answer(turn, qid, answer)]
  → serialize_turn(turn, model_context, include_debug=False)
  → 응답 JSON (medmap-turn-v1, session 봉투 포함)
```

- 장점: 이미 고정된 세션 계약을 그대로 사용, 서버 저장소 불필요, 개인정보 보관 최소화, UI 결합도 낮음, 재현 쉬움.

### 3-1. 질문 수와 model_context_match (개정 2: 2026-09-23)

엔진의 `Turn.questions_asked_in_session` 은 한 프로세스 내 대화를 기준으로 세므로 stateless 에서는 요청마다 0 이 된다.
클라이언트가 별도 카운터를 들고 다니면 `PatientState` 와 어긋날 수 있으므로, **질문 수는 복원된 상태에서만 계산한다.**

```
baseline       = int(model_context[1:])                 # k3 → 3 (모델 학습 뷰의 추가 관측 수)
delta          = state.n_additional - baseline
questions_used = delta if delta >= 0 else None          # None = 판정 불가(엔진이 만들 수 없는 상태)
remaining      = max(MAX_QUESTIONS - questions_used, 0)
engine         = NextInformationEngine(..., max_questions=remaining)

model_context_match = (state.n_additional == baseline)  # 정확히 k 일 때만 true
```

- `MAX_QUESTIONS` 는 **서버 설정값**(기본 3, 환경변수 `MEDMAP_MAX_QUESTIONS`). 요청 본문에 넣을 수 없다(보내면 422).
- `remaining <= 0` 이면 엔진이 새 질문을 고르지 않고 `stop_reason: MAX_QUESTIONS` 를 낸다. 질문 수를 API 와 엔진이 따로 관리하지 않는다.
- **baseline 을 빼는 이유**: 세션 시작 상태에는 선택한 모델의 학습 뷰에 해당하는 관측 k 개가 이미 들어 있다.
  그대로 `MAX_QUESTIONS − n_additional` 을 쓰면 정상적인 k3 세션이 첫 질문도 하기 전에 멈춘다(k5/k10 은 음수).
  baseline 을 빼면 "엔진이 이 세션에서 실제로 물어 답변된 수"만 남는다.
- **`model_context_match` 는 `n_additional == k` 다.** MODEL_k 는 "초기 evidence + 정확히 k 개 추가 관측"으로 학습됐으므로,
  질문이 하나 추가될 때마다 상태는 학습 뷰에서 멀어지고 match 는 `false` 가 된다(k3+3 → true, k3+4 → false, k3+6 → false).
  이는 표시값이며 **모델을 자동으로 바꾸지 않는다.**
- 응답의 `questions_asked_in_session` 은 `questions_used`(판정 불가면 `null`), `model_context_match` 는 위 규칙으로
  API 계층이 통일해 내보낸다. `diagnoses`, `next_question`, `information_gain`, `session`, `model_context` 는 엔진 출력 그대로다.
- `asked_question_ids` ↔ `answers` ↔ `n_additional_questions` 불일치는 `deserialize_session` 이 이미 검증해 오류로 만든다(조용한 보정 없음).

#### 비정규 세션 형태 (v1 정책)

세션 JSON 만으로는 "호출자가 처음부터 많이 준 관측"과 "엔진이 물어서 늘어난 관측"을 구별할 수 없다(둘 다 `n_additional > k`).
따라서 **새 세션임이 선언되는 `/start` 에서만 exact-k 를 요구**하고, 그 이후 상태는 정상 세션의 연장으로 본다.

| 상황 | 처리 |
|---|---|
| `/start` 에서 `n_additional == k` | 정상 interactive 세션. `questions_used = 0`, match `true` |
| `/start` 에서 `n_additional != k` | **막지 않는다.** 진단(top3)과 세션은 돌려주되 `model_context_match:false`, `questions_asked_in_session:null`, `next_question:null`, `stop_reason:"UNSUPPORTED_SESSION_SHAPE"` — 질문 예산을 추정하지 않는다 |
| `/resume`·`/answer` 에서 `n_additional >= k` | 정상 세션의 연장으로 계속 진행(`questions_used = n_additional − k`) |
| `/resume` 에서 `n_additional < k` | 엔진이 만들 수 없는 상태 → 위와 같은 제한 응답 |
| `/answer` 에서 `n_additional < k` | 409 `MEDMAP_UNSUPPORTED_SESSION_SHAPE` |

`UNSUPPORTED_SESSION_SHAPE` 는 **API 계층의 stop_reason** 이며 엔진 계약의 `MAX_QUESTIONS`/`NO_ELIGIBLE_QUESTION` 과 별개다.
새 카운터를 추가하지 않고 `PatientState` + `model_context` 만으로 판정한다.

## 4. 프레임워크

- **제안: FastAPI + uvicorn** — JSON API 에 적합, pydantic 으로 요청 스키마 검증, 자동 문서(`/docs`), 이후 웹/앱 연결 용이.
- 현재 `~/ai_env` 상태(읽기 전용 확인): `pydantic 2.13.4`, `httpx 0.28.1` **있음** / `fastapi`, `uvicorn`, `starlette` **없음**.
- 사용자 승인(2026-09-23)으로 `fastapi 0.141.1`, `uvicorn[standard] 0.53.0` 설치 완료. 목록은 `requirements-api.txt`.
  테스트는 이미 있던 `httpx` 기반 `TestClient` 로 in-process 실행한다.
- 표준 `http.server` 대안은 채택하지 않는다.
- 실행: `~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000`
  (모델은 lifespan 에서 1회 로딩되며, 자동 문서는 `/docs`).

## 5. Endpoint 4개

| method | path | 입력 | 출력 |
|---|---|---|---|
| GET | `/health` | 없음 | 상태·스키마 버전 |
| POST | `/v1/session/start` | 신규 세션 입력(평문형) | `medmap-turn-v1` |
| POST | `/v1/session/answer` | `session` + `submission` | `medmap-turn-v1` |
| POST | `/v1/session/resume` | `medmap-session-v1` 봉투 | `medmap-turn-v1` |

`start` 와 `resume` 은 둘 다 "상태 → 첫 Turn"이지만 입력 형태가 다르다.
`start` 는 클라이언트가 `asked_question_ids` 같은 파생 필드를 만들지 않아도 되는 **신규 생성용 평문 입력**,
`resume` 은 저장본을 그대로 돌려받는 **엄격한 봉투 입력**이다.

### 5-1. `GET /health`

환자 데이터 없음. 모델·IG 표·카탈로그 로딩 완료 여부만 알린다.

```json
{
  "status": "ok",
  "engine_ready": true,
  "model_contexts": ["k3", "k5", "k10"],
  "schema": {"session": "medmap-session-v1", "turn": "medmap-turn-v1", "answer": "medmap-answer-v1"},
  "api_version": "v1"
}
```

### 5-2. `POST /v1/session/start`

요청:

```json
{
  "age": 45,
  "sex": "M",
  "model_context": "k3",
  "initial_evidence": "E_53",
  "answers": [
    {"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
    {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
    {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}
  ]
}
```

> `max_questions` / `questions_asked_in_session` 은 요청 본문에 넣지 않는다(서버 설정값·서버 계산값). 보내면 422.

- `initial_evidence` 는 evidence ID 하나 또는 `null`(엔진 계약과 동일하게 단일 값; 배열이 오면 400).
- `answers` 의 각 항목은 `medmap-answer-v1` 의 `answer` 와 같은 모양이며 `question_id` 를 함께 갖는다.
- 서버 처리: 각 항목을 `parse_answer_submission({"question_id":…, "answer":…}, catalog, state)` 로 순차 검증하며
  `PatientState.new(...)` → `with_answer(...)` 로 상태를 만든 뒤 `engine.start(state)`.
  (부모 gate·중복·제외 질문이 여기서 그대로 걸린다.)

응답: `medmap-turn-v1` (§6).

### 5-3. `POST /v1/session/answer`

요청:

```json
{
  "session": {
    "schema_version": "medmap-session-v1",
    "patient_state": {
      "age": 45, "sex": "M", "model_context": "k3", "initial_evidence": "E_53",
      "answers": [
        {"question_id": "E_53", "kind": "POSITIVE", "value": null},
        {"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
        {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
        {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}
      ],
      "asked_question_ids": ["E_53", "E_55", "E_56", "E_204"],
      "n_additional_questions": 3
    }
  },
  "submission": {
    "schema_version": "medmap-answer-v1",
    "question_id": "E_54",
    "answer": {"kind": "VALUE", "value": ["V_181"]}
  }
}
```

서버 처리: `deserialize_session` → `engine.start(state)` 로 Turn 재구성 → `parse_answer_submission(submission, catalog, state)`
→ `engine.answer(turn, question_id, answer)` → `serialize_turn`.

**규칙**: 클라이언트는 **엔진이 방금 제안한 질문에만** 답할 수 있다. 다른 질문 ID 를 보내면 엔진이
`MEDMAP_UNEXPECTED_ANSWER` 로 거부하고 API 는 409 를 돌려준다(임의 보정하지 않는다).
`model_context` 는 세션 JSON 의 값을 사용한다(요청에서 따로 바꾸지 않는다).

### 5-4. `POST /v1/session/resume`

요청: `medmap-session-v1` 봉투 그대로.

```json
{"session": {"schema_version": "medmap-session-v1", "patient_state": { "...": "..." }}}
```

처리: `deserialize_session` → `engine.start(state)` → `serialize_turn`. 저장된 세션 재개용.

## 6. 응답 스키마 (`medmap-turn-v1`)

엔진 계약 §6 과 동일하며, API 는 `questions_asked_in_session`·`model_context_match` 를 상태 기준으로 통일하고
`max_questions`(서버 설정값)를 덧붙인다(§3-1).

```json
{
  "schema_version": "medmap-turn-v1",
  "diagnoses": [{"name": "Chronic rhinosinusitis", "probability": 0.2435}],
  "diagnoses_before": null,
  "next_question": {
    "question_id": "E_57",
    "question_ko": "통증이 다른 부위로 퍼지나요? (해당하는 곳을 모두 고르세요)",
    "question_original": "Does the pain radiate to another location?",
    "answer_type": "MULTI_CHOICE",
    "choices": [{"value": "V_123", "label": "없음", "original_label": "nowhere", "is_fallback": false}],
    "information_gain": 1.0446,
    "is_fallback": false,
    "explanation": null,
    "question_text": "Does the pain radiate to another location?",
    "answer_type_raw": "MULTI",
    "possible_values": ["V_123", "V_14"]
  },
  "stop_reason": null,
  "n_asked": 5,
  "questions_asked_in_session": 1,
  "max_questions": 3,
  "model_context": "k3",
  "model_context_match": false,
  "session": {"schema_version": "medmap-session-v1", "patient_state": {"...": "..."}}
}
```

- 기본 응답은 항상 `serialize_turn(..., include_debug=False)`. **전체 49-class posterior 와 candidate IG 목록은 반환하지 않는다.**
- 종료 시 `next_question` 은 `null`, `stop_reason` 은 `MAX_QUESTIONS` 또는 `NO_ELIGIBLE_QUESTION`.
- 응답의 `session` 을 다음 요청에 그대로 되돌려 보내면 대화가 이어진다.

## 7. 오류 계약

응답 형식(모든 오류 공통):

```json
{"error": {"code": "MEDMAP_PARENT_GATE_VIOLATION", "message": "MEDMAP_PARENT_GATE_VIOLATION:E_130<-E_129", "field": "question_id"}}
```

`code` 는 엔진 예외 메시지의 `MEDMAP_...` 접두 토큰(`message.split(":")[0]`)을 그대로 쓴다. 새 코드 체계를 만들지 않는다.

**상태 코드 규칙 (하나로 고정)**

| 상황 | status | 예시 code |
|---|---|---|
| 요청 본문 모양 오류(필드 누락·타입 오류, pydantic 검증 실패) | **422** | `REQUEST_VALIDATION_ERROR` |
| 계약 위반: 존재하지 않는 evidence ID, 존재하지 않는 value ID, answer kind 불일치, 제외 질문(E_134/E_152), 잘못된 age/sex/model_context, 지원하지 않는 `schema_version` | **400** | `MEDMAP_UNKNOWN_EVIDENCE_ID`, `MEDMAP_INVALID_ANSWER_VALUE`, `MEDMAP_INVALID_ANSWER`, `MEDMAP_EXCLUDED_QUESTION`, `MEDMAP_INVALID_AGE`, `MEDMAP_INVALID_MODEL_CONTEXT`, `MEDMAP_UNSUPPORTED_SCHEMA_VERSION` |
| 현재 상태와의 충돌: 부모 gate 위반, 이미 답한 질문, 제안되지 않은 질문에 답변, 지원 범위를 벗어난 세션에 답변 | **409** | `MEDMAP_PARENT_GATE_VIOLATION`, `MEDMAP_ALREADY_ASKED`, `MEDMAP_UNEXPECTED_ANSWER`, `MEDMAP_UNSUPPORTED_SESSION_SHAPE` |
| 그 외 예기치 못한 오류 | **500** | `INTERNAL_ERROR`(상세는 로그에만) |

엔진 예외 → HTTP 매핑:

| 엔진 예외 | 매핑 |
|---|---|
| `serialization.UnsupportedSchemaVersion` | 400 |
| `serialization.SessionValidationError` | 400, 단 code 가 `MEDMAP_PARENT_GATE_VIOLATION` / `MEDMAP_ALREADY_ASKED` 이면 409 |
| `ValueError`(`MEDMAP_INVALID_ANSWER*`, `MEDMAP_UNKNOWN_MODEL_CONTEXT`, `MEDMAP_UNRECOGNIZED_SELECTION`) | 400 |
| `ValueError`(`MEDMAP_UNEXPECTED_ANSWER`, `MEDMAP_ALREADY_ASKED`) | 409 |
| `config.MedMapForbiddenPath`, 그 외 예외 | 500 (코드 노출 없이 `INTERNAL_ERROR`) |

오류를 숨기거나 임의 보정하지 않는다(예: 부모 gate 위반을 UNKNOWN 으로 바꾸는 식의 처리 금지).

## 8. 모델 수명주기

- **서버 시작 시 1회 로딩**(FastAPI lifespan): `EvidenceCatalog` 1개, `AnswerLikelihoodTable` 1개(3개 엔진이 공유),
  `DiagnosisEngine` 3개(k3/k5/k10), `QuestionPresenter` 1개.
- 요청마다 재로딩 금지. 요청 처리 시에는 `NextInformationEngine` 만 가볍게 조립한다
  (`NextInformationEngine(diagnosis_engines[ctx], likelihoods=shared_table, presenter=shared_presenter, max_questions=…)`).
- 로딩된 객체는 읽기 전용으로만 사용한다. **`fit()` / `train()` / fine-tune 호출 금지.**
- 기동 시 `model_contexts` 3개 로딩과 IG 표 정합성 확인에 실패하면 `engine_ready: false` 로 `/health` 를 노출하고
  세션 endpoint 는 503 을 반환한다.

## 9. model_context

- 지원 `k3` / `k5` / `k10`. **API 가 자동으로 바꾸지 않는다.**
- `start` 에서 호출자가 명시(생략 시 `k3`), 이후 요청은 세션 JSON 의 값을 사용한다.
- `model_context_match` 는 `state.n_additional == k` 여부다(k3+3 true / k3+4 false / 관측 3개로 `k5` 선택 시 false).
  **`false` 여도 서버가 다른 모델로 바꾸지 않는다.** 바꾸려면 클라이언트가 다른 `model_context` 로 새 `start` 를 호출한다.

## 10. 개인정보 · 로깅

- **받는 필드**: `age`, `sex`, 임상 evidence 답변, `model_context`, `session`, `submission`.
- **받지 않는 필드**: 이름, 주민등록번호, 전화번호, 주소, 이메일, 계정 ID. 요청에 오면 무시하지 않고 422 로 거부한다
  (pydantic `extra="forbid"`).
- **기본 로그**: request ID, endpoint, HTTP status, 처리 시간(ms), `model_context`, `stop_reason`, 오류 `code`.
- **기본 로그 금지**: 전체 `answers`, 전체 `PatientState`/세션 JSON, posterior 전체, 질문·답변 원문.
  개발용 상세 로그는 환경변수(`MEDMAP_API_LOG_PAYLOAD=1`)로 명시적으로 켠 경우에만 허용한다.
- 응답 본문에는 서버가 저장하는 것이 없으므로, 세션 보관 책임은 클라이언트에 있다(문서에 명시).

## 11. CORS

- 기본값은 **차단**. `allow_origins=["*"]` 를 쓰지 않는다.
- 허용 origin 은 환경변수 `MEDMAP_API_CORS_ORIGINS`(쉼표 구분)로 주입하며, 미설정 시 CORS 미들웨어를 붙이지 않는다.
- 개발 예시: `MEDMAP_API_CORS_ORIGINS=http://localhost:5173`. 허용 메서드는 `GET, POST`, 자격증명 전송은 사용하지 않는다.

## 12. API 버전

- 경로는 `/v1/...`. HTTP API 버전과 JSON `schema_version` 은 **별개**다.
- 향후 `/v2` 가 생겨도 `medmap-session-v1` 을 계속 받을 수 있게, 입력 처리는 `schema_version` 분기로만 갈라지게 둔다.
- 지원하지 않는 `schema_version` 은 400 으로 명확히 실패한다(추정 금지).

## 13. 결정론

같은 `session` + 같은 `submission` 이면 `diagnoses`(이름·확률), `next_question.question_id`, `information_gain`, `stop_reason` 이 항상 같아야 한다.
API 계층은 결과를 가공하지 않는다. 예외는 §3-1 의 `questions_asked_in_session`·`model_context_match` 상태 기준 통일과
`max_questions` 표기뿐이며, 진단·질문 선택·IG 에는 영향을 주지 않는다.

## 14. 테스트 계획 (구현 단계에서 작성, 기존 54개와 별도)

1. `GET /health` 200, `engine_ready: true`, 스키마 3종 노출
2. `start` 정상 → `medmap-turn-v1`, top3 3개, `next_question` 존재
3. `answer` 정상 → `diagnoses_before` 채워지고 `n_asked` 증가
4. `resume` 정상 → 저장 세션에서 같은 Turn
5. `start → answer → resume` 연속 흐름에서 상태 일관
6. 존재하지 않는 evidence ID → 400 `MEDMAP_UNKNOWN_EVIDENCE_ID`
7. 존재하지 않는 value ID → 400 `MEDMAP_INVALID_ANSWER_VALUE`
8. 부모 gate 위반 → 409 `MEDMAP_PARENT_GATE_VIOLATION`
9. `E_134`/`E_152` 제출 → 400 `MEDMAP_EXCLUDED_QUESTION`
10. 이미 답한 질문 재제출 → 409 `MEDMAP_ALREADY_ASKED`
11. 지원하지 않는 `schema_version` → 400 `MEDMAP_UNSUPPORTED_SCHEMA_VERSION`
12. 잘못된 `model_context`(예 `k7`) → 400 `MEDMAP_INVALID_MODEL_CONTEXT`
13. 공개 응답에 전체 posterior·candidate IG 없음(`debug` 키 부재, 확률 항목 3개)
14. 엔진 직접 호출 결과와 API 결과 동일(top3·question_id·IG)
15. 같은 요청 2회 반복 시 바이트 수준 동일 응답
16. `model.fit` 호출 0회(monkeypatch 로 fit 을 예외로 치환한 상태에서 전 흐름 통과)
17. 원본 VALIDATION/TEST 접근 0(`config.check_path` 가드 + 서버 코드에 경로 문자열 부재)
18. (추가) 질문 수 규칙: 답변 3회 후 `stop_reason: MAX_QUESTIONS`, 그 세션을 `resume` 해도 같은 판정
18b. (추가) `model_context_match`: k3+3/k5+5/k10+10 → true, +1 → false, 질문마다 false 유지
18c. (추가) 비정규 start(k3+4, k3+1, k5+3)는 제한 응답(`UNSUPPORTED_SESSION_SHAPE`, 카운터 null, 질문 없음)
19. (추가) 제안되지 않은 질문에 답변 → 409 `MEDMAP_UNEXPECTED_ANSWER`
20. (추가) 미허용 추가 필드(`name`, `phone`) 포함 요청 → 422

테스트는 `httpx` 기반 `TestClient` 로 in-process 실행하며 실제 포트를 열지 않는다.

## 15. 성능 — 로컬 실측 (2026-09-23)

설계 목표: 모델·IG 표는 서버 시작 시 1회 로딩, 요청 시 재로딩 금지, 단일 세션 요청은 동기 처리.
최적화·GPU·분산 구조는 만들지 않는다.

> **주의: 아래는 개발 PC 의 localhost(127.0.0.1) 측정값이며, 배포 서버나 모바일 네트워크의 성능을 의미하지 않는다.**
> 실제 서비스 지연에는 네트워크 왕복·TLS·서버 사양·동시 요청이 더해진다.

측정 환경: AMD Ryzen 5 7500F (6C/12T), WSL2(Linux 6.18), Python 3.12.3, FastAPI 0.141.1, uvicorn 0.53.0,
scikit-learn 1.9.0, numpy 2.1.2. **GPU 미사용**(추론은 sklearn LogisticRegression + numpy CPU 연산, `medmap/` 는 torch/CUDA 를 import 하지 않는다).

**Cold start**(프로세스 기동 → `/health` 의 `engine_ready: true`, 독립 재시작 3회): 1354.8 / 1127.3 / 1077.8 ms, 평균 **1186.6 ms**.
모델 3개 + IG 표 + 카탈로그 로딩이 여기 포함된다. 요청 처리와 섞어서 보지 않는다.

**Warm latency**(서버 기동 후, 각 100회, 단위 ms)

| endpoint | min | median | mean | p95 | max |
|---|---|---|---|---|---|
| `GET /health` | 0.61 | 0.75 | 1.29 | 0.95 | 52.04 |
| `POST /v1/session/start` | 1.46 | 1.64 | 1.68 | 1.92 | 2.35 |
| `POST /v1/session/answer` | 2.15 | 2.46 | 2.90 | 2.84 | 44.42 |
| `POST /v1/session/resume` | 1.03 | 1.15 | 1.17 | 1.35 | 1.42 |

(`max` 의 44~52 ms 이상치는 첫 호출 직후의 일회성 튐이며 p95 는 3 ms 미만이다.)

**전체 3문항 흐름**(start + answer×3, 30회): median **8.61 ms**, p95 9.55 ms, max 10.18 ms.

**정확성 회귀**: 측정 전후 같은 입력에서 top3(Anemia 0.23933228850364685 / URTI 0.17142263054847717 /
Chronic rhinosinusitis 0.08021262288093567), 첫 질문 `E_54`, IG 1.6559701313777224, 3문항 후 `MAX_QUESTIONS` 가 모두 동일했다.
성능 측정을 위해 알고리즘·캐시·후보 축소를 도입하지 않았다.

## 16. 설계 self-audit

| 점검 | 결과 |
|---|---|
| 엔진 계약과 충돌 | 없음 — 모든 처리는 계약 §4~§10 규칙을 그대로 따른다 |
| 존재하지 않는 API/클래스 사용 | 없음 — `EvidenceCatalog`, `DiagnosisEngine`, `NextInformationEngine`, `QuestionPresenter`, `AnswerLikelihoodTable`, `PatientState`, `serialize_turn`, `deserialize_session`, `parse_answer_submission` 만 사용 |
| 세션 JSON 필드 임의 변경 | 없음 — `medmap-session-v1` 을 그대로 주고받는다 |
| turn 필드 변경 | `questions_asked_in_session`·`model_context_match` 를 상태 기준으로 통일하고 `max_questions` 추가(§3-1). 진단·질문·IG·stop_reason·session 은 엔진 출력 그대로 |
| model_context 자동 전환 | 없음 |
| posterior 를 source of truth 로 사용 | 없음(응답에 전체 posterior 자체가 없음) |
| 새 임상 로직 | 없음 |
| DB 의존 | 없음(stateless) |
| 새 의존성 | `fastapi 0.141.1`, `uvicorn[standard] 0.53.0` — 사용자 승인 후 설치 완료, `requirements-api.txt` 기록 |
