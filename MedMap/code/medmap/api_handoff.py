"""기기 간 인계 API(/v1/handoff/*, Phase A S1). opt-in `MEDMAP_HANDOFF_CODES=1` — 꺼져 있으면 codes·claim 은 404.

- 저장은 `handoff_codes.HandoffStore`(메모리 전용, 15분·1회용·기기별 + 전체 실패 잠금). 디스크·DB 없음.
- 세션 검증은 기존 `restore_session`(= deserialize_session) 그대로. cache 는 {evidence_id, status} 만 남긴다(프론트 sanitizeCache 와 같은 규칙).
- 로그·오류 메시지에 번호·세션·증상 내용을 넣지 않는다(이벤트·대기 수만).
설계: docs/superpowers/specs/2026-10-01-medmap-illness-episode-phase-a.md rev2 §0-A
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .handoff_codes import TTL_S, HandoffCapacity, HandoffInvalid, HandoffLocked, HandoffStore

LOG = logging.getLogger("medmap.handoff")
ENABLED = os.environ.get("MEDMAP_HANDOFF_CODES") == "1"
CACHE_MAX = 100
# 세션은 메모리에 최대 15분·50개 보관된다 → 크기 상한(정상 세션은 수 KB: 답 수십 개). 넘으면 보관하지 않는다
SESSION_MAX_BYTES = 32 * 1024
EVIDENCE_ID = re.compile(r"^E_\d+$")
CACHE_STATUSES = {"POSITIVE", "NEGATIVE"}

router = APIRouter()
_store: HandoffStore | None = None
_store_lock = threading.Lock()


def store() -> HandoffStore:
    global _store
    if _store is None:
        with _store_lock:                                     # 동기 endpoint 는 threadpool — 첫 요청 경합에도 저장소는 하나
            if _store is None:
                _store = HandoffStore()
    return _store


def set_store_for_tests(value: HandoffStore | None) -> None:
    global _store
    _store = value


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: dict
    cache: list[dict] = Field(default_factory=list, max_length=CACHE_MAX)


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(max_length=32)


def _api():
    from . import api          # 지연 import: api.py 가 이 모듈을 include 한다(순환 방지)
    return api


def _error(status: int, code: str):
    return _api().ApiError(status, code, code)


def _require_enabled() -> None:
    if not ENABLED:
        raise _error(404, "HANDOFF_DISABLED")


def sanitize_cache(entries: list[dict]) -> list[dict]:
    seen, clean = set(), []
    for entry in entries:
        evidence_id, status = entry.get("evidence_id"), entry.get("status")
        if not isinstance(evidence_id, str) or not EVIDENCE_ID.match(evidence_id) or status not in CACHE_STATUSES \
                or evidence_id in seen:
            continue
        seen.add(evidence_id)
        clean.append({"evidence_id": evidence_id, "status": status})
    return clean


@router.get("/v1/handoff/status")
def handoff_status() -> dict:
    return {"enabled": ENABLED, "ttl_s": TTL_S}


@router.post("/v1/handoff/codes", status_code=201)
def handoff_create(body: CreateRequest) -> dict:
    _require_enabled()
    if len(json.dumps(body.session, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > SESSION_MAX_BYTES:
        raise _error(413, "HANDOFF_TOO_LARGE")
    _api().restore_session(body.session)                    # 무효 세션 → 기존 오류 계약(400), 저장 안 함
    try:
        code = store().create({"session": body.session, "cache": sanitize_cache(body.cache)})
    except HandoffCapacity:
        LOG.info("handoff event=capacity")
        raise _error(503, "HANDOFF_CAPACITY") from None
    LOG.info("handoff event=created pending=%d", store().pending())
    return {"code": code, "expires_in_s": store().ttl_s}


@router.post("/v1/handoff/claim")
def handoff_claim(body: ClaimRequest, request: Request) -> dict:
    _require_enabled()
    code = re.sub(r"[\s-]", "", body.code)
    client = request.client.host if request.client else None   # 기기별 잠금(메모리만, 로그 없음). uvicorn 은 기본으로 루프백의 X-Forwarded-For 를 믿는다 → --no-proxy-headers 필수(demo_serve.sh)
    try:
        payload = store().claim(code, client=client)
    except HandoffLocked:
        LOG.info("handoff event=locked")
        raise _error(429, "HANDOFF_LOCKED") from None
    except HandoffInvalid:
        LOG.info("handoff event=invalid")
        raise _error(404, "HANDOFF_CODE_INVALID") from None
    LOG.info("handoff event=claimed pending=%d", store().pending())
    return payload
