"""Doctor View (medmap-doctor-view-v1): 같은 엔진 결과를 의사용으로 투영한다.

원칙
  - 엔진·IG·모델을 호출하지 않는다. 입력(기존 _run 이 만든 turn payload + 같은 상태의 DiagnosisResult)을 투영만 한다.
    다음 질문 선택은 기존 NextInformationEngine 결과(turn_payload["next_question"])를 그대로 쓴다.
  - 확률·IG·점수를 출력하지 않는다(보정 미검증). 감별 후보는 기존 ranking 순서의 상위 8개 이름만 — 표시 전용이며
    IG 계산 범위와 무관하다.
  - Blind: working diagnosis 가 PENDING 이면 후보·질문을 응답에 넣지 않는다.
  - Working diagnosis 는 에코만 한다. 후보와의 비교·일치/불일치 판정은 하지 않는다(Disease Knowledge Layer 이후).
  - 환자 요약 버킷은 clinical_summary.build_clinical_summary 를 호출해 쓴다(로직 복제 없음). 저장 없음.
설계: docs/superpowers/specs/2026-09-29-medmap-doctor-mode-foundation.md
"""
from __future__ import annotations

from .clinical_summary import LabelProvider, build_clinical_summary
from .serialization import deserialize_session

DOCTOR_VIEW_SCHEMA_VERSION = "medmap-doctor-view-v1"
DOCTOR_VIEW_KEYS = ("schema_version", "patient_summary", "working_diagnosis", "independent_assessment",
                    "next_information", "extensions", "session")
DOCTOR_CANDIDATES_MAX = 8          # 표시 전용 상한. IG 입력과 무관
WD_STATES = ("PENDING", "ENTERED", "SKIPPED")
WD_LABEL_MAX = 80
SCOPE_KO = "모델이 학습한 49개 질환 안에서만 고려합니다"

# 환자 요약에 담을 clinical_summary 필드(진단 후보·disclaimer 는 의사 화면에서 따로 다룬다)
SUMMARY_FIELDS = ("chief_complaint", "confirmed_positive", "confirmed_negative", "confirmed_values",
                  "not_applicable", "unknown", "answered_questions", "questions_used")
# 다음 질문에서 남길 표현 키(information_gain·explanation 등 수치/내부 키 제외)
QUESTION_KEYS = ("question_id", "question_ko", "question_original", "answer_type", "choices", "is_fallback")
STOP_STATUS = {"MAX_QUESTIONS": "BUDGET_REACHED", "NO_ELIGIBLE_QUESTION": "NONE_ELIGIBLE",
               "UNSUPPORTED_SESSION_SHAPE": "UNSUPPORTED_SESSION_SHAPE"}
EXTENSION_REASONS = {
    "timeline": "EPISODE_BACKEND_MISSING",
    "episode": "EPISODE_BACKEND_MISSING",
    "diagnosis_coverage": "DISEASE_KNOWLEDGE_LAYER_MISSING",
    "unexplained_findings": "DISEASE_KNOWLEDGE_LAYER_MISSING",
    "alternatives": "DISEASE_KNOWLEDGE_LAYER_MISSING",
    "turning_points": "EPISODE_BACKEND_MISSING",
    "visit": "VISIT_INGESTION_MISSING",
    "recovery": "RECOVERY_MODEL_MISSING",
}
LOCKED = {"status": "LOCKED"}


def _invalid(detail: str) -> ValueError:
    return ValueError(f"MEDMAP_INVALID_WORKING_DIAGNOSIS:{detail}")


def parse_working_diagnosis(raw, disease_classes) -> dict:
    """{state, value?} 검증·정규화 → {"state", "value": None | {kind, code, label?}}. label 은 CATALOG 면 투영 때 채운다."""
    if not isinstance(raw, dict) or raw.get("state") not in WD_STATES:
        raise _invalid("state")
    state = raw["state"]
    value = raw.get("value")
    if state != "ENTERED":
        if value is not None:
            raise _invalid("value_not_allowed")
        return {"state": state, "value": None}
    if not isinstance(value, dict):
        raise _invalid("value")
    kind = value.get("kind")
    if kind == "CATALOG":
        code = value.get("code")
        if not isinstance(code, str) or code not in set(disease_classes):
            raise _invalid("code")
        return {"state": state, "value": {"kind": kind, "code": code}}
    if kind == "OUT_OF_SCOPE":
        label = value.get("label")
        if not isinstance(label, str):
            raise _invalid("label")
        label = label.strip()
        if not label or len(label) > WD_LABEL_MAX or any(ord(ch) < 32 or ord(ch) == 127 for ch in label):
            raise _invalid("label")
        return {"state": state, "value": {"kind": kind, "code": None, "label": label}}
    raise _invalid("kind")


def _working_diagnosis(wd: dict, labels: LabelProvider) -> dict:
    value = wd["value"]
    if value is not None and value["kind"] == "CATALOG":
        value = {"kind": "CATALOG", "code": value["code"], "label": labels.diagnosis(value["code"])[0]}
    return {"state": wd["state"], "value": value}


def _patient_summary(session: dict, catalog, labels: LabelProvider) -> dict:
    snapshot = deserialize_session(session, catalog)
    summary = build_clinical_summary(snapshot.state, snapshot.model_context, [], labels=labels)
    out = {"age": int(snapshot.state.age), "sex": snapshot.state.sex}
    out.update({key: summary[key] for key in SUMMARY_FIELDS})
    return out


def _candidates(diagnoses, labels: LabelProvider) -> dict:
    ranking = diagnoses.ranking[:DOCTOR_CANDIDATES_MAX]
    return {"status": "AVAILABLE",
            "candidates": [{"code": name, "label_ko": labels.diagnosis(name)[0]} for name, _ in ranking],
            "scope_ko": SCOPE_KO,
            "model": {"context": diagnoses.model_context}}


def _next_information(turn_payload: dict) -> dict:
    question = turn_payload.get("next_question")
    if question is not None:
        status, shown = "QUESTION", {key: question.get(key) for key in QUESTION_KEYS}
    else:
        stop = turn_payload.get("stop_reason")
        if stop not in STOP_STATUS:
            raise ValueError(f"MEDMAP_DOCTOR_UNKNOWN_STOP_REASON:{stop}")
        status, shown = STOP_STATUS[stop], None
    return {"status": status, "question": shown,
            "questions_used": turn_payload.get("questions_asked_in_session"),
            "max_questions": turn_payload.get("max_questions")}


def build_doctor_view(*, turn_payload: dict, diagnoses, working_diagnosis: dict, labels: LabelProvider,
                      catalog=None) -> dict:
    """기존 turn payload + 같은 상태의 DiagnosisResult + 검증된 WD → medmap-doctor-view-v1(키 순서 = DOCTOR_VIEW_KEYS)."""
    session = turn_payload["session"]
    blind = working_diagnosis["state"] == "PENDING"
    view = {
        "schema_version": DOCTOR_VIEW_SCHEMA_VERSION,
        "patient_summary": _patient_summary(session, catalog, labels),
        "working_diagnosis": _working_diagnosis(working_diagnosis, labels),
        "independent_assessment": dict(LOCKED) if blind else _candidates(diagnoses, labels),
        "next_information": dict(LOCKED) if blind else _next_information(turn_payload),
        "extensions": {name: {"status": "NOT_AVAILABLE", "reason": reason} for name, reason in EXTENSION_REASONS.items()},
        "session": session,
    }
    assert tuple(view) == DOCTOR_VIEW_KEYS
    return view
