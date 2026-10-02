"""Clinical Summary (medmap-clinical-summary-v1): 세션 종료 후 "현재까지 확인된 정보"를 결정적으로 만든다.

원칙
  - summary 는 PatientState(= medmap-session-v1) + 최종 Turn 의 진단 후보 top3 의 결정적 투영이다.
    LLM·번역 호출·난수·시각 없음. 같은 세션을 복원하면 같은 summary 가 나온다.
  - 파생값이므로 세션·서버에 저장하지 않는다. 세션에 없는 정보(intake cache 의 미적용 답,
    bootstrap "잘 모르겠어요", 원문 transcript, 매퍼 matched_text)는 만들지 않는다.
  - 전체 posterior·IG·MEDMAP_* 코드는 출력하지 않는다. 진단 후보는 top3 만, "현재 확인이 필요한 진단 후보" 의미로만.
  - 조용한 보정 없음: 세션 검증 실패는 기존 예외를 그대로 올리고, 후보 입력이 계약과 다르면 ValueError.
  - 기존 모듈(patient_state/serialization/question_presentation/api)은 읽기만 한다. 모델을 로딩하지 않는다.
설계: docs/superpowers/plans/2026-09-26-medmap-clinical-summary.md
"""
from __future__ import annotations

import json
from pathlib import Path

from .evidence import EvidenceCatalog
from .patient_state import AnswerStatus, PatientState
from .question_presentation import SCALE, QuestionPresenter
from .serialization import deserialize_session

CLINICAL_SUMMARY_SCHEMA_VERSION = "medmap-clinical-summary-v1"

SUMMARY_KEYS = ("schema_version", "chief_complaint", "confirmed_positive", "confirmed_negative",
                "confirmed_values", "not_applicable", "unknown", "answered_questions",
                "diagnosis_candidates", "questions_used", "disclaimer")

# 한 문자열, 두 줄(\n 구분). 화면/복사/인쇄 계층이 줄바꿈을 그대로 쓸 수 있게 한다.
DISCLAIMER_KO = ("현재까지 입력하고 확인한 내용을 진료 전 참고용으로 정리한 것입니다.\n"
                 "진단 결과가 아니며, 진단에는 의료진의 평가가 필요합니다.")

# 상태 NOT_APPLICABLE 표시 문구(question_labels_ko.json 에 상태용 키가 없어 모듈 상수로 둔다).
NOT_APPLICABLE_LABEL_KO = "해당 없음"
MAX_CANDIDATES = 3

INITIAL_LABELS_JSON = Path(__file__).resolve().parent / "data" / "initial_evidence_ko.json"

_STATUS_KEY = {
    AnswerStatus.POSITIVE: "confirmed_positive",
    AnswerStatus.NEGATIVE: "confirmed_negative",
    AnswerStatus.VALUE: "confirmed_values",
    AnswerStatus.NOT_APPLICABLE: "not_applicable",
    AnswerStatus.UNKNOWN: "unknown",
}


# ---------------- 표시 라벨 (향후 terminology 계층이 교체할 자리) ----------------
class LabelProvider:
    """표시 문구 공급자 인터페이스. 계산 규칙에는 관여하지 않는다."""

    def question(self, evidence_id: str) -> tuple:       # (question_ko, question_original, is_fallback)
        raise NotImplementedError

    def value(self, evidence_id: str, code: str) -> tuple:   # (label, is_fallback)
        raise NotImplementedError

    def status_label(self, status: AnswerStatus) -> str:
        raise NotImplementedError

    def initial_label(self, evidence_id: str) -> str | None:
        raise NotImplementedError

    def diagnosis(self, name: str) -> tuple:              # (display_name, is_fallback)
        raise NotImplementedError


