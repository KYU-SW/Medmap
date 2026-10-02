# MedMap Clinical Summary (core builder) — Bounded Design + Implementation Plan

> **Revision 1 (2026-09-26, 설계 단계 — 승인 대기).** 코드 미구현. 이 문서와 `.ledger.md`만 커밋한다.
> 실행 방식(승인 후): Subagent-driven(task별 implementer + spec/code review, 전체 완료 후 whole-branch review). 실행 제약은 `project-safety-review` + 사용자 CLAUDE.md 1-2(실행 전 승인).

> **Revision 2 (2026-09-26, 사용자 승인 B1–B3 — 구현 완료).** 아래 "rev2 확정 계약"이 §3–§10과 충돌하면 rev2가 우선한다. rev1 본문은 설계 이력으로 남긴다.

## rev2 확정 계약 (사용자 결정 B1–B3)

- **B1:** PatientState에서 안정적으로 재구성되지 않는 것은 전부 제외. intake cache의 미적용 NEGATIVE, 세션에 없는 bootstrap UNKNOWN은 만들지 않는다. 우선순위 = 새로고침 전후 summary 동일.
- **B2:** 범위 = `medmap/clinical_summary.py`(결정적) + 스키마 + 단위 테스트만. API endpoint(api.py 0줄)·UI·PDF·인쇄·복사·LLM 요약 제외. §6의 router 옵션은 이번 범위 밖.
- **B3:** `schema_version: "medmap-clinical-summary-v1"`. 최종 키(순서 고정, `SUMMARY_KEYS`):
  `schema_version`, `chief_complaint`, `confirmed_positive`, `confirmed_negative`, `confirmed_values`, `not_applicable`, `unknown`, `answered_questions`, `diagnosis_candidates`, `questions_used`, `disclaimer`
  - 사용자 권장 스키마 대비 **추가 2개**: `unknown`(PatientState에 있는 UNKNOWN 답), `answered_questions`(initial 포함 asked 순서 전체). 둘 다 원 스펙 키이고 PatientState에서 재구성된다. **누락 0개**.
  - rev1에서 **삭제**: `source_session_schema`, `model_context`, `patient`, `max_questions`, `stop_reason`, `session_shape`, `display`(→ `disclaimer`로 대체), Item의 `source`(initial/start/engine — 비정상 형태에서 추정이 되므로 제거, 순서는 `answered_questions`로 보존).
  - `disclaimer`: **한 문자열, `\n` 1개로 두 줄** — `"현재까지 입력하고 확인한 내용을 진료 전 참고용으로 정리한 것입니다.\n진단 결과가 아니며, 진단에는 의료진의 평가가 필요합니다."`
  - Item: `question_id, status, values, question_ko, question_original, answer_ko, is_fallback` (+ `chief_complaint`에만 `label_ko`).
  - Candidate(top3만, 전체 posterior 없음): `name, display_name, is_fallback, probability`. 입력은 내림차순이어야 하며 아니면 `ValueError`(조용한 정렬 없음).
  - `questions_used`: `n_additional − k`, 음수면 `null` — API `questions_asked_in_session`과 같은 "판정 불가" 표기(추정값 아님). `summary_from_turn_payload`는 turn의 `questions_asked_in_session`과 다르면 `ValueError`.
  - `chief_complaint`: `initial_evidence`가 없으면 `null`(세션에 initial이 없다는 사실 그대로).
  - 금지: "최종 진단"/"final diagnosis" 키·문구, transcript, 매퍼 `matched_text`, IG, `MEDMAP_*` 출력(테스트 03).
- 구현 API: `build_clinical_summary(state, model_context, diagnoses, *, labels)`, `summary_from_session(session, diagnoses, *, catalog, labels)`, `summary_from_turn_payload(turn, *, catalog, labels)`, `questions_used(state, model_context)`, `LabelProvider`/`PresenterLabelProvider`(terminology hook). `max_questions`·`stop_reason` 인자는 rev1 §5와 달리 두지 않는다.
- 테스트: `tests/test_clinical_summary.py` 23개(rev1 §8 목록을 rev2 키에 맞춰 조정: source 분류 테스트 삭제, disclaimer 정확 일치·turn 질문 수 불일치 거부·후보 정렬/범위 거부 추가).

