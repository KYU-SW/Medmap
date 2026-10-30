"""가상 세계(단위 테스트·SYNTHETIC 실행 전용). 실데이터를 쓰지 않는다.

s16b_core.Semantics 와 같은 인터페이스의 SynthSemantics + 생성 규칙을 아는 ig 표 + 가상 환자 생성기.
"""
from __future__ import annotations

import collections

import numpy as np

from core import POS, NEG, NA


class SynthSemantics:
    def __init__(self, n_binary=12, child_of=None, categorical=None, excluded=()):
        """child_of: {자식 q: 부모 q}(이진 자식), categorical: {q: (부모 or None, [값...])}."""
        self.qids = [f"E_{i}" for i in range(n_binary)]
        self.dtype = {q: "B" for q in self.qids}
        self.parent = dict(child_of or {})
        self.values = {}
        for q, (par, vals) in (categorical or {}).items():
            self.qids.append(q)
            self.dtype[q] = "C"
            self.values[q] = list(vals)
            if par:
                self.parent[q] = par
        self.qids.sort(key=lambda e: int(e[2:]))
        self.answer_space = {q: (["POS", "NEG"] if self.dtype[q] == "B" else [f"VALUE::{v}" for v in self.values[q]] + ["NA"])
                             for q in self.qids}
        self.safe = {q: q not in set(excluded) for q in self.qids}

    def reconstruct(self, qid, full_tokens):
        base = {t.partition("_@_")[0] for t in full_tokens}
        if self.dtype[qid] == "B":
            return POS if qid in base else NEG
        vals = tuple(sorted(t.partition("_@_")[2] for t in full_tokens if t.partition("_@_")[0] == qid))
        if vals:
            return tuple(f"VALUE::{v}" for v in vals)
        par = self.parent.get(qid)
        if par and par not in base:
            return NA
        raise RuntimeError(f"UNSAFE:{qid}")

    def currently_eligible(self, qid, visible):
        if qid in visible or not self.safe[qid]:
            return False
        par = self.parent.get(qid)
        return visible.get(par) == POS if par else True


def make_world(n_classes=6, n_binary=12, seed=0, child_of=None):
    """질환별 근거 확률 행렬 P[d, q] 와 그로부터 만든 ig 표(정확한 생성 확률)."""
    rng = np.random.default_rng(seed)
    sem = SynthSemantics(n_binary=n_binary, child_of=child_of)
    P = rng.uniform(0.02, 0.4, size=(n_classes, n_binary))
    for d in range(n_classes):
        P[d, rng.choice(n_binary, 3, replace=False)] = rng.uniform(0.7, 0.95, 3)
    classes = [f"D{d}" for d in range(n_classes)]
    prior = np.full(n_classes, 1.0 / n_classes)
    table = {}
    for j, q in enumerate(sem.qids):
        table[q] = np.stack([P[:, j], 1 - P[:, j]], 1)
    return sem, classes, prior, table, P


def sample_cases(sem, classes, P, n, seed=1, child_of=None):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        d = int(rng.integers(len(classes)))
        pos = [q for j, q in enumerate(sem.qids) if rng.random() < P[d, j]]
        if child_of:
            pos = [q for q in pos if q not in child_of or child_of[q] in pos]
        top = [q for q in pos if q not in sem.parent]
        if not top:
            top = [sem.qids[int(np.argmax(P[d]))]]
            pos = sorted(set(pos) | set(top), key=lambda e: int(e[2:]))
        init = top[int(rng.integers(len(top)))]
        out.append({"row_index": i, "age": int(rng.integers(1, 90)), "sex": "M" if rng.random() < .5 else "F",
                    "initial": init, "tokens": tuple(pos), "truth": classes[d]})
    return out


def class_counts(cases, classes):
    c = collections.Counter(x["truth"] for x in cases)
    return np.array([c.get(k, 0) for k in classes], dtype=float)
