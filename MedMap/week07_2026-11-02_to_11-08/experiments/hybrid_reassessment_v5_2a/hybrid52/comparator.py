"""다질환 비교(그래프·평면표 공용). 입력 수집만 그래프 순회/평면표 필터로 다르고, 평가는 이 함수 하나로 한다.
v5-1 evaluate_common(연구용 분류·시계열·후보)을 그대로 호출한 뒤, 가설별 기준 행·증거 연결·부족 정보·중복/종속·공통/차별 소견을 붙인다.
확률·순위·가중치·신규 SUPPORT/WEAKEN 없음. Working Diagnosis 자동 변경 없음."""
from __future__ import annotations

from hybrid5.graphs import evaluate_common

from . import ACTIVE_DIRECTION_RELATIONS_V52, CLINICAL_VALIDATION_STATUS
from . import criteria as CR, dependency as DP, evidence_linker as EL
from .hypotheses import MUTUAL_EXCLUSIVITY

LIMITATIONS = [
    "합성 사례 기반 기술 검증. 임상 성능 NOT_EVALUATED.",
    "신규 진단 방향(SUPPORT/WEAKEN) 관계 0건 — 가설 간 우열·확률·순위 없음.",
    "심낭염·심근손상 기준은 연구용(RESEARCH_ONLY_NOT_VALIDATED). 기준 충족 ≠ 확진.",
    "PE 판단은 v4 레거시(LEGACY_V4_UNVALIDATED). 전문의 검토 전.",
    "중복·종속은 명시 메타데이터만 사용. 메타데이터 없으면 DEPENDENCY_UNKNOWN.",
    "추출 범위는 v3·v5-1 사전·정규식 한계를 그대로 가짐(UNSUPPORTED_EXTRACTION 로 표시).",
]