**Goal:** 세션 종료 후 환자가 진료 시 보여줄 수 있는 "현재까지 확인된 정보"를 **LLM 없이** `PatientState`(+ 진단 후보 top3)에서 결정적으로 재구성하는 core builder + JSON 계약(`medmap-clinical-summary-v1`) + 테스트.

**Architecture:** 새 순수 모듈 `medmap/clinical_summary.py` 1개(+ 테스트 1개). 기존 `patient_state` / `serialization` / `diagnosis` / `next_information` / `question_presentation` / `api.py`는 **import만 하고 수정하지 않는다**. summary는 파생값이므로 세션에 저장하지 않으며, 새로고침 후에도 `medmap-session-v1`에서 다시 만든다.

**Tech Stack:** Python 3.12(`~/ai_env`) · 표준 라이브러리 + 기존 `medmap` 모듈 · unittest. 새 의존성 0. 프론트 변경 0.

**Spec:** 사용자 2026-09-26 PARALLEL B 프롬프트(CLINICAL SUMMARY) · `PRODUCT.md`(Terminology) · `docs/medmap_engine_contract.md` · `docs/medmap_api_design.md` §3-1.

---

## 1. 판정: **BOUNDED**

| 기준 | 근거 | 결과 |
|---|---|---|
| 필요한 사실이 기존 상태에 다 있는가 | `PatientState`에 age·sex·initial_evidence·answers(evidence_id→Answer)·asked(물은 순서) 존재(`medmap/patient_state.py:60-65`). 세션 JSON에 answers가 **asked 순서로** 직렬화(`medmap/serialization.py:76-78`), 복원 시 같은 순서로 재생(`serialization.py:118-128`) | 충족 |
| 상태값 구분이 충분한가 | POSITIVE / NEGATIVE / VALUE / NOT_APPLICABLE / UNKNOWN 5종, UNASKED는 "키 없음"(`patient_state.py:3-9,17-25`), 직렬화도 NEGATIVE·UNKNOWN 구분 저장(`serialization.py:6`) | 충족 |
| 질문 수 규칙이 상태만으로 계산되는가 | `questions_used = n_additional − k`(음수면 None) — `medmap/api.py:228-240`, 설계 `docs/medmap_api_design.md:45-82`. `n_additional`은 상태 파생(`patient_state.py:90-93`) | 충족(같은 식 재사용) |
| initial/start/engine 구분 가능한가 | `/start`는 exact-k 강제(`api.py:317-318`, `_run` `api.py:264-273`) → asked 순서상 initial 1 + 다음 k개 = 시작 관측, 그 뒤 = 엔진 질문 | 충족(정상 세션 형태에서) |
| 진단 후보 | top3 `{name, probability}`가 turn에 있음(`serialization.py:160,179-180`). 상태만 있으면 `DiagnosisEngine.diagnose(state)`로 재계산 가능(`medmap/diagnosis.py:50-54`, `/resume`이 하는 일 `api.py:327-330`) | 충족 |
| 한국어 표시 | 질문 53·값 188 정적 매핑 + fallback 플래그(`medmap/question_presentation.py:1-6,77-84,96-104`), initial 96개 짧은 라벨 `label_ko`(`medmap/data/initial_evidence_ko.json`) | 충족(없는 것은 fallback 표시) |
| 계약·상태 변경 필요? | 없음. 새 모듈이 기존 타입을 읽기만 한다. `medmap-session-v1`/`medmap-turn-v1`/`medmap-answer-v1` 무변경 | **BOUNDED** |

**architectural로 넘어가는 경계(이번 범위에서 하지 않음):** (a) summary를 turn payload에 끼워 넣기(turn 계약 변경), (b) intake cache·bootstrap UNKNOWN을 `PatientState`에 넣기(상태 계약 변경), (c) 원문 transcript 저장. 셋 다 채택하지 않는다.

