"""연구용 진단 기준 분류(RESEARCH_ONLY). 지침의 진단 등급(DIAGNOSTIC_CLASSIFICATION)을 표현하며, MedMap 근거 방향(EVIDENCE_DIRECTION)으로 바꾸지 않는다.
- 심낭염: ESC 2025 Table 4(임상 양상 + 추가 기준 개수). 영상 2항목 계산은 CRQ-15 미결이라 두 방식을 함께 출력
- 급성·만성 심근손상: UDMI5 Box 1·2. 손상 기준 충족 ≠ MI(UDMI5 §5: 허혈 근거 필요)
기준 사실은 그래프·평면표가 같은 함수(criterion_facts_*)로 만든다."""
from __future__ import annotations

import re

from . import logic as L
from . import observations as OB

RESEARCH = "RESEARCH_ONLY_NOT_VALIDATED"
CHEST = {"HP:0100749", "HP:0033771"}                 # Chest pain, Pleuritic chest pain
RUB, EFF, CRP_HP = "HP:0034788", "HP:0001698", "HP:0011227"
R_NEWEFF = re.compile(r"\b(?:new|newly|worsening|increasing|increased|enlarging)\b", re.I)
R_CMR = re.compile(r"\b(?:CMR|cardiac (?:MRI|magnetic resonance)|cardiovascular magnetic resonance)\b", re.I)
R_CMR_PERI = re.compile(r"\bpericardial\s+(?:o?edema|late gadolinium enhancement|LGE|enhancement)\b|\bLGE of the pericardium\b", re.I)
R_NEG_NEAR = re.compile(r"\b(?:no|without|absence of|negative for)\b[^.;]{0,30}$", re.I)
R_TROP_DYN = re.compile(r"\btroponin[^.;]{0,40}\b(rose|rising|rise and fall|rise and/or fall|increased from|fell|falling|dynamic (?:change|rise))\b", re.I)
R_TROP_FLAT = re.compile(r"\btroponin[^.;]{0,40}\b(unchanged|flat|stable without (?:a )?(?:rise|change)|no dynamic change)\b", re.I)
R_STABLE = re.compile(r"\b(?:clinically stable|stable clinical setting|outpatient follow-up|routine (?:clinic|outpatient))\b", re.I)


def existential(criterion_id: str, items: list) -> "L.Fact":
    """'값이 하나라도 기준을 넘는가'형 기준: 서로 다른 측정값은 모순이 아님. TRUE 하나면 TRUE, 전부 FALSE 일 때만 FALSE, 판정 불가 값이 섞이면 TRUE 없을 때 UNKNOWN."""
    if any(v is True for v, _ in items):
        return L.Fact(criterion_id, "FOUND", True, (True,), tuple(s for v, s in items if v is True))
    if items and all(v is False for v, _ in items):
        return L.Fact(criterion_id, "FOUND", False, (False,), tuple(s for _, s in items))
    return L.Fact(criterion_id, "NOT_FOUND", None, (), tuple(s for _, s in items))


