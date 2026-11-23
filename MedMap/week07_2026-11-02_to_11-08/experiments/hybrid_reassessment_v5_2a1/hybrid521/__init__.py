"""MedMap v5-2A.1: 검사 사건 단위 근거 그룹화·출처 추적. v5-2A 비교 엔진(무수정) 위의 표시 계층.
레거시 v4 판단 방향은 바꾸지 않는다. 신규 SUPPORT/WEAKEN 0건. 임상 성능 NOT_EVALUATED."""
import sys
from pathlib import Path

_V52 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v5_2a"
if str(_V52) not in sys.path:
    sys.path.insert(0, str(_V52))

import hybrid52  # noqa: E402,F401  (v5-1·v4·v3·v1 경로 설정)
