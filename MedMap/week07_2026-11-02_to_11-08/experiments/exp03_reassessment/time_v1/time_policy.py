"""EXP-03-TIME 시간 정책(PROTOCOL_TIME.md §2–§4). 원시 기록 → 시간 등급·이용 가능 시각 → 기존 reassess.Timeline(수정 없이 재사용).

정책: STRICT_AVAILABLE_TIME(주) · S1_TRIAGE_AT_INTIME_APPROX · S2_STRICT_A_ONLY. ECG 는 모든 정책에서 NOT_IDENTIFIABLE.
존재하지 않는 시각을 만들지 않는다(대체·추정 없음). triage 근사는 S1 에서만, APPROX 표시.
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PARENT = Path(__file__).resolve().parents[1]
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from reassess import Evidence, HypothesisEvent, Timeline  # noqa: E402  (기존 EXP-03 모듈, 수정 없음)

A, B, C = "A_DOCUMENTED_AVAILABILITY", "B_CONSERVATIVE_PROXY", "C_UNKNOWN_OR_CONFLICT"
POLICIES = {
    "STRICT_AVAILABLE_TIME": {"grades": {A, B}, "triage_at_intime": False},
    "S1_TRIAGE_AT_INTIME_APPROX": {"grades": {A, B}, "triage_at_intime": True},
    "S2_STRICT_A_ONLY": {"grades": {A}, "triage_at_intime": False},
}
SOURCES = {"triage", "vitalsign", "lab", "radiology", "ecg_waveform", "ecg_machine", "ecg_cardiologist", "order"}
ECG_SOURCES = {"ecg_waveform", "ecg_machine", "ecg_cardiologist"}


@dataclass(frozen=True)
class Stay:
    stay_id: str
    subject_id: str
    intime: float
    outtime: float


@dataclass(frozen=True)
class RawRecord:
    record_id: str
    subject_id: str
    source: str
    source_reference: str
    stay_id: str | None = None             # ED 표·ECG(ed_stay_id) 처럼 체류 키가 있는 경우
    observed_at: float | None = None       # 시행·채취·차트 시각
    charted_at: float | None = None
    signed_or_stored_at: float | None = None
    evidence_type: str = "SYMPTOM"
    evidence_status: str = "POSITIVE"
    concept: str = ""
    pe_class: str = ""
    order_ref: str = ""
    supersedes: str | None = None
    uncertainty_status: str = ""


@dataclass(frozen=True)
class TimeInfo:
    available_at: float | None
    grade: str
    flag: str                              # OK · POST_ED · UNKNOWN_AVAILABILITY · TIME_CONFLICT · NOT_IDENTIFIABLE · EXCLUDED_BY_POLICY · APPROX_INTIME
    approx: bool = False
    proxy: bool = False


def time_info(r: RawRecord, stay: Stay, policy: str) -> TimeInfo:
    p = POLICIES[policy]
    if r.source not in SOURCES:
        raise ValueError(f"알 수 없는 원천 {r.source}")
    if r.source == "triage":
        if p["triage_at_intime"]:
            return TimeInfo(stay.intime, C, "APPROX_INTIME", approx=True)
        return TimeInfo(None, C, "UNKNOWN_AVAILABILITY")
    if r.source in ECG_SOURCES:
        return TimeInfo(None, C, "NOT_IDENTIFIABLE")
    if r.source == "vitalsign":
        return TimeInfo(None, C, "UNKNOWN_AVAILABILITY")
    if r.source == "order":
        if r.observed_at is None:
            return TimeInfo(None, C, "UNKNOWN_AVAILABILITY")
        return TimeInfo(r.observed_at, A, "OK")
    s = r.signed_or_stored_at
    if s is None:
        return TimeInfo(None, C, "UNKNOWN_AVAILABILITY")
    if r.observed_at is not None and s < r.observed_at:
        return TimeInfo(None, C, "TIME_CONFLICT")
    grade = A if r.source == "lab" else B
    if grade not in p["grades"]:
        return TimeInfo(None, grade, "EXCLUDED_BY_POLICY", proxy=grade == B)
    return TimeInfo(s, grade, "POST_ED" if s > stay.outtime else "OK", proxy=grade == B)


def attribute(r: RawRecord, stays: list) -> str | None:
    """체류 귀속: 체류 키가 있으면 그것(같은 subject 일 때만), 없으면 관찰 시각이 든 체류 창. 두 창에 들면 AMBIGUOUS."""
    mine = [s for s in stays if s.subject_id == r.subject_id]
    if r.stay_id is not None:
        return r.stay_id if any(s.stay_id == r.stay_id for s in mine) else None
    if r.observed_at is None:
        return None
    hit = [s.stay_id for s in mine if s.intime <= r.observed_at <= s.outtime]
    if len(hit) > 1:
        return "AMBIGUOUS"
    return hit[0] if hit else None


@dataclass
class Built:
    timeline: Timeline
    meta: dict = field(default_factory=dict)      # event_id → TimeInfo
    audit: Counter = field(default_factory=Counter)


def build(stay: Stay, stays: list, records: list, policy: str, hypotheses=()) -> Built:
    tl = Timeline(stay.stay_id)
    out = Built(tl)
    for h in hypotheses:
        tl.set_hypothesis(HypothesisEvent(h[0], stay.stay_id, h[1], h[2]))
    for r in records:
        sid = attribute(r, stays)
        if sid == "AMBIGUOUS":
            out.audit["AMBIGUOUS_STAY"] += 1
            continue
        if sid != stay.stay_id:
            out.audit["OTHER_OR_NO_STAY"] += 1
            continue
        ti = time_info(r, stay, policy)
        out.audit[f"flag:{ti.flag}"] += 1
        out.audit[f"grade:{ti.grade}"] += 1
        if not r.source_reference:
            out.audit["REJECTED_NO_SOURCE"] += 1
            continue
        if ti.available_at is None:
            continue                                            # 어떤 시점에도 사용 안 함(시각을 만들지 않음)
        sup = r.supersedes
        if sup is not None and not any(x.event_id == sup for x in tl.evidence):
            out.audit["CORRECTION_TARGET_NOT_IN_TIMELINE"] += 1     # 원 기록이 시간 정책으로 제외됨 → 연결 없이 별도 증거
            sup = None
        e = Evidence(r.record_id, stay.stay_id, r.evidence_type, r.source, r.source_reference, r.observed_at,
                     r.charted_at, ti.available_at, r.evidence_status, concept=r.concept, uncertainty_status=r.uncertainty_status,
                     pe_class=r.pe_class, order_ref=r.order_ref, supersedes=sup)
        tl.add(e)
        out.meta[r.record_id] = ti
    return out


def used_at(b: Built, T: float) -> list:
    """시점 T 에 판단에 들어간 기록 id(이용 가능 시각 ≤ T)."""
    return sorted(e.event_id for e in b.timeline.evidence if e.available_at is not None and e.available_at <= T)


def policy_counts(b: Built, T: float) -> dict:
    used = used_at(b, T)
    return {"used": len(used), "approx_used": sum(b.meta[i].approx for i in used), "proxy_used": sum(b.meta[i].proxy for i in used)}
