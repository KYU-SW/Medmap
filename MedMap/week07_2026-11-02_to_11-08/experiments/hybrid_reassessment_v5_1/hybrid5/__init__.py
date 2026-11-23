"""MedMap v5-1: 다질환 개념·검사 수치·시계열·ECG·K-of-N·연구용 진단 등급(방향 판단과 분리). v1~v4 무수정 재사용. 신규 방향 관계 0."""
import sys
from pathlib import Path

_V4 = Path(__file__).resolve().parents[2] / "hybrid_reassessment_v4"
if str(_V4) not in sys.path:
    sys.path.insert(0, str(_V4))
