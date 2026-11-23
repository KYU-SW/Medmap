"""정정만 바꾼 가상 비교. 같은 입력 이력을 다시 쌓되, 지정 사건의 판독 버전 하나만 남겨(나머지 버전 제외) 기준 시점 T_ref 에서 같은 평가기로 평가한다.
결과는 실제 과거 판단이 아니다: COUNTERFACTUAL_REPLAY / NOT_HISTORICAL_OBSERVATION / NOT_CAUSAL_PROOF.
T_ref 이후에 공개된 버전을 쓰면 '주입(INJECTED)'으로 표시한다. 비교 대상 외 입력이 하나라도 다르면 결과를 무효로 표시한다."""
from __future__ import annotations

import dataclasses

from . import COUNTERFACTUAL
from .graphs import PatientGraph522

LABELS = {"comparison_type": COUNTERFACTUAL, "replay_type": "COUNTERFACTUAL_REPLAY", "historical_status": "NOT_HISTORICAL_OBSERVATION", "causal_status": "NOT_CAUSAL_PROOF"}


def replay(pg, keep: str, drop: set, t_ref: float) -> tuple:
    """입력 이력 재생. keep 기록은 정정 관계를 떼고(유일 버전), T_ref 이후 공개분이면 공개 시각을 T_ref 로 당겨 주입."""
    new = PatientGraph522(pg.pid, pg.sex)
    injected = None
    for x in pg.input_log:
        k = x[0]
        if k == "episode":
            new.add_episode(x[1])
        elif k == "hypothesis":
            new.add_hypothesis_spec(x[1])
        elif k == "record":
            doc = x[1]
            if doc.doc_id in drop:
                continue
            if doc.doc_id == keep:
                av = doc.available_at
                if isinstance(av, (int, float)) and av > t_ref:
                    injected = {"record_key": keep, "original_available_time": av, "replay_available_time": t_ref}
                    av = t_ref
                obs = doc.observed_at if not (isinstance(doc.observed_at, (int, float)) and doc.observed_at > av) else av
                doc = dataclasses.replace(doc, supersedes=None, available_at=av, observed_at=obs)
            new.add_record52(doc, x[2], x[3], x[4], x[5])
        elif k == "observation":
            new.add_observation52(x[1], x[2], x[3], x[4])
        elif k == "declare":
            if x[1] not in drop:
                new.declare_meta(x[1], x[2], x[3], x[4])
        elif k == "test":
            new.add_test_order(*x[1:])
    return new, injected


def fixed_context(pg, t_ref: float, exclude: set) -> dict:
    """비교 대상 외 고정 문맥(T_ref 에 공개된 기록·관측·가설·검사·메타데이터) — 두 재생에서 같아야 한다."""
    vis = set(pg.visible_records(t_ref))
    docs = sorted([[d.doc_id, d.text, d.doc_type, d.observed_at, d.available_at, d.supersedes] for k, d in pg.docs.items() if k in vis and k not in exclude])
    obs = sorted([[o.obs_id, o.raw_value, o.observation_time, o.available_time] for o in pg.obs if o.source_type == "STRUCTURED_LAB"
                  and isinstance(o.available_time, (int, float)) and o.available_time <= t_ref])
    meta = sorted([[k, m.source_event_id, list(m.derived_from), m.exact_duplicate_of] for k, m in pg.meta.items() if k not in exclude])
    return {"record_ids": [d[0] for d in docs], "records": docs, "structured_observations": obs, "metadata": meta,
            "hypotheses": [s.as_row() for s in pg.specs], "tests": sorted([[e, t.test_id, t.event, t.at] for e, t in pg.tests]), "sex": pg.sex}


def _compact(c521: dict) -> dict:
    eg = c521["evidence_grouping"]
    return {"raw_judgments": [{k: r[k] for k in ("raw_id", "raw_kind", "hypothesis_id", "relation_id", "evidence_id", "source_record_id", "directional_result", "hold_reason")}
                              for r in eg["raw_judgments"]],
            "evaluation_results": {h["hypothesis_id"]: {r["criterion_id"]: r["evaluation_result"] for r in h.get("condition_evaluations", [])} for h in c521["v5_2a"]["hypotheses"]}}


