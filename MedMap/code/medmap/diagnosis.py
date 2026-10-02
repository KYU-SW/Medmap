"""DiagnosisEngine: STEP16B 에서 학습된 MODEL_k 를 읽어 예측만 수행한다(런타임 fit/retrain 금지)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass

import numpy as np

from . import config
from .evidence import EvidenceCatalog


@dataclass(frozen=True)
class DiagnosisResult:
    probabilities: dict        # disease → prob
    ranking: tuple             # (disease, prob) 내림차순 전체
    model_context: str

    @property
    def top1(self): return self.ranking[0]
    @property
    def top2(self): return self.ranking[1]
    @property
    def top3(self): return self.ranking[:3]


class DiagnosisEngine:
    """model_context 는 호출자가 명시한다. STEP16B 연구에 없는 자동 k 전환 규칙은 두지 않는다."""

    def __init__(self, catalog: EvidenceCatalog, model_context: str = "k3", model_paths=None):
        if model_context not in config.MODEL_CONTEXTS:
            raise ValueError(f"MEDMAP_UNKNOWN_MODEL_CONTEXT:{model_context}")
        self.catalog = catalog
        self.model_context = model_context
        path = (model_paths or config.MODEL_PATHS)[model_context]
        with open(config.check_path(path), "rb") as fh:
            self.model = pickle.load(fh)
        self.classes = list(self.model.classes_)
        n_features = getattr(self.model, "n_features_in_", len(catalog.columns))
        if n_features != len(catalog.columns):
            raise ValueError(f"MEDMAP_FEATURE_LAYOUT_MISMATCH:{n_features}!={len(catalog.columns)}")

    def expected_additional_questions(self) -> int:
        """이 모델이 학습된 partial view 의 추가 질문 수(k)."""
        return int(self.model_context[1:])

    def posterior(self, state) -> np.ndarray:
        return self.model.predict_proba(self.catalog.encode([state]))[0]

    def diagnose(self, state) -> DiagnosisResult:
        probs = self.posterior(state)
        order = np.argsort(-probs)
        ranking = tuple((self.classes[i], float(probs[i])) for i in order)
        return DiagnosisResult({c: float(p) for c, p in zip(self.classes, probs)}, ranking, self.model_context)
