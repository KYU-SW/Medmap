"""STEP29 ↔ STEP28.8 P5 어댑터(P5 원본 수정 없음). 반환 구조는 STEP28.8 policies.PolicyEngine.combine 의 실제 키를 사용
(status · canonical_id · ontology_id · relation_to_existing · evidence_level · isolation_status · model_supported · usable_by_disease_model ·
 display · requires_confirmation · reason · evidence_sources · ko_tier · ko_evidence · polarity · subject · temporal · span_text · span_start · span_end ·
 normalized_expression). p5(text) = run_all(text)["P5"] 과 같은 경로만 계산(속도) — tests/test_p5_adapter 가 동일성 확인."""
from __future__ import annotations

import s29_common  # noqa: F401  (경로)
from policies import PolicyEngine

_E = None


def engine() -> PolicyEngine:
    global _E
    if _E is None:
        _E = PolicyEngine()
    return _E


_CACHE: dict[str, list] = {}
USE_CACHE = True   # 평가 속도용 메모(결정적). 지연 측정 시 False


def p5(text: str) -> list[dict]:
    import copy
    if USE_CACHE and text in _CACHE:
        return copy.deepcopy(_CACHE[text])
    out = _p5(text)
    if USE_CACHE:
        _CACHE[text] = copy.deepcopy(out)
    return out


def _p5(text: str) -> list[dict]:
    E = engine()
    E.R.ko_mode = "repaired"
    rep = E.R.run(text, "KO_ONLY")
    out = []
    for o in rep:
        ks = E.keys(text, o, len(rep))
        r = E.combine(text, o, E.clean.lookup(ks), "P5")
        out.append(E.apply_distinct(E.apply_held(r, o, ks), ks))
    return out


def silver_rows(key: str) -> list[dict]:
    return engine().clean.by_key.get(key, [])