## 2. 감사 결과 (read-only, worktree HEAD `336463f`)

### 2-1. 위치 지도

| 대상 | 위치 | 비고 |
|---|---|---|
| `PatientState`, `Answer`, `AnswerStatus` | `medmap/patient_state.py:17-117` | frozen dataclass. `initial_evidence`는 항상 POSITIVE로 자동 기록(`:111-112`) |
| `medmap-session-v1` 직렬화/복원 | `medmap/serialization.py:21,67-132` | 복원 시 부모 gate·중복·asked 일치·`n_additional_questions` 일치 검증, 조용한 보정 없음 |
| `medmap-turn-v1` | `medmap/serialization.py:155-180` | diagnoses top3, diagnoses_before, next_question, stop_reason, questions_asked_in_session, session |
| `Turn` dataclass | `medmap/next_information.py:76-93` | 엔진 내부 `questions_asked_in_session`은 요청 단위 카운터(stateless에선 의미 없음, `docs/medmap_api_design.md:47`) |
| stop reason | `next_information.py:19-20`(MAX_QUESTIONS, NO_ELIGIBLE_QUESTION), `api.py:46`(UNSUPPORTED_SESSION_SHAPE) | |
| 질문 수 | `api.py:223-240`(`_baseline`, `_questions_used`), `api.py:243-253`(payload에 덮어씀) | 상한 `MAX_QUESTIONS` = env 또는 3(`api.py:38`, `config.py:18`) |
| 진단 | `medmap/diagnosis.py:12-54` | 클래스명은 **영문 DDXPlus 이름**(`model.classes_`) |
| 한국어 질문/값 | `medmap/question_presentation.py`, `medmap/data/question_labels_ko.json`(questions 53, values 188, unknown/yes/no 라벨) | "해당 없음"은 값 코드 `V_11` 라벨로만 존재. NOT_APPLICABLE 상태용 라벨 키는 없음 |
| initial 짧은 라벨 | `medmap/data/initial_evidence_ko.json` items 96개 `label_ko`(예 `E_53` → "통증") | 96개 중 `question_labels_ko`에도 있는 것은 27개 — 짧은 라벨은 이 파일이 유일한 출처 |
| 질환 한국어명 | **master에 없음**(grep: `medmap/`·`medmap-web/src`·`docs`에 disease 한국어 매핑 없음) | 화면도 영문 그대로(`medmap-web/src/components/CandidatePanel.jsx`) |
| 프론트 세션 저장 | `medmap-web/src/session/useMedmapSession.js:35,59,73` | **sessionStorage** `medmap.session`에 `turn.session`(= `medmap-session-v1`)만 저장. localStorage 아님 → 새로고침은 유지, 탭 닫으면 소멸 |
| 새로고침 복원 | `useMedmapSession.js:90-121` | `/resume` → turn 재수신. `diagnoses_before`는 `/resume`에서 null(엔진 start) |
| 기존 요약 화면 | `medmap-web/src/screens/SummaryScreen.jsx:4-30` | "내가 답한 항목"은 React state `history`(`useMedmapSession.js:43,149,165`)에서 옴 — **새로고침 후 복원되지 않음(빈 목록)**. 이 기능이 메우는 실제 공백 |
| intake cache | `medmap-web/src/intake/answerCache.js:3,18-37` | sessionStorage `medmap.intakeCache`에 `{evidence_id,status}`. 엔진이 제안하기 전엔 **PatientState에 없음** |
| bootstrap UNKNOWN | `docs/superpowers/plans/2026-09-25-medmap-natural-intake.md` Global Constraints(rev2) | `/start` 본문에 넣지 않음 → **PatientState에 없음**, 프론트 `history`에만 |
| 테스트 fixture | `medmap-web/src/test/fixtures/turn.answer3.json` | 실제 세션(age 45 M, initial E_53, VALUE 5개 + NEGATIVE 1, `n_additional 6`, `MAX_QUESTIONS`), fallback 질문(E_204·E_146) 포함 → 모델 없이 테스트 가능 |

