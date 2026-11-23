"""그래프 A·B 연결 추론, 가설별 근거 종합(합산·확률 없음), 미설명 소견 구분, 진단 재검토 트리.
평면 규칙표(flat.py)와 같은 평가 함수(evaluate_one)를 공유한다. 다른 점은 관계·증거를 찾는 방법뿐(그래프 순회 vs 표 조회)."""
from __future__ import annotations

from collections import OrderedDict

from hybrid3 import reasoner as R3

from . import graphs as GR, logic as LG

CC, EC = GR.CP.CC_MOD, GR.CP.EC_MOD
PHASE_NONDX = {"UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP", "RECURRENCE_EVALUATION", "CONFIRMED_PE"}


def phase_fact(ev, h, agg, episode_evidence, episode_facts, view_vis):
    """임상 단계 사실(P2 resolve·target_check 재사용). 반환 (LG.Fact, 대상 게이트 결과 또는 None, 단계 상세)."""
    t_ev = ev["available_time"]
    sig = sorted({f["value"] for f in episode_facts if f["key"] == "clinical_phase_signal" and f["source_record_id"] != ev["source_record_id"]
                  and isinstance(f["available_time"], (int, float)) and isinstance(t_ev, (int, float)) and f["available_time"] <= t_ev})
    prior_pos = any(o["finding_state"].get("finding") == "CTPA_REPORTS_PE" and o["source_record_id"] != ev["source_record_id"] and isinstance(o["available_time"], (int, float))
                    and isinstance(t_ev, (int, float)) and o["available_time"] <= t_ev for o in episode_evidence)
    sus = agg["suspected"]
    ctx = {"suspected": True if sus.status == "FOUND" and sus.value is True else None,
           "case_phase_signals": sig + (["CONFIRMED_PE"] if prior_pos and h.kind != "PAST_EPISODE" else [])}
    if h.kind != "CURRENT_EVALUATION":
        ctx["hypothesis_target"] = {"diagnosis_episode_id": h.episode_id, "kind": h.kind, "hypothesis_target_time": h.target_time}
        ctx["evidence_observed_at"] = ev["observation_time"] if isinstance(ev["observation_time"], (int, float)) else None
    cc = CC.resolve(ev["sentence"], h.status.value, ctx)
    tgt = EC.target_check(ctx, cc["phase"])
    detail = {**cc, "phase_after_target": tgt["phase"], "case_phase_signals": ctx["case_phase_signals"]}
    src = (f"{ev['source_record_id']}:sentence",) if cc["basis"] == "SENTENCE_TEXT" else tuple(sus.sources) if cc["basis"] == "INPUT_CONTEXT" else (f"basis:{cc['basis']}",)
    if tgt["phase"] == CC.UNKNOWN:
        f = LG.Fact("clinical_phase", "CONFLICT", None, sus.values, sus.sources) if sus.status == "CONFLICT" else LG.Fact("clinical_phase", "NOT_FOUND")
    else:
        f = LG.Fact("clinical_phase", "FOUND", tgt["phase"], (tgt["phase"],), src)
    return f, tgt["result"], detail


def evaluate_one(ev, norm, h, agg, episode_evidence, episode_facts, vis):
    """증거 1건 × 정규화 관계 1개 → 조건 평가 결과. 그래프·평면 규칙표 공용."""
    facts = dict(agg)
    fs = ev["finding_state"]
    facts["level"] = LG.Fact("level", "FOUND", fs["level"], (fs["level"],), (ev["evidence_id"],)) if fs.get("level") else LG.Fact("level", "NOT_FOUND")
    if norm["finding"] == "DDIMER_NORMAL":
        dd = EC.ddimer_conditions(ev["sentence"], {})
        for k, v in (("ddimer_assay", dd["assay"]), ("ddimer_cutoff", dd["cutoff"])):
            if v:
                facts[k] = LG.Fact(k, "FOUND", v, (v,), (f"{ev['evidence_id']}:sentence",))
    pf, tgt_res, detail = phase_fact(ev, h, agg, episode_evidence, episode_facts, vis)
    facts["clinical_phase"] = pf
    if tgt_res:                                                                    # 가설 대상 에피소드·시점 게이트(P2)
        d = {"relation_id": norm["relation_id"], "direction": tgt_res["direction"], "stage": "EPISODE_TARGET_GATE", "note": tgt_res["note"], "gates": [], "required": None,
             "alternatives": None, "fallbacks": [], "missing": tgt_res["missing_context"], "conflicts": []}
    else:
        d = LG.decide(norm["structured"], facts)
    used = {k: {"status": f.status, "value": f.value, "values": list(f.values), "sources": list(f.sources)} for k, f in facts.items()}
    return {"decision": d, "facts_used": used, "clinical_phase_detail": detail}


