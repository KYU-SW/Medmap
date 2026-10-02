# MedMap 엔진 계약 (Engine Contract)

대상: MedMap 위에 UI 또는 API 서버를 붙이는 개발자.
기준 코드: `medmap/` 패키지 (commit 426f76b 시점), 테스트 `tests/` 54개.
이 문서는 코드에 맞춰 쓴 것이며, 문서 때문에 코드를 바꾸지 않는다.

---

## 1. 엔진이 하는 일

```
PatientState  ──▶ DiagnosisEngine     진단 후보(확률) 계산
              ──▶ QuestionEligibility 지금 물어볼 수 있는 질문 목록
              ──▶ NextInformationEngine 정보이득으로 다음 질문 1개 선택
              ──▶ QuestionPresenter   환자용 한국어 질문/선택지로 표현
              ──▶ 사용자 답변 → PatientState 갱신 → 같은 모델로 재추론 (반복)
```

- 진단 모델은 세션 중 **재학습하지 않는다**. 답변이 추가되면 같은 모델로 다시 예측만 한다.
- 다음 질문은 **내부 정보이득(INTERNAL_IG)** 으로만 고른다.
- 외부 질환 프로필은 현재 질문 선택 점수에 **사용하지 않는다**(설명용 자리 `explanation` 만 열려 있음).

### 연구와 제품의 경계
제품 엔진은 STEP16B에서 확정된 규칙(안전한 답변 의미, 질문 자격, 정보이득 계산, 제외 질문)을 제품 코드로 옮긴 것이다.
정보이득 기반 질문 선택 방식은 **내부 개발 검증에서 채택**되었다. 이 문서는 제품 계약 문서이므로 연구 수치는 싣지 않으며,
"실제 임상에서 정확도가 검증되었다"는 식의 주장에는 사용할 수 없다.

---

## 2. 주요 클래스와 함수

| 이름 | 위치 | 역할 | 주요 입력 → 출력 |
|---|---|---|---|
| `PatientState` | `medmap/patient_state.py` | 환자의 현재 관측 상태(불변 객체) | `PatientState.new(age, sex, initial_evidence, observed)` → 상태 / `state.with_answer(qid, answer)` → 새 상태 |
| `Answer`, `AnswerStatus` | 〃 | 한 질문의 답변 상태 | 헬퍼 `positive()`, `negative()`, `value(*codes)`, `unknown()`, `not_applicable()` |
| `EvidenceCatalog` | `medmap/evidence.py` | 질문 정의·부모 관계·답변 공간·인코딩 열 | `catalog.question(qid)` → `Question`, `catalog.validate_answer(qid, answer)` |
| `DiagnosisEngine` | `medmap/diagnosis.py` | 저장된 MODEL_k 로 예측만 수행 | `DiagnosisEngine(catalog, model_context)` / `diagnose(state)` → `DiagnosisResult` |
| `DiagnosisResult` | 〃 | 진단 결과 | `.probabilities`(전체), `.ranking`, `.top1/.top2/.top3`, `.model_context` |
| `QuestionEligibility` | `medmap/eligibility.py` | 지금 물어볼 수 있는 질문 판정 | `eligible_questions(state)` → evidence ID 목록(번호 오름차순) |
| `AnswerLikelihoodTable` | `medmap/next_information.py` | STEP16B 산출물 `P(answer\|disease)` 로드 | `information_gain(posterior)` → 질문별 IG 벡터 |
| `NextInformationEngine` | 〃 | 진단 + 질문 선택 + 종료 판단 | `start(state)` → `Turn`, `answer(turn, qid, answer)` → `Turn`, `rank_questions(diagnoses, eligible)` |
| `QuestionProposal` | 〃 | 선택된 질문(+표현) | `.to_dict()` → next_question JSON |
| `Turn` | 〃 | 한 턴의 화면 데이터 | `.state`, `.diagnoses`, `.diagnoses_before`, `.next_question`, `.stop_reason`, `.candidates`, `.model_context_match`, `.questions_asked_in_session` |
| `ExplanationProvider` | 〃 | "왜 이 질문인가" 설명기 자리(기본 `None`) | `explain(qid, diagnoses)` → `str | None` |
| `QuestionPresenter` | `medmap/question_presentation.py` | 한국어 표현 · UI 선택값 변환 | `present(qid, ig, explanation)` → `PresentedQuestion`, `to_answer(qid, selection)` → `Answer`, `coverage()` |
| `SessionSnapshot` | `medmap/serialization.py` | 복원 결과 묶음 | `.state`, `.model_context` |
| serialization 함수 | 〃 | JSON 계약 | `serialize_patient_state`, `deserialize_session`, `deserialize_patient_state`, `serialize_turn`, `parse_answer_submission`, `dumps_patient_state`, `loads_patient_state`, `dumps_turn` |

