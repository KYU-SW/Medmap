"""EXP-01(EXP-MAI-001) 공통 부품: 답 표현, 금지 입력 guard, 시뮬레이터, 탐색 루프.

답 표현은 STEP16B Semantics 그대로: 이진 ("POS",) / ("NEG",), 범주형 ("VALUE::x", ...) / ("NA",).
탐색기는 case 레코드를 받지 않는다. 시작 관측(initial_evidence, age, sex, wd)만 받고, 답은 observe() 로만 받는다.
semantics 객체 인터페이스(s16b_core.Semantics 와 같음): qids, parent, dtype, answer_space, safe,
reconstruct(qid, full_tokens), currently_eligible(qid, visible).
"""
from __future__ import annotations

from dataclasses import dataclass, field

FORBIDDEN_KEYS = frozenset({"PATHOLOGY", "pathology", "EVIDENCES", "evidences", "DIFFERENTIAL_DIAGNOSIS",
                            "differential_diagnosis", "severity", "full_tokens", "truth", "label"})
POS, NEG, NA = ("POS",), ("NEG",), ("NA",)


class Exp01Invalid(Exception):
    """manifest failure_criterion 의 INVALID 조건."""


def guard_inputs(kwargs: dict) -> None:
    bad = sorted(set(kwargs) & FORBIDDEN_KEYS)
    if bad:
        raise Exp01Invalid(f"EXP01_FORBIDDEN_INPUT:{','.join(bad)}")


def qnum(q: str) -> int:
    return int(q[2:])


def is_positive_type(ans: tuple) -> bool:
    """양성형 답 = 이진 POS 또는 범주형 VALUE."""
    return ans == POS or (len(ans) > 0 and all(a.startswith("VALUE::") for a in ans))


class CaseSimulator:
    """숨은 기록으로 답만 돌려준다. 탐색기는 이 객체를 보지 못한다(루프가 중계)."""

    def __init__(self, sem, full_tokens):
        self._sem = sem
        self._tokens = tuple(full_tokens)
        self.revealed = []

    def answer(self, q: str) -> tuple:
        ans = self._sem.reconstruct(q, self._tokens)
        self.revealed.append(q)
        return ans


class NoisySimulator(CaseSimulator):
    """응답 잡음 민감도(manifest ablations, 기술 통계 전용). 물은 이진 질문 답만 변경, 사례·질문별 sha256 으로 결정.
    mode='flip': POS↔NEG 를 확률 p 로 뒤집음, mode='uncertain': 확률 p 로 ("UNKNOWN",)(우도 미반영)."""

    def __init__(self, sem, full_tokens, mode: str, p: float, key: str):
        super().__init__(sem, full_tokens)
        self.mode, self.p, self.key = mode, p, key

    def answer(self, q: str) -> tuple:
        import hashlib
        ans = super().answer(q)
        if ans not in (POS, NEG):
            return ans
        u = int(hashlib.sha256(f"EXP01NOISE|{self.mode}|{self.p}|{self.key}|{q}".encode()).hexdigest()[:8], 16) / 2**32
        if u >= self.p:
            return ans
        if self.mode == "flip":
            return NEG if ans == POS else POS
        return UNKNOWN


UNKNOWN = ("UNKNOWN",)


@dataclass
class Trace:
    asked: list = field(default_factory=list)          # 질문 순서
    answers: dict = field(default_factory=dict)        # q -> 답
    stop_reason: str = ""


def run_case(searcher, sem, initial_evidence, age, sex, full_tokens, budget, wd=None, on_step=None, sim=None):
    """공통 탐색 루프. 예산·중복·eligibility 를 루프가 강제한다. on_step(searcher, n_asked) 는 시작·매 답 후 호출. 반환: (Trace, searcher)."""
    sim = sim or CaseSimulator(sem, full_tokens)
    searcher.reset(initial_evidence=initial_evidence, age=age, sex=sex, wd=wd)
    visible = {initial_evidence: POS}
    tr = Trace()
    if on_step:
        on_step(searcher, 0)
    while len(tr.asked) < budget:
        q = searcher.next_question()
        if q is None:
            tr.stop_reason = "NO_QUESTION"
            break
        if q in visible:
            raise Exp01Invalid(f"EXP01_DUPLICATE_QUESTION:{q}")
        if not sem.currently_eligible(q, visible):
            raise Exp01Invalid(f"EXP01_INELIGIBLE_QUESTION:{q}")
        ans = sim.answer(q)
        visible[q] = ans
        tr.asked.append(q)
        tr.answers[q] = ans
        searcher.observe(q, ans)
        if on_step:
            on_step(searcher, len(tr.asked))
    else:
        tr.stop_reason = "BUDGET"
    return tr, searcher