def condition_location(decision, key):
    loc = []
    for i, g in enumerate(decision.get("gates", [])):
        if key in g["eval"]["missing"] or any(c["key"] == key for c in g["eval"]["conflicts"]):
            loc.append(f"EXCLUSION_GATE[{i}]")
    for name in ("required", "alternatives"):
        r = decision.get(name)
        if r and (key in r["missing"] or any(c["key"] == key for c in r["conflicts"])):
            loc.append(name.upper())
    for i, f in enumerate(decision.get("fallbacks", [])):
        if key in f["eval"]["missing"]:
            loc.append(f"FALLBACK[{i}]")
    return loc


def finding_status(item):
    d = item["direction"]
    if item.get("reason_class") == "NOT_A_GAP":
        return None
    if item["extraction_status"] in ("AMBIGUOUS", "UNSUPPORTED") or item.get("reason_class") == "D":
        return "UNSUPPORTED_CONCEPT"
    if d == "SUPPORT":
        return "EXPLAINED_BY_KNOWN_RELATION"
    if d == "WEAKEN":
        return "POTENTIAL_DISCORDANCE"
    if d in ("INSUFFICIENT_EVIDENCE",) or item.get("hold_reason") in ("NO_RESULT_YET",) or item.get("reason_class") in ("A", "B", "C"):
        return "NOT_YET_EVALUATED"
    return "INSUFFICIENT_KNOWLEDGE"                                                   # 관계 없음 또는 관계가 방향을 주지 않음


