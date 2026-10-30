"""EXP-01 탐색기 6종(manifest rev5 baseline·proposed_method 그대로).

공통 인터페이스: reset(initial_evidence, age, sex, wd=None) / next_question() / observe(q, ans) / scores() / stats().
- scores(): 질환별 점수(클래스 순서, 클수록 앞). 순위는 metrics 의 비관적 동점 처리로 만든다.
- 질환을 순위에서 삭제하는 연산은 없다. PB 의 τ 는 질문 점수 계산 후보만 줄인다(재활성 자동).
이 모듈은 질환 지식표·중증도 자료를 읽지 않는다(정적 검사 대상).
"""
from __future__ import annotations

import math

import numpy as np

from core import NA, POS, guard_inputs, is_positive_type, qnum

D8 = 8


# ------------------------------------------------------------------ 그래프 계열
class GraphSearcher:
    """variant ∈ {C, PA, PB_REL, PB, PC}. 공통: 같은 우도표·같은 이진 질문 풀·AGE·SEX 미사용."""

    VARIANTS = ("C", "PA", "PB_REL", "PB", "PC")

    def __init__(self, lik, sem, variant: str, budget: int, tau: float | None = None):
        if variant not in self.VARIANTS:
            raise ValueError(variant)
        if variant in ("PB", "PC") and tau is not None and not (0 < tau < 1):
            raise ValueError("EXP01_BAD_TAU")
        self.lik, self.sem, self.variant, self.budget, self.tau = lik, sem, variant, budget, tau
        self.use_negative = variant != "C"
        self.use_relation = variant in ("PB_REL", "PB", "PC")
        self.use_tau = variant in ("PB", "PC") and tau is not None     # PC 에서 TAU_FAIL 이면 tau=None

    # ---- 상태 ----
    def reset(self, initial_evidence, age=None, sex=None, wd=None, **kwargs):
        guard_inputs(kwargs)
        self.logpost = np.log(self.lik.prior).copy()
        self.observed = {}               # q -> ans (observe 로 받은 것 전부)
        self.used = set()                # 우도에 실제로 더한 (q, ans)
        self.wd = wd
        if self.variant == "PC" and wd is None:
            raise ValueError("EXP01_PC_NEEDS_WD")
        self.n_asked = 0
        self.counter = 0
        self.reactivations = 0
        self.prune_steps = 0
        self.cand_steps = 0             # 가지치기 발동률 분모(후보 계산이 일어난 단계만; 독립 감사 MINOR)
        self.steps = 0
        self._prev_act = None
        self._absorb(initial_evidence, POS)
        return self

    def _absorb(self, q, ans):
        self.observed[q] = ans
        self.counter += self.lik.n                                     # 사후 갱신 (질환, 답) 수
        if ans == NA:
            return
        if is_positive_type(ans) or (self.use_negative and ans == ("NEG",)):
            self.logpost = self.logpost + self.lik.loglik(q, ans)
            self.used.add((q, ans))

    def observe(self, q, ans):
        self.n_asked += 1
        self._absorb(q, ans)

    # ---- 후보·질문 ----
    def _order(self):
        return sorted(range(self.lik.n), key=lambda i: (-self.logpost[i], i))

    def active(self):
        if not self.use_tau:
            return set(range(self.lik.n))
        m = self.logpost.max()
        thr = math.log(self.tau)
        return {i for i in range(self.lik.n) if self.logpost[i] - m >= thr}

    def _eligible(self):
        return [q for q in self.lik.binary
                if q not in self.observed and self.sem.safe.get(q, True) and self.sem.currently_eligible(q, self.observed)]

    def _track_act(self):
        """활성 집합 갱신과 재활성 계산(WD 단계에서도 호출 — 인접 단계 비교 유지)."""
        act = self.active()
        if self._prev_act is not None:
            self.reactivations += len(act - self._prev_act)
        self._prev_act = act
        return act

    def _cand(self):
        top = self._order()[:D8]
        if not self.use_tau:
            return top
        act = self._track_act()
        cand = [d for d in top if d in act]
        self.cand_steps += 1
        if len(cand) < len(top):
            self.prune_steps += 1
        return cand

    def next_question(self):
        if self.n_asked >= self.budget:
            return None
        elig = self._eligible()
        if not elig:
            return None
        self.steps += 1
        if self.variant == "PC" and self.n_asked < min(2, self.budget - 1):
            wd_q = self._wd_question(elig)
            if wd_q is not None:
                self.counter += len(elig) * 1
                if self.use_tau:
                    self._track_act()
                return wd_q
        cand = self._cand()
        s = 2 if self.use_relation else 1
        self.counter += len(cand) * len(elig) * s
        def c_score(q):
            return float(sum(self.lik.p_pos[q][d] for d in cand))
        if not self.use_relation:
            return min(elig, key=lambda q: (-round(c_score(q), 12), qnum(q)))
        def rel(q):
            sg = self.lik.suggests[q]
            n_s = sum(1 for d in cand if sg[d])
            return min(n_s, len(cand) - n_s)
        return min(elig, key=lambda q: (-rel(q), -round(c_score(q), 12), qnum(q)))

    def _wd_question(self, elig):
        w = self.lik.classes.index(self.wd)
        opts = [q for q in elig if self.lik.suggests[q][w]]
        if not opts:
            return None
        return min(opts, key=lambda q: (-round(float(self.lik.p_pos[q][w]), 12), qnum(q)))

    # ---- 출력 ----
    def scores(self):
        return self.logpost.copy()

    def posterior(self):
        z = np.exp(self.logpost - self.logpost.max())
        return z / z.sum()

    def stats(self):
        return {"counter": self.counter, "reactivations": self.reactivations, "prune_steps": self.prune_steps,
                "cand_steps": self.cand_steps, "steps": self.steps, "used": frozenset(self.used), "observed": dict(self.observed)}


