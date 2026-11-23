"""의료 근거 사건 모델과 추가 전용(append-only) 저장소. 합성 환자 전용.

시각 세 가지를 구분한다(모두 시간대가 있는 ISO 8601 문자열 → aware datetime).
- observed_at : 검사·관찰이 실제로 일어난 시각(검체 채취 등). 모르면 None.
- available_at: 원천 시스템(검사실·판독·장비)이 결과를 공개한 시각(실제 의사 열람 시각 아님). 기록 도착(recorded_at)보다 이를 수 있음 —
  그 경우 recorded_at 전에는 이 시스템이 결과를 알 수 없으므로 사용하지 않는다. 결과가 없는 사건(ORDERED·PENDING·CANCELLED)은 None 가능.
- recorded_at : 이 사건 기록이 시스템에 들어온 시각(필수). 조회 시점보다 늦게 들어온 기록은 그 조회에서 '존재하지 않음'.
알 수 없는 시각은 None 으로 두고 임의로 채우지 않는다.

결과 상태(status)와 중복·정정 계보는 분리한다.
- status: ORDERED / PENDING / AVAILABLE / CORRECTED / CANCELLED / INVALID
- 계보: lineage_id(같은 검사·관찰 자료의 계보) + prev_version_id(이 기록이 대체하는 이전 버전). 정정 버전 식별자는 저장하지 않고
  (추가 전용이라 이전 기록을 고칠 수 없음) 조회 시 역방향으로 계산한다.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

STATUSES = ("ORDERED", "PENDING", "AVAILABLE", "CORRECTED", "CANCELLED", "INVALID")
RESULT_STATUSES = ("AVAILABLE", "CORRECTED", "INVALID")      # 결과 버전을 이루는 상태
KINDS = ("LAB", "IMAGING", "NOTE", "VITAL", "ECG")


class IngestError(ValueError):
    """수집 거부. code 는 거부 사유 코드."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def parse_time(v, name: str):
    """None 은 '모름'으로 유지. 문자열은 시간대가 있어야 함(없으면 INVALID_TIME)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v))
        except ValueError as ex:
            raise IngestError("INVALID_TIME", f"{name}={v!r} ({ex})") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise IngestError("INVALID_TIME", f"{name}={v!r} 시간대 없음")
    return dt


_WS = re.compile(r"\s+")


def norm_text(s: str | None) -> str:
    return _WS.sub(" ", (s or "")).strip().casefold()


@dataclass(frozen=True)
class Event:
    patient_id: str                    # 합성 환자 식별자
    feed_id: str                       # 이 기록이 들어온 수신 묶음(내원·인터페이스 배치). 환자 혼입 검사용
    event_id: str                      # 기록 고유 ID
    lineage_id: str                    # 같은 검사·관찰 자료의 계보 ID(근거 식별자)
    kind: str                          # LAB / IMAGING / NOTE / VITAL / ECG
    item: str                          # 검사·관찰 이름(표시용)
    status: str
    recorded_at: datetime
    content: str | None = None         # 근거 문장(결과가 있는 상태만)
    source: str | None = None          # 정보 출처(검사실·판독의·장비). 모르면 None
    observed_at: datetime | None = None
    available_at: datetime | None = None
    prev_version_id: str | None = None
    hypothesis_ids: tuple = ()         # 이 근거가 연결된 진단 가설 ID
    note: str = ""                     # 합성 시나리오 설명(표시용)

    def fingerprint(self) -> str:
        """중복 판정용 내용 지문: 환자·종류·항목·관찰 시각·정규화 문장·출처."""
        raw = json.dumps([self.patient_id, self.kind, norm_text(self.item), self.observed_at.isoformat() if self.observed_at else None,
                          norm_text(self.content), norm_text(self.source)], ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("recorded_at", "observed_at", "available_at"):
            d[k] = d[k].isoformat() if d[k] else None
        d["hypothesis_ids"] = list(self.hypothesis_ids)
        return d


def make_event(**kw) -> Event:
    """입력 사전 → 검증된 Event. 거부 사유는 IngestError.code."""
    for k in ("patient_id", "feed_id", "event_id", "lineage_id", "kind", "item", "status", "recorded_at"):
        if kw.get(k) in (None, ""):
            raise IngestError("MISSING_FIELD", k)
    if kw["status"] not in STATUSES:
        raise IngestError("INVALID_STATUS", str(kw["status"]))
    if kw["kind"] not in KINDS:
        raise IngestError("INVALID_KIND", str(kw["kind"]))
    t = {k: parse_time(kw.get(k), k) for k in ("recorded_at", "observed_at", "available_at")}
    if t["recorded_at"] is None:
        raise IngestError("MISSING_FIELD", "recorded_at")
    if kw["status"] in ("AVAILABLE", "CORRECTED") and not norm_text(kw.get("content")):
        raise IngestError("EMPTY_EVIDENCE", kw["event_id"])
    if kw["status"] == "CORRECTED" and not kw.get("prev_version_id"):
        raise IngestError("CORRECTION_WITHOUT_PREVIOUS", kw["event_id"])
    if kw.get("prev_version_id") == kw["event_id"]:
        raise IngestError("CORRECTION_CYCLE", kw["event_id"])
    if t["observed_at"] and t["available_at"] and t["available_at"] < t["observed_at"]:
        raise IngestError("INVALID_TIME", f"available_at < observed_at ({kw['event_id']})")
    hyp = tuple(sorted(kw.get("hypothesis_ids") or ()))
    return Event(**{**{k: v for k, v in kw.items() if k not in t and k != "hypothesis_ids"}, **t, "hypothesis_ids": hyp})


@dataclass
class EventStore:
    """추가 전용 저장소. 같은 event_id 재전송: 내용이 같으면 무시(멱등, 기록), 다르면 거부(DUPLICATE_EVENT_ID).
    거부·무시 내역도 추가 전용 로그에 남긴다(실패 사실 보존)."""
    events: dict = field(default_factory=dict)
    log: list = field(default_factory=list)

    def append(self, raw: dict) -> Event | None:
        try:
            e = make_event(**raw)
        except IngestError as ex:
            self.log.append({"action": "REJECTED", "code": ex.code, "detail": ex.detail, "event_id": raw.get("event_id")})
            return None
        except TypeError as ex:                                   # 알 수 없는 필드
            self.log.append({"action": "REJECTED", "code": "UNKNOWN_FIELD", "detail": str(ex)[:200], "event_id": raw.get("event_id")})
            return None
        old = self.events.get(e.event_id)
        if old is not None:
            if old == e:
                self.log.append({"action": "IGNORED_IDEMPOTENT_RESEND", "code": "SAME_EVENT_ID_SAME_CONTENT", "event_id": e.event_id})
                return old
            self.log.append({"action": "REJECTED", "code": "DUPLICATE_EVENT_ID", "detail": "같은 event_id 에 다른 내용", "event_id": e.event_id})
            return None
        self.events[e.event_id] = e
        self.log.append({"action": "APPENDED", "event_id": e.event_id})
        return e

    def extend(self, raws) -> "EventStore":
        for r in raws:
            self.append(r)
        return self

    def snapshot(self, as_of: datetime) -> "EventStore":
        """as_of 시점까지 시스템에 들어온 기록만 담은 저장소(재생 일치 검사용 '그 당시 시스템 상태')."""
        s = EventStore()
        s.events = {k: v for k, v in self.events.items() if v.recorded_at <= as_of}
        return s

    def all(self) -> list:
        return sorted(self.events.values(), key=lambda e: (e.recorded_at, e.event_id))
