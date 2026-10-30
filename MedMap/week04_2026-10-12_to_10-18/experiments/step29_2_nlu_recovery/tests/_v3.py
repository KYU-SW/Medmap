"""테스트 공용(개발용 단위 테스트 — 지시문 예시·개발 사례 기반, 독립 평가 아님). HOLDOUT 문장은 쓰지 않는다(run_tests 가 겹침 검사)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import s292_common as S  # noqa: E402
from nlu_pipeline_v3 import analyze  # noqa: E402

EX = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
_pf = S.DATA / "policy_freeze.json"
SEL = json.loads(_pf.read_text(encoding="utf-8"))["SELECTED_POLICY"] if _pf.exists() else "V3_B2"


def ms(t, P=None):
    return analyze(t, P or SEL)["mentions"]


def find(t, a, P=None):
    return next((m for m in ms(t, P) if m["status"] != "NON_SYMPTOM" and (a in m["raw_span"] or a in (m.get("unit_text") or ""))), None)


def autos(t, P=None):
    return [m["canonical_id"] for m in ms(t, P) if m["status"] in EX]