---

## 3. model_context 계약 (중요)

지원 값: **`k3`, `k5`, `k10`** (그 외는 오류).

- `MODEL_k` 는 "초기 evidence + **정확히 k개**의 추가 관측 답변" 상태로 학습된 모델이다.
- 제품 엔진은 **자동 전환을 하지 않는다.** 호출자가 `DiagnosisEngine(catalog, model_context=...)` 로 명시한다.
- 세션 도중 질문이 늘어도 `k3 → k5` 로 **바꾸지 않는다**(STEP16B도 같은 모델을 계속 썼다).
- `Turn.model_context_match` 는 현재 상태가 선택된 학습 조건과 일치하는지 드러내는 **표시값**이다.
  `state.n_additional == k + questions_asked_in_session` 이면 `true`.
  **`false` 라고 해서 모델을 자동으로 바꾸지 않는다.** 필요하면 호출자가 판단해 새 `DiagnosisEngine` 을 만든다.
- 선택 기준(권장): 세션 시작 시 이미 확보된 추가 답변 수에 가장 가까운 k. 확보 정보가 적으면 `k3`.

---

## 4. PatientState 계약

| 필드 | 의미 |
|---|---|
| `age` | 정수 0–130 |
| `sex` | `"M"` 또는 `"F"` |
| `model_context` | `k3` / `k5` / `k10` (세션 JSON에만 존재, 파이썬 객체에는 없음) |
| `initial_evidence` | 최초 공개된 evidence ID(항상 binary POSITIVE) 또는 `null` |
| `answers` | 질문별 답변 목록(물어본 순서) |
| `asked_question_ids` | 물어본 질문 ID 순서 |
| `n_additional_questions` | 초기 evidence 를 제외한 답변 수 |

답변 상태(`kind`): **`POSITIVE` · `NEGATIVE` · `VALUE` · `UNKNOWN` · `NOT_APPLICABLE`**

- **UNASKED 는 `answers` 에 존재하지 않는다.** 항목이 없는 것이 UNASKED 다.
- **UNASKED ≠ NEGATIVE**, **UNKNOWN ≠ NEGATIVE**. UNKNOWN 은 어떤 특징도 켜지 않지만 재질문은 막는다.
- `VALUE` 의 `value` 는 **원본 DDXPlus value ID 배열**이다. 한국어 라벨·UI 문자열을 저장하지 않는다.
- `VALUE` 외의 kind 는 `value` 가 반드시 `null` 이다.

---

## 5. 세션 JSON — `medmap-session-v1`

`serialize_patient_state(state, model_context)` 의 실제 출력:

```json
{
 "schema_version": "medmap-session-v1",
 "patient_state": {
  "age": 45,
  "sex": "M",
  "model_context": "k3",
  "initial_evidence": "E_53",
  "answers": [
   {"question_id": "E_53", "kind": "POSITIVE", "value": null},
   {"question_id": "E_55", "kind": "VALUE", "value": ["V_89"]},
   {"question_id": "E_56", "kind": "VALUE", "value": ["2"]},
   {"question_id": "E_204", "kind": "VALUE", "value": ["V_10"]}
  ],
  "asked_question_ids": ["E_53", "E_55", "E_56", "E_204"],
  "n_additional_questions": 3
 }
}
```

복원: `deserialize_session(data, catalog)` → `SessionSnapshot(state, model_context)`,
상태만 필요하면 `deserialize_patient_state(data, catalog)`.
문자열 헬퍼: `dumps_patient_state(state, model_context)` / `loads_patient_state(text, catalog)`.

---

## 6. Turn JSON — `medmap-turn-v1`

`serialize_turn(turn, model_context=None, include_debug=False)` 의 공개 필드:

