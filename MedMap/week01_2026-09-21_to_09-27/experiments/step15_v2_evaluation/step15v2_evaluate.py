#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEED = 1502
REQUIRED_FROZEN = [
    "00_source_registry.csv", "01_disease_profile_facts.csv",
    "02_disease_profile_concepts.csv", "03_profile_quality_audit.csv",
    "04_external_pair_differences.csv", "05_manual_review_queue.csv",
    "06_HUMAN_REVIEW_SHEET.csv",
]
PROFILE_DISEASES = [
    "Acute rhinosinusitis", "Chronic rhinosinusitis", "Acute laryngitis",
    "Viral pharyngitis", "Stable angina", "Unstable angina",
    "Acute / initial HIV infection", "Scombroid poisoning",
    "Acute COPD exacerbation", "Paroxysmal supraventricular tachycardia (PSVT)",
]
NAME_MAP = {
    "Acute rhinosinusitis": "Acute rhinosinusitis",
    "Chronic rhinosinusitis": "Chronic rhinosinusitis",
    "Acute laryngitis": "Acute laryngitis",
    "Viral pharyngitis": "Viral pharyngitis",
    "Stable angina": "Stable angina",
    "Unstable angina": "Unstable angina",
    "Acute / initial HIV infection": "HIV (initial infection)",
    "Scombroid poisoning": "Scombroid food poisoning",
    "Acute COPD exacerbation": "Acute COPD exacerbation / infection",
    "Paroxysmal supraventricular tachycardia (PSVT)": "PSVT",
}
FROZEN_NAME_MAP = {
    "Acute / initial HIV infection": "Acute HIV infection",
    "Paroxysmal supraventricular tachycardia (PSVT)": "PSVT",
}
ATTRIBUTE_FIELDS = [
    "location", "severity", "onset", "duration", "frequency", "progression",
    "trigger", "relieving_factor", "history_context", "family_context",
    "exposure_context", "medication_context",
]
MAPPING_STATUSES = {"DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH", "NO_MATCH", "NOT_APPLICABLE"}
DECISION_THRESHOLDS = {
    "profile_scaleup_min_strict_gain": 0.15,
    "profile_scaleup_min_value_strict": 0.35,
    "profile_scaleup_min_pair_observable_rate": 0.50,
    "question_engine_min_basic_strict": 0.25,
}


class IndependenceError(RuntimeError):
    pass


class InvalidFreezeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm(text: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


class AuditedReader:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.read_files: list[str] = []
        self.violations: list[str] = []

    def resolve(self, rel: str | Path) -> Path:
        raw = str(rel).replace("\\", "/")
        low = raw.lower()
        forbidden = (
            low.startswith(".claude/") or "/.claude/" in low or
            "release_test_patients" in low or
            any(x in low for x in ["step13_report", "step13b_report", "step14_report", "step15_report", "reviewer", "referee", "guardian", "error_pair"])
        )
        if forbidden:
            self.violations.append(raw)
            raise IndependenceError(f"Forbidden input path: {raw}")
        p = (self.root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if self.root not in p.parents and p != self.root:
            self.violations.append(raw)
            raise IndependenceError(f"Path escapes project root: {raw}")
        return p

    def text(self, rel: str | Path) -> str:
        p = self.resolve(rel)
        self.read_files.append(str(p.relative_to(self.root)))
        return p.read_text(encoding="utf-8")

    def json(self, rel: str | Path):
        return json.loads(self.text(rel))

    def csv(self, rel: str | Path) -> list[dict[str, str]]:
        return list(csv.DictReader(self.text(rel).splitlines()))


def verify_freeze(profile_dir: Path, required: list[str] = REQUIRED_FROZEN) -> dict:
    freeze_path = profile_dir / "PROFILE_FREEZE_V2.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    files = {}
    valid = True
    for name in required:
        p = profile_dir / name
        actual = sha256_file(p)
        expected = freeze["file_sha256"].get(name)
        same = actual == expected
        valid &= same
        st = p.stat()
        files[name] = {"expected_sha256": expected, "actual_sha256": actual, "match": same, "mtime_ns": st.st_mtime_ns}
    result = {
        "status": "VALID" if valid else "STEP15V2_EVAL_INVALID_FREEZE",
        "profile_freeze_sha256": sha256_file(freeze_path),
        "files": files,
    }
    if not valid:
        raise InvalidFreezeError("STEP15V2_EVAL_INVALID_FREEZE")
    return result


CANON_PATTERNS = [
    ("cough", r"\bcough|tuss"), ("fever", r"fever|temperature"),
    ("sore throat", r"sore throat|pharyng|throat pain"), ("rhinorrhea", r"rhinorr|runny nose|nasal discharge"),
    ("nasal congestion", r"nasal congestion|blocked nose|stuffy nose"), ("dyspnea", r"shortness of breath|difficulty breathing|dyspn"),
    ("wheezing", r"wheez"), ("sputum", r"sputum|phlegm"),
    ("chest pain", r"chest pain|angina"), ("palpitations", r"palpitation|heart.*beating fast|racing heart|tachycard"),
    ("nausea", r"nausea|vomit"), ("diarrhea", r"diarrh|stool frequency"),
    ("rash", r"rash|skin lesion|skin.*redness"), ("flushing", r"flushing|cheeks.*red"),
    ("hoarseness", r"hoarse|dysphonia|voice"), ("lymphadenopathy", r"lymph|adenopathy|swollen gland"),
    ("fatigue", r"fatigue|tired|malaise"), ("headache", r"headache|head pain"),
    ("myalgia", r"myalgia|muscle ache|muscle pain"), ("smoking", r"smok|cigarette|tobacco"),
    ("fish exposure", r"dark.fleshed fish|tuna|scombroid|fish"), ("hiv exposure", r"hiv|unprotected sex|sexual partner|needle"),
    ("pain", r"\bpain\b"),
]


def canonical(text: object) -> str:
    s = norm(text)
    for name, pattern in CANON_PATTERNS:
        if re.search(pattern, s):
            return name
    return s


def _attr_values(row: dict) -> dict[str, str]:
    return {k: str(row.get(k, "") or "").strip() for k in ATTRIBUTE_FIELDS if str(row.get(k, "") or "").strip()}


def _similar(a: object, b: object) -> bool:
    ca, cb = canonical(a), canonical(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    ta, tb = set(norm(ca).split()), set(norm(cb).split())
    return bool(ta and tb and len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.75)


def classify_match(evidence: dict, fact: dict) -> tuple[str, str, bool, bool]:
    if evidence.get("not_applicable"):
        return "NOT_APPLICABLE", "Evidence is demographic or otherwise not a disease finding", False, False
    if not _similar(evidence.get("base_concept"), fact.get("base_concept")):
        return "NO_MATCH", "Base clinical concepts do not correspond", False, False
    ea, fa = _attr_values(evidence), _attr_values(fact)
    if not ea:
        return "DIRECT_MATCH", "Base clinical concept directly corresponds", True, False
    matched = []
    for key, val in ea.items():
        candidates = [fa.get(key, ""), fact.get("value_raw", ""), fact.get("value_normalized", "")]
        if any(_similar(val, x) or norm(val) in norm(x) or norm(x) in norm(val) for x in candidates if x):
            matched.append(key)
    if len(matched) == len(ea):
        return "ATTRIBUTE_MATCH", "Base concept and all represented attributes correspond", True, True
    return "PARTIAL_MATCH", "Base concept corresponds but one or more evidence attributes are absent or conflicting", True, False


def coverage_counts(rows: list[dict]) -> dict:
    c = Counter(r["mapping_status"] for r in rows)
    total = sum(c[s] for s in ["DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH", "NO_MATCH"])
    strict = c["DIRECT_MATCH"] + c["ATTRIBUTE_MATCH"]
    lenient = strict + c["PARTIAL_MATCH"]
    return {
        "total_relevant_evidence": total,
        "direct_match": c["DIRECT_MATCH"], "attribute_match": c["ATTRIBUTE_MATCH"],
        "partial_match": c["PARTIAL_MATCH"], "no_match": c["NO_MATCH"],
        "strict_coverage": strict / total if total else 0.0,
        "lenient_coverage": lenient / total if total else 0.0,
    }


def observability_record(feature: str, evidence_ids: list[str], medically_discriminative: bool) -> dict:
    return {
        "feature": feature, "medically_discriminative": bool(medically_discriminative),
        "experimentally_observable": bool(evidence_ids), "ddxplus_evidence_id": ";".join(evidence_ids),
    }


def patient_observability_stats(patient_evidence: list[list[str]], matchable: set[str]) -> dict:
    visible = [len(x) for x in patient_evidence]
    counts = [len({e.split("_@_")[0] for e in x} & matchable) for x in patient_evidence]
    n = len(counts)
    return {
        "patient_count": n,
        "mean_visible_evidence": sum(visible) / n if n else 0.0,
        "mean_profile_matchable": sum(counts) / n if n else 0.0,
        "median_profile_matchable": statistics.median(counts) if n else 0.0,
        "zero_matchable_rate": sum(x == 0 for x in counts) / n if n else 0.0,
    }


def facts_for_disease(facts_by_disease: dict, requested_name: str) -> list[dict]:
    return facts_by_disease.get(FROZEN_NAME_MAP.get(requested_name, requested_name), [])


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def json_dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def evidence_struct(eid: str, raw: dict, vmap: dict[str, dict]) -> dict:
    m = vmap.get(eid, {})
    attrs = {
        "location": m.get("attribute_location", ""), "severity": m.get("attribute_severity", ""),
        "onset": m.get("attribute_onset", ""), "duration": m.get("attribute_duration", ""),
        "frequency": m.get("attribute_frequency", ""), "history_context": m.get("context_history", ""),
        "family_context": m.get("context_family", ""), "medication_context": m.get("context_medication", ""),
        "exposure_context": m.get("context_exposure", ""),
    }
    q = raw.get("question_en", "")
    base = m.get("base_concept") or canonical(q)
    return {
        "evidence_id": eid, "original_question": q, "base_concept": base,
        "value_type": raw.get("data_type", ""), "possible_values": raw.get("possible-values", []),
        **attrs, "progression": "", "trigger": "", "relieving_factor": "",
        "binary_or_value": "binary" if raw.get("data_type") == "B" else "value",
    }


def best_match(evidence: dict, facts: list[dict]) -> tuple[dict | None, tuple]:
    ranked = []
    rank = {"ATTRIBUTE_MATCH": 4, "DIRECT_MATCH": 3, "PARTIAL_MATCH": 2, "NO_MATCH": 1, "NOT_APPLICABLE": 0}
    for fact in facts:
        result = classify_match(evidence, fact)
        ranked.append((rank[result[0]], result[3], fact, result))
    if not ranked:
        return None, ("NO_MATCH", "Disease has no frozen facts", False, False)
    _, _, fact, result = max(ranked, key=lambda x: (x[0], x[1], -int(re.sub(r"\D", "", x[2].get("fact_id", "0")) or 0)))
    return fact if result[0] != "NO_MATCH" else None, result


def feature_type(row: dict) -> str:
    checks = [
        ("duration", "DURATION"), ("onset", "ONSET"), ("trigger", "TRIGGER"),
        ("relieving_factor", "RELIEF"), ("progression", "PROGRESSION"), ("location", "LOCATION"),
        ("severity", "SEVERITY"), ("exposure_context", "EXPOSURE"),
        ("history_context", "HISTORY"),
    ]
    for field, label in checks:
        if row.get(field):
            return label
    cat = norm(row.get("fact_category"))
    if "risk" in cat: return "RISK_FACTOR"
    if "physical" in cat or "sign" in cat: return "PHYSICAL_FINDING"
    if "test" in cat or "lab" in cat or "imaging" in cat: return "TEST_RESULT"
    return "OTHER"


def split_pair_features(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?:^|(?<=\.\s))([A-Z][A-Z/ ]{1,30}):\s*", text or ""))
    result = []
    for i, match in enumerate(matches):
        label = match.group(1).strip().replace("/", "_")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result.append((label, text[match.end():end].strip()))
    return result


def pair_feature_type(label: str) -> str:
    if label in {"DURATION", "ONSET", "TRIGGER", "RELIEF", "PROGRESSION", "LOCATION", "SEVERITY", "EXPOSURE", "HISTORY"}:
        return label
    if label in {"OBJECTIVE", "LAB"}:
        return "TEST_RESULT"
    if label in {"PATTERN_TRIGGER"}:
        return "TRIGGER"
    if label in {"COURSE"}:
        return "PROGRESSION"
    if label in {"CONTEXT"}:
        return "HISTORY"
    return "OTHER"


def evaluate(root: Path, out: Path) -> dict:
    reader = AuditedReader(root)
    out.mkdir(parents=True, exist_ok=True)
    profile_rel = Path("exp/step15_v2_blind_profile")
    profile_dir = root / profile_rel
    pre = verify_freeze(profile_dir)
    initial_snapshot = {k: {"sha256": v["actual_sha256"], "mtime_ns": v["mtime_ns"]} for k, v in pre["files"].items()}
    json_dump(out / "00_freeze_integrity.json", {**pre, "phase": "initial"})

    freeze = reader.json(profile_rel / "PROFILE_FREEZE_V2.json")
    facts = reader.csv(profile_rel / "01_disease_profile_facts.csv")
    concepts = reader.csv(profile_rel / "02_disease_profile_concepts.csv")
    quality = reader.csv(profile_rel / "03_profile_quality_audit.csv")
    pairs = reader.csv(profile_rel / "04_external_pair_differences.csv")
    manual = reader.csv(profile_rel / "05_manual_review_queue.csv")
    reader.csv(profile_rel / "00_source_registry.csv")
    reader.csv(profile_rel / "06_HUMAN_REVIEW_SHEET.csv")

    conditions_rel = Path("data/ddxplus/en/release_conditions.json")
    evidences_rel = Path("data/ddxplus/en/release_evidences.json")
    validate_rel = Path("data/ddxplus/en/release_validate_patients")
    conditions = reader.json(conditions_rel)
    evidences = reader.json(evidences_rel)
    value_rel = Path("exp/step14_value_context_recovery/07_evidence_value_level_map.csv")
    value_rows = reader.csv(value_rel)
    vmap = {r["evidence_id"]: r for r in value_rows}
    old_rel = Path("exp/step13b_external_verifier/00b_relation_matrix_nonzero.csv")
    old_rows = reader.csv(old_rel)

    duplicates = len(evidences) != len(set(evidences))
    binary = sum(x.get("data_type") == "B" for x in evidences.values())
    value = len(evidences) - binary
    name_rows = []
    for profile_name in PROFILE_DISEASES:
        ddx = NAME_MAP[profile_name]
        name_rows.append({"profile_disease_name": profile_name, "ddxplus_original_name": ddx, "normalized_name": norm(ddx), "exists": ddx in conditions, "review_needed": False})
    schema = {
        "condition_count": len(conditions), "evidence_count": len(evidences),
        "binary_evidence_count": binary, "categorical_or_value_evidence_count": value,
        "duplicate_evidence_ids": duplicates, "pilot_disease_names": name_rows,
        "train_path": "data/ddxplus/en/release_train_patients",
        "validate_path": str(validate_rel), "test_path_identified_but_not_opened": "data/ddxplus/en/release_test_patients",
    }
    json_dump(out / "01_ddxplus_schema_audit.json", schema)

    facts_by_disease = defaultdict(list)
    for r in facts: facts_by_disease[r["disease"]].append(r)
    map_rows = []
    structured = {}
    for profile_name in PROFILE_DISEASES:
        ddx = NAME_MAP[profile_name]
        cond = conditions.get(ddx, {})
        relevant = list(dict.fromkeys(list(cond.get("symptoms", {})) + list(cond.get("antecedents", {}))))
        for eid in relevant:
            es = evidence_struct(eid, evidences[eid], vmap)
            structured[eid] = es
            fact, result = best_match(es, facts_for_disease(facts_by_disease, profile_name))
            status, reason, medical, value_match = result
            attrs = _attr_values(es)
            map_rows.append({
                "disease": profile_name, "ddxplus_evidence_id": eid,
                "ddxplus_question": es["original_question"],
                "ddxplus_value": "; ".join(str(x) for x in es["possible_values"]),
                "profile_fact_id": fact.get("fact_id", "") if fact else "",
                "profile_base_concept": fact.get("base_concept", "") if fact else "",
                "profile_attribute": "; ".join(f"{k}={v}" for k, v in attrs.items()),
                "mapping_status": status, "mapping_reason": reason,
                "medical_match": medical, "value_level_match": value_match,
                "review_needed": status in {"PARTIAL_MATCH", "NO_MATCH"},
            })
    map_fields = ["disease", "ddxplus_evidence_id", "ddxplus_question", "ddxplus_value", "profile_fact_id", "profile_base_concept", "profile_attribute", "mapping_status", "mapping_reason", "medical_match", "value_level_match", "review_needed"]
    write_csv(out / "02_ddxplus_profile_mapping.csv", map_rows, map_fields)

    coverage_rows = []
    for disease in PROFILE_DISEASES:
        rows = [r for r in map_rows if r["disease"] == disease]
        basic = coverage_counts(rows)
        value_rows_d = [r for r in rows if structured[r["ddxplus_evidence_id"]]["binary_or_value"] == "value" or _attr_values(structured[r["ddxplus_evidence_id"]])]
        value_cov = coverage_counts(value_rows_d)
        coverage_rows.append({"disease": disease, **basic, "value_total_relevant_evidence": value_cov["total_relevant_evidence"], "value_direct_match": value_cov["direct_match"], "value_attribute_match": value_cov["attribute_match"], "value_partial_match": value_cov["partial_match"], "value_no_match": value_cov["no_match"], "value_strict_coverage": value_cov["strict_coverage"], "value_lenient_coverage": value_cov["lenient_coverage"]})
    cov_fields = list(coverage_rows[0])
    write_csv(out / "03_disease_coverage.csv", coverage_rows, cov_fields)

    before_after = []
    for disease in PROFILE_DISEASES:
        ddx = NAME_MAP[disease]
        old = [r for r in old_rows if r.get("ddxplus_disease") == ddx and float(r.get("strict_score") or 0) > 0]
        cur = [r for r in map_rows if r["disease"] == disease]
        old_eids = {r["evidence_id"] for r in old}
        strict_new = {r["ddxplus_evidence_id"] for r in cur if r["mapping_status"] in {"DIRECT_MATCH", "ATTRIBUTE_MATCH"}}
        before_after.append({
            "disease": disease, "disease_side_knowledge_old": bool(old), "disease_side_knowledge_v2": bool(facts_for_disease(facts_by_disease, disease)),
            "old_base_finding_count": len({r["finding"] for r in old}), "old_value_level_finding_count": 0,
            "v2_base_finding_count": len({r["base_concept"] for r in facts_for_disease(facts_by_disease, disease)}),
            "v2_value_level_finding_count": sum(bool(_attr_values(r)) for r in facts_for_disease(facts_by_disease, disease)),
            "old_ddxplus_overlap_count": len(old_eids), "v2_ddxplus_strict_overlap_count": len(strict_new),
            "old_strict_coverage": len(old_eids) / len(cur) if cur else 0.0,
            "v2_strict_coverage": len(strict_new) / len(cur) if cur else 0.0,
        })
    write_csv(out / "04_before_after_knowledge_coverage.csv", before_after, list(before_after[0]))

    pair_rows, missing_rows = [], []
    pair_lookup = {(p["disease_a"], p["disease_b"]): p for p in pairs}
    pair_specs = [("Acute rhinosinusitis", "Chronic rhinosinusitis"), ("Stable angina", "Unstable angina"), ("Acute laryngitis", "Viral pharyngitis")]
    for a, b in pair_specs:
        frozen_pair = pair_lookup[(a, b)]
        for label, feature in split_pair_features(frozen_pair["differentiating_features_external_only"]):
            ft = pair_feature_type(label)
            attr_map = {"DURATION": "duration", "ONSET": "onset", "TRIGGER": "trigger", "RELIEF": "relieving_factor", "PROGRESSION": "progression", "LOCATION": "location", "SEVERITY": "severity", "EXPOSURE": "exposure_context", "HISTORY": "history_context"}
            relevant_maps = [r for r in map_rows if r["disease"] in {a, b}]
            if ft in attr_map:
                field = attr_map[ft]
                candidates = [r for r in relevant_maps if structured[r["ddxplus_evidence_id"]].get(field)]
            else:
                feature_canon = {name for name, pattern in CANON_PATTERNS if re.search(pattern, norm(feature))}
                candidates = [r for r in relevant_maps if canonical(r["ddxplus_question"]) in feature_canon or canonical(r["profile_base_concept"]) in feature_canon]
                if ft == "TEST_RESULT":
                    candidates += [r for r in relevant_maps if re.search(r"\b(ecg|electrocard|troponin|test|scan|ct|endoscop|imaging|x.ray)\b", norm(r["ddxplus_question"]))]
            candidates = [r for r in candidates if r["mapping_status"] in {"DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH"}]
            eids = sorted({r["ddxplus_evidence_id"] for r in candidates})
            best_status = next((s for s in ["ATTRIBUTE_MATCH", "DIRECT_MATCH", "PARTIAL_MATCH"] if any(r["mapping_status"] == s for r in candidates)), "NO_MATCH")
            support = []
            for disease in (a, b):
                for f in facts_for_disease(facts_by_disease, disease):
                    if feature_type(f) == ft or canonical(f["base_concept"]) in {canonical(feature), *[canonical(x) for x in feature.split(";")]}:
                        support.append(f)
            fact_ids = sorted({f["fact_id"] for f in support})
            sources = sorted({f.get("source_id", "") for f in support if f.get("source_id")})
            pair_rows.append({
                "disease_a": a, "disease_b": b, "feature_disease": f"{a} vs {b}",
                "profile_fact_id": ";".join(fact_ids), "feature": f"{label}: {feature}",
                "profile_has_feature": True, "medically_discriminative": True,
                "ddxplus_has_evidence": bool(eids), "ddxplus_evidence_id": ";".join(eids),
                "mapping_status": best_status, "experimentally_observable": bool(eids),
            })
            if not eids:
                missing_rows.append({
                    "disease": a, "comparison_disease": b, "profile_fact_id": ";".join(fact_ids),
                    "feature_type": ft, "feature_value": f"{label}: {feature}", "source_id": ";".join(sources),
                    "why_discriminative": "Explicitly identified in the frozen external pair-difference summary",
                    "ddxplus_missing_reason": "No relevant DDXPlus evidence mapped to the explicit frozen pair discriminator",
                })
    pair_fields = ["disease_a", "disease_b", "feature_disease", "profile_fact_id", "feature", "profile_has_feature", "medically_discriminative", "ddxplus_has_evidence", "ddxplus_evidence_id", "mapping_status", "experimentally_observable"]
    write_csv(out / "05_pair_observability.csv", pair_rows, pair_fields)
    missing_fields = ["disease", "comparison_disease", "profile_fact_id", "feature_type", "feature_value", "source_id", "why_discriminative", "ddxplus_missing_reason"]
    write_csv(out / "06_missing_discriminative_information.csv", missing_rows, missing_fields)

    patient_evidence = defaultdict(list)
    validation_rows = []
    validate_path = reader.resolve(validate_rel)
    reader.read_files.append(str(validate_rel))
    with validate_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["PATHOLOGY"] in set(NAME_MAP.values()):
                try: evs = ast.literal_eval(row["EVIDENCES"])
                except (ValueError, SyntaxError): evs = []
                profile_name = next(k for k, v in NAME_MAP.items() if v == row["PATHOLOGY"])
                patient_evidence[profile_name].append(evs)
                validation_rows.append(row)
    obs_rows = []
    for disease in PROFILE_DISEASES:
        matchable = {r["ddxplus_evidence_id"] for r in map_rows if r["disease"] == disease and r["mapping_status"] in {"DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH"}}
        stats = patient_observability_stats(patient_evidence[disease], matchable)
        obs_rows.append({"disease": disease, "config": "all", "status": "CALCULATED", **stats, "note": "All recorded validation evidences; TEST not opened"})
        for cfg in ["k3", "k5", "k10"]:
            obs_rows.append({"disease": disease, "config": cfg, "status": "UNAVAILABLE", "patient_count": len(patient_evidence[disease]), "mean_visible_evidence": "", "mean_profile_matchable": "", "median_profile_matchable": "", "zero_matchable_rate": "", "note": "No eligible existing configuration artifact was found; no ordering was invented"})
    write_csv(out / "07_patient_observability_validation.csv", obs_rows, ["disease", "config", "status", "patient_count", "mean_visible_evidence", "mean_profile_matchable", "median_profile_matchable", "zero_matchable_rate", "note"])

    err_counts = Counter()
    for row in validation_rows:
        try: differential = ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"])
        except (ValueError, SyntaxError): differential = []
        if differential:
            working = differential[0][0]
            if working != row["PATHOLOGY"] and (row["PATHOLOGY"] in NAME_MAP.values() or working in NAME_MAP.values()):
                err_counts[(row["PATHOLOGY"], working)] += 1
    err_rows = []
    for (truth, working), count in err_counts.most_common():
        involved = [k for k, v in NAME_MAP.items() if v in {truth, working}]
        feats = [r["feature"] for r in pair_rows if r["feature_disease"] in involved]
        obs = [r["feature"] for r in pair_rows if r["feature_disease"] in involved and r["experimentally_observable"]]
        miss = [r["feature_value"] for r in missing_rows if r["disease"] in involved]
        old = [r["finding"] for r in old_rows if r.get("ddxplus_disease") in {truth, working}]
        err_rows.append({"true_disease": truth, "working_diagnosis": working, "count": count, "profile_discriminative_features": "; ".join(sorted(set(feats))), "ddxplus_observable_features": "; ".join(sorted(set(obs))), "missing_features": "; ".join(sorted(set(miss))), "external_KG_old_features": "; ".join(sorted(set(old)))})
    write_csv(out / "08_validation_error_pair_audit.csv", err_rows, ["true_disease", "working_diagnosis", "count", "profile_discriminative_features", "ddxplus_observable_features", "missing_features", "external_KG_old_features"])

    opp_counts = Counter((r["disease"], r["comparison_disease"], r["feature_type"]) for r in missing_rows)
    opp_rows = [{"disease": k[0], "comparison_disease": k[1], "missing_question_category": k[2], "count": v} for k, v in sorted(opp_counts.items())]
    write_csv(out / "09_followup_question_opportunities.csv", opp_rows, ["disease", "comparison_disease", "missing_question_category", "count"])

    revision_rows = []
    for r in map_rows:
        if r["mapping_status"] in {"PARTIAL_MATCH", "NO_MATCH"}:
            revision_rows.append({"disease": r["disease"], "profile_fact_id": r["profile_fact_id"], "issue_type": "DDXPLUS_MISMATCH_OR_GAP", "evidence_id": r["ddxplus_evidence_id"], "observation": r["mapping_reason"], "frozen_profile_modified": False})
    write_csv(out / "10_future_profile_revision_queue.csv", revision_rows, ["disease", "profile_fact_id", "issue_type", "evidence_id", "observation", "frozen_profile_modified"])

    mapped_fact_ids = {r["profile_fact_id"] for r in map_rows if r["profile_fact_id"]}
    pair_fact_ids = {r["profile_fact_id"] for r in pair_rows}
    manual_by_id = {r["fact_id"]: r for r in manual}
    review_rows = []
    for f in facts:
        if f["fact_id"] in mapped_fact_ids or f["fact_id"] in pair_fact_ids: priority = "HIGH"
        elif str(f.get("review_needed", "")).lower() == "true": priority = "MEDIUM"
        else: priority = "LOW"
        review_rows.append({"fact_id": f["fact_id"], "disease": f["disease"], "base_concept": f["base_concept"], "priority": priority, "affects_ddx_mapping": f["fact_id"] in mapped_fact_ids, "affects_pair_discrimination": f["fact_id"] in pair_fact_ids, "existing_review_reason": manual_by_id.get(f["fact_id"], {}).get("review_reasons", f.get("review_reason", ""))})
    write_csv(out / "11_evaluation_critical_review_queue.csv", review_rows, ["fact_id", "disease", "base_concept", "priority", "affects_ddx_mapping", "affects_pair_discrimination", "existing_review_reason"])

    all_cov = coverage_counts(map_rows)
    value_map_rows = [r for r in map_rows if structured[r["ddxplus_evidence_id"]]["binary_or_value"] == "value" or _attr_values(structured[r["ddxplus_evidence_id"]])]
    value_cov = coverage_counts(value_map_rows)
    old_total = sum(r["old_ddxplus_overlap_count"] for r in before_after)
    denom = sum(r["total_relevant_evidence"] for r in coverage_rows)
    old_strict = old_total / denom if denom else 0.0
    pair_obs_rate = sum(bool(r["experimentally_observable"]) for r in pair_rows) / len(pair_rows) if pair_rows else 0.0
    missing_n = len(missing_rows); observable_n = sum(bool(r["experimentally_observable"]) for r in pair_rows)
    if all_cov["strict_coverage"] - old_strict >= DECISION_THRESHOLDS["profile_scaleup_min_strict_gain"] and value_cov["strict_coverage"] >= DECISION_THRESHOLDS["profile_scaleup_min_value_strict"] and pair_obs_rate >= DECISION_THRESHOLDS["profile_scaleup_min_pair_observable_rate"]:
        decision = "PROFILE_SCALEUP"
    elif all_cov["strict_coverage"] >= DECISION_THRESHOLDS["question_engine_min_basic_strict"] and missing_n > observable_n:
        decision = "QUESTION_ENGINE_FIRST"
    else:
        decision = "STOP_EXTERNAL_VERIFIER"

    post = verify_freeze(profile_dir)
    modified = [k for k, v in post["files"].items() if v["actual_sha256"] != initial_snapshot[k]["sha256"] or v["mtime_ns"] != initial_snapshot[k]["mtime_ns"]]
    integrity = {**pre, "phase": "complete", "post_files": post["files"], "modified_files": modified, "unchanged_pre_post": not modified}
    json_dump(out / "00_freeze_integrity.json", integrity)
    summary = {
        "independence_violation": bool(reader.violations), "forbidden_files_accessed": reader.violations,
        "freeze_integrity": integrity["status"], "frozen_modified_files": modified,
        "ddxplus": schema, "pilot_evaluable": sum(x["exists"] for x in name_rows),
        "coverage": {"old_kg_strict": old_strict, "v2_basic_strict": all_cov["strict_coverage"], "v2_basic_lenient": all_cov["lenient_coverage"], "v2_value_strict": value_cov["strict_coverage"], "v2_value_lenient": value_cov["lenient_coverage"]},
        "pair_observable_rate": pair_obs_rate, "missing_discriminative_count": missing_n,
        "missing_by_category": dict(Counter(r["feature_type"] for r in missing_rows)),
        "review_priority": dict(Counter(r["priority"] for r in review_rows)),
        "decision_thresholds_preregistered_in_code": DECISION_THRESHOLDS, "next_step": decision,
        "limitations": ["Mapping is conservative automated lexical/concept mapping and requires HIGH-priority human review", "k3/k5/k10 were unavailable because no eligible existing configuration was identified", "Validation differential top entry is audited as working diagnosis; it is not a newly trained model prediction"],
    }
    json_dump(out / "12_summary.json", summary)

    read_unique = list(dict.fromkeys(reader.read_files))
    audit = ["INDEPENDENCE_VIOLATION=" + str(bool(reader.violations)).lower(), "FORBIDDEN_FILES_ACCESSED=" + (";".join(reader.violations) if reader.violations else "NONE"), "", "READ_FILES:"] + read_unique
    (out / "READ_FILES_AUDIT.txt").write_text("\n".join(audit) + "\n", encoding="utf-8")
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=root, text=True)
    pip_freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=root, text=True, capture_output=True).stdout
    input_paths = [conditions_rel, evidences_rel, validate_rel, value_rel, old_rel]
    input_hashes = {str(p): sha256_file(root / p) for p in input_paths}
    provenance = [
        "# PROVENANCE", "", f"- pwd: `{root}`", f"- git commit: `{git_commit}`", "- git status:", "```", git_status.rstrip(), "```",
        f"- PROFILE_FREEZE_V2 SHA256: `{pre['profile_freeze_sha256']}`", f"- frozen pre/post unchanged: `{not modified}`",
        "- DDXPlus inputs: `data/ddxplus/en/release_conditions.json`, `release_evidences.json`, `release_validate_patients`",
        "- DDXPlus TEST: identified but never opened", f"- Step14 mechanical mapping: `{value_rel}` SHA256 `{input_hashes[str(value_rel)]}`",
        "- Step14 columns read: `evidence_id, original_text, base_concept, attribute_location, attribute_severity, attribute_onset, attribute_duration, attribute_frequency, context_history, context_family, context_medication, context_exposure`",
        f"- Step13B mechanical relation matrix: `{old_rel}` SHA256 `{input_hashes[str(old_rel)]}`",
        "- Step13B columns read: `ddxplus_disease, evidence_id, finding, strict_score`",
        f"- Python: `{platform.python_version()}`", f"- command: `{sys.executable} {Path(__file__).name} --root {root}`",
        f"- random seed: `{SEED}`", f"- timestamp UTC: `{datetime.now(timezone.utc).isoformat()}`", "", "## Input SHA256", "",
    ] + [f"- `{p}`: `{h}`" for p, h in input_hashes.items()] + ["", "## pip freeze", "", "```", pip_freeze.rstrip(), "```", ""]
    (out / "PROVENANCE.md").write_text("\n".join(provenance), encoding="utf-8")

    best = max(before_after, key=lambda r: r["v2_strict_coverage"] - r["old_strict_coverage"])
    report = f"""# STEP 15 v2 EVALUATION REPORT

## Validity

- Independence violation: {summary['independence_violation']}
- Freeze integrity: {summary['freeze_integrity']}; modified files: {modified or 'none'}
- TEST patient reads: 0
- Pilot diseases present: {summary['pilot_evaluable']}/10

## Coverage

- Existing KG strict: {old_strict:.4f}
- v2 BASIC strict / lenient: {all_cov['strict_coverage']:.4f} / {all_cov['lenient_coverage']:.4f}
- v2 VALUE strict / lenient: {value_cov['strict_coverage']:.4f} / {value_cov['lenient_coverage']:.4f}
- Largest strict gain: {best['disease']} ({best['v2_strict_coverage'] - best['old_strict_coverage']:.4f})

## Pair observability

- Medically discriminative frozen features: {len(pair_rows)}
- Experimentally observable in DDXPlus: {observable_n}
- Missing discriminative features: {missing_n}

## Decision

**{decision}**

The decision used thresholds fixed in the evaluator before reading aggregate results. It does not evaluate TEST performance or a verifier score.

## Main limitation

Automated conservative mappings remain hypotheses, not clinician adjudications. Rows marked for HIGH review can change coverage and pair-observability counts; they are isolated in `11_evaluation_critical_review_queue.csv`.
"""
    (out / "STEP15V2_EVALUATION_REPORT.md").write_text(report, encoding="utf-8")

    required_outputs = [
        "00_freeze_integrity.json", "01_ddxplus_schema_audit.json", "02_ddxplus_profile_mapping.csv", "03_disease_coverage.csv", "04_before_after_knowledge_coverage.csv", "05_pair_observability.csv", "06_missing_discriminative_information.csv", "07_patient_observability_validation.csv", "08_validation_error_pair_audit.csv", "09_followup_question_opportunities.csv", "10_future_profile_revision_queue.csv", "11_evaluation_critical_review_queue.csv", "12_summary.json", "PROVENANCE.md", "READ_FILES_AUDIT.txt", "STEP15V2_EVALUATION_REPORT.md", "step15v2_evaluate.py", "test_step15v2_evaluate.py",
    ]
    hashes = {name: sha256_file(out / name) for name in required_outputs if (out / name).exists()}
    json_dump(out / "OUTPUT_SHA256.json", hashes)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.home() / "medmap")
    args = ap.parse_args()
    root = args.root.resolve()
    out = root / "exp/step15_v2_evaluation"
    try:
        summary = evaluate(root, out)
    except InvalidFreezeError:
        print("STEP15V2_EVAL_INVALID_FREEZE", file=sys.stderr)
        return 2
    print(json.dumps({"status": "complete", "next_step": summary["next_step"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
