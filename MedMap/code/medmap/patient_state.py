"""PatientState: 환자의 현재 관측 상태. 숨은 정답·전체 record 는 제품 상태에 존재하지 않는다.

답변 상태(STEP16B V2 규칙):
  UNASKED        아직 묻지 않음 — 상태에 항목이 없음. NEGATIVE 와 절대 같지 않다.
  POSITIVE       binary 양성
  NEGATIVE       binary 음성
  VALUE          categorical/multi 의 명시 값(1개 이상)
  NOT_APPLICABLE 부모 질문이 음성이라 해당 없음(NA)
  UNKNOWN        환자가 모름 — 어떤 특징도 켜지 않지만 다시 묻지 않는다
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class AnswerStatus(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    VALUE = "VALUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


UNASKED = None  # 상태에 키가 없는 것이 UNASKED 이며 별도 값으로 저장하지 않는다


@dataclass(frozen=True)
class Answer:
    status: AnswerStatus
    values: tuple = ()      # status VALUE 일 때만 사용

    def __post_init__(self):
        if self.status is AnswerStatus.VALUE and not self.values:
            raise ValueError("MEDMAP_VALUE_ANSWER_WITHOUT_VALUES")
        if self.status is not AnswerStatus.VALUE and self.values:
            raise ValueError("MEDMAP_VALUES_ON_NON_VALUE_ANSWER")

    @property
    def is_positive(self) -> bool:
        return self.status is AnswerStatus.POSITIVE

    def tokens(self) -> tuple:
        """인코딩 토큰. UNKNOWN 은 빈 튜플(어떤 열도 켜지 않음)."""
        if self.status is AnswerStatus.POSITIVE: return ("POS",)
        if self.status is AnswerStatus.NEGATIVE: return ("NEG",)
        if self.status is AnswerStatus.NOT_APPLICABLE: return ("NA",)
        if self.status is AnswerStatus.VALUE: return tuple(f"VALUE::{v}" for v in self.values)
        return ()


def positive() -> Answer: return Answer(AnswerStatus.POSITIVE)
def negative() -> Answer: return Answer(AnswerStatus.NEGATIVE)
def value(*values: str) -> Answer: return Answer(AnswerStatus.VALUE, tuple(str(v) for v in values))
def not_applicable() -> Answer: return Answer(AnswerStatus.NOT_APPLICABLE)
def unknown() -> Answer: return Answer(AnswerStatus.UNKNOWN)


@dataclass(frozen=True)
class PatientState:
    age: int
    sex: str                                  # "M" | "F"
    initial_evidence: str | None = None       # 최초 공개된 evidence(항상 binary POSITIVE)
    answers: dict = field(default_factory=dict)   # evidence_id → Answer
    asked: tuple = ()                         # 물어본 순서(초기 evidence 포함)

    def __post_init__(self):
        if self.sex not in ("M", "F"):
            raise ValueError(f"MEDMAP_INVALID_SEX:{self.sex}")
        for evidence_id in self.answers:
            if evidence_id not in self.asked:
                raise ValueError(f"MEDMAP_ANSWER_WITHOUT_ASKED:{evidence_id}")

    # ---- 조회 ----
    def status(self, evidence_id: str) -> AnswerStatus | None:
        answer = self.answers.get(evidence_id)
        return answer.status if answer else UNASKED

    def is_asked(self, evidence_id: str) -> bool:
        return evidence_id in self.answers or evidence_id in self.asked

    def is_positive(self, evidence_id: str) -> bool:
        answer = self.answers.get(evidence_id)
        return bool(answer and answer.is_positive)

    @property
    def n_asked(self) -> int:
        return len(self.asked)

    @property
    def n_additional(self) -> int:
        """초기 evidence 를 제외한 추가 질문 수 (MODEL_k 의 k 와 대응)."""
        return sum(1 for e in self.asked if e != self.initial_evidence)

    def feature_tokens(self):
        for evidence_id, answer in self.answers.items():
            tokens = answer.tokens()
            if tokens:
                yield evidence_id, tokens

    # ---- 갱신(불변) ----
    def with_answer(self, evidence_id: str, answer: Answer) -> "PatientState":
        if self.is_asked(evidence_id):
            raise ValueError(f"MEDMAP_ALREADY_ASKED:{evidence_id}")
        return replace(self, answers={**self.answers, evidence_id: answer}, asked=self.asked + (evidence_id,))

    @classmethod
    def new(cls, age: int, sex: str, initial_evidence: str | None = None, observed: dict | None = None) -> "PatientState":
        """observed: evidence_id → Answer (초기 evidence 는 POSITIVE 로 자동 기록)."""
        answers, asked = {}, []
        if initial_evidence:
            answers[initial_evidence] = positive(); asked.append(initial_evidence)
        for evidence_id, answer in (observed or {}).items():
            if evidence_id in answers:
                continue
            answers[evidence_id] = answer; asked.append(evidence_id)
        return cls(age=age, sex=sex, initial_evidence=initial_evidence, answers=answers, asked=tuple(asked))