class Reasoner:
    """mode='graph': A 순회로 관계, B 순회로 증거. mode='flat': 같은 원본의 표 조회."""

    def __init__(self, relations: list, mode: str = "graph", use_base=True):
        self.mode, self.relations = mode, relations
        if mode == "graph":
            self.kg = GR.DiseaseKG(relations, use_base=use_base)
        else:
            from .flat import FlatRuleTable
            self.table = FlatRuleTable(relations)

    def diagnosis_known(self, concept):
        return concept in self.kg.g.nodes if self.mode == "graph" else self.table.has_diagnosis(concept)

    def has_association(self, node, diagnosis):
        if self.mode == "graph":
            return any(e["dst"] == node and e["rel"] in ("HAS_ASSOCIATED_FINDING", "HAS_RISK_FACTOR") for e in self.kg.g.outs(diagnosis))
        return (node, diagnosis) in self.table.assoc

    def find_relations(self, finding, diagnosis):
        if self.mode == "graph":
            return [(r["norm"], r["path"]) for r in self.kg.relations_for(finding, diagnosis)]
        return [(r, ["FLAT_TABLE_ROW", r["relation_id"]]) for r in self.table.lookup(finding, diagnosis)]

    def episode_inputs(self, pg, episode_id, as_of):
        if self.mode == "graph":
            v = pg.episode_view(episode_id, as_of)
            return v["evidence"], v["facts"], v["unresolved_evidence"], v["texts"]
        from .flat import flat_episode_rows
        return flat_episode_rows(pg, episode_id, as_of)

    def evaluate(self, pg, as_of):
        out = {"as_of": as_of, "patient_id": pg.pid, "mode": self.mode, "hypotheses": []}
        vis = set(pg.visible_records(as_of))
        for h, a in pg.active_hypotheses(as_of):
            ev_list, facts, unresolved, texts = self.episode_inputs(pg, h.episode_id, as_of)
            agg = GR.aggregate_facts(facts)
            hyp = {"hyp_id": h.hyp_id, "label": h.label, "concept": h.concept, "status": h.status.value, "episode_id": h.episode_id, "episode_kind": h.kind,
                   "physician_confirmed": a.provenance.physician_confirmed, "usable": a.usable_as_hypothesis(), "items": [],
                   "context": {k: {"status": f.status, "value": f.value, "values": list(f.values), "sources": list(f.sources)} for k, f in agg.items()},
                   "unresolved_episode_evidence": [{"evidence_id": e["evidence_id"], "surface": e["surface"], "source_record_id": e["source_record_id"]} for e in unresolved],
                   "tests": pg.test_states(h.episode_id, as_of)}
            out["hypotheses"].append(hyp)
            if not hyp["usable"]:
                hyp["not_evaluated_reason"] = "HYPOTHESIS_NOT_USABLE(의사 확인 없음 또는 배제·과거 상태)"
                continue
            agg_like = {k: {"status": v["status"]} for k, v in hyp["context"].items()}
            for ev in ev_list:
                base = {k: ev[k] for k in ("evidence_id", "source_record_id", "sentence", "surface", "concept_id", "kg_node", "assertion_status", "extraction_status",
                                           "observation_time", "available_time", "diagnosis_episode_id", "confirmation_status")}
                fs = ev["finding_state"]
                rels = self.find_relations(fs["finding"], h.concept) if fs.get("finding") and self.diagnosis_known(h.concept) else []
                if not self.diagnosis_known(h.concept):
                    reason = "HYPOTHESIS_NOT_IN_GRAPH"
                elif fs.get("finding") and not rels:
                    reason = "NO_VERIFIED_RELATION_FOR_FINDING"
                else:
                    reason = fs.get("reason", "")
                if reason == "NO_VERIFIED_RELATION" and ev["kg_node"] and self.has_association(ev["kg_node"], h.concept):
                    reason = "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION"
                if reason in ("UNCERTAIN_MENTION", "TEST_PURPOSE_NOT_RESULT") and ev["concept_id"].startswith("PE") and R3.CX.R_SUSPECT.search(ev["sentence"]):
                    reason = "SUSPICION_STATEMENT_USED_AS_CONTEXT"
                if not rels:
                    cls = R3.REASON_CLASS.get(reason, "E")
                    item = {**base, "direction": "ABSTAIN", "hold_reason": reason, "reason_class": cls, "relation_id": "", "path": [],
                            "gaps": R3.classify_gaps([], reason, agg_like, texts), "sources": []}
                    item["finding_status"] = finding_status(item)
                    hyp["items"].append(item)
                    continue
                for norm, path in rels:
                    r = evaluate_one(ev, norm, h, agg, ev_list, facts, vis)
                    d = r["decision"]
                    agg2 = {**agg_like, **{k: {"status": v["status"]} for k, v in r["facts_used"].items()}}
                    gaps = R3.classify_gaps(d["missing"], "", agg2, texts) if d["direction"] == "INSUFFICIENT_EVIDENCE" else []
                    for gp in gaps:
                        gp["condition_location"] = condition_location(d, gp["item"])
                    for c in d["conflicts"]:
                        gaps.append({"item": c["key"], "class": "C", "meaning": R3.GAP_KO["C"], "condition_location": condition_location(d, c["key"]), "conflict": c})
                    item = {**base, "direction": d["direction"], "stage": d["stage"], "hold_reason": d["stage"] if d["direction"] not in LG.DIRECTIONAL else "",
                            "relation_id": norm["relation_id"], "relation_type": norm["relation_type"], "path": path, "decision": d, "facts_used": r["facts_used"],
                            "clinical_phase_detail": r["clinical_phase_detail"], "gaps": gaps, "applicability": norm["applicability"],
                            "sources": norm["sources"], "verification_status": norm["verification_status"], "evidence_version": norm["evidence_version"], "reason_class": ""}
                    item["finding_status"] = finding_status(item)
                    hyp["items"].append(item)
            groups = OrderedDict()
            for it in hyp["items"]:
                groups.setdefault((it["source_record_id"], it["relation_id"] or it["hold_reason"]), []).append(it["evidence_id"])
            for it in hyp["items"]:
                g = groups[(it["source_record_id"], it["relation_id"] or it["hold_reason"])]
                it["dependency_group"] = f"{it['source_record_id']}|{it['relation_id'] or it['hold_reason']}"
                it["duplicate_of"] = g[0] if g[0] != it["evidence_id"] else ""
        return out


