"""공통 진단·증거·검사·출처 데이터 구조(docs/EVIDENCE_SCHEMA.md). 의학 지식을 담지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DxStatus(str, Enum):
    CONFIRMED_DIAGNOSIS = "CONFIRMED_DIAGNOSIS"
    WORKING_DIAGNOSIS = "WORKING_DIAGNOSIS"
    DIFFERENTIAL_DIAGNOSIS = "DIFFERENTIAL_DIAGNOSIS"
    RULED_OUT_DIAGNOSIS = "RULED_OUT_DIAGNOSIS"
    HISTORICAL_DIAGNOSIS = "HISTORICAL_DIAGNOSIS"
    PATIENT_REPORTED_DIAGNOSIS = "PATIENT_REPORTED_DIAGNOSIS"
    UNKNOWN = "UNKNOWN"


class AssertedBy(str, Enum):
    PHYSICIAN = "PHYSICIAN"
    EMR_RECORD = "EMR_RECORD"
    PATIENT = "PATIENT"
    MODEL_EXTRACTED = "MODEL_EXTRACTED"     # 모델 추출 후보 — 의사 확인 전에는 판단 근거가 아님
    DATASET_ANNOTATION = "DATASET_ANNOTATION"
    SIMULATED = "SIMULATED"
    UNKNOWN = "UNKNOWN"


class Effect(str, Enum):
    SUPPORT = "SUPPORT"
    WEAKEN = "WEAKEN"
    CONTRADICTION = "CONTRADICTION"         # WEAKEN 과 구분: 명백한 모순
    NO_CLEAR_EFFECT = "NO_CLEAR_EFFECT"
    UNCERTAIN = "UNCERTAIN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OutcomeStatus(str, Enum):
    ANSWERED = "ANSWERED"
    ABSTAIN = "ABSTAIN"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class EvidenceKind(str, Enum):
    SYMPTOM = "SYMPTOM"
    SIGN = "SIGN"
    VITAL = "VITAL"
    LAB = "LAB"
    IMAGING_REPORT = "IMAGING_REPORT"
    PATHOLOGY = "PATHOLOGY"
    PAST_HISTORY = "PAST_HISTORY"
    FAMILY_HISTORY = "FAMILY_HISTORY"
    GENETIC = "GENETIC"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    PATIENT_REPORTED_COURSE = "PATIENT_REPORTED_COURSE"
    OTHER = "OTHER"


class Polarity(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    VALUE_ONLY = "VALUE_ONLY"
    NOT_ASSESSED = "NOT_ASSESSED"           # 기록 없음 ≠ 음성
    UNKNOWN = "UNKNOWN"


class Experiencer(str, Enum):
    PATIENT = "PATIENT"
    FAMILY = "FAMILY"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TestStatus(str, Enum):
    NOT_ORDERED = "NOT_ORDERED"
    ORDERED = "ORDERED"
    PENDING = "PENDING"
    RESULT_AVAILABLE = "RESULT_AVAILABLE"
    REVIEWED = "REVIEWED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class DataClass(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    PUBLIC_OPEN = "PUBLIC_OPEN"
    RESTRICTED = "RESTRICTED"               # 외부 전송 금지(MIMIC·ER-Reason 등)


@dataclass(frozen=True)
class Provenance:
    source_type: str
    source_ref: str
    data_class: DataClass
    text_span: str = ""
    extractor: str = ""
    extractor_version: str = ""
    physician_confirmed: bool = False

    def __post_init__(self):
        if not self.source_type or not self.source_ref:
            raise ValueError("출처 없는 기록 거부")


@dataclass(frozen=True)
class DiagnosisAssertion:
    assertion_id: str
    encounter_id: str
    diagnosis_label: str
    status: DxStatus
    asserted_by: AssertedBy
    asserted_at: float | None
    provenance: Provenance
    concept_id: str = ""
    subtype: str = ""
    certainty: str = "UNKNOWN"              # 원문 표현 범주, 확률 아님
    basis_evidence_ids: tuple = ()
    supersedes: str | None = None

    def usable_as_hypothesis(self) -> bool:
        """판단 대상 가설이 될 수 있는가. 모델 추출 후보는 의사 확인 전 불가, 배제·과거 진단은 현재 가설 아님."""
        if self.status in (DxStatus.RULED_OUT_DIAGNOSIS, DxStatus.HISTORICAL_DIAGNOSIS, DxStatus.UNKNOWN):
            return False
        if self.asserted_by == AssertedBy.MODEL_EXTRACTED and not self.provenance.physician_confirmed:
            return False
        return True


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    encounter_id: str
    kind: EvidenceKind
    text: str
    provenance: Provenance
    observed_at: float | None = None
    recorded_at: float | None = None
    available_at: float | None = None       # 없으면 어느 시점에도 사용 안 함
    reviewed_at: float | None = None
    polarity: Polarity = Polarity.UNKNOWN
    experiencer: Experiencer = Experiencer.UNKNOWN
    concept_id: str = ""                    # 표준 개념 연결이 없으면 빈 값 — 추정해서 채우지 않음
    uncertainty: str = ""
    supersedes: str | None = None


@dataclass(frozen=True)
class TestEvent:
    test_id: str
    encounter_id: str
    event: str                              # ORDER·COLLECT·RESULT·REVIEW·CANCEL·CORRECT
    at: float | None
    provenance: Provenance
    result_evidence_id: str = ""


@dataclass(frozen=True)
class Citation:
    kind: str                               # INPUT_EVIDENCE·KNOWLEDGE·RULE
    ref: str
    span: str = ""


@dataclass(frozen=True)
class ReasonerInput:
    item_id: str
    case_id: str
    hypothesis: DiagnosisAssertion
    evidence: EvidenceItem
    context_summary: str = ""
    prior_evidence: tuple = ()              # as_of 까지 공개된 증거만
    as_of: float | None = None
    data_class: DataClass = DataClass.SYNTHETIC


@dataclass(frozen=True)
class ReasonerOutput:
    item_id: str
    reasoner: str
    status: OutcomeStatus
    effect: Effect | None = None
    grade: int | None = None                # -2..+2, 근거가 등급을 정의할 때만. 임의 환산 금지
    reason_code: str = ""
    citations: tuple = ()
    claims: tuple = ()                      # 의학적 주장 문장. 근거 없는 주장 집계용
    used_evidence_ids: tuple = ()
    flags: tuple = ()

    def __post_init__(self):
        if self.status == OutcomeStatus.ANSWERED and self.effect is None:
            raise ValueError("ANSWERED 인데 effect 없음")
        if self.status != OutcomeStatus.ANSWERED and (self.effect is not None or self.grade is not None):
            raise ValueError("기권·미구현은 판단값을 가질 수 없음")
        if self.grade is not None and self.grade not in (-2, -1, 0, 1, 2):
            raise ValueError("grade 범위 오류")


@dataclass(frozen=True)
class ReferenceLabel:
    item_id: str
    case_id: str
    grade: int                              # 전문가 -2..+2
    group: str = ""
    split: str = ""


def abstain(item_id: str, reasoner: str, reason: str, flags: tuple = ()) -> ReasonerOutput:
    return ReasonerOutput(item_id, reasoner, OutcomeStatus.ABSTAIN, reason_code=reason, flags=flags)


def not_implemented(item_id: str, reasoner: str, reason: str) -> ReasonerOutput:
    return ReasonerOutput(item_id, reasoner, OutcomeStatus.NOT_IMPLEMENTED, reason_code=reason)