def compare_common(specs: list, legacy: dict, bundle: dict, sex: str, as_of: float, mode: str) -> dict:
    eps = bundle["episodes"]
    unres = bundle["unresolved"]
    base = evaluate_common([s.to_multi() for s in specs], legacy, eps, sex, as_of, mode)
    base_by = {h["hyp_id"]: h for h in base["hypotheses"]}
    cats = {ep: EL.catalog(eps[ep]) for ep in sorted(eps)}
    ucat = EL.catalog(unres)
    item_meta = {i: {"source_record_id": r["source_record_id"], "available_time": r["available_time"]} for c in list(cats.values()) + [ucat] for i, r in c.items()}
    dep = DP.analyze([r for c in list(cats.values()) + [ucat] for r in c.values()], bundle["meta"])
    hyps, item_hyps = [], {}
    for s in sorted(specs, key=lambda x: x.hypothesis_id):
        row = {**s.as_row(), "as_of": as_of}
        if s.evaluation_time > as_of:
            row.update(hypothesis_status_at_as_of="NOT_APPLICABLE_AT_AS_OF", gaps=[{"category": "NOT_APPLICABLE", "reason": "as_of 이후에 제기된 가설"}])
            hyps.append(row)
            continue
        ep = s.diagnosis_episode_id
        inp, cat = eps[ep], cats[ep]
        rows, facts_by = CR.evaluate(s, inp, sex, as_of, item_meta)
        CR.attach_gaps(rows, facts_by, s, inp, unres, sex, as_of)
        leg = legacy.get(s.hypothesis_id, []) if s.family == "PE" else []
        links = EL.link(s, cat, rows, leg)
        for iid, l_ in links.items():
            item_hyps.setdefault(iid, []).append((s.hypothesis_id, l_["link_basis"]))
        b = base_by[s.hypothesis_id]
        for r in rows:
            r["source_dependency"] = DP.source_dependency(r["input_item_ids"], dep)
        gaps = [{"condition_id": r["condition_id"], "criterion_id": r["criterion_id"], **r["gap"]} for r in rows
                if r["gap"] and r["gap"]["category"] != "SEE_COMPONENT_CRITERIA"] + CR.legacy_gaps(s, inp, as_of)
        row.update(
            hypothesis_status_at_as_of="EVALUATED", directional_relation_status=EL.LEGACY if s.family == "PE" else EL.NO_DIR,
            supporting_evidence_ids=[], weakening_evidence_ids=[],
            evidence_ids=sorted(links), source_record_ids=sorted({CR._rec(i, item_meta) for i in links}),
            evaluated_criteria=[r["criterion_id"] for r in rows if r["evaluation_result"] in (CR.T, CR.F)],
            unresolved_criteria=[r["criterion_id"] for r in rows if r["evaluation_result"] in (CR.U, CR.C)],
            no_verified_rule_criteria=[r["criterion_id"] for r in rows if r["criterion_role"] == "NO_VERIFIED_RULE"],
            condition_evaluations=rows, evidence_links=links, present_not_linked=sorted(set(cat) - set(links)),
            excluded_other_episode_items=sorted(i for e2, c2 in cats.items() if e2 != ep for i in c2),
            gaps=gaps, research_classifications=b["classifications"], series=b["series"],
            v51_consistency_mismatches=CR.consistency_with_v51(rows, b["classifications"]),
            legacy_v4={"label": EL.LEGACY + "(전문의 검토 전, v5 검증 결과 아님)",
                       "items": [{**i, "dependency_group_id": dep["items"].get(i["evidence_id"], {}).get("dependency_group_id"),
                                  "duplicate_group_id": dep["items"].get(i["evidence_id"], {}).get("duplicate_group_id")} for i in leg],
                       "same_source_note": "v4 는 표현마다 따로 판단함 — duplicate_group_id 가 같은 항목은 같은 원본 사건(독립 근거 아님)"} if s.family == "PE" else None)
        hyps.append(row)
    for iid, hs in item_hyps.items():
        if iid in dep["items"] and len(hs) >= 2:
            dep["items"][iid]["shared_evidence_hypotheses"] = sorted(h for h, _ in hs)
    hyp_eps = sorted({s.diagnosis_episode_id for s in specs if s.evaluation_time <= as_of})
    shared, specific, unlinked = [], [], []
    for ep in hyp_eps:
        for iid, it in sorted(cats[ep].items()):
            hs = item_hyps.get(iid, [])
            if len(hs) >= 2:
                shared.append({"item_id": iid, "class": "SHARED_FINDING", "hypotheses": sorted(h for h, _ in hs), "link_basis": {h: b for h, b in hs},
                               "interpretation": "USED_IN_MULTIPLE_EVALUATIONS_NOT_SUPPORT(여러 질환 지지·특이성·동시 확진·타 질환 약화 의미 없음)"})
            elif len(hs) == 1:
                specific.append({"item_id": iid, "class": "HYPOTHESIS_SPECIFIC_CRITERION" if "CRITERION_INPUT" in hs[0][1] else "LEGACY_V4_ONLY_LINK",
                                 "hypothesis": hs[0][0], "interpretation": "현재 등록 기준 구조에서 이 가설의 평가 항목일 뿐 — 다른 질환에서 나타날 수 없다는 뜻 아님"})
            else:
                c = EL.classify_unlinked(it)
                unlinked.append({"item_id": iid, "class": c, "label": it["label"], "source_record_id": it["source_record_id"], "meaning": EL.UNLINKED_CLASSES[c]})
        unlinked += EL.record_level_findings(eps[ep])
    unlinked += [{"item_id": iid, "class": "UNRESOLVED_EPISODE", "label": it["label"], "source_record_id": it["source_record_id"],
                  "meaning": EL.UNLINKED_CLASSES["UNRESOLVED_EPISODE"]} for iid, it in sorted(ucat.items())]
    unlinked += [{"item_id": p["record_key"], "class": "RESULT_NOT_YET_AVAILABLE", "label": "", "source_record_id": p["record_key"],
                  "meaning": EL.UNLINKED_CLASSES["RESULT_NOT_YET_AVAILABLE"]} for p in bundle["provenance"] if p["status_at_as_of"] == "NOT_YET_AVAILABLE"]
    ev_rows = [r for h in hyps for r in h.get("condition_evaluations", [])]
    gaps = [{"hypothesis_id": h["hypothesis_id"], **g} for h in hyps for g in h.get("gaps", [])]
    return {
        "patient_id": bundle["patient_id"], "as_of": as_of, "mode": mode,
        "working_diagnosis": [s.hypothesis_id for s in specs if s.is_working_diagnosis], "mutual_exclusivity": MUTUAL_EXCLUSIVITY,
        "hypotheses": hyps, "shared_findings": shared, "hypothesis_specific_findings": specific,
        "condition_evaluations": ev_rows,
        "condition_satisfied": [r["condition_id"] for r in ev_rows if r["evaluation_result"] == CR.T],
        "condition_unresolved": [r["condition_id"] for r in ev_rows if r["evaluation_result"] in (CR.U, CR.C)],
        "duplicate_evidence_groups": dep["duplicate_groups"], "dependency_groups": dep["dependency_groups"], "dependency_items": dep["items"],
        "value_discrepancies": dep["value_discrepancies"], "dependency_policy": dep["policy"],
        "missing_information": [g for g in gaps if g["category"] == "MISSING_INFORMATION"],
        "pending_results": [g for g in gaps if g["category"] == "PENDING_RESULT"],
        "conflicting_information": [g for g in gaps if g["category"] == "CONFLICTING_INFORMATION"],
        "unresolved_episode_links": [g for g in gaps if g["category"] == "UNRESOLVED_EPISODE"],
        "no_verified_rule": [g for g in gaps if g["category"] == "NO_VERIFIED_RULE"],
        "other_gaps": [g for g in gaps if g["category"] in ("UNSUPPORTED_EXTRACTION", "NOT_APPLICABLE")],
        "unmapped_and_unevaluated_findings": unlinked,
        "ai_candidates_unconfirmed": sorted([{k: c[k] for k in ("concept_id", "assertion", "diagnosis_status", "surface", "source_record_id")}
                                             for ep in hyp_eps for c in eps[ep]["candidates"]], key=lambda c: (c["source_record_id"], c["surface"])),
        "source_provenance": bundle["provenance"],
        "active_direction_relations_v5_2a": ACTIVE_DIRECTION_RELATIONS_V52, "clinical_validation_status": CLINICAL_VALIDATION_STATUS,
        "limitations": LIMITATIONS}