### 2-2. 새로고침 후 재구성 가능 여부

| 요약 필드 | PatientState + (turn 또는 재계산)만으로 | 비고 |
|---|---|---|
| chief_complaint | 가능 | `initial_evidence` |
| confirmed_positive / negative / values / unknown / not_applicable | 가능 | `answers` 전수 |
| answered_questions(순서·출처) | 가능(정상 형태) | asked 순서 + exact-k |
| questions_used | 가능 | `n_additional − k` |
| diagnosis_candidates | 가능 | turn top3 또는 `DiagnosisEngine.diagnose(state)` 재계산(`/resume`과 같은 값) |
| diagnoses_before(직전 후보) | **불가** | `/resume`에서 null. summary에 넣지 않는다 |
| 엔진이 제안하기 전 intake 확인 NEGATIVE(cache) | **PatientState만으로는 불가** | 결정 D1 |
| bootstrap "잘 모르겠어요" | **불가** | 상태에 없음. 결정 D1 |
| 원문 transcript | 요구하지 않음 | 계약에서 금지 |

## 3. JSON 계약 `medmap-clinical-summary-v1`

### 3-1. 원칙
- 파생값. **세션·sessionStorage·서버에 저장하지 않는다.** 같은 입력 → 같은 JSON(시간·난수 없음).
- 입력은 `PatientState`(또는 `medmap-session-v1` dict) + `model_context` + 진단 top3. 원문 텍스트·`matched_text`·IG(bits)·`MEDMAP_*` 코드는 입력으로 받지도 출력하지도 않는다.
- 버전 키는 기존 계약과 같은 이름 `schema_version`을 쓴다(사용자 예시의 `schema`와 다름 — 결정 D3에서 확인).
- 식별정보 없음(age·sex만, 기존 세션 계약과 같은 범위).
- 조용한 보정 없음: 세션 검증 실패는 기존 `SessionValidationError`/`UnsupportedSchemaVersion`을 그대로 올린다.

### 3-2. 필드 (키 순서 고정 = 아래 순서)

| # | 키 | 타입 | 규칙 |
|---|---|---|---|
| 1 | `schema_version` | `"medmap-clinical-summary-v1"` | 상수 |
| 2 | `source_session_schema` | `"medmap-session-v1"` | 입력 세션 버전 |
| 3 | `model_context` | `"k3"\|"k5"\|"k10"` | 세션 값 |
| 4 | `patient` | `{age:int, sex:"M"\|"F"}` | 상태 그대로 |
| 5 | `chief_complaint` | `Item \| null` | `initial_evidence`가 있으면 Item(`source:"initial"`), 없으면 null. `label_ko` = `initial_evidence_ko.json`의 `label_ko`(없으면 question_ko) |
| 6 | `confirmed_positive` | `Item[]` | status POSITIVE, **initial 제외**, asked 순서 |
| 7 | `confirmed_negative` | `Item[]` | status NEGATIVE, asked 순서 |
| 8 | `confirmed_values` | `Item[]` | status VALUE(부위·양상·0~10 척도 등), asked 순서. 사용자 예시에 없는 **추가 키**(VALUE를 양성/음성에 억지로 넣지 않기 위해) |
| 9 | `unknown` | `Item[]` | status UNKNOWN("잘 모르겠어요"), asked 순서 |
| 10 | `not_applicable` | `Item[]` | status NOT_APPLICABLE, asked 순서 |
| 11 | `answered_questions` | `Item[]` | **initial 포함 전체** asked 순서(원장 역할). 6~10은 이 목록의 status별 부분집합 |
| 12 | `diagnosis_candidates` | `Candidate[]` (0~3) | 입력 top3를 확률 내림차순 그대로. 순위 번호 필드 없음 |
| 13 | `questions_used` | `int \| null` | `n_additional − k`, 음수면 null(`api._questions_used`와 동일 식, parity 테스트로 고정) |
| 14 | `max_questions` | `int` | 호출자가 준 값(기본 `config.DEFAULT_MAX_QUESTIONS`=3). API는 서버 설정값을 넘긴다 |
| 15 | `stop_reason` | `str \| null` | turn에서 받은 값(`MAX_QUESTIONS`/`NO_ELIGIBLE_QUESTION`/`UNSUPPORTED_SESSION_SHAPE`), 상태만으로 만들면 null |
| 16 | `session_shape` | `"NORMAL"\|"UNSUPPORTED"` | `questions_used is None` → UNSUPPORTED |
| 17 | `display` | `{section_titles_ko:{...}, notice_ko:str}` | 화면/복사/인쇄용 고정 문구(§4). 계산값 아님 |

