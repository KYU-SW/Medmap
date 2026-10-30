"""M1(독립 감사 2026-10-27): Baseline A 실제 평가 경로의 독립 재계산.

BaselineASearcher 는 medmap 제품 엔진(EvidenceCatalog.encode → DiagnosisEngine → NextInformationEngine)을 쓴다.
이 모듈은 같은 pkl·ig 표를 STEP16B 연구 코드 경로(s16b_core.Encoder → model.predict_proba, s16b_core.pack_ig/ig_all,
Semantics.currently_eligible)로 따로 계산해 매 단계 대조한다.
  (1) 사후확률: 관측(visible)만으로 다시 인코딩 → predict_proba, 엔진 사후확률과 |차| ≤ 1e-9
  (2) 다음 질문: 독립 IG argmax(동점 = 근거 번호 오름차순, IG 는 12자리 반올림 — STEP16B 규칙) == 엔진이 고른 질문
  (3) 답 변환: 엔진 상태의 (질문, 토큰) == 시뮬레이터가 준 답(초기 근거 포함)
불일치 = Exp01Invalid(INVALID).
"""
from __future__ import annotations

import numpy as np

from core import Exp01Invalid

K_FOR_BUDGET = {3: 3, 5: 5, 10: 10}


class AReference:
    def __init__(self, c, sem, models: dict, ig_table: dict, classes):
        self.c, self.sem, self.models = c, sem, models
        self.enc = c.Encoder(sem)
        self.qs, self.qidx, self.M, self.grp = c.pack_ig(sem, ig_table)
        self.classes = list(classes)
        self.max_abs_diff = 0.0                      # 실행 중 사후확률 최대 |차| 기록(설계 gate5 MINOR)
        for k, m in models.items():
            if list(m.classes_) != self.classes:
                raise Exp01Invalid(f"EXP01_AREF_CLASS_ORDER:k{k}")

    def posterior(self, k, visible: dict, age, sex) -> np.ndarray:
        return self.models[k].predict_proba(self.enc.transform([dict(visible)], [age], [sex]))[0]

    def next_question(self, post, visible: dict):
        gains = self.c.ig_all(np.asarray(post, dtype=np.float64), self.M, self.grp, len(self.qs))
        elig = [q for q in self.qs if self.sem.currently_eligible(q, visible)]
        if not elig:
            return None
        return min(elig, key=lambda q: (-round(float(gains[self.qidx[q]]), 12), int(q[2:])))

    def check_step(self, searcher, age, sex, tol=1e-9) -> None:
        visible = dict(searcher.observed)
        k = K_FOR_BUDGET[searcher.budget]
        ref = self.posterior(k, visible, age, sex)
        got = searcher.scores()
        self.max_abs_diff = max(self.max_abs_diff, float(np.abs(ref - got).max()))
        if not np.allclose(ref, got, atol=tol, rtol=0):
            raise Exp01Invalid(f"EXP01_AREF_POSTERIOR_MISMATCH:max={float(np.abs(ref - got).max()):.3g}")
        eng = {(q, tuple(t)) for q, t in searcher.turn.state.feature_tokens()}
        if eng != {(q, a) for q, a in visible.items()}:
            raise Exp01Invalid("EXP01_AREF_ANSWER_CONVERSION_MISMATCH")
        if searcher.n_asked < searcher.budget:
            nq = searcher.turn.next_question.evidence_id if searcher.turn.next_question is not None else None
            if nq != self.next_question(ref, visible):
                raise Exp01Invalid(f"EXP01_AREF_QUESTION_MISMATCH:{nq}")
