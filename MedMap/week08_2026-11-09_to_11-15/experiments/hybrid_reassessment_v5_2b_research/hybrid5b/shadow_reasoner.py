"""PE_SHADOW_RESEARCH 판단기. v4 를 무수정 재사용한다:
- 관계 조회: hybrid4.reason.Reasoner(shadow 카탈로그, mode) 의 find_relations(그래프 = DiseaseKG 순회, 평면 = FlatRuleTable 조회)
- 에피소드 입력: 같은 Reasoner.episode_inputs(그래프 순회 / 평면 행 필터, as_of 공개 정책)
- 조건 평가: hybrid4.reason.evaluate_one(임상 단계·D-dimer 문장 조건 포함) → hybrid4.logic.decide
Shadow 가 더하는 것: 맥락 키(혈역학 상태·2단계·입원·임신·항응고·YEARS), 검사 전 확률 해석 세계(정책), YEARS 별도 경로.
출력 라벨: RESEARCH_ONLY · NOT_CLINICALLY_VALIDATED · ENGINE_ACTIVE_FALSE."""
from __future__ import annotations

from hybrid4 import logic as LG
from hybrid4 import reason as RS4

from . import LABELS
from . import clinical_context as CC
from . import shadow_catalog as SC

DIRECTIONAL = ("SUPPORT", "WEAKEN")
_CACHE = {}


def _reasoner(mode: str, policy: dict):
    key = (mode, tuple(sorted(policy.items())))
    if key not in _CACHE:
        _CACHE[key] = RS4.Reasoner(SC.build(policy), mode)
    return _CACHE[key]


def episode_records(pg, episode_id: str, as_of: float, mode: str) -> list:
    """기록 원문(에피소드·as_of 공개분). graph = EP -HAS_RECORD-> 순회, flat = SOURCE_RECORD 행 필터."""
    vis = set(pg.visible_records(as_of))
    if mode == "graph":
        nodes = [pg.g.nodes[e["dst"]] for e in pg.g.outs(f"EP:{episode_id}", "HAS_RECORD")]
    else:
        nodes = [v for v in pg.g.nodes.values() if v["kind"] == "SOURCE_RECORD" and v["diagnosis_episode_id"] == episode_id]
    return sorted([{"record_id": n["doc_id"], "text": n["text"], "available_time": n["available_time"]} for n in nodes if n["doc_id"] in vis], key=lambda r: r["record_id"])


def _eval_worlds(ev, norm, h, agg, ev_list, facts, vis, worlds):
    outs = []
    for w in worlds:
        a = dict(agg)
        if w == "__CONFLICT__":
            pass                                                   # v4 집계 그대로(CONFLICT)
        elif w is None:
            a["pretest"] = LG.Fact("pretest", "NOT_FOUND")
        else:
            a["pretest"] = LG.Fact("pretest", "FOUND", w, (w,), tuple(agg["pretest"].sources))
        outs.append((w, RS4.evaluate_one(ev, norm, h, a, ev_list, facts, vis)))
    return outs


def _combine(outs, wk):
    sig = {(o["decision"]["direction"], o["decision"]["stage"]) for _, o in outs}
    base = outs[0][1]
    if len(sig) == 1:
        d = dict(base["decision"])
        if len(outs) > 1:
            d["stage"] = d["stage"] + "|PRETEST_OUTCOME_INVARIANT"
        return d, base, "INVARIANT" if len(outs) > 1 else "SINGLE"
    d = dict(base["decision"])
    d.update(direction="INSUFFICIENT_EVIDENCE",
             stage="PRETEST_CONFLICT_OUTCOME_DEPENDS" if wk == "MULTI_SAME_TIME" else "PRETEST_REASSESSMENT_POLICY_UNVERIFIED")
    return d, base, "DEPENDS"


def _row(h, ev, norm, d, used, ctx, pw, combo, outs, mode, policy):
    status = norm.get("shadow_status", "RESEARCH_DIRECTIONAL")
    review = status != "RESEARCH_DIRECTIONAL" or combo == "DEPENDS" or d["stage"].startswith("PRETEST_REASSESSMENT") \
        or ("haemo_state" in d.get("missing", []) and policy["haemo"] != "A_LEGACY_BLOCK_ONLY_IF_UNSTABLE")
    return {"engine": "PE_SHADOW_RESEARCH", "labels": list(LABELS), "mode": mode, "policy": dict(policy), "hyp_id": h.hyp_id, "episode_id": h.episode_id,
            "evidence_id": ev["evidence_id"], "source_record_id": ev["source_record_id"], "finding": (ev.get("finding_state") or {}).get("finding") or norm["finding"],
            "relation_id": norm["relation_id"], "legacy_counterpart": norm.get("legacy_counterpart"), "shadow_status": status,
            "direction": d["direction"], "stage": d["stage"], "note": d.get("note", ""), "missing": sorted(d.get("missing", [])),
            "conflicts": [c.get("key") if isinstance(c, dict) else str(c) for c in d.get("conflicts", [])], "optional_unchecked": sorted(d.get("optional_unchecked", [])),
            "pretest_resolution": {**pw, "combination": combo, "per_world": [{"pretest": w, "direction": o["decision"]["direction"], "stage": o["decision"]["stage"]} for w, o in outs]},
            "facts_used": {k: {"status": v["status"], "value": v["value"], "sources": v["sources"]} for k, v in used.items()},
            "applied_sources": [s["summary"] for s in norm["sources"]], "source_access": sorted({s["access"].split("(")[0] for s in norm["sources"]}),
            "clinician_review_required": bool(review), "context": {"haemodynamic": ctx["haemodynamic"], "years": ctx["years"] if norm["relation_id"] == "SH-DD-YEARS" else None}}


def evaluate(pg, as_of: float, mode: str = "graph", policy: dict | None = None) -> dict:
    pol = {**SC.DEFAULT_POLICY, **(policy or {})}
    rs = _reasoner(mode, pol)
    yrel = SC.years_relation(pol)
    out = {"engine": "PE_SHADOW_RESEARCH", "labels": list(LABELS), "as_of": as_of, "mode": mode, "policy": pol, "patient_id": pg.pid, "judgments": [], "contexts": {}}
    vis = set(pg.visible_records(as_of))
    for h, a in pg.active_hypotheses(as_of):
        if not a.usable_as_hypothesis() or not rs.diagnosis_known(h.concept):
            continue
        ev_list, facts, _unres, _texts = rs.episode_inputs(pg, h.episode_id, as_of)
        recs = episode_records(pg, h.episode_id, as_of, mode)
        agg, ctx = CC.build_agg(facts, recs)
        out["contexts"][h.hyp_id] = ctx
        for ev in sorted(ev_list, key=lambda e: e["evidence_id"]):
            fs = ev["finding_state"]
            rels = rs.find_relations(fs["finding"], h.concept) if fs.get("finding") else []
            if ev.get("base_concept") == "DDIMER" and ctx["years"]["years_items"]:
                rels = rels + [(yrel, ["SHADOW_YEARS_PATHWAY"])]
            for norm, _path in sorted(rels, key=lambda x: x[0]["relation_id"]):
                pw = CC.pretest_worlds(ctx["pretest_observations"], pol["pretest"], ev["available_time"])
                outs = _eval_worlds(ev, norm, h, agg, ev_list, facts, vis, pw["worlds"])
                d, base, combo = _combine(outs, pw["kind"])
                out["judgments"].append(_row(h, ev, norm, d, base["facts_used"], ctx, pw, combo, outs, mode, pol))
    out["judgments"].sort(key=lambda j: (j["hyp_id"], j["evidence_id"], j["relation_id"]))
    return out
