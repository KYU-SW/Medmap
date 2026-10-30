"""STEP30 테스트 공통 — 지시문 §11(노출 회귀) 문장과 개발 문장만 쓴다(INTEGRATION_NEW 평가 문장 사용 금지)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import s30_common as S  # noqa: E402
import doctor_integration_adapter as AD  # noqa: E402
import model_input_eligibility as ELIG  # noqa: E402
import clinician_confirmation_simulator as SIM  # noqa: E402

_CACHE = {}


def packet(text):
    if text not in _CACHE:
        _CACHE[text] = AD.analyze(text)
    return copy.deepcopy(_CACHE[text])


def item_at(p, surface):
    s = p["source_text"].find(surface)
    e = s + len(surface)
    best = None
    for it in p["items"]:
        if it["span_start"] is not None and min(it["span_end"], e) > max(it["span_start"], s):
            best = it
    return best


def supported_mention():
    """실제 NLU 의 STAGE_A 항목('숨이 차') 원본 mention 사본 — 속성만 바꿔 규칙을 시험한다."""
    p = packet("기침은 없는데 숨이 차요.")
    it = item_at(p, "숨이 차")
    assert it["eligibility"]["eligible"], "기준 mention 이 STAGE_A 가 아님"
    return copy.deepcopy(it["nlu_original"])


def item_from(m):
    return AD.build_item(m, 0, S.sha_text(m["source_text"]))
