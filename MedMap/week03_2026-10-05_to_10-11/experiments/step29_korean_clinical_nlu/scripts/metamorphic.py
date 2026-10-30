"""STEP29 §15 metamorphic 검사(규칙 일관성 — 임상 정확도 아님). 변환별 기대(사전 고정):
 neg   : 기본 concept 이 다른 concept 으로 바뀌지 않음(같거나 연결 없음) + 그 mention assertion = ABSENT
 past  : concept 불변(같거나 없음) + temporality ∈ {PAST, RESOLVED}
 other : concept 불변(같거나 없음) + experiencer ∈ {OTHER_PERSON, MULTIPLE}
 plus  : 기본 concept 유지 + mention ≥ 2
 irrelevant(무관 문장 추가): 기본 mention 의 span_start·span_end·concept 동일"""
from __future__ import annotations

from contract_check import concept_of, load


def run(analyze, level="NLU_P5") -> dict:
    rows = []
    for t in load()["metamorphic"]:
        c = t["concept"]
        base = analyze(t["base"], level)["mentions"]
        bm = next((m for m in base if concept_of(m) == c), None)
        rows.append({"base": t["base"], "check": "base_has_concept", "pass": bm is not None})

        def first(text):
            ms = analyze(text, level)["mentions"]
            return ms, next((m for m in ms if m.get("is_symptom")), None)
        ms, m = first(t["neg"])
        rows.append({"base": t["base"], "check": "neg_concept_stable", "pass": all(concept_of(x) in (c, None) for x in ms)})
        rows.append({"base": t["base"], "check": "neg_absent", "pass": bool(m) and m["assertion"] == "ABSENT"})
        ms, m = first(t["past"])
        rows.append({"base": t["base"], "check": "past_concept_stable", "pass": all(concept_of(x) in (c, None) for x in ms)})
        rows.append({"base": t["base"], "check": "past_temporality", "pass": bool(m) and m["temporality"] in ("PAST", "RESOLVED")})
        ms, m = first(t["other"])
        rows.append({"base": t["base"], "check": "other_concept_stable", "pass": all(concept_of(x) in (c, None) for x in ms)})
        rows.append({"base": t["base"], "check": "other_experiencer", "pass": bool(m) and m["experiencer"] in ("OTHER_PERSON", "MULTIPLE")})
        ms = analyze(t["plus"], level)["mentions"]
        rows.append({"base": t["base"], "check": "plus_retains_base", "pass": any(concept_of(x) == c for x in ms) and len(ms) >= 2})
        ir = analyze(t["irrelevant"], level)["mentions"]
        im = next((x for x in ir if concept_of(x) == c), None)
        rows.append({"base": t["base"], "check": "irrelevant_span_stable", "pass": bool(bm and im and (bm["span_start"], bm["span_end"]) == (im["span_start"], im["span_end"]))})
    by = {}
    for r in rows:
        by.setdefault(r["check"], [0, 0])
        by[r["check"]][0] += r["pass"]
        by[r["check"]][1] += 1
    return {"rows": rows, "summary": {k: f"{a}/{b}" for k, (a, b) in by.items()}, "pass": sum(r["pass"] for r in rows), "n": len(rows)}
