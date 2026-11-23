"""원시 판단과 근거 그룹을 분리해 설명. '동일 사건' 문장은 명시 메타데이터로 확인된 그룹에만 쓴다.
그룹 수를 증거 강도·확률·독립 근거 수로 표현하지 않는다."""
from __future__ import annotations

from . import grouping as GP

DIR_KO = {"WEAKEN": "약화", "SUPPORT": "지지", "UNCERTAIN": "불확실", "ABSTAIN": "판단 보류", "INSUFFICIENT_EVIDENCE": "근거 부족", "NOT_APPLICABLE": "적용 제외"}
DX_KO = {"DX:Pulmonary embolism": "폐색전증", "V5:DX:ACS": "급성관상동맥증후군", "V5:DX:MI": "심근경색", "DX:Pericarditis": "심낭염",
         "V5:STATE:ACUTE_MYOCARDIAL_INJURY": "급성 심근손상"}


def statements(raw: list, groups: list) -> list:
    out = []
    by = {r["raw_id"]: r for r in raw}
    for g in groups:
        if g["group_kind"] != GP.DIRECTIONAL:
            continue
        r0 = by.get(g["raw_judgment_ids"][0])
        dx = DX_KO.get(r0["disease_concept_id"], r0["disease_concept_id"]) if r0 else g["hypothesis_id"]
        d = DIR_KO.get(g["directional_result"], g["directional_result"])
        n = len(g["raw_judgment_ids"])
        if g["dependency_status"] in (GP.SAME_EVENT, GP.EXACT) and n >= 2:
            out.append({"group_id": g["group_id"], "text": f"{dx} {d} 판단(레거시 v4, 미검증)이 {n}개 출력됐지만, 동일 검사 사건({g['source_event_id']})에서 파생된 기록"
                                                          f"({', '.join(g['source_record_ids'])})으로 확인돼 근거 그룹 1개로 표시했습니다. 원시 판단 {n}개와 출처는 모두 보존합니다."})
        elif g["dependency_status"] == GP.UNKNOWN:
            out.append({"group_id": g["group_id"], "text": f"{dx} {d} 판단 1개(기록 {', '.join(g['source_record_ids'])})는 같은 검사 사건인지 확인할 메타데이터가 없어 "
                                                          f"종속 여부 미확인으로 표시했습니다({g['grouping_reason']}). 독립 근거라는 뜻이 아닙니다."})
        elif g["dependency_status"] == GP.SUPERSEDED:
            out.append({"group_id": g["group_id"], "text": f"{dx} {d} 판단(기록 {', '.join(g['source_record_ids'])})은 이후 정정 기록으로 대체됐습니다"
                                                          f"({g['correction_status']}). 감사용으로 보존하며 현재 판단이 아닙니다."})
        if g["conflict_status"] != "NONE":
            out.append({"group_id": g["group_id"], "text": f"같은 검사 사건({g['source_event_id']})의 기록끼리 결과가 다릅니다(충돌 그룹 {g['conflict_partner_groups']}). "
                                                          "정정 관계가 없어 어느 쪽도 선택하지 않았습니다."})
    return out


def render(res: dict, title: str = "") -> str:
    eg = res["evidence_grouping"]
    L = [f"### 근거 그룹 — {title or res['patient_id']} (as_of={res['as_of']})", ""]
    for h, c in sorted(eg["counts_by_hypothesis"].items()):
        d = c["directional"]
        L.append(f"- {h}: 레거시 방향 원시 판단 {d['raw_count']}개 · 그룹 {d['group_count']}개 · 중복 연결 {d['raw_in_multi_member_groups']}개 · "
                 f"종속 미확인 {d['dependency_unknown_raw']}개 · 충돌 그룹 {d['conflict_groups']}개 · 정정된 그룹 {d['superseded_groups']}개 / "
                 f"기준 입력 원시 {c['criterion_input']['raw_count']}개 · 그룹 {c['criterion_input']['group_count']}개")
    for s in eg["statements"]:
        L.append(f"  - {s['text']}")
    if eg["unresolved_episode_records"]:
        L.append(f"- 에피소드 불명 기록(사용 안 함): {', '.join(x['record_key'] for x in eg['unresolved_episode_records'])}")
    L += ["- 그룹 수는 증거 강도·확률·통계적 독립 근거 수가 아닙니다. 레거시 판단은 LEGACY_V4_UNVALIDATED, 임상 성능 NOT_EVALUATED.", ""]
    return "\n".join(L)
