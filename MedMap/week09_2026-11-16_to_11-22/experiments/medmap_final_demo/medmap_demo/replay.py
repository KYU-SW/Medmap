"""시간순 재생 REPLAY(as_of) 와 근거 유효성 검사.

as_of 시점에 '시스템이 알고 있던' 기록(recorded_at <= as_of)만 보고, 그중 결과가 이용 가능한(available_at <= as_of) 버전만 근거로 쓴다.
계보 검사는 기존 v5-2A.1 출처 해석(hybrid521.lineage, 읽기 전용 import)을 재사용한다.
출력은 사건 입력 순서와 무관하다(모든 반복을 정렬된 키로 수행).

근거 상태
- USABLE  : AI 입력 가능(한 계보당 최대 1개 버전)
- HELD    : 지금은 평가 보류(나중에 바뀔 수 있음) — 대기·미가용·시각 모름·출처 모름·버전 충돌·계보 오류·환자 ID 충돌
- EXCLUDED: 근거로 쓰지 않음 — 취소·무효·중복·다른 환자·가설 미연결
평가 보류는 '변화 없음(0점)'이 아니다. 보류 근거에는 점수를 만들지 않는다.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .events import EventStore

EXP = Path(__file__).resolve().parents[2]
for _d in ("hybrid_reassessment_v5_2a1", "hybrid_reassessment_v4"):
    if str(EXP / _d) not in sys.path:
        sys.path.insert(0, str(EXP / _d))
from hybrid521 import lineage as LN  # noqa: E402  기존 출처 해석 재사용

HELD_CODES = ("EVIDENCE_ORDERED_ONLY", "EVIDENCE_PENDING", "EVIDENCE_NOT_YET_AVAILABLE", "TIME_UNKNOWN", "SOURCE_UNKNOWN",
              "CONFLICTING_VERSIONS", "LINEAGE_INVALID", "PATIENT_ID_CONFLICT", "NEWER_VERSION_TIME_UNKNOWN")
EXCLUDED_CODES = ("EVIDENCE_CANCELLED", "EVIDENCE_INVALID", "DUPLICATE_EVIDENCE", "DUPLICATE_OF_SUPERSEDED_VERSION", "PATIENT_MISMATCH",
                  "NOT_LINKED_TO_HYPOTHESIS")
VERSION_ROLES = ("USED", "SUPERSEDED", "DUPLICATE", "NOT_YET_AVAILABLE", "TIME_UNKNOWN", "ORDER", "PENDING", "CANCEL", "INVALID_RESULT",
                 "CONFLICT", "OTHER_PATIENT", "SOURCE_UNKNOWN", "NOT_LINKED", "HELD_VERSION")


@dataclass(frozen=True)
class Case:
    patient_id: str
    feed_ids: tuple
    hypothesis_id: str
    hypothesis_text: str            # 의사가 지정한 진단 가설(모델 입력 '진단 후보')


@dataclass
class Item:
    lineage_id: str
    item: str
    kind: str
    state: str                      # USABLE / HELD / EXCLUDED
    reasons: list
    used: object = None             # Event | None
    versions: list = field(default_factory=list)   # [(event, role)]
    duplicate_of: str | None = None

    def to_dict(self) -> dict:
        u = self.used
        return {"lineage_id": self.lineage_id, "item": self.item, "kind": self.kind, "state": self.state, "reasons": list(self.reasons),
                "duplicate_of": self.duplicate_of,
                "used": None if u is None else {"event_id": u.event_id, "status": u.status, "content": u.content, "source": u.source,
                                                 "observed_at": u.observed_at.isoformat() if u.observed_at else None,
                                                 "available_at": u.available_at.isoformat() if u.available_at else None,
                                                 "prev_version_id": u.prev_version_id},
                # 화면 노출 정책(1차 심사 반영): 근거 문장은 AI 입력으로 실제 사용한 버전만. 보류·제외·다른 환자 버전 내용과 환자 ID 는 보내지 않음
                "versions": [{"event_id": e.event_id, "status": e.status, "role": r, "source": e.source if r != "OTHER_PATIENT" else None,
                              "content": e.content if r == "USED" else None, "other_patient": r == "OTHER_PATIENT",
                              "recorded_at": e.recorded_at.isoformat(), "available_at": e.available_at.isoformat() if e.available_at else None,
                              "observed_at": e.observed_at.isoformat() if e.observed_at else None, "prev_version_id": e.prev_version_id,
                              "item": e.item, "note": e.note} for e, r in self.versions]}


@dataclass
class Replay:
    case: Case
    as_of: datetime
    items: list
    n_known_records: int
    n_unknown_future_records: int   # as_of 이후에 들어온 기록 수(존재 자체를 모르는 기록, 내용 미사용)

    def usable(self) -> list:
        return [i for i in self.items if i.state == "USABLE"]

    def by_lineage(self) -> dict:
        return {i.lineage_id: i for i in self.items}

    def to_dict(self) -> dict:
        return {"as_of": self.as_of.isoformat(), "patient_id": self.case.patient_id, "hypothesis": self.case.hypothesis_text,
                "n_known_records": self.n_known_records, "n_unknown_future_records": self.n_unknown_future_records,
                "items": [i.to_dict() for i in self.items]}


def _vkey(e):
    return (e.available_at or e.recorded_at, e.recorded_at, e.event_id)


def _lineage_issues(evs: list, known_ids: set) -> list:
    """기존 hybrid521.lineage 로 정정 사슬 검사(순환·누락 이전 버전). 다른 계보를 가리키는 정정도 오류."""
    decl = LN.declarations([{"record_key": e.event_id, "derived_from": [e.prev_version_id] if e.prev_version_id else []} for e in evs])
    issues = set()
    lids = {e.event_id for e in evs}
    for e in evs:
        r = LN.resolve(e.event_id, decl, known_ids)
        for i in r["issues"]:
            issues.add("DERIVATION_CYCLE" if i.startswith("DERIVATION_CYCLE") else "PREVIOUS_VERSION_MISSING" if i.startswith("PARTIAL_PROVENANCE")
                       else i.split("(")[0])
        if e.prev_version_id and e.prev_version_id in known_ids and e.prev_version_id not in lids:
            issues.add("CROSS_LINEAGE_CORRECTION")
    return sorted(issues)


def _resolve_lineage(lid: str, evs: list, as_of: datetime, case: Case, known_ids: set) -> Item:
    evs = sorted(evs, key=_vkey)
    first = evs[0]
    item = Item(lid, first.item, first.kind, "HELD", [])
    roles = {}
    pats = {e.patient_id for e in evs}
    if len(pats) > 1:
        item.reasons = ["PATIENT_ID_CONFLICT"]
        item.versions = [(e, "CONFLICT") for e in evs]
        return item
    iss = _lineage_issues(evs, known_ids)
    if iss:
        item.reasons = ["LINEAGE_INVALID"] + [f"LINEAGE:{i}" for i in iss]
        item.versions = [(e, "CONFLICT") for e in evs]
        return item
    for e in evs:
        if e.status == "ORDERED":
            roles[e.event_id] = "ORDER"
        elif e.status == "PENDING":
            roles[e.event_id] = "PENDING"
        elif e.status == "CANCELLED":
            roles[e.event_id] = "CANCEL"
    results = [e for e in evs if e.status in ("AVAILABLE", "CORRECTED", "INVALID")]
    no_time = [e for e in results if e.available_at is None]
    future = [e for e in results if e.available_at is not None and e.available_at > as_of]
    visible = [e for e in results if e.available_at is not None and e.available_at <= as_of]
    for e in no_time:
        roles[e.event_id] = "TIME_UNKNOWN"
    for e in future:
        roles[e.event_id] = "NOT_YET_AVAILABLE"
    # 같은 계보 안 중복(정정 연결 없이 같은 내용) → 정본 1개
    canon, dup_of = [], {}
    for e in visible:
        twin = next((c for c in canon if c.fingerprint() == e.fingerprint() and c.status == e.status and c.prev_version_id == e.prev_version_id), None)
        if twin is not None:
            dup_of[e.event_id] = twin.event_id
            roles[e.event_id] = "DUPLICATE"
        else:
            canon.append(e)
    superseded = {e.prev_version_id for e in canon if e.prev_version_id}
    for e in canon:
        if e.event_id in superseded:
            roles[e.event_id] = "SUPERSEDED"
    heads = [e for e in canon if e.event_id not in superseded]
    item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
    if any(e.status == "CANCELLED" for e in evs):
        item.state, item.reasons = "EXCLUDED", ["EVIDENCE_CANCELLED"]
        return item
    if len(heads) > 1:
        for e in heads:
            roles[e.event_id] = "CONFLICT"
        item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
        item.reasons = ["CONFLICTING_VERSIONS"]
        return item
    if len(heads) == 1:
        h = heads[0]
        if h.status == "INVALID":
            roles[h.event_id] = "INVALID_RESULT"
            item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
            item.state, item.reasons = "EXCLUDED", ["EVIDENCE_INVALID"]
            return item
        if not h.source:
            roles[h.event_id] = "SOURCE_UNKNOWN"
            item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
            item.reasons = ["SOURCE_UNKNOWN"]
            return item
        if case.hypothesis_id not in h.hypothesis_ids:
            roles[h.event_id] = "NOT_LINKED"
            item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
            item.state, item.reasons = "EXCLUDED", ["NOT_LINKED_TO_HYPOTHESIS"]
            return item
        if any(e.prev_version_id == h.event_id for e in no_time):     # 이 버전을 대체하는 새 버전이 있는데 이용 가능 시각을 모름 → 보수적으로 보류(1차 심사 반영)
            roles[h.event_id] = "HELD_VERSION"
            item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
            item.reasons = ["NEWER_VERSION_TIME_UNKNOWN"]
            return item
        roles[h.event_id] = "USED"
        item.versions = [(e, roles.get(e.event_id, "?")) for e in evs]
        item.state, item.used, item.reasons = "USABLE", h, []
        if any(e.prev_version_id == h.event_id for e in future):      # 조회 시점에는 이 버전이 유효(새 버전은 아직 이용 불가) — 알림만
            item.reasons = ["NEWER_VERSION_NOT_YET_AVAILABLE"]
        return item
    # 이용 가능한 결과 없음
    if future:
        item.reasons = ["EVIDENCE_NOT_YET_AVAILABLE"]
    elif no_time:
        item.reasons = ["TIME_UNKNOWN"]
    elif any(e.status == "PENDING" for e in evs):
        item.reasons = ["EVIDENCE_PENDING"]
    else:
        item.reasons = ["EVIDENCE_ORDERED_ONLY"]
    return item


def replay(store: EventStore, case: Case, as_of: datetime, exclude_event_ids=()) -> Replay:
    if as_of.tzinfo is None:
        raise ValueError("as_of 에 시간대가 필요함")
    ex = set(exclude_event_ids)
    allev = [e for e in store.events.values() if e.event_id not in ex]
    known = [e for e in allev if e.recorded_at <= as_of]
    known_ids = {e.event_id for e in known}
    n_future = sum(1 for e in allev if e.recorded_at > as_of and (e.patient_id == case.patient_id or e.feed_id in case.feed_ids))
    mine = [e for e in known if e.patient_id == case.patient_id or e.feed_id in case.feed_ids]
    by_lin = {}
    for e in mine:
        by_lin.setdefault(e.lineage_id, []).append(e)
    # 다른 계보에 속한 같은 lineage 를 다른 환자가 쓰는 경우까지 보려면 전체 known 에서 lineage 를 모은다
    all_lin = {}
    for e in known:
        all_lin.setdefault(e.lineage_id, []).append(e)
    items = []
    for lid in sorted(by_lin):
        evs = all_lin[lid]
        if all(e.patient_id != case.patient_id for e in evs):         # 이 환자 수신 묶음에 섞여 들어온 다른 환자 자료
            it = Item(lid, evs[0].item, evs[0].kind, "EXCLUDED", ["PATIENT_MISMATCH"], versions=[(e, "OTHER_PATIENT") for e in sorted(evs, key=_vkey)])
            items.append(it)
            continue
        items.append(_resolve_lineage(lid, evs, as_of, case, known_ids))
    # 계보가 다른데 같은 자료(재전송 등) → 먼저 이용 가능해진 것 하나만. 동점이면 먼저 기록된 것(1차 심사: recorded_at 누락으로 재전송본이 남던 결함 수정)
    # 다른 계보에서 정정으로 대체된(SUPERSEDED) 버전과 같은 자료면 정정 전 내용의 사본 → 제외(1차 심사 반영)
    sup_fp = {}
    for it in items:
        for e, r in it.versions:
            if r == "SUPERSEDED":
                sup_fp.setdefault(e.fingerprint(), it.lineage_id)
    usable = sorted([i for i in items if i.state == "USABLE"], key=lambda i: (i.used.available_at, i.used.recorded_at, i.used.event_id))
    seen = {}
    for it in usable:
        fp = it.used.fingerprint()
        if fp in sup_fp and sup_fp[fp] != it.lineage_id:
            it.state, it.reasons, it.duplicate_of = "EXCLUDED", ["DUPLICATE_OF_SUPERSEDED_VERSION"], sup_fp[fp]
            it.versions = [(e, "DUPLICATE" if e is it.used else r) for e, r in it.versions]
            it.used = None
            continue
        if fp in seen:
            it.state, it.reasons, it.duplicate_of = "EXCLUDED", ["DUPLICATE_EVIDENCE"], seen[fp]
            it.versions = [(e, "DUPLICATE" if e is it.used else r) for e, r in it.versions]
            it.used = None
        else:
            seen[fp] = it.lineage_id
    return Replay(case, as_of, items, len(mine), n_future)
