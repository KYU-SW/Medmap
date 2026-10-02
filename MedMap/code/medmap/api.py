"""MedMap API v1 — 기존 제품 엔진을 HTTP JSON 으로 감싸기만 한다.

진단 계산·질문 자격·정보이득·질문 선택·한국어 표현·답변 검증·세션 직렬화는 전부 `medmap/` 엔진이 담당한다.
서버는 세션을 저장하지 않는다(stateless). 세션의 source of truth 는 클라이언트가 보내는 `medmap-session-v1` 뿐이다.
설계 문서: docs/medmap_api_design.md · 엔진 계약: docs/medmap_engine_contract.md
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import clinical_summary
from . import config
from . import speech
from .diagnosis import DiagnosisEngine
from .evidence import EvidenceCatalog
from .next_information import AnswerLikelihoodTable, NextInformationEngine
from .patient_state import PatientState
from .question_presentation import QuestionPresenter
from .serialization import (ANSWER_SCHEMA_VERSION, SESSION_SCHEMA_VERSION, TURN_SCHEMA_VERSION,
                            SessionValidationError, UnsupportedSchemaVersion, deserialize_session,
                            parse_answer_submission, serialize_turn)
import json
from pathlib import Path

from .intake import extract as intake_extract

API_VERSION = "v1"
LOG = logging.getLogger("medmap.api")

# 질문 수 상한은 서버 설정값이다(클라이언트 요청 본문으로 바꾸지 않는다).
MAX_QUESTIONS = int(os.environ.get("MEDMAP_MAX_QUESTIONS", config.DEFAULT_MAX_QUESTIONS))
LOG_PAYLOAD = os.environ.get("MEDMAP_API_LOG_PAYLOAD") == "1"
CORS_ORIGINS = [o.strip() for o in os.environ.get("MEDMAP_API_CORS_ORIGINS", "").split(",") if o.strip()]
# P2-7 demo(opt-in, 기본 꺼짐): 빌드된 medmap-web/dist 를 API 와 same-origin 으로 서빙 / Whisper 백그라운드 prewarm.
WEB_DIST = os.environ.get("MEDMAP_SERVE_WEB_DIST") or None
STT_PREWARM = os.environ.get("MEDMAP_STT_PREWARM") == "1"

CONFLICT_CODES = {"MEDMAP_PARENT_GATE_VIOLATION", "MEDMAP_ALREADY_ASKED", "MEDMAP_UNEXPECTED_ANSWER",
                  "MEDMAP_UNSUPPORTED_SESSION_SHAPE"}

# API 계층 stop_reason (엔진 계약의 MAX_QUESTIONS / NO_ELIGIBLE_QUESTION 과 별개).
STOP_UNSUPPORTED_SESSION_SHAPE = "UNSUPPORTED_SESSION_SHAPE"

# Natural Intake: frozen 매퍼 v1.2(freeze 2372e2f)를 감싸기만 한다. medmap/intake/ 는 수정하지 않는다.
MAPPER_VERSION = "v1.2"
INTAKE_TEXT_MAX_CHARS = 1000
INITIAL_CATALOG_JSON = Path(__file__).resolve().parent / "data" / "initial_evidence_ko.json"


def load_initial_ids(path=INITIAL_CATALOG_JSON) -> frozenset:
    """TRAIN INITIAL_EVIDENCE 고유값 96개(표시용 정적 파일). 런타임 추론·원본 데이터 접근 없음."""
    with open(path, encoding="utf-8") as f:
        return frozenset(item["evidence_id"] for item in json.load(f)["items"])


class EngineRegistry:
    """서버 시작 시 1회 로딩. 요청마다 모델을 다시 읽지 않는다. fit/retrain 호출 없음."""

    def __init__(self):
        self.catalog = EvidenceCatalog()
        self.likelihoods = AnswerLikelihoodTable(self.catalog)
        self.presenter = QuestionPresenter(self.catalog)
        self.diagnosis = {ctx: DiagnosisEngine(self.catalog, ctx) for ctx in config.MODEL_CONTEXTS}
        self.initial_ids = load_initial_ids()
        # 요약 표시 라벨 공급자: 서버 시작 시 1회 생성해 요청마다 재사용한다(medmap/clinical_summary.py 는 읽기만 함).
        # 질환 표시명은 한국어 용어 정본(medmap/terminology.py)에서 — 응답 키·형태는 그대로, name 은 내부 ID 유지.
        self.summary_labels = clinical_summary.TerminologyLabelProvider(self.catalog, self.presenter)
        self.ready = True

    def engine(self, model_context: str, max_questions: int) -> NextInformationEngine:
        return NextInformationEngine(self.diagnosis[model_context], catalog=self.catalog,
                                     likelihoods=self.likelihoods, presenter=self.presenter,
                                     max_questions=max_questions)


REGISTRY: EngineRegistry | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global REGISTRY
    REGISTRY = EngineRegistry()
    LOG.info("engine loaded contexts=%s max_questions=%d", list(config.MODEL_CONTEXTS), MAX_QUESTIONS)
    if STT_PREWARM:            # 서버 시작·health 를 막지 않는 백그라운드 로드. 실패해도 첫 요청 때 lazy load 가 재시도
        speech.start_prewarm(speech.get_transcriber())
    yield
    REGISTRY = None


app = FastAPI(title="MedMap API", version=API_VERSION, lifespan=lifespan)

if CORS_ORIGINS:          # 기본은 차단. 와일드카드를 쓰지 않는다.
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False)


# ---------------- 요청 모델 (추가 필드 금지 → 식별정보 유입 차단) ----------------
class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    value: list[str] | None = None


class AnswerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    kind: str
    value: list[str] | None = None


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: int
    sex: str
    model_context: str = "k3"
    initial_evidence: str | None = None
    answers: list[AnswerItem] = Field(default_factory=list)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = ANSWER_SCHEMA_VERSION
    question_id: str
    answer: AnswerBody


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict
    submission: Submission


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict


class SummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict


class IntakeExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=INTAKE_TEXT_MAX_CHARS)


# ---------------- 오류 계약 ----------------
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field


def _error_response(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "field": field}})


def _code_of(exc: Exception) -> str:
    return str(exc).split(":")[0] or exc.__class__.__name__


# ---------------- STT (medmap/speech.py 래핑만. 매퍼·세션과 무관) ----------------
def _stt_error(exc: Exception) -> ApiError:
    """speech.py 예외 → HTTP 오류. message에 오디오·transcript 내용을 담지 않는다."""
    if isinstance(exc, speech.AudioTooLarge):
        return ApiError(413, "AUDIO_TOO_LARGE", "audio payload too large")
    if isinstance(exc, speech.AudioTooLong):
        return ApiError(413, "AUDIO_TOO_LONG", "audio duration too long")
    if isinstance(exc, speech.UnsupportedAudioType):
        return ApiError(415, "UNSUPPORTED_AUDIO_TYPE", "unsupported audio content type")
    if isinstance(exc, speech.AudioEmpty):
        return ApiError(422, "AUDIO_EMPTY", "no speech detected")
    if isinstance(exc, speech.AudioDecodeError):
        return ApiError(422, "AUDIO_DECODE_ERROR", "could not decode audio")
    if isinstance(exc, speech.TranscriberUnavailable):
        return ApiError(503, "STT_UNAVAILABLE", "speech-to-text is unavailable")
    return ApiError(500, "STT_FAILED", "speech-to-text failed")


def _stt_transcribe_sync(data: bytes) -> tuple[str, float]:
    """worker thread에서 실행되는 동기 파이프라인: decode → check → transcribe.

    `medmap.intake`를 import/호출하지 않는다(STT는 audio→transcript 뿐).
    """
    x, duration = speech.decode_audio(data)
    speech.check_speech(x, duration)
    transcript = speech.get_transcriber().transcribe(x)
    return transcript, duration


@app.exception_handler(ApiError)
async def _api_error(request: Request, exc: ApiError):
    return _error_response(exc.status, exc.code, exc.message, exc.field)


@app.exception_handler(UnsupportedSchemaVersion)
async def _unsupported_schema(request: Request, exc: UnsupportedSchemaVersion):
    return _error_response(400, _code_of(exc), str(exc), "schema_version")


@app.exception_handler(SessionValidationError)
async def _session_invalid(request: Request, exc: SessionValidationError):
    code = _code_of(exc)
    return _error_response(409 if code in CONFLICT_CODES else 400, code, str(exc), _field_of(code))


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError):
    code = _code_of(exc)
    if not code.startswith("MEDMAP_"):
        LOG.exception("unhandled value error")
        return _error_response(500, "INTERNAL_ERROR", "internal error")
    return _error_response(409 if code in CONFLICT_CODES else 400, code, str(exc), _field_of(code))


@app.exception_handler(RequestValidationError)
async def _request_invalid(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or None
    return _error_response(422, "REQUEST_VALIDATION_ERROR", first.get("msg", "invalid request body"), field)


@app.exception_handler(config.MedMapForbiddenPath)
async def _forbidden_path(request: Request, exc: config.MedMapForbiddenPath):
    LOG.error("forbidden path access blocked")
    return _error_response(500, "INTERNAL_ERROR", "internal error")


def _field_of(code: str) -> str | None:
    if code in ("MEDMAP_INVALID_AGE", "MEDMAP_INVALID_SEX", "MEDMAP_INVALID_MODEL_CONTEXT"):
        return code.replace("MEDMAP_INVALID_", "").lower()
    if code == "MEDMAP_UNSUPPORTED_SCHEMA_VERSION":
        return "schema_version"
    return "question_id"


# ---------------- 로깅 (환자 데이터 미기록) ----------------
@app.middleware("http")
async def _access_log(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    LOG.info("rid=%s %s %s status=%s ms=%.1f", request_id, request.method, request.url.path,
             response.status_code, (time.perf_counter() - started) * 1000)
    return response


# ---------------- 공통 처리 ----------------
def _registry() -> EngineRegistry:
    if REGISTRY is None or not REGISTRY.ready:
        raise ApiError(503, "ENGINE_NOT_READY", "engine is not loaded")
    return REGISTRY


def _baseline(model_context: str) -> int:
    """MODEL_k 가 학습된 partial view 의 추가 관측 수(k3 → 3)."""
    return int(model_context[1:])


def _questions_used(state: PatientState, model_context: str) -> int | None:
    """이 세션에서 엔진이 물어 답변된 질문 수.

    정상 세션은 start 시 정확히 k 개의 추가 관측으로 시작하므로 `n_additional − k` 가 질문 수가 된다.
    추가 관측이 k 보다 적은 상태는 엔진이 만들어낼 수 없으므로(질문은 수를 늘리기만 한다) 질문 수를
    확정할 수 없다 → None(판정 불가). 클라이언트 카운터를 따로 두지 않는다.

    한계(계약 문서에도 명시): `n_additional > k` 인 상태만 보고는 "호출자가 처음부터 많이 준 관측"과
    "엔진이 물어서 늘어난 관측"을 구별할 수 없다. 그래서 새 세션의 시작 상태(start)에서만 exact-k 를 요구하고,
    그 이후 상태는 정상 세션의 연장으로 간주한다.
    """
    delta = state.n_additional - _baseline(model_context)
    return delta if delta >= 0 else None


def _turn_payload(turn, model_context: str, used: int | None, stop_reason: str | None = None) -> dict:
    payload = serialize_turn(turn, model_context, include_debug=False)
    # stateless 에서는 엔진의 요청 단위 카운터 대신 세션 상태에서 계산한 누적값을 쓴다(판정 불가면 null).
    payload["questions_asked_in_session"] = used
    # 학습 조건 일치: 현재 상태가 MODEL_k 의 학습 뷰와 정확히 같은가(질문이 늘면 false 가 된다).
    payload["model_context_match"] = turn.state.n_additional == _baseline(model_context)
    payload["max_questions"] = MAX_QUESTIONS
    if stop_reason is not None:
        payload["stop_reason"] = stop_reason
        payload["next_question"] = None
    return payload


def _limited_turn(state: PatientState, model_context: str) -> dict:
    """지원 범위를 벗어난 세션 형태: 진단은 돌려주되 질문 예산을 추정하지 않고 질문도 제안하지 않는다."""
    engine = _registry().engine(model_context, 0)
    turn = engine.start(state)          # max_questions=0 → 질문 선택 없음
    LOG.info("model_context=%s shape=unsupported n_additional=%d", model_context, state.n_additional)
    return _turn_payload(turn, model_context, None, STOP_UNSUPPORTED_SESSION_SHAPE)


def _run(state: PatientState, model_context: str, submission: dict | None = None,
         require_exact_k: bool = False) -> dict:
    registry = _registry()
    used = _questions_used(state, model_context)
    if used is None or (require_exact_k and used != 0):
        if submission is not None:
            raise ApiError(409, "MEDMAP_UNSUPPORTED_SESSION_SHAPE",
                           f"MEDMAP_UNSUPPORTED_SESSION_SHAPE:n_additional={state.n_additional}"
                           f",model_context={model_context}", "session")
        return _limited_turn(state, model_context)
    engine = registry.engine(model_context, max(MAX_QUESTIONS - used, 0))
    turn = engine.start(state)
    if submission is not None:
        question_id, answer = parse_answer_submission(submission, registry.catalog, state)
        turn = engine.answer(turn, question_id, answer)
        used = _questions_used(turn.state, model_context)
    if LOG_PAYLOAD:
        LOG.debug("state=%s", turn.state)
    LOG.info("model_context=%s questions_used=%s stop_reason=%s", model_context, used, turn.stop_reason)
    return _turn_payload(turn, model_context, used)


def _restore(session: dict) -> tuple:
    snapshot = deserialize_session(session, _registry().catalog)
    return snapshot.state, snapshot.model_context


# ---------------- Endpoints ----------------
@app.get("/health")
def health() -> dict:
    ready = REGISTRY is not None and REGISTRY.ready
    return {"status": "ok" if ready else "loading", "engine_ready": ready, "api_version": API_VERSION,
            "model_contexts": list(config.MODEL_CONTEXTS), "max_questions": MAX_QUESTIONS,
            "schema": {"session": SESSION_SCHEMA_VERSION, "turn": TURN_SCHEMA_VERSION, "answer": ANSWER_SCHEMA_VERSION}}


@app.post(f"/{API_VERSION}/session/start")
def session_start(body: StartRequest) -> dict:
    registry = _registry()
    if body.model_context not in config.MODEL_CONTEXTS:
        raise ApiError(400, "MEDMAP_INVALID_MODEL_CONTEXT", f"MEDMAP_INVALID_MODEL_CONTEXT:{body.model_context}",
                       "model_context")
    if body.sex not in ("M", "F"):
        raise ApiError(400, "MEDMAP_INVALID_SEX", f"MEDMAP_INVALID_SEX:{body.sex}", "sex")
    if body.age < 0 or body.age > 130:
        raise ApiError(400, "MEDMAP_INVALID_AGE", f"MEDMAP_INVALID_AGE:{body.age}", "age")

    state = PatientState.new(body.age, body.sex, body.initial_evidence)
    for item in body.answers:
        question_id, answer = parse_answer_submission(
            {"question_id": item.question_id, "answer": {"kind": item.kind, "value": item.value}},
            registry.catalog, state)
        state = state.with_answer(question_id, answer)
    # 새 세션은 정확히 k 개의 추가 관측에서 시작해야 질문 수를 명확히 셀 수 있다.
    return _run(state, body.model_context, require_exact_k=True)


@app.post(f"/{API_VERSION}/session/answer")
def session_answer(body: AnswerRequest) -> dict:
    state, model_context = _restore(body.session)
    return _run(state, model_context, body.submission.model_dump())


@app.post(f"/{API_VERSION}/session/resume")
def session_resume(body: ResumeRequest) -> dict:
    state, model_context = _restore(body.session)
    return _run(state, model_context)


@app.post(f"/{API_VERSION}/session/summary")
def session_summary(body: SummaryRequest) -> dict:
    """세션 종료 후 "현재까지 확인된 정보" 요약(medmap-clinical-summary-v1). 서버는 저장하지 않는다(stateless).

    검증·진단 재계산은 기존 공식 경로(/session/resume 과 동일한 _restore/_run)를 그대로 쓰고, 요약 계산은
    전부 medmap/clinical_summary.py 에 위임한다(로직 복제 없음).
    """
    registry = _registry()
    state, model_context = _restore(body.session)
    payload = _run(state, model_context)
    return clinical_summary.summary_from_session(body.session, payload["diagnoses"], catalog=registry.catalog,
                                                  labels=registry.summary_labels)


@app.post(f"/{API_VERSION}/intake/extract")
def intake_extract_endpoint(body: IntakeExtractRequest) -> dict:
    """자유문장 → evidence 후보만. 원문은 저장·로그하지 않는다. PatientState·세션과 무관(stateless).

    후보는 사용자 확인 전까지 어떤 상태에도 들어가지 않는다. confidence·alias_id·source 는 내보내지 않는다.
    """
    registry = _registry()
    candidates = []
    for found in intake_extract(body.text):
        evidence_id, status = found["evidence_id"], found["status"]
        candidates.append({
            "evidence_id": evidence_id,
            "status": status,
            "label_ko": registry.presenter.present(evidence_id).to_dict()["question_ko"],
            "matched_text": found["matched_text"],
            "initial_eligible": status == "POSITIVE" and evidence_id in registry.initial_ids,
        })
    LOG.info("intake extract n_candidates=%d", len(candidates))       # 개수만. 원문·matched_text 미기록
    return {"candidates": candidates, "mapper_version": MAPPER_VERSION}


@app.post(f"/{API_VERSION}/stt/transcribe")
async def stt_transcribe(request: Request) -> dict:
    """audio → transcript 뿐. 매퍼·엔진·세션과 무관(stateless, 원문 raw binary body).

    evidence 추출·진단·PatientState 변경 없음. transcript는 응답으로만 나가고 로그에 남기지 않는다.
    """
    mime = speech.normalize_mime(request.headers.get("content-type"))
    if mime not in speech.ALLOWED_MIME:
        raise ApiError(415, "UNSUPPORTED_AUDIO_TYPE", "unsupported audio content type")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = None
        if declared is not None and declared > speech.MAX_BYTES:
            raise ApiError(413, "AUDIO_TOO_LARGE", "audio payload too large")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > speech.MAX_BYTES:            # 선언된 Content-Length를 믿지 않고 실제 스트림에서 재확인
            raise ApiError(413, "AUDIO_TOO_LARGE", "audio payload too large")

    if not body:
        raise ApiError(422, "AUDIO_EMPTY", "no audio data received")

    started = time.perf_counter()
    try:
        transcript, duration = await anyio.to_thread.run_sync(_stt_transcribe_sync, bytes(body))
    except Exception as exc:
        mapped = _stt_error(exc)
        LOG.info("stt bytes=%d code=%s ms=%.1f", len(body), mapped.code, (time.perf_counter() - started) * 1000)
        raise mapped from exc
    LOG.info("stt bytes=%d duration_s=%.2f ms=%.1f code=OK", len(body), duration,
             (time.perf_counter() - started) * 1000)
    return {"transcript": transcript, "duration_s": round(duration, 2), "language": "ko"}


# ---------------- Doctor Mode (/v1/doctor/*): 기존 경로를 공개 별칭으로 재사용, 라우트는 dist mount 보다 먼저 ----------------
run_session = _run
restore_session = _restore
registry = _registry

from .api_doctor import router as _doctor_router  # noqa: E402

app.include_router(_doctor_router)

# Streaming STT(/v1/stt/stream*, status, prewarm): opt-in MEDMAP_STT_STREAMING=1. 기존 /v1/stt/transcribe 는 그대로.
from .api_stt_stream import router as _stt_stream_router  # noqa: E402

app.include_router(_stt_stream_router)

# ---------------- 기기 간 인계(/v1/handoff/*, Phase A S1, opt-in MEDMAP_HANDOFF_CODES=1). 메모리 전용 ----------------
from .api_handoff import router as _handoff_router  # noqa: E402

app.include_router(_handoff_router)


# ---------------- P2-7 demo: 정적 프론트 same-origin 서빙 (opt-in) ----------------
def mount_web_dist(target: FastAPI, dist_dir) -> None:
    """빌드된 프론트(dist)를 `/` 에 mount 한다. 반드시 모든 API 라우트를 등록한 뒤 호출한다(라우트가 먼저 매칭됨).

    index.html 이 없으면 시작 시 바로 실패한다(조용한 404 대신).
    """
    from fastapi.staticfiles import StaticFiles

    dist = Path(dist_dir).expanduser().resolve()
    if not (dist / "index.html").is_file():
        raise ValueError(f"MEDMAP_SERVE_WEB_DIST has no index.html: {dist}")
    target.mount("/", StaticFiles(directory=dist, html=True), name="web")
    LOG.info("serving web dist=%s", dist)


if WEB_DIST:
    mount_web_dist(app, WEB_DIST)
