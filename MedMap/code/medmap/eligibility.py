"""QuestionEligibility: 지금 물어볼 수 있는 질문만 반환한다.

규칙(STEP16B 사전등록과 동일):
  - 이미 물었거나 답이 있는 질문 제외
  - 제외 질문(E_134, E_152) 제외
  - 부모가 없는 질문은 사용 가능
  - 부모가 있는 질문은 현재 visible parent 가 POSITIVE 일 때만 사용 가능
    (부모가 UNASKED / NEGATIVE / UNKNOWN / NOT_APPLICABLE 이면 닫힘)
숨은 답·미래 답·정답 진단·질환별 symptom 목록은 사용하지 않는다.
"""
from __future__ import annotations

from .evidence import EvidenceCatalog
from .patient_state import PatientState


class QuestionEligibility:
    def __init__(self, catalog: EvidenceCatalog):
        self.catalog = catalog

    def is_eligible(self, evidence_id: str, state: PatientState) -> bool:
        if self.catalog.is_excluded(evidence_id):
            return False
        if state.is_asked(evidence_id):
            return False
        parent = self.catalog.parent.get(evidence_id)
        if parent is None:
            return True
        return state.is_positive(parent)

    def eligible_questions(self, state: PatientState) -> list[str]:
        """evidence 번호 오름차순. 동일 상태면 항상 같은 목록."""
        return [e for e in self.catalog.selectable_ids() if self.is_eligible(e, state)]