| 필드 | 내용 |
|---|---|
| `schema_version` | `"medmap-turn-v1"` |
| `diagnoses` | 상위 3개 `[{"name": ..., "probability": ...}]` |
| `diagnoses_before` | 직전 턴의 상위 3개 또는 `null` |
| `next_question` | 아래 표 또는 `null`(종료 시) |
| `stop_reason` | `null` / `"MAX_QUESTIONS"` / `"NO_ELIGIBLE_QUESTION"` |
| `n_asked` | 상태에 기록된 총 답변 수 |
| `questions_asked_in_session` | 이번 세션에서 엔진이 물어 답변된 수 |
| `model_context` | `k3` / `k5` / `k10` |
| `model_context_match` | 학습 조건 일치 표시(3절) |
| `session` | `medmap-session-v1` 봉투 전체 |

`next_question` 필드(= `QuestionProposal.to_dict()`):

| 필드 | 내용 |
|---|---|
| `question_id` | evidence ID (예 `E_54`) |
| `question_ko` | 환자용 한국어(미등록이면 원문) |
| `question_original` | DDXPlus 원문 |
| `answer_type` | `YES_NO` / `SINGLE_CHOICE` / `MULTI_CHOICE` / `SCALE` (표현 계층이 붙었을 때) |
| `choices` | `[{"value", "label", "original_label", "is_fallback"}]`, 마지막은 항상 `{"value": null, "label": "잘 모르겠어요"}` |
| `information_gain` | bits |
| `is_fallback` | 한국어 미등록 여부 |
| `explanation` | 현재 항상 `null` |
| `question_text`, `answer_type_raw`, `possible_values` | 하위 호환 필드(원문 텍스트, `BINARY`/`CATEGORICAL`/`MULTI`, 원본 value ID 목록) |

표현 계층을 붙이지 않으면 `question_ko`/`question_original`/`choices`/`is_fallback` 이 없고 `answer_type` 이 `answer_type_raw` 와 같다.

### Debug 출력
기본은 `include_debug=False` 이며 일반 UI/API 는 debug 를 사용하지 않는다.
`include_debug=True` 일 때만 `debug` 키가 붙는다: `posterior`(전체 확률), `posterior_before`, `candidates`(상위 질문과 IG).
**전체 posterior 는 세션 상태의 source of truth 가 아니다**(세션 JSON 에는 저장되지 않는다).

---

## 7. 답변 제출 — `medmap-answer-v1`

```json
{"schema_version": "medmap-answer-v1", "question_id": "E_155", "answer": {"kind": "NEGATIVE", "value": null}}
{"schema_version": "medmap-answer-v1", "question_id": "E_54",  "answer": {"kind": "VALUE",    "value": ["V_181", "V_183"]}}
{"schema_version": "medmap-answer-v1", "question_id": "E_91",  "answer": {"kind": "UNKNOWN",  "value": null}}
```

- `parse_answer_submission(data, catalog, state=None)` → `(question_id, Answer)`.
  `state` 를 넘기면 중복 답변·부모 gate 까지 검증한다. `schema_version` 은 생략 시 `medmap-answer-v1` 로 간주한다.
- 예/아니오 질문은 `POSITIVE`/`NEGATIVE`, 모름은 `UNKNOWN`, 선택형은 `VALUE` + **원본 value ID 배열**.
- **UI 한국어 문자열을 그대로 제출하지 않는다.** 화면 선택값은 `QuestionPresenter.to_answer(question_id, selection)` 로
  원본 코드로 변환한 뒤 제출한다(`selection` 은 `True/False/None`, value code, 또는 라벨 문자열).

---

## 8. 질문 자격 규칙

질문 후보가 되려면 **모두** 만족해야 한다.

1. 아직 묻지 않았고 상태에 답변이 없다(`state.is_asked(qid)` 가 거짓).
2. 제외 질문이 아니다 — **`E_134`, `E_152` 는 영구 제외**(후보·표현·IG 인덱스 어디에도 없다).
3. 부모 조건이 없거나, 부모가 있으면 **현재 visible parent 가 POSITIVE** 이다.
   부모가 `NEGATIVE` · `UNKNOWN` · `NOT_APPLICABLE` · UNASKED 이면 자식은 후보가 아니다.

hidden answer(아직 공개되지 않은 실제 답), 정답 질환, 질환별 증상 목록은 eligibility 계산에 사용하지 않는다.
목록은 evidence 번호 오름차순으로 결정적이다.

---

## 9. 질문 선택 규칙

현재 선택기는 **INTERNAL_IG** 하나다. 개념적으로