def compare_pair(pg, event: dict, before: dict, after: dict, t_ref: float, evaluate) -> dict:
    chain = {v["source_record_id"] for v in event["versions"] if v["chain_index"] == before["chain_index"]}
    rb, ra = before["source_record_id"], after["source_record_id"]
    blocked = [k for k, m in pg.meta.items() if k not in chain and set(m.derived_from) & chain]
    base = {**LABELS, "reference_time": t_ref, "changed_event_id": event["source_event_id"], "changed_event_key": event["event_key"],
            "before_version_id": before["version_id"], "after_version_id": after["version_id"], "before_record_id": rb, "after_record_id": ra}
    if blocked:
        return {**base, "performed": False, "reason": f"고정 문맥 기록 {blocked} 이 교체 대상 버전에서 파생됨 — 문맥을 고정할 수 없어 비교하지 않음"}
    gb, ib = replay(pg, rb, chain - {rb}, t_ref)
    ga, ia = replay(pg, ra, chain - {ra}, t_ref)
    fb, fa = fixed_context(gb, t_ref, chain), fixed_context(ga, t_ref, chain)
    cb, ca = _compact(evaluate(gb, t_ref)), _compact(evaluate(ga, t_ref))

    def role(r):
        return "CHANGED_EVENT_VERSION" if r["source_record_id"] in chain else r["source_record_id"]

    kb = {(r["hypothesis_id"], r["raw_kind"], r["relation_id"], role(r)): r for r in cb["raw_judgments"]}
    ka = {(r["hypothesis_id"], r["raw_kind"], r["relation_id"], role(r)): r for r in ca["raw_judgments"]}
    diff = []
    for k in sorted(set(kb) | set(ka), key=str):
        b, a = kb.get(k), ka.get(k)
        bb = b and [b["directional_result"], b["hold_reason"]]
        aa = a and [a["directional_result"], a["hold_reason"]]
        if bb != aa:
            diff.append({"hypothesis_id": k[0], "raw_kind": k[1], "relation_id": k[2], "record_role": k[3], "before": bb, "after": aa,
                         "before_raw_id": b and b["raw_id"], "after_raw_id": a and a["raw_id"]})
    eval_diff = {h: {c: [cb["evaluation_results"][h].get(c), ca["evaluation_results"].get(h, {}).get(c)] for c in cb["evaluation_results"][h]
                     if cb["evaluation_results"][h].get(c) != ca["evaluation_results"].get(h, {}).get(c)} for h in cb["evaluation_results"]}
    same = fb == fa
    return {**base, "performed": True, "fixed_context_identical": same, "fixed_context_record_ids": fb["record_ids"], "fixed_context": fb,
            "injected_versions": [x for x in (ib, ia) if x], "before_result": cb, "after_result": ca, "difference": diff,
            "evaluation_difference": {h: d for h, d in eval_diff.items() if d},
            "statement": ("동일한 기록 문맥을 고정하고 이 사건의 판독 버전만 바꿨을 때 추론 엔진 출력이 달라졌습니다." if diff else
                          "동일한 기록 문맥을 고정하고 이 사건의 판독 버전만 바꿨을 때 추론 엔진 출력은 같았습니다.") +
                         " 실제 과거 판단·실제 진단 변경·인과 증명이 아닙니다." if same else "고정 문맥이 두 재생에서 달라 비교 무효",
            "valid": same}


def run_all(pg, hist: dict, t_ref: float, evaluate) -> list:
    out = []
    for e in hist["events"]:
        if any(v["source_record_id"] in hist["held_records"] for v in e["versions"]):
            out.append({**LABELS, "changed_event_key": e["event_key"], "performed": False, "reason": "정정 관계 순환 — 유효 버전을 정할 수 없어 비교하지 않음"})
            continue
        chains = {}
        for v in e["versions"]:
            chains.setdefault(v["chain_index"], []).append(v)
        for vs in chains.values():
            for b, a in zip(vs, vs[1:]):
                out.append(compare_pair(pg, e, b, a, t_ref, evaluate))
    return out