def criterion_facts_pericarditis(evidence: list, ecg_findings: list, observations: list, records: list, structured: dict | None = None) -> dict:
    """증거 행 → 기준 사실. FALSE 는 '평가했고 음성'이라는 기록이 있을 때만. 같은 기준 중복 근거는 하나로(combine_evidence)."""
    acc = {k: [] for k in ("CLINICAL_PRESENTATION", "PERI_RUB", "ECG_PR_DEPRESSION", "ECG_WIDESPREAD_STE", "PERI_CRP", "PERI_EFFUSION_NEW_OR_WORSENING", "PERI_CMR_OEDEMA_LGE")}
    for e in evidence:
        c, a, eid = e.get("base_concept") or e.get("concept_id"), e["assertion_status"], e["evidence_id"]
        if e.get("v5_override"):
            continue
        if c in CHEST and a == "PRESENT":
            acc["CLINICAL_PRESENTATION"].append((True, eid))          # 흉통 부정은 다른 임상 양상 가능성 때문에 FALSE 로 쓰지 않음
        if c == RUB and a in ("PRESENT", "NEGATED"):
            acc["PERI_RUB"].append((a == "PRESENT", eid))
        if c == EFF and a == "NEGATED":
            acc["PERI_EFFUSION_NEW_OR_WORSENING"].append((False, eid))
        if c == EFF and a == "PRESENT" and R_NEWEFF.search(e["sentence"]):
            acc["PERI_EFFUSION_NEW_OR_WORSENING"].append((True, eid))
        if c == CRP_HP and a in ("PRESENT", "NEGATED"):
            acc["PERI_CRP"].append((a == "PRESENT", eid))
    for f in ecg_findings:
        t, a, fid = f["finding_type"], f["assertion_status"], f["finding_id"]
        if t == "NORMAL_ECG" and a == "PRESENT":
            acc["ECG_PR_DEPRESSION"].append((False, fid))
            acc["ECG_WIDESPREAD_STE"].append((False, fid))
        if t == "PR_DEPRESSION" and a in ("PRESENT", "NEGATED"):
            acc["ECG_PR_DEPRESSION"].append((a == "PRESENT", fid))
        if t == "ST_ELEVATION" and a == "PRESENT" and f["lead_or_distribution"]["distribution"] == "DIFFUSE":
            acc["ECG_WIDESPREAD_STE"].append((True, fid))
        if t == "ST_ELEVATION" and (a == "NEGATED" or (a == "PRESENT" and f["lead_or_distribution"]["distribution"] == "REGIONAL")):
            acc["ECG_WIDESPREAD_STE"].append((False, fid))             # 국소 ST 상승은 '광범위'가 아님
    crp_obs = []                                                          # 측정값(서로 다른 시점)은 존재 기준으로 합침
    for o in observations:
        if o["analyte"] != "CRP":
            continue
        q = o["result_qualifier"]
        if q in ("elevated", "raised", "increased", "high", "positive"):
            crp_obs.append((True, o["obs_id"]))
        elif q in ("normal", "within normal limits", "negative", "undetectable"):
            crp_obs.append((False, o["obs_id"]))
        else:
            rc = OB.above_reference(OB.Observation(**{k: o[k] for k in OB.Observation.__dataclass_fields__}))
            crp_obs.append(((rc["status"] == "ABOVE") if rc["status"] in ("ABOVE", "NOT_ABOVE") else None, o["obs_id"]))
    for r in records:
        for sent in re.split(r"(?<=[.;])\s+", r["text"]):
            m = R_CMR_PERI.search(sent)
            if R_CMR.search(sent) and m:
                acc["PERI_CMR_OEDEMA_LGE"].append((not R_NEG_NEAR.search(sent[:m.start()]), f"{r['record_id']}:CMR"))
    for k, v in (structured or {}).items():
        acc[k] += v
    out = {k: L.combine_evidence(k, v) for k, v in acc.items()}
    if crp_obs:                                                           # 진술(HPO)과 측정값이 함께면: 진술 충돌은 유지, 측정값은 존재 기준
        m = existential("PERI_CRP", crp_obs)
        stated = out["PERI_CRP"]
        if stated.status == "NOT_FOUND":
            out["PERI_CRP"] = m
        elif m.status == "FOUND" and stated.status == "FOUND" and m.value != stated.value:
            out["PERI_CRP"] = L.Fact("PERI_CRP", "CONFLICT", None, (True, False), stated.sources + m.sources)
    return out


def _A(k):
    return L.Atom(k, (True,))


def pericarditis_classification(facts: dict, episode_id: str, as_of: float) -> dict:
    ecg = L.Or((_A("ECG_PR_DEPRESSION"), _A("ECG_WIDESPREAD_STE")))
    crit5 = (("PERI_RUB", _A("PERI_RUB")), ("PERI_ECG", ecg), ("PERI_CRP", _A("PERI_CRP")), ("PERI_EFFUSION", _A("PERI_EFFUSION_NEW_OR_WORSENING")), ("PERI_CMR", _A("PERI_CMR_OEDEMA_LGE")))
    crit4 = crit5[:3] + (("PERI_IMAGING_MERGED", L.Or((_A("PERI_EFFUSION_NEW_OR_WORSENING"), _A("PERI_CMR_OEDEMA_LGE")))),)

    def grade(crit):
        al2 = L.eval_kofn(L.KofN("AL2", "AT_LEAST_K", 2, crit), facts)
        ex1 = L.eval_kofn(L.KofN("EX1", "EXACTLY_K", 1, crit), facts)
        ex0 = L.eval_kofn(L.KofN("EX0", "EXACTLY_K", 0, crit), facts)
        t = al2["minimum_true"]
        g = "DEFINITE" if al2["value"] == L.T else "POSSIBLE" if ex1["value"] == L.T else "UNLIKELY_REJECTED" if ex0["value"] == L.T else \
            "POSSIBLE_OR_DEFINITE_UNRESOLVED" if t == 1 else "GRADE_UNDETERMINED"
        unc = "NONE" if g in ("DEFINITE", "POSSIBLE", "UNLIKELY_REJECTED") else ("CONFLICT" if al2["conflict_count"] else "UNKNOWN_CRITERIA")
        return g, unc, {"AT_LEAST_2": al2, "EXACTLY_1": ex1, "EXACTLY_0": ex0}
    pre = L.eval5(_A("CLINICAL_PRESENTATION"), facts)
    out = {"classification_id": f"CLS:PERI:{episode_id}:{as_of}", "target_concept": "DX:Pericarditis", "episode_id": episode_id, "as_of": as_of,
           "classification_source": "ESC 2025 myocarditis/pericarditis Table 4 (pericarditis column) + footnote b; v5-0B PERI5-01~03", "clinical_review_status": RESEARCH,
           "related_review_items": ["CRQ-10", "CRQ-11", "CRQ-15"], "evidence_direction": "NOT_DERIVED(지침 등급을 SUPPORT/WEAKEN 으로 바꾸지 않음)",
           "prerequisite_clinical_presentation": pre["value"]}
    if pre["value"] != L.T:
        out.update(guideline_classification="NOT_GENERATED_PREREQUISITE_" + pre["value"], criteria_count_range=None, uncertainty_state="PREREQUISITE_NOT_CONFIRMED",
                   classification_conditions=None)
        return out
    g5, u5, c5 = grade(crit5)
    g4, u4, _ = grade(crit4)
    k = c5["AT_LEAST_2"]
    out.update(guideline_classification=g5, uncertainty_state=u5, criteria_count_range=[k["minimum_true"], k["maximum_possible_true"]],
               criteria_states=k["criteria"], classification_conditions=c5, supporting_evidence_ids=k["supporting_evidence_ids"],
               imaging_count_sensitivity={"two_imaging_items(기본)": g5, "imaging_merged_one_item": g4, "differs": g5 != g4, "note": "CRQ-15 미결 — 어느 쪽도 확정하지 않음"})
    return out