**Item**
```json
{
  "question_id": "E_55",
  "source": "initial | start | engine",
  "status": "POSITIVE | NEGATIVE | VALUE | UNKNOWN | NOT_APPLICABLE",
  "values": ["V_89"],
  "question_ko": "어느 부위에 통증이 있나요? (해당하는 곳을 모두 고르세요)",
  "question_original": "Do you feel pain somewhere?",
  "answer_ko": "이마",
  "label_ko": null,
  "is_fallback": false
}
```
- `values`: VALUE일 때 DDXPlus value code 배열(세션과 동일), 그 외 `[]`.
- `answer_ko`: POSITIVE→`yes_label`("예"), NEGATIVE→`no_label`("아니요"), UNKNOWN→`unknown_choice_label`("잘 모르겠어요"), NOT_APPLICABLE→"해당 없음"(모듈 상수, 라벨 파일에 상태용 키가 없음), VALUE→값별 한국어(없으면 영문 `value_labels`, 그것도 없으면 code; 0~10 척도는 숫자 문자열) `", "`로 연결. 규칙은 `QuestionPresenter._choices`(`question_presentation.py:96-110`)와 같게.
- `label_ko`: chief_complaint에만 채움(initial 짧은 라벨), 나머지는 null — 향후 terminology 계층이 채울 자리.
- `is_fallback`: 질문 문구 또는 어떤 값 라벨이라도 영문 fallback이면 true.
- `source` 판정: asked 순서에서 `initial_evidence` = `initial`; 그 뒤 추가 관측 중 앞 `k`개 = `start`(intake 확인·bootstrap 답); 나머지 = `engine`(엔진이 제안해 답한 질문, cache 자동 적용 포함). `n_additional < k`(UNSUPPORTED)이면 추가 관측 전부 `start`.

**Candidate**
```json
{"name": "URTI", "display_name": "URTI", "is_fallback": true, "probability": 0.3879264295101166}
```
- `name`: 모델 클래스명(영문, 원본 키). `display_name`: 현재는 `name`과 동일 + `is_fallback: true`(master에 질환 한국어명 없음). terminology 계층이 들어오면 `display_name`만 바뀐다.
- `probability`: float 원값(반올림은 표시 계층 몫 — 기존 `formatPercent` 규칙과 충돌 방지).

### 3-3. 출력 예 (fixture `turn.answer3.json` 기준, 축약)
```json
{
  "schema_version": "medmap-clinical-summary-v1",
  "source_session_schema": "medmap-session-v1",
  "model_context": "k3",
  "patient": {"age": 45, "sex": "M"},
  "chief_complaint": {"question_id": "E_53", "source": "initial", "status": "POSITIVE", "values": [],
                      "question_ko": "이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?",
                      "question_original": "…", "answer_ko": "예", "label_ko": "통증", "is_fallback": false},
  "confirmed_positive": [],
  "confirmed_negative": [{"question_id": "E_146", "source": "engine", "status": "NEGATIVE", "answer_ko": "아니요", "is_fallback": true, "…": "…"}],
  "confirmed_values": [{"question_id": "E_55", "source": "start", "answer_ko": "이마", "…": "…"}, "… E_56·E_204·E_54·E_57"],
  "unknown": [],
  "not_applicable": [],
  "answered_questions": ["E_53(initial)", "E_55·E_56·E_204(start)", "E_54·E_57·E_146(engine)"],
  "diagnosis_candidates": [{"name": "URTI", "display_name": "URTI", "is_fallback": true, "probability": 0.3879},
                           "… PSVT, HIV (initial infection)"],
  "questions_used": 3,
  "max_questions": 3,
  "stop_reason": "MAX_QUESTIONS",
  "session_shape": "NORMAL",
  "display": {"section_titles_ko": {"…": "…"}, "notice_ko": "…"}
}
```

