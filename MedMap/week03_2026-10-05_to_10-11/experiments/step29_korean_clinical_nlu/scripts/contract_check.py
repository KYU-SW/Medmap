"""계약(개발용 합성) 채점 — tests·evaluate_nlu 공용. mention 대응 = raw_span 이 anchor 를 포함하는 첫 mention(같은 anchor 반복 시 순서대로).
오류 종류(별도 집계): 1 NOT_EXTRACTED · 2 WRONG_NORMALIZATION(concept_any 밖 또는 forbid 자동) · 3 NEGATION · 4 TEMPORALITY · 5 EXPERIENCER ·
 기타 ATTRIBUTE(속성 미보존) · ONSET · FREQUENCY · SCOPE · MUST_NOT_AUTO(문장 전체 자동 concept 금지 위반)."""
from __future__ import annotations

import json

import s29_common as S

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")


def load():
    return json.loads((S.DATA / "synthetic_nlu_contracts.json").read_text(encoding="utf-8"))


def concept_of(m):
    if m["status"] in EXISTING:
        return m["canonical_id"]
    if m["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
        return m.get("ontology_id") or m.get("canonical_id")
    return None


def check(contract, out) -> list[dict]:
    errs, used = [], set()
    ms = out["mentions"]
    for exp in contract["mentions"]:
        idx = next((i for i, m in enumerate(ms) if i not in used and exp["anchor"] in m["raw_span"]), None)
        if idx is None:
            idx = next((i for i, m in enumerate(ms) if i not in used and exp["anchor"] in (m.get("unit_text") or "")), None)
        if idx is None:
            errs.append({"type": "NOT_EXTRACTED", "anchor": exp["anchor"], "safety": exp.get("safety")})
            continue
        used.add(idx)
        m = ms[idx]
        c = concept_of(m)
        ok_c = c in exp["concept_any"] or (m["status"] == "EXISTING_SUBTYPE" and m.get("canonical_id") in exp["concept_any"])
        if not ok_c or (m["status"] in EXISTING and c in exp.get("forbid", [])):
            errs.append({"type": "WRONG_NORMALIZATION", "anchor": exp["anchor"], "got": c, "status": m["status"]})
        if m["assertion"] not in exp["assertion_any"]:
            errs.append({"type": "NEGATION", "anchor": exp["anchor"], "got": m["assertion"], "want": exp["assertion_any"], "safety": exp.get("safety"),
                         "unsafe": exp.get("safety") == "NEG" and m["assertion"] == "PRESENT" and m["model_input"]["polarity"] == "POSITIVE"})
        if exp.get("temporality_any") and m["temporality"] not in exp["temporality_any"]:
            errs.append({"type": "TEMPORALITY", "anchor": exp["anchor"], "got": m["temporality"], "want": exp["temporality_any"]})
        if m["experiencer"] not in exp["experiencer_any"]:
            errs.append({"type": "EXPERIENCER", "anchor": exp["anchor"], "got": m["experiencer"], "want": exp["experiencer_any"], "safety": exp.get("safety"),
                         "unsafe": exp.get("safety") == "OTHER" and m["experiencer"] == "PATIENT" and m["model_input"]["eligible"]})
        for a in exp.get("attributes_include", []):
            if not any(a in x for x in m.get("attributes", [])):
                errs.append({"type": "ATTRIBUTE", "anchor": exp["anchor"], "missing": a})
        if exp.get("onset_text") and m.get("onset_text") != exp["onset_text"]:
            errs.append({"type": "ONSET", "anchor": exp["anchor"], "got": m.get("onset_text")})
        if exp.get("frequency_text") and m.get("frequency_text") != exp["frequency_text"]:
            errs.append({"type": "FREQUENCY", "anchor": exp["anchor"], "got": m.get("frequency_text")})
        if exp.get("time_scope") and m.get("time_scope") != exp["time_scope"]:
            errs.append({"type": "SCOPE", "anchor": exp["anchor"], "got": m.get("time_scope")})
        if exp.get("role") and m.get("role") != exp["role"]:
            errs.append({"type": "ROLE", "anchor": exp["anchor"], "got": m.get("role")})
    autos = {m["canonical_id"] for m in ms if m["status"] in EXISTING}
    for c in contract.get("must_not_auto", []):
        if c in autos:
            errs.append({"type": "MUST_NOT_AUTO", "concept": c})
    return errs