def review_tree(result: dict, pg) -> list:
    """진단 재검토 트리: 실제 판단 항목에서만 생성. 중복(같은 기록·같은 관계)은 대표 1건 + 묶인 증거 ID."""
    trees = []
    for h in result["hypotheses"]:
        primary = [i for i in h["items"] if not i["duplicate_of"]]

        def card(i):
            return {"evidence_id": i["evidence_id"], "grouped_evidence": [x["evidence_id"] for x in h["items"] if x["duplicate_of"] == i["evidence_id"]],
                    "source_record_id": i["source_record_id"], "sentence": i["sentence"], "surface": i["surface"], "concept": i["concept_id"], "kg_node": i["kg_node"],
                    "assertion": i["assertion_status"], "relation_id": i["relation_id"], "graph_path": i["path"], "direction": i["direction"],
                    "condition_trace": _cond_summary(i.get("decision")), "available_time": i["available_time"], "observation_time": i["observation_time"],
                    "sources": [f"{s['name'][:50]} {s['location']}: \"{s['quote'][:110]}\"" for s in i["sources"]], "hold_reason": i["hold_reason"],
                    "gaps": i["gaps"], "finding_status": i["finding_status"]}
        sec = lambda pred: [card(i) for i in primary if pred(i)]  # noqa: E731
        t = {"working_diagnosis": h["label"], "hypothesis_id": h["hyp_id"], "status": h["status"], "physician_confirmed": h["physician_confirmed"],
             "diagnosis_episode": {"episode_id": h["episode_id"], "kind": h["episode_kind"]}, "as_of": result["as_of"], "mode": result["mode"]}
        if not h["usable"]:
            t["not_evaluated"] = h["not_evaluated_reason"]
        t.update({"supporting": sec(lambda i: i["direction"] == "SUPPORT"), "weakening": sec(lambda i: i["direction"] == "WEAKEN"),
                  "uncertain_or_no_clear_effect": sec(lambda i: i["direction"] in ("UNCERTAIN", "NO_CLEAR_EFFECT")),
                  "not_applicable": sec(lambda i: i["direction"] == "NOT_APPLICABLE"),
                  "held_insufficient": sec(lambda i: i["direction"] == "INSUFFICIENT_EVIDENCE"),
                  "pending_tests": {"test_states": {k: v for k, v in h["tests"].items() if v in ("ORDERED", "PENDING")},
                                    "order_mentions": sec(lambda i: i["hold_reason"] == "NO_RESULT_YET")},
                  "unexplained_findings": [{"evidence_id": i["evidence_id"], "surface": i["surface"], "status": i["finding_status"], "reason": i["hold_reason"] or i["direction"]}
                                           for i in primary if i["finding_status"] not in (None, "EXPLAINED_BY_KNOWN_RELATION")],
                  "conflicts": [{"evidence_id": i["evidence_id"], **g["conflict"], "condition_location": g["condition_location"]} for i in primary for g in i["gaps"] if g.get("conflict")]
                  + [{"context_key": k, "values": v["values"], "sources": v["sources"]} for k, v in h["context"].items() if v["status"] == "CONFLICT"]
                  + [{"evidence_id": i["evidence_id"], "extractor_conflict": i["hold_reason"]} for i in primary if i["hold_reason"] == "EXTRACTOR_CONFLICT"],
                  "missing_information": [{"evidence_id": i["evidence_id"], **{k: g[k] for k in ("item", "class", "meaning")}, "condition_location": g.get("condition_location", [])}
                                          for i in primary for g in i["gaps"] if g["class"] in ("A", "B")],
                  "unresolved_episode_evidence": h["unresolved_episode_evidence"],
                  "ai_diagnosis_candidates_unconfirmed": [{"candidate_id": nid, "text": v["text"], "physician_confirmed": v["physician_confirmed"], "usable_as_hypothesis": v["usable_as_hypothesis"]}
                                                          for nid, v in pg.g.nodes.items() if v["kind"] == "AI_DIAGNOSIS_CANDIDATE" and nid.split(":")[1] in pg.visible_records(result["as_of"])],
                  "medical_sources_used": sorted({f"{s['name'][:60]} {s['location']}" for i in primary if i["relation_id"] for s in i["sources"]})})
        trees.append(t)
    return trees


def _cond_summary(d):
    if not d:
        return None

    def flat(r):
        if r is None:
            return None
        if r["op"] == "ATOM":
            return {"key": r["key"], "allowed": r["allowed"], "value": r["value"], "observed": r["observed"], "sources": r["sources"]}
        return {"op": r["op"], "value": r["value"], "children": [flat(k) for k in r["children"]]}
    return {"stage": d["stage"], "gates": [{"outcome": g["outcome"], "policy": g["unknown_policy"], "value": g["eval"]["value"], "tree": flat(g["eval"])} for g in d["gates"]],
            "required": flat(d["required"]), "alternatives": flat(d["alternatives"]), "fallbacks": [{"outcome": f["outcome"], "value": f["eval"]["value"]} for f in d["fallbacks"]],
            "missing": d["missing"], "conflicts": d["conflicts"]}