class PresenterLabelProvider(LabelProvider):
    """기본 구현: master 에 있는 정적 파일만 읽는다(question_labels_ko.json, initial_evidence_ko.json).

    질환 한국어명은 master 에 없으므로 모델 클래스명을 그대로 쓰고 is_fallback=True 로 표시한다.
    """

    def __init__(self, catalog: EvidenceCatalog, presenter: QuestionPresenter | None = None,
                 initial_labels_path=None):
        self.catalog = catalog
        self.presenter = presenter or QuestionPresenter(catalog)
        with open(initial_labels_path or INITIAL_LABELS_JSON, encoding="utf-8") as f:
            self._initial = {item["evidence_id"]: item["label_ko"] for item in json.load(f)["items"]}

    def question(self, evidence_id: str) -> tuple:
        original = self.catalog.question(evidence_id).text
        korean = self.presenter.questions_ko.get(evidence_id)
        return (korean or original, original, korean is None)

    def value(self, evidence_id: str, code: str) -> tuple:
        """QuestionPresenter._choices 와 같은 규칙: 척도는 숫자 문자열, 그 외 한국어 → 영문 → code."""
        if self.presenter.answer_type(evidence_id) == SCALE:
            return (str(code), False)
        korean = self.presenter.values_ko.get(code)
        english = self.catalog.question(evidence_id).value_labels.get(code)
        return (korean or english or code, korean is None)

    def status_label(self, status: AnswerStatus) -> str:
        if status is AnswerStatus.POSITIVE:
            return self.presenter.yes_label
        if status is AnswerStatus.NEGATIVE:
            return self.presenter.no_label
        if status is AnswerStatus.UNKNOWN:
            return self.presenter.unknown_label
        if status is AnswerStatus.NOT_APPLICABLE:
            return NOT_APPLICABLE_LABEL_KO
        raise ValueError(f"MEDMAP_SUMMARY_STATUS_WITHOUT_LABEL:{status.value}")

    def initial_label(self, evidence_id: str) -> str | None:
        return self._initial.get(evidence_id)

    def diagnosis(self, name: str) -> tuple:
        return (name, True)


class TerminologyLabelProvider(PresenterLabelProvider):
    """선택형: 질환 표시명만 한국어 용어 정본(medmap/terminology.py)에서 가져온다. 나머지는 PresenterLabelProvider 그대로.

    ok 항목만 한국어(is_fallback=False). review_needed·미등록은 모델 class 명 + is_fallback=True.
    """

    def __init__(self, catalog: EvidenceCatalog, presenter: QuestionPresenter | None = None,
                 initial_labels_path=None, terminology=None):
        super().__init__(catalog, presenter, initial_labels_path)
        from .terminology import Terminology
        self.terminology = terminology or Terminology()

    def diagnosis(self, name: str) -> tuple:
        label = self.terminology.disease(name)
        return (label.label, label.is_fallback)


# ---------------- 계산 ----------------
def questions_used(state: PatientState, model_context: str) -> int | None:
    """엔진이 물어 답변된 질문 수 = n_additional − k (음수면 판정 불가 None).

    `medmap.api._questions_used` 와 같은 식이다(api 를 import 하지 않기 위해 복제, parity 테스트로 고정).
    """
    delta = state.n_additional - int(model_context[1:])
    return delta if delta >= 0 else None


def _item(state: PatientState, evidence_id: str, labels: LabelProvider, with_label: bool = False) -> dict:
    answer = state.answers[evidence_id]
    question_ko, question_original, fallback = labels.question(evidence_id)
    if answer.status is AnswerStatus.VALUE:
        pairs = [labels.value(evidence_id, code) for code in answer.values]
        answer_ko = ", ".join(label for label, _ in pairs)
        fallback = fallback or any(is_fb for _, is_fb in pairs)
    else:
        answer_ko = labels.status_label(answer.status)
    item = {
        "question_id": evidence_id,
        "status": answer.status.value,
        "values": list(answer.values),
        "question_ko": question_ko,
        "question_original": question_original,
        "answer_ko": answer_ko,
        "is_fallback": fallback,
    }
    if with_label:
        item["label_ko"] = labels.initial_label(evidence_id)
    return item


