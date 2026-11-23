"""의사 발화 → 진단 진술 후보 → 의사 확인 계약. 추출기는 주입식이며 포함하지 않는다. AI 는 확정하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .schema import AssertedBy, DiagnosisAssertion, DxStatus, Provenance


@dataclass(frozen=True)
class UtteranceCandidate:
    candidate_id: str
    encounter_id: str
    raw_text: str
    diagnosis_label: str
    proposed_status: DxStatus
    speaker: str                            # UNKNOWN 이면 진단 진술로 보지 않음
    source: Provenance                      # STT·NLU 버전을 보존해 오류를 분리 평가
    stt_text_ref: str = ""


def to_assertion(c: UtteranceCandidate, at: float) -> DiagnosisAssertion:
    """후보 상태 그대로 변환 — 이 값은 usable_as_hypothesis() 가 거짓(의사 확인 전)."""
    return DiagnosisAssertion(c.candidate_id, c.encounter_id, c.diagnosis_label, c.proposed_status, AssertedBy.MODEL_EXTRACTED, at, c.source)


def physician_confirm(a: DiagnosisAssertion, confirmed_status: DxStatus, at: float, confirm_ref: str, new_id: str) -> DiagnosisAssertion:
    """의사 확인 사건으로만 상태가 정해진다. 원 후보는 지우지 않고 대체한다."""
    if not confirm_ref:
        raise ValueError("의사 확인 기록 필요")
    p = replace(a.provenance, physician_confirmed=True, source_ref=confirm_ref)
    return replace(a, assertion_id=new_id, status=confirmed_status, asserted_by=AssertedBy.PHYSICIAN, asserted_at=at, provenance=p, supersedes=a.assertion_id)