## 4. 문구 규칙

- `display.section_titles_ko`(고정):
  `chief_complaint`="처음 말씀하신 증상", `confirmed_positive`="있다고 답한 증상", `confirmed_negative`="없다고 답한 증상", `confirmed_values`="자세히 답한 내용", `unknown`="잘 모르겠다고 답한 항목", `not_applicable`="해당 없음", `answered_questions`="답한 순서", `diagnosis_candidates`="현재 확인이 필요한 진단 후보", 문서 제목 `title`="현재까지 확인된 정보".
- `display.notice_ko`(초안, 결정 D2에서 확정): "진료 전 참고용으로 정리한 정보이며 진단 결과가 아닙니다. 진단은 의료진이 합니다."
- **금지어(테스트로 검사, 출력 JSON 전체 문자열 대상):** "최종 진단", "진단했습니다", "진단 결과입니다", "1위", "2위", "3위", "확진". "진단 결과가 아닙니다"는 허용(부정문) — 금지어 목록은 정확한 부분문자열로 정의해 오탐 없게.
- UI 비노출 항목은 출력에 없음: `information_gain`, `MEDMAP_*`, `candidates`(debug), 원문/`matched_text`.
- `UNKNOWN`은 음성으로 쓰지 않는다(별도 목록). UNASKED 항목은 어떤 목록에도 나오지 않는다("없음"으로 추정 금지).

## 5. 모듈 설계 `medmap/clinical_summary.py`

```python
CLINICAL_SUMMARY_SCHEMA_VERSION = "medmap-clinical-summary-v1"

class LabelProvider:                      # terminology 계층 hook
    def question(self, evidence_id) -> tuple[str, str, bool]   # (question_ko, question_original, is_fallback)
    def value(self, evidence_id, code) -> tuple[str, bool]      # (label, is_fallback)
    def initial_label(self, evidence_id) -> str | None          # initial 96 label_ko
    def diagnosis(self, name) -> tuple[str, bool]               # (display_name, is_fallback) — 기본: (name, True)

class PresenterLabelProvider(LabelProvider):  # 기본 구현: QuestionPresenter + initial_evidence_ko.json 읽기만

def questions_used(state, model_context) -> int | None        # n_additional − k, 음수 None
def build_clinical_summary(state, model_context, diagnoses, *, labels, max_questions=3,
                           stop_reason=None) -> dict          # diagnoses: [(name, prob)] 또는 [{"name","probability"}]
def summary_from_session(session: dict, diagnoses, *, catalog, labels, **kw) -> dict   # deserialize_session 재사용
def summary_from_turn_payload(turn: dict, *, catalog, labels) -> dict                   # turn["session"], ["diagnoses"], ["stop_reason"], ["max_questions"]
```
- 모델을 import하지 않는다(진단은 인자로 받음) → 테스트에 `model_k*.pkl` 불필요. `EvidenceCatalog`(evidence 정의 JSON)만 필요.
- `questions_used`는 `api._questions_used`를 import하지 않고 같은 식을 둔다(`api` import 시 FastAPI 로딩 회피). parity 테스트가 두 구현을 대조.
- 향후 확장(이번 미구현): `render_text(summary) -> str`(복사용 plain text), `render_html(summary)`(인쇄 CSS), PDF는 그 위 별도 계층. 모두 summary JSON만 입력으로 받게 해 계산 로직과 분리.

## 6. API 영향

