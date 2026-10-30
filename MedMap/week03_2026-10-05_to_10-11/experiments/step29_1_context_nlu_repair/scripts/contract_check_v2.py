"""STEP29.1 계약 채점 — STEP29 contract_check.check(원본) + 새 필드: optional · no_symptom_mentions · max_symptom_mentions · no_model_positive · forbid_assertion."""
from __future__ import annotations

from contract_check import check as check29
from contract_check import concept_of

POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")


def check(c: dict, out: dict) -> list[dict]:
    opt = {m["anchor"] for m in c["mentions"] if m.get("optional")}
    errs = [e for e in check29(c, out) if not (e["type"] == "NOT_EXTRACTED" and e.get("anchor") in opt)]
    ms = out["mentions"]
    sym = [m for m in ms if m["status"] in POS]
    if c.get("no_symptom_mentions") and sym:
        errs.append({"type": "UNEXPECTED_SYMPTOM", "got": [concept_of(m) or m.get("canonical_id") for m in sym]})
    if c.get("max_symptom_mentions") and len(sym) > c["max_symptom_mentions"]:
        errs.append({"type": "OVER_SPLIT", "got": len(sym)})
    if c.get("no_model_positive"):
        pos = [m["raw_span"] for m in ms if m["model_input"]["eligible"] and m["model_input"]["polarity"] == "POSITIVE"]
        if pos:
            errs.append({"type": "MODEL_POSITIVE_FORBIDDEN", "got": pos, "unsafe": True})
    for con, a in c.get("forbid_assertion", []):
        if any((concept_of(m) == con or m.get("canonical_id") == con) and m["assertion"] == a for m in ms):
            errs.append({"type": "FORBIDDEN_ASSERTION", "got": f"{con}:{a}"})
    return errs
