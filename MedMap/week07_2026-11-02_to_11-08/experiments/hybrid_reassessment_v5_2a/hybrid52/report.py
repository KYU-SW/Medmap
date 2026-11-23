"""비교 결과 → 사람이 읽는 진단 재검토 비교 보고서(한국어 Markdown). 결과에 없는 내용은 채우지 않는다."""
from __future__ import annotations

KO = {"TRUE": "충족", "FALSE": "미충족(음성 명시)", "UNKNOWN": "미확인", "CONFLICT": "충돌", "NOT_EVALUATED_NO_VERIFIED_RULE": "검증 규칙 없음"}
SRC = {"PHYSICIAN_WORKING_DIAGNOSIS": "의사 Working Diagnosis", "PHYSICIAN_ADDITIONAL_HYPOTHESIS": "의사 추가 가설",
       "AI_CANDIDATE_UNCONFIRMED": "AI 미확인 후보", "RECORD_HISTORY": "기록상 과거력"}


def render(res: dict, title: str = "") -> str:
    L = [f"### 다질환 비교 — {title or res['patient_id']} (as_of={res['as_of']})", "",
         f"- 환자: {res['patient_id']} · Working Diagnosis: {', '.join(res['working_diagnosis']) or '없음'} · 가설 간 배타 관계: 가정하지 않음",
         f"- 임상적 판단: {res['clinical_validation_status']} · 신규 방향 관계: {res['active_direction_relations_v5_2a']}건", ""]
    for h in res["hypotheses"]:
        L.append(f"#### {h['hypothesis_id']} — {h['disease_concept_id']} ({SRC[h['hypothesis_source']]}, 의사 확인 {h['physician_confirmation_status']}, 에피소드 {h['diagnosis_episode_id']})")
        if h["hypothesis_status_at_as_of"] != "EVALUATED":
            L += [f"- 이 시점 평가 대상 아님: {h['hypothesis_status_at_as_of']}", ""]
            continue
        L.append(f"- 방향 관계: {h['directional_relation_status']} · 연결 증거 {len(h['evidence_ids'])}개 · 원본 기록 {', '.join(h['source_record_ids']) or '없음'}")
        for r in h["condition_evaluations"]:
            src = ", ".join(r["source_evidence_ids"] or r["input_item_ids"]) or "-"
            g = f" · 이유: {r['gap']['category']}" if r.get("gap") and r["gap"]["category"] != "SEE_COMPONENT_CRITERIA" else ""
            L.append(f"  - {r['criterion_id']}: {KO.get(r['evaluation_result'], r['evaluation_result'])} (출처 {src}){g}")
        for c in h["research_classifications"]:
            grade = c.get("guideline_classification") or c.get("acute_injury")
            L.append(f"  - 연구용 분류 {c['target_concept']}: {grade} — {c['clinical_review_status']}, 방향 {c['evidence_direction']}")
        if h.get("legacy_v4"):
            L.append(f"  - 레거시 v4: {[(i['relation_id'], i['direction']) for i in h['legacy_v4']['items']]} — {h['legacy_v4']['label']}")
        if h["excluded_other_episode_items"]:
            L.append(f"  - 다른 에피소드 정보(적용 안 함): {', '.join(h['excluded_other_episode_items'])}")
        L.append("")
    L.append(f"- 공통 소견(SHARED_FINDING, 지지 의미 없음): {', '.join(f'{s['item_id']}→{s['hypotheses']}' for s in res['shared_findings']) or '없음'}")
    L.append(f"- 중복 증거 그룹: {', '.join(f'{d['duplicate_group_id']}({len(d['members'])}개, {d['relation']})' for d in res['duplicate_evidence_groups']) or '없음'}")
    if res["value_discrepancies"]:
        L.append(f"- 같은 사건 값 불일치(미해결 유지): {[(v['analyte'], v['items']) for v in res['value_discrepancies']]}")
    for key, ko in (("pending_results", "결과 대기"), ("conflicting_information", "충돌"), ("unresolved_episode_links", "에피소드 불명"),
                    ("missing_information", "정보 없음"), ("no_verified_rule", "검증 규칙 없음")):
        if res[key]:
            L.append(f"- {ko}: {', '.join(f'{g['hypothesis_id']}:{g['criterion_id']}' for g in res[key])}")
    un = {}
    for u in res["unmapped_and_unevaluated_findings"]:
        un.setdefault(u["class"], []).append(u["item_id"])
    for c, ids in sorted(un.items()):
        L.append(f"- 미연결·미평가 [{c}]: {', '.join(ids)}")
    L += ["", "한계: " + " / ".join(res["limitations"]), ""]
    return "\n".join(L)
