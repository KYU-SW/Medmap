"""EXP-03 비교 기준선(PROTOCOL §8). 일부러 고장 낸 부분 없음 — 정의 그대로.

naive(BASELINE-N, 새 비교 대상): 시간 = observed_at(검사 시행 시각), 정정 무시(모든 판독 유효), 의뢰 대기 무시,
       판독 ACUTE_POS 지지 / NEGATIVE 모순 / 그 외 무영향, 증상은 그래프 간선 있으면 지지. 알림 = 모순 판독마다 AL1.
exp01b(BASELINE-E, 기존 구현): EXP-01b ReasoningSession·assess_working_dx 그대로 호출.
"""
from __future__ import annotations

from reassess import PE, Timeline, current_hypothesis, graph


def naive(tl: Timeline, T: float) -> tuple:
    h = current_hypothesis(tl, T)
    if h is None:
        return ("NO_HYPOTHESIS", frozenset())
    seen = [e for e in tl.evidence if e.observed_at is not None and e.observed_at <= T]
    g = graph()
    alerts, sup, con = set(), False, False
    for e in seen:
        if e.evidence_type == "IMAGING_REPORT" and h.dx == PE:
            if e.pe_class == "ACUTE_POS":
                sup = True
            elif e.pe_class == "NEGATIVE":
                con = True
                alerts.add("AL1_NEW_CONFLICT")
        elif e.evidence_type in ("SYMPTOM", "VITAL", "LAB") and e.evidence_status == "POSITIVE":
            if e.concept in g.nodes and any(x.dst == h.dx for x in g.out_edges(e.concept, "SUGGESTS")):
                sup = True
    return ("CONFLICT" if con else "SUPPORTED" if sup else "INSUFFICIENT", frozenset(alerts))


def exp01b(tl: Timeline, T: float) -> tuple:
    from graph_engine import EvidenceRecord, PatientRecord, Status, assess_working_dx, infer
    h = current_hypothesis(tl, T)
    if h is None:
        return ("NO_HYPOTHESIS", frozenset())
    g = graph()
    pr = PatientRecord(tl.encounter_id)
    st_map = {"ACUTE_POS": Status.POSITIVE, "NEGATIVE": Status.NEGATIVE}
    for e in sorted(tl.evidence, key=lambda x: (x.available_at is None, x.available_at or 0)):
        if e.available_at is None or e.evidence_type == "IMAGING_ORDER":
            continue                                               # EXP-01b 는 recorded_at 필수, 의뢰 개념 없음
        if e.evidence_type == "IMAGING_REPORT":
            node, st = "CONCEPT:ctpa_filling_defect", st_map.get(e.pe_class, Status.UNCERTAIN)
        else:
            node, st = e.concept, Status(e.evidence_status) if e.evidence_status in Status.__members__ else Status.UNCERTAIN
        try:
            pr.add(EvidenceRecord(node, st, e.source_reference, e.observed_at if e.observed_at is not None else e.available_at,
                                  e.available_at, e.source_type, evidence_id=e.event_id,
                                  supersedes=e.supersedes))
        except (ValueError, KeyError):
            continue
    inf = infer(g, pr, T)
    wd = assess_working_dx(g, inf, pr, h.dx)
    if wd.conflicting:
        return ("CONFLICT", frozenset({"AL1_NEW_CONFLICT"}))
    return ("SUPPORTED" if wd.supporting else "INSUFFICIENT", frozenset())
