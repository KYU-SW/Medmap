"""MedMap v5-2A: 다질환 가설 비교 엔진(증거 연결·조건 상태·중복/종속·시간/에피소드·부족 정보).
v1~v5-1 코드는 무수정 재사용(경로만 추가). 신규 SUPPORT/WEAKEN 관계 0건. 임상 성능 NOT_EVALUATED."""
import sys
from pathlib import Path

_V51 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v5_1"
if str(_V51) not in sys.path:
    sys.path.insert(0, str(_V51))

import hybrid5  # noqa: E402,F401  (v4 경로 설정)
from hybrid4 import graphs as _g4  # noqa: E402,F401  (v3·v1 경로 설정 — import 순서와 무관하게)

CLINICAL_VALIDATION_STATUS = "NOT_EVALUATED"
ACTIVE_DIRECTION_RELATIONS_V52 = 0
