"""기존 EXP-MAI-006 모델 D(EXP-MAI-008 에서 겹별 저장)의 읽기 전용 추론 어댑터.

- 사전 고정: 겹 0 모델 하나만 사용(다섯 겹 결합·출력 비교 선택 없음). 겹 0 은 성능을 보고 고른 것이 아니라 번호 순 첫 겹.
- 신뢰: 자체 생성 joblib 파일이며, 불러오기 전에 EXP-MAI-008 실행 기록의 sha256 과 대조한다(불일치면 불러오지 않음 → MODEL_UNAVAILABLE).
- 입력: (진단 후보 문장, 근거 문장) 한 쌍 → 출력: −2..+2 중 하나와 다섯 점수 확률(전문가 점수 예측 연구 모델, 임상 판단 아님).
- 모델·변환기는 수정하지 않는다(predict_proba 호출만).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

SEALED_RUN = Path(os.environ.get("MEDMAP_D_MODEL_RUN_DIR", str(Path.home() / "medmap_er_reason_ordinal_sealed" / "s1_20261113_01")))   # 봉인 위치(저장소 밖)
FOLD = 0
PINNED_SHA256 = {0: "0f6baf0aa36bc7f646c650007079f65e93a2716ec4abb536e53253371ad39882"}   # EXP-MAI-008 s1_unmasked.json reload 기록과 동일
SCORES = (-2, -1, 0, 1, 2)
ORD_SRC = Path(__file__).resolve().parents[2] / "medmap_er_reason_ordinal" / "src"     # joblib 안 CumulativeBinaryOrdinal 클래스 해석용


class ModelUnavailable(RuntimeError):
    pass


class DModel:
    """불러오기 실패는 예외로 숨기지 않고 status/error 로 노출."""

    def __init__(self, path: Path | None = None, fold: int = FOLD, expected_sha256: str | None = None):
        self.fold = fold
        self.path = Path(path) if path else SEALED_RUN / "models" / f"fold{fold}.joblib"
        self.expected = expected_sha256 if expected_sha256 is not None else PINNED_SHA256.get(fold)
        self.pipe, self.status, self.error, self.sha256 = None, "NOT_LOADED", None, None

    def load(self) -> "DModel":
        try:
            if not self.path.exists():
                raise ModelUnavailable(f"파일 없음: {self.path.name}")
            h = hashlib.sha256(self.path.read_bytes()).hexdigest()
            self.sha256 = h
            if not self.expected:
                raise ModelUnavailable("고정된 기대 sha256 없음 — 불러오지 않음")
            if h != self.expected:
                raise ModelUnavailable("sha256 불일치 — 신뢰할 수 없는 파일, 불러오지 않음")
            if str(ORD_SRC) not in sys.path:
                sys.path.insert(0, str(ORD_SRC))
            import joblib
            obj = joblib.load(self.path)
            pipe = obj["base"]
            if list(pipe.classes_) != list(SCORES):
                raise ModelUnavailable(f"점수 클래스 순서 불일치: {list(pipe.classes_)}")
            if [t[0] for t in pipe.named_steps["feat"].transformers] != ["candidate", "evidence"]:
                raise ModelUnavailable("입력 열 순서 불일치")
            self.pipe, self.status = pipe, "LOADED"
        except Exception as ex:                                   # noqa: BLE001 — 실패 원인을 상태로 노출
            self.pipe, self.status, self.error = None, "MODEL_UNAVAILABLE", f"{type(ex).__name__}: {ex}"[:300]
        return self

    @property
    def model_id(self) -> str:
        return f"EXP-MAI-006 D (EXP-MAI-008 재현 저장본) fold{self.fold} sha256:{(self.sha256 or '')[:12]}"

    def predict(self, candidate: str, evidence: str) -> dict:
        if self.pipe is None:
            raise ModelUnavailable(self.error or "모델이 불러와지지 않음")
        import pandas as pd
        X = pd.DataFrame({"candidate": [candidate], "evidence": [evidence]})
        p = self.pipe.predict_proba(X)[0]
        i = int(p.argmax())                                       # 동점이면 더 음수 점수(EXP-MAI-008 과 같은 규칙)
        return {"score": SCORES[i], "probs": {str(s): round(float(v), 4) for s, v in zip(SCORES, p)}}
