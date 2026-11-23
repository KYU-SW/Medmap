"""ACS·MI 와 심낭염 연구용 기준 비교 + 다질환 연구 비교. 재사용: v5-2A 비교 엔진(pg.compare: 기준 행·시계열·연구 분류), v5-2A 입력 수집(pg.collect),
v5-1 classification(criterion_facts_pericarditis, pericarditis_classification). 방향 판단(SUPPORT/WEAKEN) 생성 없음, 점수·확률·순위 없음.
- MI: 관찰값 / 기준 상태 / 미확인 / 연구 분류 / 미지원 판단 / 출처를 분리. 단일 검사 배제 경로(§14.1.3, 분류 목적)와 MI 기준 미충족(§6·§14.1.5 정의)을 구분.
- 심낭염: CRQ-15 영상 계수 정책 A/B/C, 임상 양상 BROAD/STRICT 를 나란히 계산. 등급 → 방향 변환 금지."""
from __future__ import annotations

import re

from hybrid5 import classification as CL
from hybrid5 import logic as L

UNSUPPORTED = {"MI_SUPPORT": "NOT_DERIVED(검증된 방향 관계 없음)", "MI_WEAKEN": "NOT_DERIVED", "ACS_SUPPORT": "NOT_DERIVED"}
R_ISCH_SYM = re.compile(r"\b(isch(?:a)?emic chest pain|angina|chest (?:pressure|tightness)|squeezing chest)\b", re.I)
R_RULEOUT_LOW = re.compile(r"\b(below the limit of detection|undetectable|below the (?:limit of quantification|risk[- ]stratification threshold))\b", re.I)
R_EARLY = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hours?)\s+after\s+(?:symptom|pain|chest pain)\s+onset\b", re.I)
R_RULEIN = re.compile(r"\b(rule[- ]in|0\s*/\s*1\s*h|0h/1h)\b[^.]{0,60}\b(algorithm|pathway|threshold|zone)\b|\b(algorithm|pathway)\b[^.]{0,40}\brule[- ]in\b", re.I)
R_POSITIONAL = re.compile(r"\b(positional|worse (?:when )?lying|better (?:when )?sitting|leaning forward|worse on inspiration|pleuritic)\b", re.I)
ISCH_ECG = ("ST_ELEVATION", "ST_DEPRESSION", "T_WAVE_INVERSION", "Q_WAVES", "LBBB")


def _hyp(res, family):
    return [h for h in res["hypotheses"] if h.get("family") == family and h.get("hypothesis_status_at_as_of") == "EVALUATED"]