def expected_used(observed: dict, use_negative: bool) -> set:
    """근거 집합 일치 assert 의 기준: observe 로 받은 답 중 우도에 들어가야 하는 것."""
    return {(q, a) for q, a in observed.items()
            if a != NA and (is_positive_type(a) or (use_negative and a == ("NEG",)))}


# ------------------------------------------------------------------ Baseline B
def build_b_features(sem, excluded=("E_134", "E_152")):
    """부모 없는 이진 근거 + AGE 10구간 + SEX. 반환: (feature 이름 목록, 근거 feature 인덱스→qid)."""
    ev = [q for q in sem.qids if sem.dtype[q] == "B" and q not in sem.parent and q not in excluded]
    names = [f"EV::{q}" for q in ev] + [f"AGE_{a}" for a in range(10)] + ["SEX_M", "SEX_F"]
    return names, {i: q for i, q in enumerate(ev)}


def encode_b(names, positives: set, age, sex) -> np.ndarray:
    """학습 인코딩: EVIDENCES 에 기재 1, 미기재 0(시뮬레이터 NEG 규약과 같음)."""
    x = np.zeros(len(names))
    for i, nm in enumerate(names):
        if nm.startswith("EV::") and nm[4:] in positives:
            x[i] = 1
    x[names.index(f"AGE_{min(int(age) // 10, 9)}")] = 1
    x[names.index(f"SEX_{sex}")] = 1
    return x


def fit_baseline_b(X, y, classes, seed, max_depth=10, min_samples_leaf=50):
    from sklearn.tree import DecisionTreeClassifier
    t = DecisionTreeClassifier(criterion="entropy", max_depth=max_depth, min_samples_leaf=min_samples_leaf,
                               random_state=seed)
    t.fit(X, y)
    if list(t.classes_) != list(classes):
        raise ValueError("EXP01_B_CLASS_ORDER")
    return t


