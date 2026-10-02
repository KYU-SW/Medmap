"""Evidence 카탈로그: 질문 정의·부모 관계·답변 공간·인코딩 열 순서.

답변 공간과 열 순서는 STEP16B 학습 시점(`s16b_core.Encoder`)과 동일해야 하며,
DiagnosisEngine 이 모델 n_features 와 대조해 검증한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from . import config


@dataclass(frozen=True)
class Question:
    evidence_id: str
    text: str
    answer_type: str          # "BINARY" | "CATEGORICAL" | "MULTI"
    possible_values: tuple    # value code 목록 (binary 는 빈 튜플)
    value_labels: dict        # value code → 영문 라벨
    parent_id: str | None


_TYPE = {"B": "BINARY", "C": "CATEGORICAL", "M": "MULTI"}


class EvidenceCatalog:
    def __init__(self, path=None, excluded=config.EXCLUDED_QUESTIONS):
        path = config.check_path(path or config.EVIDENCES_JSON)
        raw = json.loads(path.read_text())
        self.excluded = frozenset(excluded)
        self.ids = sorted(raw, key=lambda e: int(e[2:]))
        self.parent = {e: v["code_question"] for e, v in raw.items() if v["code_question"] != e and v["code_question"] in raw}
        self.children: dict[str, list[str]] = {}
        for child, par in self.parent.items():
            if child not in self.excluded:
                self.children.setdefault(par, []).append(child)
        self.dtype = {e: v["data_type"] for e, v in raw.items()}
        self.questions = {
            e: Question(e, v["question_en"], _TYPE[v["data_type"]], tuple(str(x) for x in v["possible-values"]),
                        {k: m.get("en", "") for k, m in (v.get("value_meaning") or {}).items()}, self.parent.get(e))
            for e, v in raw.items()
        }
        self.answer_space = {
            e: (["POS", "NEG"] if self.dtype[e] == "B" else [f"VALUE::{v}" for v in self.questions[e].possible_values] + ["NA"])
            for e in self.ids
        }
        self.columns = [f"Q::{e}::{a}" for e in self.ids for a in self.answer_space[e]] + [f"AGE_{d}" for d in range(10)] + ["SEX_M", "SEX_F"]
        self._col_index = {c: i for i, c in enumerate(self.columns)}

    # ---- 질문 조회 ----
    def question(self, evidence_id: str) -> Question:
        return self.questions[evidence_id]

    def is_excluded(self, evidence_id: str) -> bool:
        return evidence_id in self.excluded

    def selectable_ids(self) -> list[str]:
        return [e for e in self.ids if e not in self.excluded]

    def validate_answer(self, evidence_id: str, answer) -> None:
        """제품 입력 검증: 질문 유형과 맞지 않는 답변을 인코딩 단계까지 끌고 가지 않는다."""
        from .patient_state import AnswerStatus

        question = self.questions[evidence_id]
        if answer.status is AnswerStatus.UNKNOWN:
            return
        if question.answer_type == "BINARY":
            if answer.status not in (AnswerStatus.POSITIVE, AnswerStatus.NEGATIVE):
                raise ValueError(f"MEDMAP_INVALID_ANSWER:{evidence_id}:expected POSITIVE/NEGATIVE, got {answer.status.value}")
            return
        if answer.status is AnswerStatus.NOT_APPLICABLE:
            return
        if answer.status is not AnswerStatus.VALUE:
            raise ValueError(f"MEDMAP_INVALID_ANSWER:{evidence_id}:expected VALUE, got {answer.status.value}")
        unknown_values = [v for v in answer.values if v not in question.possible_values]
        if unknown_values:
            raise ValueError(f"MEDMAP_INVALID_ANSWER_VALUE:{evidence_id}:{','.join(unknown_values)}")

    # ---- 인코딩 ----
    def encode(self, states) -> sp.csr_matrix:
        """PatientState 목록 → 모델 입력 행렬. UNASKED/UNKNOWN 은 어떤 열도 켜지 않는다."""
        rows, cols = [], []
        for i, st in enumerate(states):
            for evidence_id, tokens in st.feature_tokens():
                for token in tokens:
                    j = self._col_index.get(f"Q::{evidence_id}::{token}")
                    if j is None:
                        raise KeyError(f"MEDMAP_UNKNOWN_ENCODING:{evidence_id}:{token}")
                    rows.append(i); cols.append(j)
            rows.append(i); cols.append(self._col_index[f"AGE_{min(int(st.age) // 10, 9)}"])
            rows.append(i); cols.append(self._col_index[f"SEX_{st.sex}"])
        return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(states), len(self.columns)))
