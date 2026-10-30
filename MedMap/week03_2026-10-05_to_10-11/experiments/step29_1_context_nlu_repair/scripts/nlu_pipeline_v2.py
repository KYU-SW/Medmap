"""STEP29.1 NLU v2 — STEP29 NLU_P5 출력(analyze, 원본 무수정) 위에 단계별 후처리. analyze(text, level):
 P0 = STEP29 NLU_P0(STEP28.8 P5 단독) · P1 = P2 = STEP29 NLU_P5 그대로(P1·P2 차이는 검사기뿐) · P3 = + evaluative_negation · P4 = + resolution_temporality ·
 P5 = + mention_context_validator + unsupported_input_guard. 모든 수정은 원문·원래 값 보존(assertion_basis·guard_reasons·resolution·context).
 model_input 은 STEP29 symptom_context_builder.model_input 으로 다시 계산 + assertion_certainty LOW 이면 eligible False. applied=false(표시만)."""
from __future__ import annotations

import s291_common  # noqa: F401  (경로)
import clinical_nlu_pipeline as P29
import evaluative_negation as EVN
import mention_context_validator as MCV
import resolution_temporality as RT
import unsupported_input_guard as UIG
from clause_segmenter import segment
from symptom_context_builder import model_input

LEVELS = ("P0", "P1", "P2", "P3", "P4", "P5")


def _mi(m):
    mi = model_input(m)
    if m.get("assertion_certainty") == "LOW" or m.get("assertion") == "UNKNOWN":
        mi = {**mi, "eligible": False, "polarity": None}
    return mi


def analyze(text: str, level: str = "P5") -> dict:
    if level == "P0":
        return P29.analyze(text, "NLU_P0")
    base = P29.analyze(text, "NLU_P5")
    if level in ("P1", "P2"):
        return {**base, "level": level}
    L = LEVELS.index(level)
    clauses = segment(text)
    ms = []
    for m in base["mentions"]:
        cl = next((c for c in clauses if c["start"] <= m["span_start"] < c["end"]), None)
        ms.append(EVN.apply(m, cl["text"] if cl else ""))
    ctx = dict(base.get("context") or {})
    ctx["v2_dropped_unsure"] = [m["raw_span"] for m in ms if m.get("drop_as_context")]
    ms = [m for m in ms if not m.get("drop_as_context")]
    if L >= 4:
        ms, extra = RT.apply(text, ms, clauses)
        ctx["v2_context"] = extra
    if L >= 5:
        ms = [UIG.apply(MCV.apply(m)) for m in ms]
    for m in ms:
        m["model_input"] = _mi(m)
        if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not (m.get("reason") or m.get("guard_reasons")):
            m["reason"] = "NO_SUPPORTED_LINK(원문 보존)"
    return {"source_text": text, "level": level, "mentions": ms, "context": ctx}


if __name__ == "__main__":
    import json
    import sys
    for t in sys.argv[1:]:
        for m in analyze(t)["mentions"]:
            print(json.dumps({k: m.get(k) for k in ("raw_span", "status", "canonical_id", "assertion", "assertion_basis", "temporality", "resolution", "experiencer",
                                                     "guard_reasons", "model_input")}, ensure_ascii=False))
