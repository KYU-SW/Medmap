"""MedMap 세션 JSON 계약 (v1).

원칙
  - 세션의 source of truth 는 PatientState 하나뿐이다. posterior·top3·next question·IG 는
    전부 파생값이며 복원 시 모델로 다시 계산한다(세션에 저장하지 않는다).
  - UNASKED 는 저장하지 않는다(answers 목록에 없는 것이 UNASKED). NEGATIVE 와 UNKNOWN 은 구분해 저장한다.
  - value 는 항상 DDXPlus 원본 value ID 배열이다. 한국어/UI 문자열은 상태로 저장하지 않는다.
  - 식별정보(이름·연락처 등)는 계약에 포함하지 않는다. age/sex/evidence 답변만 다룬다.
  - 조용한 보정은 하지 않는다. 형식·규칙 위반은 예외로 실패한다.
표준 json 모듈 외 의존성을 추가하지 않는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import config
from .evidence import EvidenceCatalog
from .patient_state import Answer, AnswerStatus, PatientState

SESSION_SCHEMA_VERSION = "medmap-session-v1"
TURN_SCHEMA_VERSION = "medmap-turn-v1"
ANSWER_SCHEMA_VERSION = "medmap-answer-v1"

VALUE_KINDS = {AnswerStatus.VALUE.value}
NULL_VALUE_KINDS = {AnswerStatus.POSITIVE.value, AnswerStatus.NEGATIVE.value,
                    AnswerStatus.UNKNOWN.value, AnswerStatus.NOT_APPLICABLE.value}


class UnsupportedSchemaVersion(Exception):
    """지원하지 않는 schema_version — 추정하지 않고 실패한다."""


class SessionValidationError(Exception):
    """세션/답변 JSON 이 계약을 위반했을 때."""


@dataclass(frozen=True)
class SessionSnapshot:
    state: PatientState
    model_context: str


# ---------------- Answer ----------------
def serialize_answer(answer: Answer) -> dict:
    kind = answer.status.value
    return {"kind": kind, "value": list(answer.values) if kind in VALUE_KINDS else None}


def deserialize_answer(data: dict) -> Answer:
    if not isinstance(data, dict):
        raise SessionValidationError("MEDMAP_ANSWER_NOT_AN_OBJECT")
    kind = data.get("kind")
    if kind in VALUE_KINDS:
        values = data.get("value")
        if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
            raise SessionValidationError("MEDMAP_VALUE_ANSWER_REQUIRES_STRING_LIST")
        return Answer(AnswerStatus.VALUE, tuple(values))
    if kind in NULL_VALUE_KINDS:
        if data.get("value") not in (None, [], ()):
            raise SessionValidationError(f"MEDMAP_{kind}_ANSWER_MUST_HAVE_NULL_VALUE")
        return Answer(AnswerStatus(kind))
    raise SessionValidationError(f"MEDMAP_UNKNOWN_ANSWER_KIND:{kind}")


# ---------------- PatientState ----------------
def serialize_patient_state(state: PatientState, model_context: str = "k3") -> dict:
    _check_model_context(model_context)
    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "patient_state": {
            "age": int(state.age),
            "sex": state.sex,
            "model_context": model_context,
            "initial_evidence": state.initial_evidence,
            "answers": [{"question_id": evidence_id, **serialize_answer(state.answers[evidence_id])}
                        for evidence_id in state.asked if evidence_id in state.answers],
            "asked_question_ids": list(state.asked),
            "n_additional_questions": state.n_additional,
        },
    }


def deserialize_session(data: dict, catalog: EvidenceCatalog | None = None) -> SessionSnapshot:
    if not isinstance(data, dict):
        raise SessionValidationError("MEDMAP_SESSION_NOT_AN_OBJECT")
    version = data.get("schema_version")
    if version != SESSION_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(f"MEDMAP_UNSUPPORTED_SCHEMA_VERSION:{version}")
    body = data.get("patient_state")
    if not isinstance(body, dict):
        raise SessionValidationError("MEDMAP_MISSING_PATIENT_STATE")

    age = body.get("age")
    if not isinstance(age, int) or isinstance(age, bool) or age < 0 or age > 130:
        raise SessionValidationError(f"MEDMAP_INVALID_AGE:{age}")
    sex = body.get("sex")
    if sex not in ("M", "F"):
        raise SessionValidationError(f"MEDMAP_INVALID_SEX:{sex}")
    model_context = body.get("model_context", "k3")
    _check_model_context(model_context)

    catalog = catalog or EvidenceCatalog()
    initial = body.get("initial_evidence")
    if initial is not None:
        _check_evidence_id(catalog, initial)
    asked = body.get("asked_question_ids", [])
    if not isinstance(asked, list) or any(not isinstance(e, str) for e in asked):
        raise SessionValidationError("MEDMAP_INVALID_ASKED_LIST")
    if len(set(asked)) != len(asked):
        raise SessionValidationError("MEDMAP_DUPLICATE_ASKED_QUESTION")

    entries = body.get("answers", [])
    if not isinstance(entries, list):
        raise SessionValidationError("MEDMAP_INVALID_ANSWERS_LIST")
    state = PatientState(age=age, sex=sex, initial_evidence=initial, answers={}, asked=())
    seen = []
    for entry in entries:
        if not isinstance(entry, dict) or "question_id" not in entry:
            raise SessionValidationError("MEDMAP_INVALID_ANSWER_ENTRY")
        evidence_id = entry["question_id"]
        _check_evidence_id(catalog, evidence_id)
        answer = deserialize_answer(entry)
        _check_answerable(catalog, evidence_id, answer, state)
        state = state.with_answer(evidence_id, answer)
        seen.append(evidence_id)
    if asked and list(state.asked) != asked:
        raise SessionValidationError(f"MEDMAP_ASKED_LIST_MISMATCH:{asked}!={list(state.asked)}")
    declared = body.get("n_additional_questions")
    if declared is not None and declared != state.n_additional:
        raise SessionValidationError(f"MEDMAP_ADDITIONAL_COUNT_MISMATCH:{declared}!={state.n_additional}")
    return SessionSnapshot(state, model_context)


def deserialize_patient_state(data: dict, catalog: EvidenceCatalog | None = None) -> PatientState:
    return deserialize_session(data, catalog).state


# ---------------- 답변 제출 ----------------
def parse_answer_submission(data: dict, catalog: EvidenceCatalog, state: PatientState | None = None) -> tuple:
    """UI/API 제출 JSON → (question_id, Answer). state 가 있으면 중복·부모 gate 까지 검증한다."""
    if not isinstance(data, dict):
        raise SessionValidationError("MEDMAP_SUBMISSION_NOT_AN_OBJECT")
    version = data.get("schema_version", ANSWER_SCHEMA_VERSION)
    if version != ANSWER_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(f"MEDMAP_UNSUPPORTED_SCHEMA_VERSION:{version}")
    evidence_id = data.get("question_id")
    _check_evidence_id(catalog, evidence_id)
    answer = deserialize_answer(data.get("answer"))
    _check_answerable(catalog, evidence_id, answer, state)
    return evidence_id, answer


# ---------------- Turn ----------------
def serialize_turn(turn, model_context: str | None = None, include_debug: bool = False) -> dict:
    """공개 필드만 내보낸다. 전체 posterior·후보 IG 는 include_debug=True 일 때만 붙는다(세션에 저장되지 않음)."""
    context = model_context or turn.diagnoses.model_context
    payload = {
        "schema_version": TURN_SCHEMA_VERSION,
        "diagnoses": _top(turn.diagnoses),
        "diagnoses_before": None if turn.diagnoses_before is None else _top(turn.diagnoses_before),
        "next_question": None if turn.next_question is None else turn.next_question.to_dict(),
        "stop_reason": turn.stop_reason,
        "n_asked": turn.state.n_asked,
        "questions_asked_in_session": turn.questions_asked_in_session,
        "model_context": context,
        "model_context_match": turn.model_context_match,
        "session": serialize_patient_state(turn.state, context),
    }
    if include_debug:
        payload["debug"] = {
            "posterior": turn.diagnoses.probabilities,
            "posterior_before": None if turn.diagnoses_before is None else turn.diagnoses_before.probabilities,
            "candidates": [{"question_id": q, "information_gain": g} for q, g in turn.candidates],
        }
    return payload


def _top(result, n: int = 3) -> list:
    return [{"name": disease, "probability": prob} for disease, prob in result.ranking[:n]]


# ---------------- json 문자열 헬퍼 ----------------
def dumps_patient_state(state: PatientState, model_context: str = "k3", **kwargs) -> str:
    return json.dumps(serialize_patient_state(state, model_context), ensure_ascii=False, **kwargs)


def loads_patient_state(text: str, catalog: EvidenceCatalog | None = None) -> SessionSnapshot:
    return deserialize_session(json.loads(text), catalog)


def dumps_turn(turn, model_context: str | None = None, include_debug: bool = False, **kwargs) -> str:
    return json.dumps(serialize_turn(turn, model_context, include_debug), ensure_ascii=False, **kwargs)


# ---------------- 검증 도우미 ----------------
def _check_model_context(model_context) -> None:
    if model_context not in config.MODEL_CONTEXTS:
        raise SessionValidationError(f"MEDMAP_INVALID_MODEL_CONTEXT:{model_context}")


def _check_evidence_id(catalog: EvidenceCatalog, evidence_id) -> None:
    if not isinstance(evidence_id, str) or evidence_id not in catalog.questions:
        raise SessionValidationError(f"MEDMAP_UNKNOWN_EVIDENCE_ID:{evidence_id}")
    if catalog.is_excluded(evidence_id):
        raise SessionValidationError(f"MEDMAP_EXCLUDED_QUESTION:{evidence_id}")


def _check_answerable(catalog: EvidenceCatalog, evidence_id: str, answer: Answer, state: PatientState | None) -> None:
    try:
        catalog.validate_answer(evidence_id, answer)
    except ValueError as exc:                       # 질문 타입/값 불일치
        raise SessionValidationError(str(exc)) from exc
    if state is None:
        return
    if state.is_asked(evidence_id):
        raise SessionValidationError(f"MEDMAP_ALREADY_ASKED:{evidence_id}")
    parent = catalog.parent.get(evidence_id)
    if parent is not None and not state.is_positive(parent):
        raise SessionValidationError(f"MEDMAP_PARENT_GATE_VIOLATION:{evidence_id}<-{parent}")