```
IG(질문) = 현재 진단 불확실성 − 그 질문에 답했을 때 예상되는 불확실성
```

이 가장 큰 질문을 고른다. 계약 세부:

- STEP16B 에서 만들어 저장된 `P(answer | disease)` 통계(`ig_table_step16b_train.npz`)만 사용한다.
- 런타임에 통계를 다시 추정하지 않고, 모델도 재학습하지 않는다.
- Laplace α = 1.0 (저장된 표에 이미 반영), 로그 밑 2.
- 확률 0 인 답변(불가능한 답)은 기여 0.
- 동점은 **evidence ID 오름차순**.
- 외부 프로필 점수를 IG 에 섞지 않는다.

---

## 10. 종료(stopping) 계약

현재 종료 사유는 두 가지뿐이다.

| `stop_reason` | 조건 |
|---|---|
| `MAX_QUESTIONS` | 이번 세션에서 물은 수가 `max_questions` 에 도달(기본 **3**, `NextInformationEngine(..., max_questions=n)` 로 조정) |
| `NO_ELIGIBLE_QUESTION` | 후보 질문이 하나도 없음 |

확신도 임계값·IG 임계값 같은 종료 규칙은 **현재 존재하지 않는다**(향후 별도 연구·기능).
종료 시 `next_question` 은 `null` 이다.

---

## 11. 질문 표현 계층

- 한국어 매핑 **53 / 223**, fallback **170 / 223**(원문 그대로 반환 + `is_fallback: true`), value code 매핑 188개.
  부모 질문 3/3, 선택 가능한 자식 질문 12/12 포함.
- 한국어는 `medmap/data/question_labels_ko.json` 의 **정적 매핑**이다. **런타임 번역 API·LLM 호출은 없다.**
- 모든 질문의 선택지 마지막에 `"잘 모르겠어요"`(value `null`)가 붙고, 이는 모델의 `UNKNOWN` 상태로 변환된다.
- 표현 계층은 질문 선택·IG·후보 목록·진단 확률에 **영향을 주지 않는다**(테스트로 고정).

---

## 12. 세션 저장·복원

- **source of truth 는 `PatientState` 하나.** posterior, 진단 top3, 다음 질문, IG, 설명은 모두 파생값이며 저장하지 않는다.
- 복원 절차: JSON → `PatientState`(+`model_context`) → 모델 재추론 → 질문 재계산.
  같은 상태면 top3·전체 확률·다음 질문 ID·IG 가 동일하다.

CLI 예시:

```bash
# 새 세션 진행 후 저장
~/ai_env/bin/python -m medmap.demo_cli --age 45 --sex M --initial E_53 \
    --observed E_55=V_89 --observed E_56=2 --observed E_204=V_10 \
    --answers "8" --max-questions 1 --save-session session.json

# 저장된 세션에서 이어서
~/ai_env/bin/python -m medmap.demo_cli --load-session session.json --max-questions 2
```

---

## 13. Python 사용 예제

```python
from medmap import DiagnosisEngine, EvidenceCatalog, NextInformationEngine, PatientState, value
from medmap.question_presentation import QuestionPresenter
from medmap.serialization import dumps_patient_state, loads_patient_state, parse_answer_submission

catalog = EvidenceCatalog()
presenter = QuestionPresenter(catalog)
engine = NextInformationEngine(DiagnosisEngine(catalog, "k3"), presenter=presenter, max_questions=3)

state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"), "E_204": value("V_10")})
turn = engine.start(state)
view = turn.next_question.to_dict()          # question_ko, choices, information_gain ...

answer = presenter.to_answer(view["question_id"], "타는 듯한")   # 화면 선택값 → 원본 코드
turn = engine.answer(turn, view["question_id"], answer)

text = dumps_patient_state(turn.state, "k3")                      # 세션 저장
snapshot = loads_patient_state(text, catalog)                     # 복원
turn = engine.start(snapshot.state)

submission = {"question_id": turn.next_question.evidence_id, "answer": {"kind": "VALUE", "value": ["V_123"]}}
question_id, parsed = parse_answer_submission(submission, catalog, turn.state)
turn = engine.answer(turn, question_id, parsed)
print(turn.stop_reason, [d for d, _ in turn.diagnoses.top3])
```

---

## 14. 오류 계약

