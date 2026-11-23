"""MedMap v5-2B-Research: PE_SHADOW_RESEARCH(격리 연구용 규칙) + Legacy v4 비교, 시간·중복·정정 통합, ACS·MI·심낭염 연구용 분류 비교.
v1~v5-2B-P0 무수정 재사용. Shadow 판단은 RESEARCH_ONLY · NOT_CLINICALLY_VALIDATED · ENGINE_ACTIVE_FALSE. 임상 성능 NOT_EVALUATED."""
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[2]
for p in ("hybrid_reassessment_v5_2a2",):
    if str(EXP / p) not in sys.path:
        sys.path.insert(0, str(EXP / p))

import hybrid522  # noqa: E402,F401  (v5-2A.1·v5-2A·v5-1·v4·v3·v1 경로)

LABELS = ("RESEARCH_ONLY", "NOT_CLINICALLY_VALIDATED", "ENGINE_ACTIVE_FALSE")
P0 = EXP / "hybrid_reassessment_v5_2b_p0"