class TreeSearcher:
    """Baseline B: 루트부터 내려가며 근거 노드는 질문(예산 1), AGE·SEX 노드는 무료. 깊이는 확률로 쓰지 않는다."""

    def __init__(self, tree, names, ev_index, n_classes, budget):
        self.t, self.names, self.ev_index, self.nc, self.budget = tree.tree_, names, ev_index, n_classes, budget

    def reset(self, initial_evidence, age=None, sex=None, wd=None, **kwargs):
        guard_inputs(kwargs)
        self.known = {initial_evidence: 1}
        self.age, self.sex = age, sex
        self.node = 0
        self.n_asked = 0
        self.pending = None
        self.counter = 0
        self.observed = {initial_evidence: POS}
        self._descend()
        return self

    def _feat_value(self, f):
        nm = self.names[f]
        if nm.startswith("AGE_"):
            return 1.0 if int(nm[4:]) == min(int(self.age) // 10, 9) else 0.0
        if nm.startswith("SEX_"):
            return 1.0 if nm[4:] == self.sex else 0.0
        q = self.ev_index[f]
        return None if q not in self.known else float(self.known[q])

    def _descend(self):
        while self.t.children_left[self.node] != -1:
            f = self.t.feature[self.node]
            v = self._feat_value(f)
            self.counter += 1
            if v is None:
                self.pending = self.ev_index[f]
                return
            self.node = self.t.children_left[self.node] if v <= self.t.threshold[self.node] else self.t.children_right[self.node]
        self.pending = None

    def next_question(self):
        if self.n_asked >= self.budget or self.pending is None:
            return None
        return self.pending

    def observe(self, q, ans):
        self.n_asked += 1
        self.observed[q] = ans
        self.known[q] = 1 if ans == POS else 0
        self.pending = None
        self._descend()

    def scores(self):
        return np.asarray(self.t.value[self.node][0], dtype=np.float64)

    def posterior(self):
        v = self.scores()
        return v / v.sum()

    def stats(self):
        used = {(q, POS if v == 1 else ("NEG",)) for q, v in self.known.items()}
        return {"counter": self.counter, "used": frozenset(used), "observed": dict(self.observed),
                "node": int(self.node)}


# ------------------------------------------------------------------ Baseline A
class BaselineASearcher:
    """STEP16B MODEL_k + INTERNAL_IG. ~/medmap 의 medmap 패키지를 읽기 전용으로 쓴다(engine 주입 가능 — 테스트용)."""

    K_FOR_BUDGET = {3: "k3", 5: "k5", 10: "k10"}

    def __init__(self, engine_factory, budget):
        """engine_factory(model_context, max_questions) -> NextInformationEngine 호환 객체(start/answer)."""
        self.factory, self.budget = engine_factory, budget
        self.ctx = self.K_FOR_BUDGET[budget]

    def reset(self, initial_evidence, age=None, sex=None, wd=None, **kwargs):
        guard_inputs(kwargs)
        from medmap.patient_state import PatientState
        self.engine = self.factory(self.ctx, self.budget)
        self.turn = self.engine.start(PatientState.new(age=int(age), sex=sex, initial_evidence=initial_evidence))
        self.observed = {initial_evidence: POS}
        self.n_asked = 0
        return self

    def next_question(self):
        if self.n_asked >= self.budget or self.turn.next_question is None:
            return None
        return self.turn.next_question.evidence_id

    def observe(self, q, ans):
        from medmap import patient_state as ps
        if ans == POS:
            a = ps.positive()
        elif ans == ("NEG",):
            a = ps.negative()
        elif ans == NA:
            a = ps.not_applicable()
        else:
            a = ps.value(*[x.split("::", 1)[1] for x in ans])
        self.turn = self.engine.answer(self.turn, q, a)
        self.observed[q] = ans
        self.n_asked += 1

    def scores(self):
        probs = self.turn.diagnoses.probabilities
        return np.array([probs[c] for c in self.engine.diagnosis.classes], dtype=np.float64)

    def posterior(self):
        return self.scores()

    def stats(self):
        used = {(q, tuple(toks)) for q, toks in self.turn.state.feature_tokens()}   # 모델 인코딩에 들어간 토큰
        return {"counter": None, "used": frozenset(used), "observed": dict(self.observed)}
