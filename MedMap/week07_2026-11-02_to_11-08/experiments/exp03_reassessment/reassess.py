"""EXP-03 시간순 증거·진단 재검토 안전망(PROTOCOL.md §3–§6 구현). 확률·진단 분류 없음.

재사용: EXP-01b 실제 그래프(build_real_graph)의 SUGGESTS 간선만 읽음(수정 없음).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get("EXP03_ENGINE") or ROOT / "exp01b_graph_engine")
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

PE = "DX:Pulmonary embolism"
CTPA_CONCEPT = "CONCEPT:ctpa_filling_defect"
PE_CLASSES = ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE", "NO_MENTION")
EVIDENCE_TYPES = ("SYMPTOM", "VITAL", "LAB", "IMAGING_ORDER", "IMAGING_REPORT")
STATUSES = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "PENDING", "NOT_ASSESSABLE")


@dataclass(frozen=True)
class Evidence:
    event_id: str
    encounter_id: str
    evidence_type: str
    source_type: str
    source_reference: str
    observed_at: float | None
    recorded_at: float | None
    available_at: float | None
    evidence_status: str
    concept: str = ""
    uncertainty_status: str = ""
    pe_class: str = ""                 # IMAGING_REPORT 전용(v2/v3b 분류)
    order_ref: str = ""                # IMAGING_REPORT → IMAGING_ORDER 연결
    revision_id: str = "r1"
    supersedes: str | None = None


@dataclass(frozen=True)
class HypothesisEvent:
    hypothesis_id: str
    encounter_id: str
    dx: str | None                     # WITHDRAW 면 None
    set_at: float
    provenance: str = "SIMULATED_WD"
    action: str = "SET"


class Timeline:
    """체류 1개의 증거·가설 이벤트(추가만). 출처 없음·다른 체류·잘못된 값은 추가 시 거부."""

    def __init__(self, encounter_id: str):
        self.encounter_id = encounter_id
        self.evidence: list[Evidence] = []
        self.hypotheses: list[HypothesisEvent] = []

    def add(self, e: Evidence):
        if e.encounter_id != self.encounter_id:
            raise ValueError(f"다른 체류 증거 거부: {e.event_id}")
        if not e.source_reference:
            raise ValueError(f"출처 없는 증거 거부: {e.event_id}")
        if e.evidence_type not in EVIDENCE_TYPES or e.evidence_status not in STATUSES:
            raise ValueError(f"유형·상태 값 오류: {e.event_id}")
        if e.evidence_type == "IMAGING_REPORT" and e.pe_class not in PE_CLASSES:
            raise ValueError(f"판독 분류 값 오류: {e.event_id}")
        if any(x.event_id == e.event_id for x in self.evidence):
            raise ValueError(f"중복 event_id: {e.event_id}")
        if e.supersedes is not None and not any(x.event_id == e.supersedes for x in self.evidence):
            raise ValueError(f"정정 대상 없음: {e.supersedes}")
        self.evidence.append(e)

    def set_hypothesis(self, h: HypothesisEvent):
        if h.encounter_id != self.encounter_id:
            raise ValueError("다른 체류 가설 거부")
        if h.provenance != "SIMULATED_WD":
            raise ValueError("이번 단계 가설은 SIMULATED_WD 만 허용")
        self.hypotheses.append(h)

    def truncated(self, T: float) -> "Timeline":
        """T 까지 사용 가능했던 이벤트만 남긴 사본(누출 검사용)."""
        t = Timeline(self.encounter_id)
        t.evidence = [e for e in self.evidence if usable(e, T)]
        t.hypotheses = [h for h in self.hypotheses if h.set_at <= T]
        return t


def usable(e: Evidence, T: float) -> bool:
    if e.available_at is None:
        return False
    if e.observed_at is not None and e.available_at < e.observed_at:
        return False
    return e.available_at <= T


def current_hypothesis(tl: Timeline, T: float) -> HypothesisEvent | None:
    hs = sorted((h for h in tl.hypotheses if h.set_at <= T), key=lambda h: h.set_at)
    if not hs or hs[-1].action == "WITHDRAW" or hs[-1].dx is None:
        return None
    return hs[-1]


def effective_evidence(tl: Timeline, T: float) -> tuple[list, dict]:
    """T 에 사용 가능 + 정정되지 않은 증거. 반환 (유효 증거, 제외 집계, 정정 쌍)."""
    use = [e for e in tl.evidence if usable(e, T)]
    superseded = {e.supersedes: e for e in use if e.supersedes}
    excl = {"EXCLUDED_UNKNOWN_AVAILABILITY": sum(e.available_at is None for e in tl.evidence),
            "EXCLUDED_TIME_INVERSION": sum(e.available_at is not None and e.observed_at is not None
                                           and e.available_at < e.observed_at for e in tl.evidence),
            "NOT_YET_AVAILABLE": sum(e.available_at is not None and e.available_at > T for e in tl.evidence)}
    eff = [e for e in use if e.event_id not in superseded]
    return eff, excl, superseded


_GRAPH = None


def graph():
    global _GRAPH
    if _GRAPH is None:
        from knowledge_real_kg import build_real_graph
        _GRAPH, _ = build_real_graph(extra_hp_nodes=("HP:0410174", "HP:0033106", "HP:0003565"), discriminators=True)
    return _GRAPH


def relation(e: Evidence, dx: str) -> tuple[str, str]:
    """증거 1건 → (관계, 규칙 ID). PROTOCOL §4."""
    if e.evidence_type == "IMAGING_REPORT":
        if dx != PE:
            return "NOT_DEFINED", "-"
        return {"ACUTE_POS": ("SUPPORTS", "R1"), "NEGATIVE": ("CONFLICTS", "R2"),
                "CHRONIC_OR_PERSISTENT": ("NOT_CONFIRM_ACUTE", "R3"), "UNCERTAIN": ("UNKNOWN", "R4"),
                "NO_MENTION": ("UNKNOWN", "R5")}[e.pe_class]
    if e.evidence_type == "IMAGING_ORDER":
        return ("PENDING", "R6") if dx == PE else ("NOT_DEFINED", "-")
    g = graph()
    linked = e.concept in g.nodes and any(x.dst == dx for x in g.out_edges(e.concept, "SUGGESTS"))
    if not linked:
        return "NO_KNOWLEDGE", "R9"
    if e.evidence_status == "POSITIVE":
        return "SUPPORTS", "R7"
    if e.evidence_status == "NEGATIVE":
        return "NO_EFFECT", "R8"
    return "UNKNOWN", "R7u"


@dataclass
class Assessment:
    T: float
    hypothesis_id: str | None
    dx: str | None
    summary: str
    flags: dict
    relations: list = field(default_factory=list)      # (event_id, 관계, 규칙, evidence_type, source_reference, available_at)
    alerts: list = field(default_factory=list)         # dict
    excluded: dict = field(default_factory=dict)

    def key(self) -> tuple:
        return (self.hypothesis_id, self.summary, tuple(sorted(self.flags.items())), tuple(self.relations),
                tuple(sorted((a["rule"], a["event_id"]) for a in self.alerts)))


def assess(tl: Timeline, T: float) -> Assessment:
    h = current_hypothesis(tl, T)
    eff, excl, superseded = effective_evidence(tl, T)
    if h is None:
        return Assessment(T, None, None, "NO_HYPOTHESIS", {}, [], [], excl)
    rels = []
    for e in sorted(eff, key=lambda x: x.event_id):
        if e.evidence_type == "IMAGING_ORDER":
            continue                                              # 대기 여부는 아래에서 판독과 짝지어 판단
        r, rule = relation(e, h.dx)
        rels.append((e.event_id, r, rule, e.evidence_type, e.source_reference, e.available_at))
    reports = [e for e in eff if e.evidence_type == "IMAGING_REPORT"]
    for o in sorted((e for e in eff if e.evidence_type == "IMAGING_ORDER"), key=lambda x: x.event_id):
        answered = any(r.order_ref == o.event_id for r in reports) or \
            any(s.order_ref == o.event_id for s in superseded.values() if usable(s, T))
        if not answered:
            r, rule = relation(o, h.dx)
            rels.append((o.event_id, r, rule, o.evidence_type, o.source_reference, o.available_at))
    kinds = [r[1] for r in rels]
    decisive = [r for r in rels if r[2] in ("R1", "R2", "R3", "R4", "R5")]
    flags = {"support": "SUPPORTS" in kinds, "conflict": "CONFLICTS" in kinds, "pending": "PENDING" in kinds,
             "unknown": "UNKNOWN" in kinds, "chronic_only": any(r[2] == "R3" for r in decisive) and
             not any(r[2] in ("R1", "R2") for r in decisive), "decisive": bool(decisive)}
    if decisive:
        rs = {r[2] for r in decisive}
        summary = "CONFLICT" if "R2" in rs else "SUPPORTED" if "R1" in rs else "INSUFFICIENT" if "R3" in rs else "UNKNOWN"
    elif flags["pending"]:
        summary = "PENDING"
    elif flags["support"]:
        summary = "SUPPORTED"
    else:
        summary = "INSUFFICIENT"
    alerts = []
    for r in rels:
        if r[2] == "R2":
            alerts.append(_alert(h, "AL1_NEW_CONFLICT", r))
    for old_id, new in superseded.items():
        old = next(e for e in tl.evidence if e.event_id == old_id)
        if relation(old, h.dx)[1] == "R1" and relation(new, h.dx)[0] != "SUPPORTS":
            alerts.append(_alert(h, "AL2_SUPPORT_RETRACTED", (new.event_id, "", "AL2", new.evidence_type,
                                                              new.source_reference, new.available_at), retracted=old_id))
    alerts = [a for a in alerts if all(a.get(k) not in (None, "") for k in
                                       ("hypothesis_id", "rule", "event_id", "source_reference", "evidence_type", "available_at"))]
    return Assessment(T, h.hypothesis_id, h.dx, summary, flags, rels, alerts, excl)


def _alert(h, rule, r, retracted=None) -> dict:
    a = {"hypothesis_id": h.hypothesis_id, "dx": h.dx, "provenance": h.provenance, "rule": rule, "event_id": r[0],
         "evidence_type": r[3], "source_reference": r[4], "available_at": r[5]}
    if retracted:
        a["retracted_event_id"] = retracted
    return a


def session(tl: Timeline, checkpoints: list) -> list:
    """체크포인트별 평가 + 알림 생김/사라짐 로그(사유 포함)."""
    out, prev = [], None
    for T in checkpoints:
        a = assess(tl, T)
        new, gone = [], []
        if prev is not None:
            pk = {(x["hypothesis_id"], x["rule"], x["event_id"]): x for x in prev.alerts}
            ck = {(x["hypothesis_id"], x["rule"], x["event_id"]): x for x in a.alerts}
            new = [ck[k] for k in ck if k not in pk]
            for k in pk:
                if k not in ck:
                    reason = "HYPOTHESIS_CHANGED" if a.hypothesis_id != prev.hypothesis_id else \
                        "RESOLVED_BY_CORRECTION" if k[1] == "AL1_NEW_CONFLICT" and \
                        any(e.supersedes == k[2] for e in tl.evidence if usable(e, T)) else "OTHER"
                    gone.append({"key": k, "reason": reason})
        else:
            new = list(a.alerts)
        out.append({"assessment": a, "alerts_new": new, "alerts_cleared": gone})
        prev = a
    return out