| 예외 | 발생 시점 |
|---|---|
| `serialization.SessionValidationError` | 존재하지 않는 evidence ID, 존재하지 않는 value ID, 질문 타입과 맞지 않는 answer kind, 제외 질문(E_134/E_152) 제출·복원, 부모 gate 위반, 이미 물은 질문 중복 답변, 잘못된 age/sex/model_context, 세션 구조 불일치 |
| `serialization.UnsupportedSchemaVersion` | `schema_version` 이 지원 값(`medmap-session-v1`, `medmap-answer-v1`)이 아닐 때 |
| `ValueError` (`MEDMAP_INVALID_ANSWER…`) | `EvidenceCatalog.validate_answer` / `NextInformationEngine.answer` 에서 질문 유형·값이 맞지 않을 때 |
| `ValueError` (`MEDMAP_UNEXPECTED_ANSWER`) | 제안된 질문이 아닌 질문에 답을 넣었을 때 |
| `ValueError` (`MEDMAP_ALREADY_ASKED`) | 같은 질문에 두 번 답을 넣을 때(`PatientState.with_answer`) |
| `ValueError` (`MEDMAP_UNRECOGNIZED_SELECTION`) | `QuestionPresenter.to_answer` 가 UI 선택값을 원본 코드로 환원하지 못할 때 |
| `ValueError` (`MEDMAP_UNKNOWN_MODEL_CONTEXT`) | `DiagnosisEngine` 에 k3/k5/k10 이 아닌 값을 줬을 때 |
| `config.MedMapForbiddenPath` | 제품 코드가 연구 봉인 경로(원본 VALIDATION/TEST, `release_conditions.json`)에 접근하려 할 때 |
| `ValueError` (`MEDMAP_CLASS_ORDER_MISMATCH`, `MEDMAP_FEATURE_LAYOUT_MISMATCH`, `MEDMAP_ANSWER_SPACE_MISMATCH`) | 모델·IG 표·evidence 정의의 형식이 서로 어긋날 때(산출물 교체 사고 방지) |

---

## 15. 개인정보

엔진 세션에는 **실명·주민등록번호·전화번호·주소·계정 정보를 저장하지 않는다.**
엔진이 쓰는 값은 `age`, `sex`, 그리고 임상 답변뿐이다.
사용자 계정 ID나 진료 식별자가 필요하면 앱/서버 계층에서 별도로 관리하고 세션 JSON과 분리한다.

---

## 16. 금지사항 (DO NOT)

1. 런타임에 `model.fit` 호출 금지 — 답변이 추가돼도 예측만 한다.
2. `model_context` 를 무음으로 자동 전환하지 말 것. `model_context_match=false` 는 표시일 뿐이다.
3. `E_134` / `E_152` 를 질문하거나 답변으로 제출하지 말 것.
4. 부모 gate 우회 금지 — 부모가 POSITIVE 가 아닌데 자식 질문/답변을 넣지 않는다.
5. `UNKNOWN` 을 `NEGATIVE` 로 바꾸지 말 것. UNASKED 를 NEGATIVE 로 채우지도 않는다.
6. UI 한국어 문자열을 모델 value 로 직접 저장하지 말 것 — 항상 원본 value ID.
7. posterior(또는 top3)를 세션의 source of truth 로 쓰지 말 것 — 상태는 `PatientState` 뿐이다.
8. 외부 질환 프로필 점수를 IG 에 임의로 결합하지 말 것.
9. 제품 코드가 연구 데이터(원본 VALIDATION/TEST, `release_conditions.json`)에 접근하는 구조를 추가하지 말 것.
10. 새 종료 임계값(확신도·IG)을 근거 없이 넣지 말 것 — 현재 계약에 없다.

---

## 17. UI / API 개발자를 위한 최소 흐름

1. 세션 생성 (`PatientState` 또는 저장된 `medmap-session-v1` 복원)
2. `engine.start(state)` 로 `Turn` 받기
3. `diagnoses` 표시
4. `next_question`(`question_ko`, `choices`) 표시
5. 선택값을 `medmap-answer-v1` JSON 으로 제출
6. `engine.answer(...)` 로 새 `Turn` 받기
7. `stop_reason` 이 생길 때까지 2–6 반복, 필요하면 `session` 을 저장

API 서버가 붙어도 동일하다. 서버는 `serialize_turn(...)` 결과를 그대로 응답 본문으로 쓰고,
요청 본문은 `medmap-answer-v1` 을 받아 `parse_answer_submission` 으로 검증하면 된다.
