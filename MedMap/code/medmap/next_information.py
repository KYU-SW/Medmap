"""NextInformationEngine: STEP16B 에서 검증된 내부 정보이득(INTERNAL_IG)으로 다음 질문 1개를 고른다.

IG(q) = H(posterior) − Σ_a P(a)·H(posterior|a),  P(a|d) 는 STEP16B_TRAIN Laplace α=1.0 추정,
log base 2, 동점은 evidence 번호 오름차순. 제품화를 이유로 수식을 바꾸지 않는다.
외부 질환 프로필은 점수에 섞지 않는다(설명 provider 인터페이스만 열어 둔다).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from . import config
from .diagnosis import DiagnosisEngine, DiagnosisResult
from .eligibility import QuestionEligibility
from .evidence import EvidenceCatalog
from .patient_state import Answer, PatientState

STOP_MAX_QUESTIONS = "MAX_QUESTIONS"
STOP_NO_ELIGIBLE_QUESTION = "NO_ELIGIBLE_QUESTION"


class AnswerLikelihoodTable:
    """질문별 P(answer | disease). STEP16B 산출물 `ig_table_step16b_train.npz` 를 그대로 읽는다."""

    def __init__(self, catalog: EvidenceCatalog, path=None):
        data = np.load(config.check_path(path or config.IG_TABLE_NPZ), allow_pickle=True)
        self.classes = [str(c) for c in data["__classes__"]]
        self.question_ids = [e for e in catalog.selectable_ids() if e in data]
        blocks = [np.asarray(data[e], dtype=np.float64) for e in self.question_ids]
        for e, block in zip(self.question_ids, blocks):
            if block.shape[1] != len(catalog.answer_space[e]):
                raise ValueError(f"MEDMAP_ANSWER_SPACE_MISMATCH:{e}")
        self.matrix = np.concatenate(blocks, axis=1)                       # (n_disease, n_answer_columns)
        self.group = np.concatenate([np.full(b.shape[1], i) for i, b in enumerate(blocks)])
        self.index = {e: i for i, e in enumerate(self.question_ids)}

    def information_gain(self, posterior: np.ndarray) -> np.ndarray:
        """질문별 IG 벡터(question_ids 순). 확률 0 인 답(impossible)은 기여 0."""
        posterior = np.asarray(posterior, dtype=np.float64)
        joint = posterior[:, None] * self.matrix
        p_answer = joint.sum(axis=0)
        safe = np.where(p_answer > 0, p_answer, 1.0)
        conditional = joint / safe
        logs = np.where(conditional > 0, np.log2(np.where(conditional > 0, conditional, 1.0)), 0.0)
        entropy_per_answer = -(conditional * logs).sum(axis=0)
        expected = np.bincount(self.group, weights=p_answer * entropy_per_answer, minlength=len(self.question_ids))
        p = posterior[posterior > 0]
        return float(-(p * np.log2(p)).sum()) - expected


@dataclass(frozen=True)
class QuestionProposal:
    evidence_id: str
    question_text: str
    answer_type: str
    possible_values: tuple
    value_labels: dict
    information_gain: float
    explanation: str | None = None
    presented: object | None = None      # QuestionPresenter 가 붙인 환자용 표현(선택 결과에는 영향 없음)

    def to_dict(self) -> dict:
        payload = {"question_id": self.evidence_id, "question_text": self.question_text,
                   "answer_type": self.answer_type, "answer_type_raw": self.answer_type,
                   "possible_values": list(self.possible_values), "information_gain": self.information_gain,
                   "explanation": self.explanation}
        if self.presented is not None:       # 표현 계층이 있으면 한국어 필드를 덧붙인다(기존 키 유지)
            presented = self.presented.to_dict()
            payload.update({"question_ko": presented["question_ko"], "question_original": presented["question_original"],
                            "answer_type": presented["answer_type"], "choices": presented["choices"],
                            "is_fallback": presented["is_fallback"]})
        return payload


@dataclass
class Turn:
    state: PatientState
    diagnoses: DiagnosisResult
    next_question: QuestionProposal | None
    stop_reason: str | None = None
    diagnoses_before: DiagnosisResult | None = None
    candidates: tuple = ()          # 디버깅용 상위 질문 (evidence_id, IG)
    model_context_match: bool = True
    questions_asked_in_session: int = 0

    def to_dict(self) -> dict:
        return {"diagnoses": [{"disease": d, "probability": p} for d, p in self.diagnoses.top3],
                "diagnoses_before": None if self.diagnoses_before is None else
                    [{"disease": d, "probability": p} for d, p in self.diagnoses_before.top3],
                "next_question": None if self.next_question is None else self.next_question.to_dict(),
                "stop_reason": self.stop_reason, "n_asked": self.state.n_asked,
                "model_context": self.diagnoses.model_context, "model_context_match": self.model_context_match}


class ExplanationProvider:
    """외부 질환 프로필 설명기 자리. 기본 구현은 설명 없음(점수에 영향 없음)."""

    def explain(self, evidence_id: str, diagnoses: DiagnosisResult) -> str | None:
        return None


class NextInformationEngine:
    def __init__(self, diagnosis_engine: DiagnosisEngine, catalog: EvidenceCatalog | None = None,
                 likelihoods: AnswerLikelihoodTable | None = None, max_questions: int = config.DEFAULT_MAX_QUESTIONS,
                 explanation_provider: ExplanationProvider | None = None, n_debug_candidates: int = 5,
                 presenter=None):
        self.catalog = catalog or diagnosis_engine.catalog
        self.diagnosis = diagnosis_engine
        self.eligibility = QuestionEligibility(self.catalog)
        self.likelihoods = likelihoods or AnswerLikelihoodTable(self.catalog)
        if self.likelihoods.classes != list(self.diagnosis.classes):
            raise ValueError("MEDMAP_CLASS_ORDER_MISMATCH")
        self.max_questions = max_questions
        self.explanations = explanation_provider
        self.n_debug_candidates = n_debug_candidates
        self.presenter = presenter        # 표현 전용. 질문 선택·IG·pool 에 관여하지 않는다.

    # ---- 공개 API ----
    def start(self, state: PatientState) -> Turn:
        diagnoses = self.diagnosis.diagnose(state)
        return self._turn(state, diagnoses, questions_asked_in_session=0)

    def answer(self, turn: Turn, question_id: str, answer: Answer) -> Turn:
        if turn.next_question is None or question_id != turn.next_question.evidence_id:
            raise ValueError(f"MEDMAP_UNEXPECTED_ANSWER:{question_id}")
        self.catalog.validate_answer(question_id, answer)
        new_state = turn.state.with_answer(question_id, answer)
        diagnoses_after = self.diagnosis.diagnose(new_state)
        asked_in_session = turn.questions_asked_in_session + 1
        next_turn = self._turn(new_state, diagnoses_after, questions_asked_in_session=asked_in_session)
        next_turn.diagnoses_before = turn.diagnoses
        return next_turn

    # ---- 내부 ----
    def _turn(self, state: PatientState, diagnoses: DiagnosisResult, questions_asked_in_session: int) -> Turn:
        match = state.n_additional == self.diagnosis.expected_additional_questions() + questions_asked_in_session
        if questions_asked_in_session >= self.max_questions:
            turn = Turn(state, diagnoses, None, STOP_MAX_QUESTIONS, model_context_match=match,
                        questions_asked_in_session=questions_asked_in_session)
        else:
            eligible = self.eligibility.eligible_questions(state)
            if not eligible:
                turn = Turn(state, diagnoses, None, STOP_NO_ELIGIBLE_QUESTION, model_context_match=match,
                            questions_asked_in_session=questions_asked_in_session)
            else:
                ranked = self.rank_questions(diagnoses, eligible)
                best_id, best_ig = ranked[0]
                question = self.catalog.question(best_id)
                explanation = self.explanations.explain(best_id, diagnoses) if self.explanations else None
                proposal = QuestionProposal(best_id, question.text, question.answer_type, question.possible_values,
                                            question.value_labels, best_ig, explanation)
                if self.presenter is not None:
                    proposal = replace(proposal, presented=self.presenter.present(best_id, best_ig, explanation))
                turn = Turn(state, diagnoses, proposal, None, candidates=tuple(ranked[:self.n_debug_candidates]),
                            model_context_match=match, questions_asked_in_session=questions_asked_in_session)
        return turn

    def rank_questions(self, diagnoses: DiagnosisResult, eligible: list[str]) -> list[tuple]:
        """IG 내림차순, 동점은 evidence 번호 오름차순(STEP16B tie-break 과 동일)."""
        posterior = np.array([diagnoses.probabilities[c] for c in self.diagnosis.classes], dtype=np.float64)
        gains = self.likelihoods.information_gain(posterior)
        scored = [(e, float(gains[self.likelihoods.index[e]])) for e in eligible if e in self.likelihoods.index]
        scored.sort(key=lambda item: (-round(item[1], 12), int(item[0][2:])))
        return scored
