"""질문 표현 계층: evidence ID → 환자용 한국어 질문·선택지, 그리고 UI 선택값 → PatientState Answer.

질문 선택 알고리즘·진단 모델·IG 점수·candidate pool 은 이 계층에서 전혀 건드리지 않는다.
한국어는 `data/question_labels_ko.json` 의 정적 매핑이며 런타임 번역/LLM 호출은 없다.
매핑이 없는 질문·값은 DDXPlus 원문으로 fallback 하고 `is_fallback` 로 표시한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .evidence import EvidenceCatalog
from .patient_state import Answer, negative, not_applicable, positive, unknown, value

LABELS_PATH = Path(__file__).resolve().parent / "data" / "question_labels_ko.json"

YES_NO = "YES_NO"
SINGLE_CHOICE = "SINGLE_CHOICE"
MULTI_CHOICE = "MULTI_CHOICE"
SCALE = "SCALE"

ANSWER_YES = "YES"
ANSWER_NO = "NO"
ANSWER_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Choice:
    value: object          # UI 가 되돌려줄 값: True/False/None 또는 DDXPlus value code
    label: str             # 환자에게 보이는 한국어(또는 fallback 원문)
    original_label: str | None = None
    is_fallback: bool = False

    def to_dict(self) -> dict:
        return {"value": self.value, "label": self.label, "original_label": self.original_label,
                "is_fallback": self.is_fallback}


@dataclass(frozen=True)
class PresentedQuestion:
    question_id: str
    question_ko: str
    question_original: str
    answer_type: str            # YES_NO | SINGLE_CHOICE | MULTI_CHOICE | SCALE
    choices: tuple
    is_fallback: bool
    information_gain: float | None = None
    explanation: str | None = None   # 외부 프로필 설명 자리(현재 None, IG 에 영향 없음)

    def to_dict(self) -> dict:
        return {"question_id": self.question_id, "question_ko": self.question_ko,
                "question_original": self.question_original, "answer_type": self.answer_type,
                "choices": [c.to_dict() for c in self.choices], "information_gain": self.information_gain,
                "is_fallback": self.is_fallback, "explanation": self.explanation}


class QuestionPresenter:
    def __init__(self, catalog: EvidenceCatalog, labels_path=None):
        self.catalog = catalog
        data = json.loads(Path(labels_path or LABELS_PATH).read_text())
        self.questions_ko = data["questions"]
        self.values_ko = data["values"]
        self.unknown_label = data["unknown_choice_label"]
        self.yes_label = data["yes_label"]
        self.no_label = data["no_label"]

    # ---- 표현 ----
    def answer_type(self, evidence_id: str) -> str:
        question = self.catalog.question(evidence_id)
        if question.answer_type == "BINARY":
            return YES_NO
        if not question.value_labels:          # 정의 파일에 라벨이 없는 수치 척도(0~10)
            return SCALE
        return MULTI_CHOICE if question.answer_type == "MULTI" else SINGLE_CHOICE

    def present(self, evidence_id: str, information_gain: float | None = None,
                explanation: str | None = None) -> PresentedQuestion:
        question = self.catalog.question(evidence_id)
        korean = self.questions_ko.get(evidence_id)
        answer_type = self.answer_type(evidence_id)
        choices = self._choices(evidence_id, answer_type)
        return PresentedQuestion(evidence_id, korean or question.text, question.text, answer_type, choices,
                                 is_fallback=korean is None, information_gain=information_gain,
                                 explanation=explanation)

    def present_proposal(self, proposal) -> PresentedQuestion:
        """NextInformationEngine 의 QuestionProposal 을 그대로 감싼다(질문 ID·IG 불변)."""
        return self.present(proposal.evidence_id, proposal.information_gain, proposal.explanation)

    def _choices(self, evidence_id: str, answer_type: str) -> tuple:
        question = self.catalog.question(evidence_id)
        if answer_type == YES_NO:
            return (Choice(True, self.yes_label), Choice(False, self.no_label),
                    Choice(None, self.unknown_label))
        choices = []
        for code in question.possible_values:
            english = question.value_labels.get(code)
            korean = self.values_ko.get(code)
            if answer_type == SCALE:
                choices.append(Choice(code, str(code), english, False))
            else:
                choices.append(Choice(code, korean or english or code, english, korean is None))
        choices.append(Choice(None, self.unknown_label))
        return tuple(choices)

    # ---- UI 선택값 → 모델 입력 ----
    def to_answer(self, evidence_id: str, selection) -> Answer:
        """selection: YES_NO 는 True/False/None 또는 '예'/'아니요'/'잘 모르겠어요',
        선택형은 value code(또는 code 목록), None 은 UNKNOWN. UI 문자열은 모델에 들어가지 않는다."""
        answer_type = self.answer_type(evidence_id)
        if selection is None:
            return unknown()
        if answer_type == YES_NO:
            token = self._normalize_yes_no(selection)
            if token == ANSWER_YES: return positive()
            if token == ANSWER_NO: return negative()
            return unknown()
        codes = [selection] if isinstance(selection, (str, int)) else list(selection)
        codes = [c for c in codes if c is not None]
        if not codes:
            return unknown()
        resolved = []
        for code in codes:                       # 중복 선택은 한 번만 반영
            item = self._resolve_code(evidence_id, code)
            if item not in resolved:
                resolved.append(item)
        if any(r == "NOT_APPLICABLE" for r in resolved):
            return not_applicable()
        answer = value(*resolved)
        self.catalog.validate_answer(evidence_id, answer)
        return answer

    def _normalize_yes_no(self, selection) -> str:
        if isinstance(selection, bool):
            return ANSWER_YES if selection else ANSWER_NO
        text = str(selection).strip()
        if text in (self.yes_label, "Y", "YES", "POS", "예"): return ANSWER_YES
        if text in (self.no_label, "N", "NO", "NEG", "아니요"): return ANSWER_NO
        if text in (self.unknown_label, "UNKNOWN", "?"): return ANSWER_UNKNOWN
        raise ValueError(f"MEDMAP_UNRECOGNIZED_SELECTION:{evidence_label(selection)}")

    def _resolve_code(self, evidence_id: str, selection) -> str:
        """value code 를 그대로 쓰되, 한국어/영문 라벨이 들어와도 code 로 되돌린다."""
        question = self.catalog.question(evidence_id)
        code = str(selection)
        if code in question.possible_values:
            return code
        for candidate in question.possible_values:
            if self.values_ko.get(candidate) == code or question.value_labels.get(candidate) == code:
                return candidate
        raise ValueError(f"MEDMAP_UNRECOGNIZED_SELECTION:{evidence_id}:{code}")

    # ---- 커버리지 ----
    def coverage(self) -> dict:
        mapped = [e for e in self.catalog.ids if e in self.questions_ko]
        parents = sorted({p for p in self.catalog.parent.values()})
        return {"total_evidence": len(self.catalog.ids), "korean_mapped": len(mapped),
                "fallback": len(self.catalog.ids) - len(mapped),
                "parent_questions": len(parents),
                "parent_questions_mapped": sum(1 for p in parents if p in self.questions_ko),
                "value_codes_mapped": len(self.values_ko)}
