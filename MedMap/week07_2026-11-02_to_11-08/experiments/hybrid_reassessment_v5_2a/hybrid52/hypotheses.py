"""진단 가설 등록. 명시적으로 제공된 가설만 비교한다(증상·언급으로 가설을 자동 생성하지 않음).
- 가설 출처(hypothesis_source)와 의사 확인 상태를 분리 보관
- AI 후보·기록 이력은 의사 확진으로 승격 불가
- 가설끼리 경쟁·배타 관계를 두지 않는다(복수 질환 동시 존재 가능)
- 개념 검증·분류 축은 v5-1 MultiHypothesis 를 그대로 사용"""
from __future__ import annotations

from dataclasses import dataclass

from hybrid5 import concepts as CN

SOURCES = ("PHYSICIAN_WORKING_DIAGNOSIS", "PHYSICIAN_ADDITIONAL_HYPOTHESIS", "AI_CANDIDATE_UNCONFIRMED", "RECORD_HISTORY")
PHYSICIAN_SOURCES = SOURCES[:2]
CONFIRMATION = ("CONFIRMED", "UNCONFIRMED")
STATUS = ("UNDER_EVALUATION", "HISTORY_ONLY")
MUTUAL_EXCLUSIVITY = "NOT_ASSUMED(가설 간 경쟁·배타 관계 없음 — 복수 질환 동시 존재 가능)"


@dataclass(frozen=True)
class HypothesisSpec:
    hypothesis_id: str
    disease_concept_id: str
    diagnosis_episode_id: str
    hypothesis_source: str
    physician_confirmation_status: str = "UNCONFIRMED"
    evaluation_time: float = 0.0
    hypothesis_status: str = "UNDER_EVALUATION"
    provenance: tuple = ()

    def __post_init__(self):
        if self.hypothesis_source not in SOURCES:
            raise ValueError(f"가설 출처 {self.hypothesis_source}")
        if self.physician_confirmation_status not in CONFIRMATION:
            raise ValueError(self.physician_confirmation_status)
        if self.physician_confirmation_status == "CONFIRMED" and self.hypothesis_source not in PHYSICIAN_SOURCES:
            raise ValueError("AI 후보·기록 이력은 의사 확진으로 승격하지 않음")
        if self.hypothesis_status not in STATUS:
            raise ValueError(self.hypothesis_status)
        if self.disease_concept_id not in CN.CONCEPTS:
            raise ValueError(f"지원하지 않는 개념 {self.disease_concept_id}(다른 개념에 붙이지 않음)")

    @property
    def family(self) -> str:
        return CN.CONCEPTS[self.disease_concept_id]["family"]

    @property
    def is_working_diagnosis(self) -> bool:
        return self.hypothesis_source == "PHYSICIAN_WORKING_DIAGNOSIS"

    @property
    def physician_asserted(self) -> bool:
        return self.hypothesis_source in PHYSICIAN_SOURCES

    def to_multi(self) -> CN.MultiHypothesis:
        st = {"AI_CANDIDATE_UNCONFIRMED": "AI_CANDIDATE_UNCONFIRMED", "RECORD_HISTORY": "RECORD_HISTORY"}.get(
            self.hypothesis_source, "PHYSICIAN_CONFIRMED" if self.physician_confirmation_status == "CONFIRMED" else "PHYSICIAN_SUSPECTED")
        return CN.MultiHypothesis(self.hypothesis_id, self.disease_concept_id, self.diagnosis_episode_id, self.evaluation_time, diagnosis_status=st,
                                  physician_confirmation_status=self.physician_confirmation_status, source_ids=list(self.provenance))

    def as_row(self) -> dict:
        return {"hypothesis_id": self.hypothesis_id, "disease_concept_id": self.disease_concept_id, "family": self.family, "diagnosis_episode_id": self.diagnosis_episode_id,
                "hypothesis_source": self.hypothesis_source, "physician_confirmation_status": self.physician_confirmation_status, "hypothesis_status": self.hypothesis_status,
                "is_working_diagnosis": self.is_working_diagnosis, "evaluation_time": self.evaluation_time, "provenance": list(self.provenance)}


def check_addition(existing: list, new: HypothesisSpec) -> None:
    if any(s.hypothesis_id == new.hypothesis_id for s in existing):
        raise ValueError(f"가설 ID 중복 {new.hypothesis_id}")
    if new.is_working_diagnosis and any(s.is_working_diagnosis and s.diagnosis_episode_id == new.diagnosis_episode_id for s in existing):
        raise ValueError("에피소드당 Working Diagnosis 1개(자동 변경·추가 없음)")
