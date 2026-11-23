"""지식 관계 v2 데이터 모델(설계 구현, 의학 내용 없음). 온톨로지·공출현 연결을 지지·약화 근거로 자동 승격하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass

REL_TYPES = {"HAS_FINDING", "HAS_RISK_FACTOR", "EVALUATED_BY", "SUPPORTS_HYPOTHESIS", "WEAKENS_HYPOTHESIS", "DIFFERENTIAL_OF", "REQUIRES_CONTEXT", "EVIDENCE_FROM",
             "HAS_SUBTYPE", "HAS_CONTRAINDICATION", "HAS_UNCERTAINTY"}
DIRECTIONAL = {"SUPPORTS_HYPOTHESIS", "WEAKENS_HYPOTHESIS"}
REVIEW = {"PROPOSED", "SOURCE_QUOTE_CHECKED", "CLINICIAN_REVIEWED", "RETIRED"}
SOURCE_KIND = {"GUIDELINE", "PRIMARY_STUDY", "SYSTEMATIC_REVIEW", "TEXTBOOK", "ONTOLOGY", "COOCCURRENCE"}


@dataclass(frozen=True)
class KnowledgeAssertion:
    assertion_id: str
    subject: str
    relation: str
    obj: str
    source_kind: str
    source_ref: str
    source_version: str
    review_status: str = "PROPOSED"
    source_quote: str = ""
    applicability: str = ""
    exceptions: str = ""
    evidence_level: str = "UNKNOWN"

    def __post_init__(self):
        if self.relation not in REL_TYPES or self.review_status not in REVIEW or self.source_kind not in SOURCE_KIND:
            raise ValueError("관계·검토·출처 값 오류")
        if not self.source_ref or not self.source_version:
            raise ValueError("출처·버전 없는 관계 거부")
        if self.relation in DIRECTIONAL:
            if self.source_kind in ("ONTOLOGY", "COOCCURRENCE"):
                raise ValueError("온톨로지·공출현 연결은 방향 근거로 승격 불가")
            if not self.source_quote or not self.applicability:
                raise ValueError("방향 관계에는 원문 인용과 적용 조건 필요")

    def usable_for_reasoning(self) -> bool:
        return self.relation in DIRECTIONAL and self.review_status in ("SOURCE_QUOTE_CHECKED", "CLINICIAN_REVIEWED")


def legacy_edge_view(edge) -> dict:
    """EXP-01b 간선을 읽기 전용으로 분류. 공출현·DisMech 간선은 방향 근거가 아니라 HAS_FINDING 후보로만 본다."""
    return {"src": edge.src, "dst": edge.dst, "rel": edge.rel, "tier": edge.tier, "source": str(edge.source)[:200], "v2_view": "HAS_FINDING_CANDIDATE", "directional_evidence": False}