def _candidates(diagnoses, labels: LabelProvider) -> list:
    """top3 만. 입력: DiagnosisResult(.ranking) · [(name, prob)] · [{"name","probability"}]. 내림차순이어야 한다."""
    if hasattr(diagnoses, "ranking"):
        diagnoses = diagnoses.ranking
    pairs = []
    for entry in list(diagnoses or []):
        if isinstance(entry, dict):
            name, prob = entry.get("name"), entry.get("probability")
        else:
            try:
                name, prob = entry
            except (TypeError, ValueError):
                raise ValueError(f"MEDMAP_SUMMARY_INVALID_CANDIDATE:{entry!r}") from None
        if not isinstance(name, str) or isinstance(prob, bool) or not isinstance(prob, (int, float)) \
                or not 0.0 <= float(prob) <= 1.0:
            raise ValueError(f"MEDMAP_SUMMARY_INVALID_CANDIDATE:{name}")
        pairs.append((name, float(prob)))
    for (_, a), (_, b) in zip(pairs, pairs[1:]):
        if b > a:
            raise ValueError("MEDMAP_SUMMARY_CANDIDATES_NOT_SORTED")
    result = []
    for name, prob in pairs[:MAX_CANDIDATES]:
        display_name, fallback = labels.diagnosis(name)
        result.append({"name": name, "display_name": display_name, "is_fallback": fallback, "probability": prob})
    return result


def build_clinical_summary(state: PatientState, model_context: str, diagnoses, *, labels: LabelProvider) -> dict:
    """PatientState + 진단 후보(top3) → medmap-clinical-summary-v1 dict(키 순서 = SUMMARY_KEYS)."""
    buckets = {key: [] for key in _STATUS_KEY.values()}
    answered = []
    chief = None
    for evidence_id in state.asked:
        if evidence_id not in state.answers:          # 조용히 건너뛰지 않는다(추정·보정 금지)
            raise ValueError(f"MEDMAP_SUMMARY_ASKED_WITHOUT_ANSWER:{evidence_id}")
        if evidence_id == state.initial_evidence:
            chief = _item(state, evidence_id, labels, with_label=True)
            answered.append(_item(state, evidence_id, labels))
            continue
        item = _item(state, evidence_id, labels)
        answered.append(item)
        buckets[_STATUS_KEY[state.answers[evidence_id].status]].append({**item, "values": list(item["values"])})
    summary = {
        "schema_version": CLINICAL_SUMMARY_SCHEMA_VERSION,
        "chief_complaint": chief,
        "confirmed_positive": buckets["confirmed_positive"],
        "confirmed_negative": buckets["confirmed_negative"],
        "confirmed_values": buckets["confirmed_values"],
        "not_applicable": buckets["not_applicable"],
        "unknown": buckets["unknown"],
        "answered_questions": answered,
        "diagnosis_candidates": _candidates(diagnoses, labels),
        "questions_used": questions_used(state, model_context),
        "disclaimer": DISCLAIMER_KO,
    }
    assert tuple(summary) == SUMMARY_KEYS
    return summary


# ---------------- 어댑터 ----------------
def summary_from_session(session: dict, diagnoses, *, catalog: EvidenceCatalog, labels: LabelProvider) -> dict:
    """medmap-session-v1 dict(예: 새로고침 후 저장본) + top3 → summary. 세션 검증은 기존 deserialize_session."""
    snapshot = deserialize_session(session, catalog)
    return build_clinical_summary(snapshot.state, snapshot.model_context, diagnoses, labels=labels)


def summary_from_turn_payload(turn: dict, *, catalog: EvidenceCatalog, labels: LabelProvider) -> dict:
    """최종 medmap-turn-v1 payload → summary. turn 의 질문 수가 상태 계산과 다르면 거부한다."""
    summary = summary_from_session(turn["session"], turn.get("diagnoses") or [], catalog=catalog, labels=labels)
    declared = turn.get("questions_asked_in_session")
    if declared is not None and declared != summary["questions_used"]:
        raise ValueError(f"MEDMAP_SUMMARY_QUESTION_COUNT_MISMATCH:{declared}!={summary['questions_used']}")
    return summary
