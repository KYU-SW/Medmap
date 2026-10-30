"""그래프 우도: STEP16B ig_table(TRAIN16, Laplace α=1)의 P(a|q,d) 를 그대로 쓴다(재추정 금지).

이 모듈은 질환 지식표·중증도 자료를 읽지 않는다(정적 검사 대상).
관계 유형(이진 근거만): SUGGESTS(q,d) ⇔ P(POS|q,d) > P(POS|q) = Σ_d prior(d)·P(POS|q,d).
"""
from __future__ import annotations

import numpy as np


class GraphLikelihood:
    def __init__(self, table: dict, answer_space: dict, classes, prior):
        """table: q -> (n_classes, |answer_space[q]|) 배열, prior: TRAIN16 질환 빈도(합 1)."""
        self.classes = list(classes)
        self.n = len(self.classes)
        self.prior = np.asarray(prior, dtype=np.float64)
        if self.prior.shape != (self.n,) or not np.isclose(self.prior.sum(), 1.0) or (self.prior <= 0).any():
            raise ValueError("EXP01_BAD_PRIOR")
        self.table, self.col = {}, {}
        for q, arr in table.items():
            a = np.asarray(arr, dtype=np.float64)
            if a.shape != (self.n, len(answer_space[q])):
                raise ValueError(f"EXP01_TABLE_SHAPE:{q}")
            self.table[q] = a
            self.col[q] = {ans: i for i, ans in enumerate(answer_space[q])}
        self.binary = sorted((q for q in self.table if list(answer_space[q]) == ["POS", "NEG"]), key=lambda q: int(q[2:]))
        self.p_pos = {q: self.table[q][:, self.col[q]["POS"]] for q in self.binary}
        self.marg_pos = {q: float(self.prior @ self.p_pos[q]) for q in self.binary}
        self.suggests = {q: self.p_pos[q] > self.marg_pos[q] for q in self.binary}

    @classmethod
    def from_npz(cls, path, answer_space: dict, prior):
        z = np.load(path, allow_pickle=True)
        classes = [str(c) for c in z["__classes__"]]
        table = {k: z[k] for k in z.files if k != "__classes__"}
        return cls(table, answer_space, classes, prior)

    def loglik(self, q: str, ans: tuple) -> np.ndarray:
        """답 토큰마다 log P(a|q,d) 합(다중값은 값마다 합산 — manifest baseline)."""
        out = np.zeros(self.n)
        for a in ans:
            out += np.log(self.table[q][:, self.col[q][a]])
        return out

    def relation_counts(self) -> dict:
        s = sum(int(v.sum()) for v in self.suggests.values())
        return {"SUGGESTS": s, "ARGUES_AGAINST": len(self.binary) * self.n - s}
