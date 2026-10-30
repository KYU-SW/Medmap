"""테스트 공용(개발용 — 계약·노출 사례 기반 단위 테스트, 독립 평가 아님)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clinical_nlu_pipeline import analyze  # noqa: E402,F401
from contract_check import concept_of, load  # noqa: E402,F401


def ms(text, level="NLU_P5"):
    return analyze(text, level)["mentions"]


def find(text, anchor, level="NLU_P5"):
    return next((m for m in ms(text, level) if anchor in m["raw_span"] or anchor in (m.get("unit_text") or "")), None)