def mi_research(pg, as_of: float) -> list:
    res = pg.compare(as_of)
    bundle = pg.collect(as_of)
    out = []
    for h in _hyp(res, "MI") + _hyp(res, "ACS"):
        inp = bundle["episodes"][h["diagnosis_episode_id"]]
        rows = {r["criterion_id"]: r["evaluation_result"] for r in h["condition_evaluations"]}
        pts = [p | {"analyte": s["analyte"]} for s in h["series"] if s["analyte"].startswith("TROPONIN") for p in s["points"]]
        pairs = [p for s in h["series"] if s["analyte"].startswith("TROPONIN") for p in s["pairs"]]
        texts = " ".join(r["text"] for r in inp["records"])
        ecg = [f for f in inp["ecg"] if f["finding_type"] in ISCH_ECG and f["assertion_status"] == "PRESENT" and not (f["finding_type"] == "ST_ELEVATION"
                                                                                                                  and f["lead_or_distribution"].get("distribution") == "DIFFUSE")]
        ecg_new = [f for f in ecg if f["temporal_context"] in ("NEW",)]
        chest = [e for e in inp["evidence"] if (e.get("base_concept") in CL.CHEST) and e["assertion_status"] == "PRESENT"]
        acute = rows.get("ACUTE_INJURY_RESEARCH")
        isch_ecg = "TRUE(새·추정 새 변화 기록)" if ecg_new else ("UNKNOWN(변화 있으나 '새로운' 여부 미기록)" if ecg else "NOT_RECORDED")
        isch_sym = "DESCRIBED_POSSIBLY_ISCHAEMIC_UNADJUDICATED(CRQ-06)" if R_ISCH_SYM.search(texts) else ("NONSPECIFIC_CHEST_PAIN(§12 비특이)" if chest else "NOT_RECORDED")
        if acute == L.T and ecg_new:
            box3 = "BOX3_LIKELY_COMPONENTS_PRESENT_ECG_PATH(다른 급성 질환 유발 여부 미평가 — MI 확정 아님)"
        elif acute == L.T:
            box3 = "ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가)"
        else:
            box3 = "NOT_ASSESSABLE(급성 심근손상 미확정: " + str(acute) + ")"
        early = [float(m.group(1)) for m in R_EARLY.finditer(texts)]
        if R_RULEOUT_LOW.search(texts):
            rule_out = "SINGLE_SAMPLE_VERY_LOW_STATED → RULE_OUT_PATHWAY_TRIAGE(§14.1.3) — 위험 분류 임계값(§14.1.5), MI 기준 미충족 증명 아님"
            if early and min(early) < 3:
                rule_out += " | 조기 내원(<3h) — Box 6 연속 측정 필요"
        else:
            rule_out = "NOT_APPLICABLE(단일 매우 낮은 값 진술 없음)"
        not_above = [p for p in pts if p["reference_check"]["status"] == "NOT_ABOVE" and p["reference_check"].get("sex_specific_reference") == "MATCHES_PATIENT_SEX"]
        comparable = [p for p in pairs if p["comparable"] is True and p["interval"] is not None]
        if len(pts) >= 2 and len(not_above) == len(pts) and comparable:
            not_met = "NOT_MET_CANDIDATE(모든 값 성별 99백분위 이하·연속·동일 검사법 — 채혈 시점 적정성 미검증, CRQ-07)"
        elif len(pts) == 1 and not_above:
            not_met = "UNKNOWN(단일 측정 — 연속 측정 필요 여부는 경로·내원 시점 의존)"
        else:
            not_met = "UNKNOWN"
        risk = "RISK_STRATIFICATION_ONLY(§14.1.5 — rule-in 은 MI 확정 아님)" if R_RULEIN.search(texts) else "NOT_STATED"
        out.append({"hypothesis_id": h["hypothesis_id"], "family": h["family"], "as_of": as_of,
                    "observations": [{k: p[k] for k in ("obs_id", "analyte", "time", "value", "comparator", "unit", "assay_type", "source_record_id")}
                                     | {"reference_status": p["reference_check"]["status"], "sex_specific": p["reference_check"].get("sex_specific_reference")} for p in pts],
                    "serial_pairs": [{k: p[k] for k in ("from", "to", "comparable", "comparability_reason", "interval", "delta_status")} for p in pairs],
                    "criteria_states": {k: rows.get(k) for k in ("INJ_ABOVE_SEX_SPECIFIC_URL", "INJ_RISE_OR_FALL_REPORTED", "ACUTE_INJURY_RESEARCH")},
                    "ischaemia_evidence": {"ecg": isch_ecg, "ecg_findings": [{k: f[k] for k in ("finding_id", "finding_type", "temporal_context")} for f in ecg],
                                           "symptoms": isch_sym},
                    "research_classification": {"acute_myocardial_injury": acute, "chronic_injury": next((c.get("chronic_injury_considered") for c in h["research_classifications"]), None),
                                                "primary_mi_box3": box3, "mi_rule_out_pathway": rule_out, "mi_criteria_not_met": not_met, "risk_stratification": risk},
                    "unresolved": [g["criterion_id"] + ":" + g["category"] for g in h["gaps"]],
                    "unsupported_judgments": UNSUPPORTED, "directional_output": None,
                    "sources": ["UDMI5 Box 3", "UDMI5 §12", "UDMI5 §14.1.3", "UDMI5 §14.1.4", "UDMI5 §14.1.5 Box 6", "UDMI5 §6"],
                    "clinician_review_required": True, "labels": ["RESEARCH_ONLY", "NOT_CLINICALLY_VALIDATED", "ENGINE_ACTIVE_FALSE"]})
    return out