- **이번 범위: 없음(0줄).** `medmap/api.py` 수정·import 추가 없음.
- 다음 단계 옵션(결정 D2, 별도 승인): 작은 별도 router 파일 `medmap/clinical_summary_api.py`(`APIRouter`, `POST /v1/session/summary` {session} → 상태 복원 → `DiagnosisEngine.diagnose` → summary). `api.py`에는 `app.include_router(...)` **1줄**만 추가. 또는 프론트가 이미 가진 turn을 쓰는 JS 포트(로직 이중화라 비추천). turn payload에 summary 필드 추가는 계약 변경이라 채택하지 않는다.

## 7. 파일

**새 파일**
- `medmap/clinical_summary.py`
- `tests/test_clinical_summary.py`
- `tests/fixtures/clinical_summary_turn_answer3.json` — `medmap-web/src/test/fixtures/turn.answer3.json` 사본(백엔드 테스트가 프론트 경로에 의존하지 않도록. 동일성은 테스트 1개로 확인)

**수정 파일:** 없음. (`medmap/__init__.py` export 추가도 하지 않는다 — 다른 브랜치와 충돌 최소화.)

## 8. 테스트 목록 (`tests/test_clinical_summary.py`, unittest, 모델 불필요)

| # | 테스트 | 검증 |
|---|---|---|
| 1 | schema·키 순서 | `list(summary)`가 §3-2 순서와 정확히 같음, `schema_version` 상수 |
| 2 | chief complaint | initial E_53 → `label_ko`="통증", `source`="initial", confirmed_positive에 E_53 없음 |
| 3 | initial 없음 | `chief_complaint is None`, 예외 없음 |
| 4 | status 분할 | POSITIVE/NEGATIVE/VALUE/UNKNOWN/NA 합성 상태 → 각 목록 정확, 합집합 = answered_questions − initial, 중복 없음 |
| 5 | UNKNOWN ≠ NEGATIVE | UNKNOWN 항목이 confirmed_negative에 없음, answer_ko="잘 모르겠어요" |
| 6 | UNASKED 미출력 | 묻지 않은 evidence가 어떤 목록에도 없음 |
| 7 | VALUE 라벨 | V_89 → "이마", 척도 E_56 "2" → "2", 복수 값 ", " 연결 |
| 8 | fallback | E_204·E_146 → 영문 질문 + `is_fallback: true` |
| 9 | source 분류 | fixture: E_53 initial / E_55·E_56·E_204 start / E_54·E_57·E_146 engine |
| 10 | questions_used parity | k3·k5·k10 × n_additional 0..8 에서 `clinical_summary.questions_used` == `api._questions_used`(api import, 기존 test_api와 같은 의존) |
| 11 | UNSUPPORTED 형태 | n_additional < k → `questions_used None`, `session_shape "UNSUPPORTED"`, 추가 관측 전부 `start` |
| 12 | turn payload 입력 | fixture → questions_used 3, stop_reason MAX_QUESTIONS, 후보 URTI·PSVT·HIV 순서·확률 원값 |
| 13 | 새로고침 재구성 | fixture session을 `json.dumps/loads` 왕복 + `deserialize_session` 후 만든 summary == 원본 summary |
| 14 | 결정성 | 같은 입력 2회 → `json.dumps(sort_keys=False)` 문자열 동일 |
| 15 | 금지어 | 출력 JSON 문자열에 §4 금지어 0건, `display.section_titles_ko.diagnosis_candidates` == "현재 확인이 필요한 진단 후보" |
| 16 | 비노출 키 | 출력 전체(재귀)에 `information_gain`·`matched_text`·`text`·`transcript` 키 없음, 값에 `MEDMAP_` 없음 |
| 17 | 입력 불변 | 호출 전후 `PatientState`·입력 dict 동일(깊은 비교) |
| 18 | 잘못된 세션 | 부모 gate 위반·버전 불일치 → 기존 예외 그대로(보정 없음) |
| 19 | 후보 개수 | 0개·5개 입력 → 0개·앞 3개만, 순위 번호 키 없음 |
| 20 | fixture 동일성 | `tests/fixtures/…` == `medmap-web/src/test/fixtures/turn.answer3.json`(파일이 있을 때만, 없으면 skip) |

