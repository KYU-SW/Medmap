"""테스트 공용: scripts 경로 + PolicyEngine 1회 로드(모듈 캐시)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
_E = None


def engine():
    global _E
    if _E is None:
        from policies import PolicyEngine
        _E = PolicyEngine()
    return _E


def run(text, policy="P5"):
    return engine().run_all(text)[policy]


def autos(text, policy="P5"):
    return [o["canonical_id"] for o in run(text, policy) if o["status"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")]