# ---------------- 심근손상(UDMI5 Box 1·2) ----------------
def criterion_facts_injury(series: list, records: list, structured: dict | None = None) -> dict:
    acc = {"INJ_ABOVE_SEX_SPECIFIC_URL": [], "INJ_RISE_OR_FALL_REPORTED": [], "INJ_STABLE_SETTING": []}
    above = []                                                            # 측정값별 (True/False/None) — 존재 기준
    notes = []
    for s in series:
        if not s["analyte"].startswith("TROPONIN"):
            continue
        for p in s["points"]:
            rc = p["reference_check"]
            if rc["status"] in ("ABOVE", "NOT_ABOVE") and rc.get("sex_specific_reference") == "MATCHES_PATIENT_SEX":
                above.append((rc["status"] == "ABOVE", p["obs_id"]))
            else:
                above.append((None, p["obs_id"]))
                if rc["status"] == "ABOVE":
                    notes.append(f"{p['obs_id']}: 검사실 기준 초과이나 성별 99백분위 적용 미확인 → 기준 사실로 쓰지 않음")
        for pr in s["pairs"]:
            if pr["abs_delta"] is not None:
                notes.append(f"{pr['from']}→{pr['to']}: 수학적 변화 {pr['abs_delta']} (UDMI5 §14.1.4: 단일 유의 기준 없음 → 상승·하강 판정에 쓰지 않음)")
    for r in records:
        for m in R_TROP_DYN.finditer(r["text"]):
            acc["INJ_RISE_OR_FALL_REPORTED"].append((True, f"{r['record_id']}:text"))
        for m in R_TROP_FLAT.finditer(r["text"]):
            acc["INJ_RISE_OR_FALL_REPORTED"].append((False, f"{r['record_id']}:text"))
        if R_STABLE.search(r["text"]):
            acc["INJ_STABLE_SETTING"].append((True, f"{r['record_id']}:text"))
    for k, v in (structured or {}).items():
        acc[k] += v
    f = {k: L.combine_evidence(k, v) for k, v in acc.items()}
    f["INJ_ABOVE_SEX_SPECIFIC_URL"] = existential("INJ_ABOVE_SEX_SPECIFIC_URL", above)     # 'at least one value above'
    f["_notes"] = notes
    return f


def injury_classification(facts: dict, series: list, episode_id: str, as_of: float) -> dict:
    notes = facts.get("_notes", [])
    acute = L.eval5(L.And((_A("INJ_ABOVE_SEX_SPECIFIC_URL"), _A("INJ_RISE_OR_FALL_REPORTED"))), facts)
    n_above = sum(1 for s in series if s["analyte"].startswith("TROPONIN") for p in s["points"]
                  if p["reference_check"]["status"] == "ABOVE" and p["reference_check"].get("sex_specific_reference") == "MATCHES_PATIENT_SEX")
    chronic = L.eval5(L.And((L.Atom("_N_ABOVE_GE2", (True,)), _A("INJ_STABLE_SETTING"))),
                      {**facts, "_N_ABOVE_GE2": L.Fact("_N_ABOVE_GE2", "FOUND", n_above >= 2, (n_above >= 2,), ("count",)) if n_above >= 2 else L.Fact("_N_ABOVE_GE2", "NOT_FOUND")})
    m = {L.T: "MEETS_CRITERIA_RESEARCH", L.F: "CRITERIA_NOT_MET", L.U: "UNDETERMINED_UNKNOWN", L.C: "UNDETERMINED_CONFLICT"}
    return {"classification_id": f"CLS:INJ:{episode_id}:{as_of}", "target_concept": "V5:STATE:ACUTE_MYOCARDIAL_INJURY", "episode_id": episode_id, "as_of": as_of,
            "classification_source": "UDMI5 Box 1 (acute), Box 2 (chronic), §14.1.4", "clinical_review_status": RESEARCH,
            "acute_injury": m[acute["value"]], "chronic_injury_considered": m[chronic["value"]], "classification_conditions": {"acute": acute, "chronic": chronic},
            "criteria_states": {k: v.status if v.status != "FOUND" else v.value for k, v in facts.items() if not k.startswith("_")}, "notes": notes,
            "mi_assessment": "NOT_ASSESSED(손상 기준 충족 ≠ 심근경색: UDMI5 §5 허혈 근거 필요, 관계 미활성)", "evidence_direction": "NOT_DERIVED"}