def pericarditis_research(pg, as_of: float) -> list:
    res = pg.compare(as_of)
    bundle = pg.collect(as_of)
    out = []
    for h in _hyp(res, "PERICARDIAL"):
        inp = bundle["episodes"][h["diagnosis_episode_id"]]
        ev = sorted(inp["evidence"], key=lambda x: x["evidence_id"])
        facts = CL.criterion_facts_pericarditis(ev, sorted(inp["ecg"], key=lambda x: x["finding_id"]), [o.as_row() for o in sorted(inp["obs"], key=lambda o: o.obs_id)], inp["records"])
        texts = " ".join(r["text"] for r in inp["records"])
        strict = dict(facts)
        pleur = [e["evidence_id"] for e in ev if e.get("base_concept") == "HP:0033771" and e["assertion_status"] == "PRESENT" and not e.get("v5_override")]
        if pleur or (facts["CLINICAL_PRESENTATION"].status == "FOUND" and R_POSITIONAL.search(texts)):
            strict["CLINICAL_PRESENTATION"] = L.Fact("CLINICAL_PRESENTATION", "FOUND", True, (True,), tuple(pleur) or ("text:positional",))
        else:
            strict["CLINICAL_PRESENTATION"] = L.Fact("CLINICAL_PRESENTATION", "NOT_FOUND")
        rows = {}
        for pname, f in (("BROAD(흉통 일반, v5-1)", facts), ("STRICT(흉막성·체위성, §4.4.1)", strict)):
            c = CL.pericarditis_classification(f, h["diagnosis_episode_id"], as_of)
            g5 = c.get("guideline_classification")
            g4 = (c.get("imaging_count_sensitivity") or {}).get("imaging_merged_one_item", g5)
            rows[pname] = {"POLICY_A_FIVE_ITEMS": g5, "POLICY_B_IMAGING_MERGED": g4,
                           "POLICY_C_HOLD_IF_DEPENDS": g5 if g5 == g4 else "GRADE_HOLD_CRQ15(A·B 결과 다름)",
                           "criteria_count_range": c.get("criteria_count_range"), "prerequisite": c["prerequisite_clinical_presentation"],
                           "evidence_direction": c["evidence_direction"]}
        out.append({"hypothesis_id": h["hypothesis_id"], "as_of": as_of,
                    "criteria_states": {k: (v.status if v.status != "FOUND" else v.value) for k, v in facts.items()},
                    "policies": rows, "policy_sources": {"A": "Table 4 항목 나열(영상 2항목 각각) — v5-1 기본", "B": "Table 4 'Imaging' 한 행 = 1개(해석)",
                                                         "C": "A·B 다르면 등급 보류(CRQ-15 미결)", "STRICT": "§4.4.1 '대개 흉막성·체위성 흉통' — 해석"},
                    "directional_output": None, "grade_to_direction": "FORBIDDEN(Definite/Possible/Unlikely ≠ SUPPORT/WEAKEN)",
                    "labels": ["RESEARCH_ONLY", "NOT_CLINICALLY_VALIDATED", "ENGINE_ACTIVE_FALSE"]})
    return out


def comparison(pg, as_of: float, shadow: dict) -> dict:
    """MEDMAP_MULTI_DISEASE_RESEARCH_COMPARISON: 질환별 결과를 서로 다른 의미로 나란히 둔다(합산·순위 없음)."""
    res = pg.compare(as_of)
    return {"report_type": "MEDMAP_MULTI_DISEASE_RESEARCH_COMPARISON", "patient_id": pg.pid, "as_of": as_of,
            "PE": {"meaning": "PE_SHADOW_RESEARCH 연구용 방향 라벨(검증 안 됨)", "judgments": [{k: j[k] for k in ("evidence_id", "relation_id", "direction", "stage", "missing")}
                                                                                          for j in shadow["judgments"]]},
            "ACS_MI": {"meaning": "UDMI5 연구용 기준 분류(방향 아님)", "results": mi_research(pg, as_of)},
            "PERICARDITIS": {"meaning": "ESC 2025 Table 4 연구용 등급(방향 아님)", "results": pericarditis_research(pg, as_of)},
            "shared_information": res["shared_findings"], "missing_by_hypothesis": {h["hypothesis_id"]: [g["criterion_id"] + ":" + g["category"] for g in h.get("gaps", [])]
                                                                                 for h in res["hypotheses"]},
            "conflicts": res["conflicting_information"], "unsupported_rules": res["no_verified_rule"], "provenance": res["source_provenance"],
            "combined_score": None, "ranking": None, "note": "질환별 값은 의미가 달라 합치거나 순위화하지 않음. 공통 소견 ≠ 동시 지지", "clinical_validation_status": "NOT_EVALUATED"}
