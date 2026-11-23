"""LEGACY_V4 vs PE_SHADOW_RESEARCH 비교. 같은 환자 그래프·같은 as_of·같은 mode 에서 두 엔진을 돌려 (증거, 관계) 단위로 맞춘다.
분류: SAME_DECISION / SHADOW_MORE_CONSERVATIVE / LEGACY_MORE_CONSERVATIVE / DIFFERENT_DIRECTION / DIFFERENT_APPLICABILITY /
DIFFERENT_MISSING_REQUIREMENTS / SOURCE_INCOMPLETE / SEMANTIC_REVIEW_REQUIRED. 방향 판단 개수로 우열을 매기지 않는다."""
from __future__ import annotations

from . import experiment_matrix as EM

DIR = ("SUPPORT", "WEAKEN")


def ltoken(j):
    if j is None:
        return "NONE"
    if j["stage"] == "UNCONDITIONAL" and j["direction"] not in DIR:
        return "NODIR"
    return EM.token(j["direction"])


def pair(legacy: dict, shadow: dict) -> list:
    """(evidence_id, shadow 관계) 단위 짝. YEARS 처럼 레거시 대응이 없으면 같은 증거의 레거시 판단(없으면 NONE)과 비교."""
    rows = []
    lj = legacy["judgments"]
    for s in shadow["judgments"]:
        cands = [x for x in lj if x["evidence_id"] == s["evidence_id"] and x["relation_id"] == (s["legacy_counterpart"] or "")]
        l_ = cands[0] if cands else None
        rows.append({"evidence_id": s["evidence_id"], "shadow_relation": s["relation_id"], "legacy_relation": l_["relation_id"] if l_ else None, "legacy": l_, "shadow": s})
    used = {(r["evidence_id"], r["legacy_relation"]) for r in rows}
    for l_ in lj:
        if (l_["evidence_id"], l_["relation_id"]) not in used:
            rows.append({"evidence_id": l_["evidence_id"], "shadow_relation": None, "legacy_relation": l_["relation_id"], "legacy": l_, "shadow": None})
    return rows


def classify(l_, s) -> str:
    tl, ts = ltoken(l_), EM.token(s["direction"]) if s else "NONE"
    if s and s["shadow_status"] == "VTE_TREATMENT_SUFFICIENT_NON_DIRECTIONAL" and tl in DIR:
        return "SEMANTIC_REVIEW_REQUIRED"
    if s and s["shadow_status"] in ("INTERPRETATION_PENDING", "SOURCE_INCOMPLETE") and tl in DIR:
        return "SOURCE_INCOMPLETE"
    if tl == ts:
        if tl == "HOLD" and l_ and s and sorted(l_["missing"]) != sorted(s["missing"]):
            return "DIFFERENT_MISSING_REQUIREMENTS"
        return "SAME_DECISION"
    if tl in DIR and ts in DIR:
        return "DIFFERENT_DIRECTION"
    if ts in DIR:
        return "LEGACY_MORE_CONSERVATIVE"
    if tl in DIR:
        return "DIFFERENT_APPLICABILITY" if ts == "NA" else "SHADOW_MORE_CONSERVATIVE"
    return "DIFFERENT_APPLICABILITY"


def drivers(l_, s) -> list:
    """차이를 만든 조건(Shadow 판단 기록에서 추출)."""
    if not s:
        return ["SHADOW_NO_JUDGMENT"]
    d = []
    fu = s["facts_used"]
    if "haemo_state" in s["missing"]:
        d.append("HAEMO_STABILITY_NOT_DOCUMENTED(정책 " + s["policy"]["haemo"] + ")")
    if fu.get("haemo_state", {}).get("value") == "UNSTABLE" and any("arrest" in x or "obstructive_shock" in x for x in fu["haemo_state"]["sources"]):
        d.append("TABLE4_EXPLICIT_ARREST_OR_SHOCK")
    pr = s["pretest_resolution"]
    if pr["combination"] == "INVARIANT":
        d.append("PRETEST_CONFLICT_OUTCOME_INVARIANT")
    if pr["combination"] == "DEPENDS":
        d.append("PRETEST_CONFLICT_OUTCOME_DEPENDS:" + pr["kind"])
    if pr["kind"] == "LATEST_BEFORE_TEST":
        d.append("PRETEST_POLICY_LATEST_BEFORE_TEST")
    if s["relation_id"] == "SH-DD-YEARS":
        d.append("YEARS_SEPARATE_PATH")
    if fu.get("pretest_two_level", {}).get("status") == "FOUND":
        d.append("TWO_LEVEL_CLASSIFICATION")
    if any("hs_assay_phrase" in x for x in fu.get("ddimer_assay", {}).get("sources", [])):
        d.append("ASSAY_PHRASE_MAPPING(연구용)")
    if s["stage"].startswith("EXCLUSION_GATE_TRUE") and s["note"]:
        d.append("EXCLUSION:" + s["note"][:40])
    if s["shadow_status"] != "RESEARCH_DIRECTIONAL":
        d.append("SHADOW_STATUS:" + s["shadow_status"])
    if l_ and sorted(l_["missing"]) != sorted(s["missing"]):
        add, rem = sorted(set(s["missing"]) - set(l_["missing"])), sorted(set(l_["missing"]) - set(s["missing"]))
        d.append(f"MISSING_DIFF:+{','.join(add)};-{','.join(rem)}")
    return d or ["NONE_IDENTIFIED"]


def compare(legacy: dict, shadow: dict) -> list:
    out = []
    for p in pair(legacy, shadow):
        l_, s = p["legacy"], p["shadow"]
        cat = classify(l_, s)
        out.append({"evidence_id": p["evidence_id"], "legacy_relation": p["legacy_relation"], "shadow_relation": p["shadow_relation"],
                    "legacy": l_ and {k: l_[k] for k in ("direction", "stage", "hold_reason", "missing", "conflicts", "optional_unchecked")},
                    "shadow": s and {k: s[k] for k in ("direction", "stage", "missing", "conflicts", "optional_unchecked", "shadow_status", "clinician_review_required",
                                                       "applied_sources", "source_access", "labels")} | {"pretest_resolution": s["pretest_resolution"]["combination"]},
                    "legacy_token": ltoken(l_), "shadow_token": EM.token(s["direction"]) if s else "NONE", "category": cat,
                    "drivers": drivers(l_, s) if cat != "SAME_DECISION" else [],
                    "candidate_flag": ("LEGACY_OVER_HOLD_CANDIDATE" if cat == "LEGACY_MORE_CONSERVATIVE" else
                                       "LEGACY_PREMATURE_CANDIDATE" if (cat in ("SHADOW_MORE_CONSERVATIVE", "SEMANTIC_REVIEW_REQUIRED", "SOURCE_INCOMPLETE")
                                                                        or (cat == "DIFFERENT_APPLICABILITY" and ltoken(l_) in DIR)) else None)})
    return out
