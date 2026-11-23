"""MedMap v5-2A.2: 검사 사건별 판독 이력(EVENT_VERSION_HISTORY) · 환자 전체 as_of 이력(PATIENT_AS_OF_HISTORY) ·
정정만 바꾼 가상 비교(CORRECTION_ONLY_COUNTERFACTUAL) 분리. v5-2A.1 이하 무수정 재사용. 신규 방향 관계 0. 임상 성능 NOT_EVALUATED."""
import sys
from pathlib import Path

_V521 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v5_2a1"
if str(_V521) not in sys.path:
    sys.path.insert(0, str(_V521))

import hybrid521  # noqa: E402,F401  (v5-2A·v5-1·v4·v3·v1 경로 설정)

EVENT_HISTORY, PATIENT_HISTORY, COUNTERFACTUAL = "EVENT_VERSION_HISTORY", "PATIENT_AS_OF_HISTORY", "CORRECTION_ONLY_COUNTERFACTUAL"
