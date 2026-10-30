"""테스트 공용(개발용 단위 테스트 — 계약·노출 사례 기반, 독립 평가 아님)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import s291_common  # noqa: E402,F401
from nlu_pipeline_v2 import analyze  # noqa: E402

EX = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")


def ms(t, L="P5"):
    return analyze(t, L)["mentions"]


def find(t, a, L="P5"):
    return next((m for m in ms(t, L) if a in m["raw_span"] or a in (m.get("unit_text") or "")), None)


def autos(t, L="P5"):
    return [m["canonical_id"] for m in ms(t, L) if m["status"] in EX]