실행(승인 후, 단일 파일만): `nice -n 19 env OMP_NUM_THREADS=2 python -m unittest tests.test_clinical_summary -v` — 모델 로딩 없음, 수 초 예상. 전체 회귀(`unittest discover`)는 기존 모듈 무수정이므로 whole-branch review 시 1회만.

## 9. Tasks (승인 후 실행)

### Task 0: Preflight (coordinator)
- `git status` clean, HEAD = 이 문서 커밋, `data` symlink 읽기 가능(`EvidenceCatalog()` 로딩만), `free -m` ≥ 3GB.
- 테스트 입력 `data/ddxplus/en/release_evidences.json`(EvidenceCatalog)은 추적되지 않는다. 새 환경에서는 `scripts/download_public.sh`(figshare `files/40278013` → `data/ddxplus/en/release_evidences.json`)로 받는다. 이 worktree는 `~/medmap/data` read-only symlink를 쓴다. 신규 테스트는 `model_k*.pkl`이 필요 없다.
- 프론트 `node_modules`는 변경되지 않은 `medmap-web/package-lock.json`에서 `npm ci`로 재현한다.
- `requirements-api.txt` 버전 미고정은 프로젝트 공통 사항이라 이번 범위 밖(기록만).
- 기존 모듈 무수정 기준선: `git diff 336463f -- medmap/ tests/ medmap-web/` 빈 출력 기록.

### Task 1: LabelProvider + questions_used (TDD)
- 테스트 5·7·8·10 먼저(RED) → `PresenterLabelProvider`, `questions_used` 구현(GREEN).
- 커밋: `feat(clinical-summary): label provider hook and questions_used parity`

### Task 2: build_clinical_summary core (TDD)
- 테스트 1~4·6·9·11·14·15·16·17·19 → 구현.
- 커밋: `feat(clinical-summary): core summary builder (medmap-clinical-summary-v1)`

### Task 3: session/turn 어댑터 + fixture
- fixture 사본 추가, 테스트 12·13·18·20 → `summary_from_session`, `summary_from_turn_payload`.
- 커밋: `feat(clinical-summary): session/turn adapters and refresh reconstruction test`

### Task 4: 검증·원장
- 단일 파일 테스트 통과, `git diff 336463f --stat`이 새 파일 3개 + 이 문서/원장뿐임을 확인. whole-branch review. ledger Task log 갱신.
- 금지: api.py·프론트·기존 모듈 수정, PDF, LLM, 새 의존성.

## 10. 사용자 결정 필요

- **D1.** intake 확인 NEGATIVE(엔진 미제안 cache)와 bootstrap "잘 모르겠어요"는 PatientState에 없다. v1 summary를 **PatientState만**으로 만들고 이 둘은 제외할지(권장 — source of truth 일관, 새로고침 재구성 보장), 아니면 선택 인자로 받아 `source:"intake_unapplied"` 별도 목록으로 붙일지.
- **D2.** 이번엔 core+테스트만(API 0줄) 하고, 화면 연결 시점에 `medmap/clinical_summary_api.py` + `api.py` include 1줄로 할지. 함께 `notice_ko` 문구 확정.
- **D3.** 버전 키를 기존 계약처럼 `schema_version`으로 쓸지(권장), 예시대로 `schema`로 쓸지. VALUE 답을 위한 추가 키 `confirmed_values`·`not_applicable` 허용 여부.

## Self-Review
- 기존 계약·동작 변경: 없음(새 파일만). api.py 0줄. 프론트 0줄.
- "최종 진단" 금지: 문구 상수 + 테스트 15.
- UNKNOWN: 별도 목록, 음성과 분리, questions_used는 기존 식이라 UNKNOWN 답도 엔진 질문이면 1개로 셈(엔진 계약과 동일).
- 원문 transcript: 입력·출력 모두 없음, 테스트 16.
- 미확정: 질환 한국어명(master에 없음, fallback 표시), 상태용 "해당 없음" 라벨(모듈 상수), `notice_ko` 문구.
