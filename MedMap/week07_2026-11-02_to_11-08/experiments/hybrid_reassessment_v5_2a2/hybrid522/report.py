"""세 결과를 섞지 않고 따로 설명한다. 가상 비교는 실제 과거 판단·인과 증명이 아님을 매번 적는다."""
from __future__ import annotations

from . import COUNTERFACTUAL, EVENT_HISTORY, PATIENT_HISTORY

KO = {"WEAKEN": "약화", "SUPPORT": "지지", "UNCERTAIN": "불확실", "ABSTAIN": "보류", "INSUFFICIENT_EVIDENCE": "근거 부족", "NOT_APPLICABLE": "적용 제외"}


def _d(x):
    return f"{KO.get(x[0], x[0])}{'(' + x[1] + ')' if x[1] else ''}" if x else "없음"


def render(res: dict, title: str = "") -> str:
    L = [f"### {title or res['patient_id']}", "", "**A. 검사 사건별 판독 이력(직접 귀속 판단만)**"]
    for e in res[EVENT_HISTORY]["events"]:
        L.append(f"- 사건 {e['event_key']}: 상태 {[(s['as_of'], s['event_state']) for s in e['state_timeline']][-1]}")
        for v in e["versions"]:
            L.append(f"  - {v['version_id']} 기록 {v['source_record_id']} 공개 {v['available_time']} 정정 {v['correction_time']}")
            for j in v["direct_judgment_summary"]:
                if j["raw_kind"] != "RAW_DIRECTIONAL_JUDGMENT":
                    continue
                L.append(f"    - {j['relation_id']}: 공개 시점({j['first_observed_as_of']}) {_d(j['first_observed_result'])}" +
                         ("" if j["stable_within_validity"] else f" → 유효 구간 안 변화 {[_d(x) for x in j['results_over_validity']]} (문맥 출처 {j['context_record_ids']})"))
    for u in res[EVENT_HISTORY]["unresolved_event_links"]:
        if u["judgment_observations"]:
            L.append(f"- 사건 미연결 기록 {u['record_key']}: {u['status']} {u['issues']} — 판단 귀속 ATTRIBUTION_UNRESOLVED")
    L += ["", "**B. 환자 전체 as_of 이력(그 시점 전체 정보 기준)**"]
    for s in res[PATIENT_HISTORY]["snapshots"]:
        d = s["diff_from_previous"]
        ch = "" if not d else f" · 새 기록 {d['newly_available_record_ids']} · 정정 {d['corrected_record_ids']} · 변화 원인 {[c['cause'] for c in d['step_changes']]}"
        L.append(f"- as_of {s['as_of']}: 판단 {[(r['relation_id'], _d([r['directional_result'], r['hold_reason']])) for r in s['raw_judgments'] if r['raw_kind'] == 'RAW_DIRECTIONAL_JUDGMENT']}{ch}")
    L += ["", "**C. 정정만 바꾼 가상 비교(COUNTERFACTUAL_REPLAY · NOT_HISTORICAL_OBSERVATION · NOT_CAUSAL_PROOF)**"]
    for c in res[COUNTERFACTUAL]["comparisons"]:
        if not c["performed"]:
            L.append(f"- {c['changed_event_key']}: 비교 안 함 — {c['reason']}")
            continue
        L.append(f"- {c['changed_event_key']} {c['before_version_id']}→{c['after_version_id']} @T_ref={c['reference_time']}: 고정 문맥 동일 {c['fixed_context_identical']}, "
                 f"차이 {[(x['relation_id'], x['record_role'], _d(x['before']), _d(x['after'])) for x in c['difference']]}. {c['statement']}")
    L.append("")
    return "\n".join(L)
