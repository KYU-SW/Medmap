"""Doctor Mode API (/v1/doctor/*). 기존 세션 경로(_restore/_run)를 그대로 호출하고 결과를 doctor_view 로 투영만 한다.

- 새 진단·질문 알고리즘 없음: 다음 질문·질문 한도·409 규칙은 /v1/session/answer·/resume 과 같다.
- 서버 저장 없음(stateless). working diagnosis 문자열은 로그·오류 메시지에 남기지 않는다.
설계: docs/superpowers/specs/2026-09-29-medmap-doctor-mode-foundation.md §7-2
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from . import doctor_view
from .serialization import ANSWER_SCHEMA_VERSION, deserialize_session

DIAGNOSES_SCHEMA_VERSION = "medmap-doctor-diagnoses-v1"

router = APIRouter()


# 기존 api.Submission 과 같은 형태(순환 import 를 피하려고 여기 선언). /v1/session/answer 와 같은 dict 를 _run 에 넘긴다.
class DoctorSubmissionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    value: list[str] | None = None


class DoctorSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = ANSWER_SCHEMA_VERSION
    question_id: str
    answer: DoctorSubmissionAnswer


class DoctorViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict
    working_diagnosis: dict


class DoctorAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict
    working_diagnosis: dict
    submission: DoctorSubmission


def _api():
    from . import api          # 지연 import: api.py 가 이 모듈을 include 한다(순환 방지)
    return api


def _working_diagnosis(raw: dict, registry) -> dict:
    try:
        return doctor_view.parse_working_diagnosis(raw, registry.diagnosis["k3"].classes)
    except ValueError:
        # 입력 문자열을 메시지에 넣지 않는다(OUT_OF_SCOPE label 비기록).
        raise _api().ApiError(400, "MEDMAP_INVALID_WORKING_DIAGNOSIS", "MEDMAP_INVALID_WORKING_DIAGNOSIS",
                              "working_diagnosis") from None


def _project(payload: dict, model_context: str, wd: dict, registry) -> dict:
    # 표시용 후보는 같은 결과 상태의 기존 DiagnosisEngine ranking 에서만 가져온다(IG 선택과 무관).
    state_after = deserialize_session(payload["session"], registry.catalog).state
    diagnoses = registry.diagnosis[model_context].diagnose(state_after)
    return doctor_view.build_doctor_view(turn_payload=payload, diagnoses=diagnoses, working_diagnosis=wd,
                                         labels=registry.summary_labels, catalog=registry.catalog)


@router.get("/v1/doctor/diagnoses")
def doctor_diagnoses() -> dict:
    registry = _api().registry()
    labels = registry.summary_labels
    classes = registry.diagnosis["k3"].classes
    return {"schema_version": DIAGNOSES_SCHEMA_VERSION,
            "diagnoses": [{"code": c, "label_ko": labels.diagnosis(c)[0]} for c in classes]}


@router.post("/v1/doctor/view")
def doctor_view_endpoint(body: DoctorViewRequest) -> dict:
    api = _api()
    registry = api.registry()
    wd = _working_diagnosis(body.working_diagnosis, registry)
    state, model_context = api.restore_session(body.session)
    payload = api.run_session(state, model_context)
    return _project(payload, model_context, wd, registry)


@router.post("/v1/doctor/answer")
def doctor_answer_endpoint(body: DoctorAnswerRequest) -> dict:
    api = _api()
    registry = api.registry()
    wd = _working_diagnosis(body.working_diagnosis, registry)
    if wd["state"] == "PENDING":
        raise api.ApiError(409, "MEDMAP_WORKING_DIAGNOSIS_PENDING", "MEDMAP_WORKING_DIAGNOSIS_PENDING",
                           "working_diagnosis")
    state, model_context = api.restore_session(body.session)
    payload = api.run_session(state, model_context, body.submission.model_dump())
    return _project(payload, model_context, wd, registry)
