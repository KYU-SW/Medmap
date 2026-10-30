"""§11–§13 통합 평가(공식). 사전 고정(prereg_freeze rules+code) SHA 가 맞을 때만 실행.
사례마다: NLU R2 → packet → 스키마·구조 게이트 → 기대값 대조 → dummy 확인 2정책(STAGE_A 만 / 전부 확인) → 제품 블라인드 흐름(in-process).
출력: outputs/{end_to_end_cases.json, adapter_validation.json, model_eligibility_audit.csv, workflow_safety.json, evidence_mapping_audit.csv, evaluation_core.json}"""
from __future__ import annotations

import collections
import json
import subprocess
import sys

import blind_workflow_simulator as BW
import clinician_confirmation_simulator as SIM
import doctor_integration_adapter as AD
import model_input_eligibility as ELIG
import s30_common as S
import validate_schema as VS


def verify_freeze():
    r = subprocess.run([sys.executable, str(S.STEP / "scripts/freeze_prereg.py"), "verify"], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit("STEP30_PREREG_SHA_MISMATCH — 평가 중단(G15)")
    return json.loads(r.stdout)


def nlu_attr_violations(it: dict) -> list[str]:
    """NLU 원본 속성 기준 STAGE_A 금지 위반(범주와 무관하게 다시 계산). STAGE_A 가 아니면 위반 없음."""
    if not it["eligibility"]["eligible"]:
        return []
    m = it.get("nlu_original") or {}
    v = []
    if m.get("status") in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or (m.get("evidence_sources") or "") == "SILVER" or not m.get("model_supported"):
        v.append("G3")
    if m.get("experiencer") != "PATIENT":
        v.append("G4")
    if m.get("assertion") == "ABSENT":
        v.append("G5")
    if m.get("temporality") == "PAST" or m.get("current_status") == "RESOLVED":
        v.append("G6")
    if (m.get("assertion") in ("POSSIBLE", "UNKNOWN") or m.get("assertion_certainty") == "LOW" or m.get("status") in ("UNCERTAIN", "UNKNOWN_SYMPTOM")
            or m.get("guard_reasons") or m.get("semantic_conflict")):
        v.append("G7")
    return v


def confirm_all_violations(packet: dict, after: dict) -> list[str]:
    """'전부 확인' dummy 정책에서도 B·G·H·미지원·SILVER 는 STAGE_B 가 되면 안 되고, C·D·E·F 는 재분류 사유 없이 STAGE_B 가 되면 안 된다."""
    by = {it["item_id"]: it for it in packet["items"]}
    v = []
    for row in after["model_input"]["stage_b_clinician_confirmed"]:
        it = by[row["item_id"]]
        m = it.get("nlu_original") or {}
        if it["category"] in ("B", "G", "H") or m.get("status") in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or not m.get("model_supported"):
            v.append(f"G3_CONFIRM_ALL:{it['item_id']}")
        if it["category"] == "E":
            v.append(f"G4_CONFIRM_ALL:{it['item_id']}")
        if it["category"] == "C":
            v.append(f"G5_CONFIRM_ALL:{it['item_id']}")
        if it["category"] == "D":
            v.append(f"G6_CONFIRM_ALL:{it['item_id']}")
        if it["category"] in ("F", "H"):
            v.append(f"G7_CONFIRM_ALL:{it['item_id']}")
    return v


def locate(text: str, surface: str, occ: int = 0) -> tuple[int, int]:
    s = -1
    for _ in range(occ + 1):
        s = text.find(surface, s + 1)
    if s < 0:
        raise ValueError(f"surface not found: {surface}")
    return s, s + len(surface)


def match(items: list, s: int, e: int):
    best, best_ov = None, 0
    for it in items:
        a, b = it.get("span_start"), it.get("span_end")
        if a is None or b is None:
            continue
        ov = min(b, e) - max(a, s)
        if ov > best_ov:
            best, best_ov = it, ov
    return best


def gold_eval(case: dict, packet: dict) -> dict:
    text, items = case["text"], packet["items"]
    rows, used = [], set()
    for k, ex in enumerate(case["expect"]):
        s, e = locate(text, ex["surface"], ex.get("occ", 0))
        it = match(items, s, e)
        cat = it["category"] if it else "NONE"
        if it:
            used.add(it["item_id"])
        elig = bool(it and it["eligibility"]["eligible"])
        concept_ok = None
        if it and cat == "A" and ex.get("concepts"):
            concept_ok = it.get("canonical_id") in ex["concepts"]
        rows.append({"case_id": case["id"], "set": case["set"], "type": case["type"], "k": k, "surface": ex["surface"], "expected_cats": ex["cats"],
                     "expected_concepts": ex.get("concepts"), "expected_stage_a": ex.get("stage_a"),
                     "item_id": it["item_id"] if it else None, "got_category": cat, "got_canonical": it.get("canonical_id") if it else None,
                     "got_raw_span": it.get("raw_span") if it else None, "got_stage_a": elig,
                     "got_target": it["eligibility"]["target_evidence"] if it else None,
                     "category_ok": cat in ex["cats"], "concept_ok": concept_ok,
                     "stage_a_ok": (ex.get("stage_a") is None) or (elig == ex["stage_a"])})
    fv = []
    for f in case.get("forbid", []):
        for it in items:
            if "concept" in f and it["category"] == "A" and it.get("canonical_id") == f["concept"]:
                fv.append({"rule": f, "item_id": it["item_id"], "raw_span": it["raw_span"]})
            if "stage_a_concept" in f and it["eligibility"]["eligible"] and it.get("canonical_id") == f["stage_a_concept"]:
                fv.append({"rule": f, "item_id": it["item_id"], "raw_span": it["raw_span"]})
            if "evidence" in f and it["eligibility"]["eligible"] and it["eligibility"]["target_evidence"] == f["evidence"]:
                fv.append({"rule": f, "item_id": it["item_id"], "raw_span": it["raw_span"]})
    extra = [{"item_id": it["item_id"], "raw_span": it["raw_span"], "category": it["category"], "canonical": it.get("canonical_id"),
              "stage_a": it["eligibility"]["eligible"]} for it in items if it["item_id"] not in used]
    return {"rows": rows, "forbid_violations": fv, "extra_items": extra}


def rate(n, d):
    return {"value": round(n / d, 4) if d else None, "numerator": n, "denominator": d}


def metrics(rows: list, cases_eval: list, set_name: str) -> dict:
    R = [r for r in rows if r["set"] == set_name]
    E = [c for c in cases_eval if c["set"] == set_name]
    exp_a = [r for r in R if r["expected_stage_a"] is True]
    transfer = sum(1 for r in exp_a if r["got_category"] == "A" and r["concept_ok"] is not False and r["got_stage_a"])
    unnecessary = sum(1 for r in exp_a if r["got_category"] == "F" or (r["got_category"] == "A" and not r["got_stage_a"]))
    must = [r for r in R if "NONE" not in r["expected_cats"]]
    missing = sum(1 for r in must if r["got_category"] == "NONE")
    matched = [r for r in R if r["got_category"] != "NONE"]
    wrong = sum(1 for r in matched if not r["category_ok"])
    ctx = [r for r in R if set(r["expected_cats"]) <= {"C", "D", "E"} and r["got_category"] != "NONE"]
    ctx_ok = sum(1 for r in ctx if r["category_ok"])
    sa_err = [r for r in R if r["expected_stage_a"] is False and r["got_stage_a"]]
    concept_wrong = [r for r in R if r["concept_ok"] is False]
    fv = [v | {"case_id": c["case_id"]} for c in E for v in c["forbid_violations"]]
    extra = [x | {"case_id": c["case_id"]} for c in E for x in c["extra_items"]]
    return {"set": set_name, "cases": len(E), "expected_items": len(R),
            "normal_transfer_rate": rate(transfer, len(exp_a)), "unnecessary_confirmation_rate": rate(unnecessary, len(exp_a)),
            "missing_rate": rate(missing, len(must)), "wrong_display_rate": rate(wrong, len(matched)),
            "context_preservation_rate": rate(ctx_ok, len(ctx)),
            "concept_mismatch_on_A": len(concept_wrong),
            "stage_a_marking_errors": len(sa_err) + len(fv), "stage_a_on_expected_false": [r["case_id"] + ":" + r["surface"] for r in sa_err],
            "forbid_violations": fv,
            "extra_items_by_category": dict(collections.Counter(x["category"] for x in extra)),
            "extra_items_stage_a": [x for x in extra if x["stage_a"]],
            "category_confusion": dict(collections.Counter(f"{'/'.join(r['expected_cats'])}->{r['got_category']}" for r in R if not r["category_ok"]))}


def mapping_audit(all_items: list) -> tuple[list, dict]:
    rows = S.read_csv(S.DATA / "evidence_mapping_candidates.csv")
    S.product()
    from medmap import config
    raw = json.loads(config.EVIDENCES_JSON.read_text())
    allowed = [r for r in rows if r["conversion_allowed"] == "True"]
    by_ev = collections.defaultdict(set)
    for r in allowed:
        by_ev[r["ddxplus_evidence_id"]].add(r["nlu_concept_id"])
    conflicts = {e: sorted(c) for e, c in by_ev.items() if len(c) > 1}
    missing_ids = sorted({r["ddxplus_evidence_id"] for r in rows if r["concept_scope"].startswith("EXISTING") and r["ddxplus_evidence_id"] and r["ddxplus_evidence_id"] not in raw})
    bad_allowed = [r["nlu_concept_id"] for r in allowed if raw[r["ddxplus_evidence_id"]]["data_type"] != "B" or raw[r["ddxplus_evidence_id"]]["code_question"] != r["ddxplus_evidence_id"]
                   or r["ddxplus_evidence_id"] in config.EXCLUDED_QUESTIONS]
    silver_allowed = [r["nlu_concept_id"] for r in allowed if not r["concept_scope"].startswith("EXISTING_77")]
    hits = collections.Counter(it.get("canonical_id") for it in all_items if it["category"] == "A")
    sa_hits = collections.Counter(it.get("canonical_id") for it in all_items if it["eligibility"]["eligible"])
    out = []
    for r in rows:
        out.append({**{k: r[k] for k in ("nlu_concept_id", "concept_scope", "ddxplus_evidence_id", "relation_type", "model_compatibility", "mapping_confidence",
                                         "validation_status", "conversion_allowed", "conversion_reason")},
                    "eval_items_category_A": hits.get(r["nlu_concept_id"], 0), "eval_items_stage_a": sa_hits.get(r["nlu_concept_id"], 0) if r["conversion_allowed"] == "True" else 0,
                    "evidence_conflict": r["ddxplus_evidence_id"] in conflicts and r["conversion_allowed"] == "True"})
    inv = S.inventory()
    concepts_allowed = sorted({r["nlu_concept_id"] for r in allowed if r["concept_scope"] == "EXISTING_77"})
    summary = {"existing_concepts": len(inv), "existing_concepts_with_allowed_conversion": len(concepts_allowed),
               "existing_concepts_without_conversion": sorted(set(inv) - set(concepts_allowed)),
               "evidence_ids_in_inventory": len({e for r in inv.values() for e in r["ddxplus_evidence_ids"].split(";") if e}),
               "evidence_ids_convertible": len(by_ev), "catalog_evidence_total": len(raw),
               "G8_conflicts": conflicts, "G8_missing_ids": missing_ids, "G8_bad_allowed": bad_allowed, "G8_silver_allowed": silver_allowed,
               "G8": "PASS" if not (conflicts or missing_ids or bad_allowed or silver_allowed) else "FAIL"}
    return out, summary


def main():
    if "--dev" in sys.argv:                      # 개발 확인: 평가 세트가 아닌 data/dev_cases.json, 출력은 logs/dev_outputs(공식 아님)
        S.OUT = S.LOGS / "dev_outputs"
        S.OUT.mkdir(exist_ok=True)
        freeze = {"verify": "SKIPPED_DEV"}
        cases = S.load_json(S.DATA / "dev_cases.json")["cases"]
    else:
        freeze = verify_freeze()
        cases = S.load_json(S.DATA / "integration_contract_cases.json")["cases"]
    A = S.nlu()
    e2e, audit_rows, gold_rows, cases_eval, all_items = [], [], [], [], []
    gate_hits = collections.defaultdict(list)
    schema_field_presence = collections.Counter()
    n_mentions = 0
    blind_all, conf_stats = [], collections.Counter()
    for c in cases:
        text = c["text"]
        nlu_out = A.analyze(text, S.NLU_POLICY)
        packet = AD.build_packet(text, nlu_out)
        before = json.dumps(packet, sort_keys=True, ensure_ascii=False, default=str)
        sv = VS.check(text, nlu_out, packet)
        for x in sv:
            gate_hits[x.split(":")[0]].append(f"{c['id']}:{x}")
        for f, info in VS.nlu_field_presence(nlu_out).items():
            schema_field_presence[f] += info["present_in_nlu"]
        n_mentions += len(nlu_out["mentions"])
        for it in packet["items"]:
            for g in nlu_attr_violations(it):
                gate_hits[g].append(f"{c['id']}:{it['item_id']}:{it['raw_span']}")
            if it["eligibility"]["auto_apply"]:
                gate_hits["AUTO_APPLY"].append(f"{c['id']}:{it['item_id']}")
        # dummy 확인 2정책
        after_a, diff_a = SIM.apply_decisions(packet, SIM.policy_confirm_stage_a(packet))
        after_all, diff_all = SIM.apply_decisions(packet, SIM.policy_confirm_everything(packet))
        if json.dumps(packet, sort_keys=True, ensure_ascii=False, default=str) != before:
            gate_hits["G9"].append(f"{c['id']}:INPUT_PACKET_MUTATED_BY_CONFIRMATION")
        sa = sorted((r["item_id"], r["evidence_id"]) for r in packet["model_input"]["stage_a_technically_eligible"])
        sb = sorted((r["item_id"], r["evidence_id"]) for r in after_a["model_input"]["stage_b_clinician_confirmed"])
        sa_dedup = sorted({e for _, e in sa})
        if sorted(after_a["model_input"]["patient_state_delta"]) != sa_dedup:
            gate_hits["CONFIRM_POLICY_MISMATCH"].append(c["id"])
        for x in confirm_all_violations(packet, after_all):
            gate_hits[x.split("_")[0]].append(f"{c['id']}:{x}")
        val = SIM.validate_candidate(after_a["model_input"]["patient_state_delta"])
        if not val["valid"]:
            gate_hits["STAGE_B_PRODUCT_CONTRACT"].append(f"{c['id']}:{val['errors']}")
        blocked_all = len(packet["items"]) - len(after_all["model_input"]["stage_b_clinician_confirmed"])
        conf_stats["confirm_all_items"] += len(packet["items"])
        conf_stats["confirm_all_stage_b"] += len(after_all["model_input"]["stage_b_clinician_confirmed"])
        conf_stats["confirm_all_blocked"] += blocked_all
        # 블라인드 흐름(제품 in-process)
        bw = BW.simulate(packet)
        blind_all.append({"case_id": c["id"], **{k: v for k, v in bw.items() if k != "stage4_model_inputs"}, "stage4_model_inputs": bw["stage4_model_inputs"]})
        for x in bw["violations"]:
            gate_hits["G10"].append(f"{c['id']}:{x}")
        ge = gold_eval(c, packet)
        gold_rows += ge["rows"]
        cases_eval.append({"case_id": c["id"], "set": c["set"], "forbid_violations": ge["forbid_violations"], "extra_items": ge["extra_items"]})
        for it in packet["items"]:
            all_items.append(it)
            el = it["eligibility"]
            audit_rows.append({"case_id": c["id"], "set": c["set"], "item_id": it["item_id"], "raw_span": it["raw_span"], "span": f"{it['span_start']}-{it['span_end']}",
                               "category": it["category"], "mapping_status": it["mapping_status"], "canonical_id": it.get("canonical_id"),
                               "ontology_id": it.get("ontology_id"), "assertion": it.get("assertion"), "temporality": it.get("temporality"),
                               "current_status": it.get("current_status"), "experiencer": it.get("experiencer"), "model_supported": it.get("model_supported"),
                               "stage_a": el["eligible"], "stage_a_target": el["target_evidence"], "blocking_reasons": ";".join(el["blocking_reasons"]),
                               "stage_b_policy_stage_a": next((r["evidence_id"] for r in after_a["model_input"]["stage_b_clinician_confirmed"] if r["item_id"] == it["item_id"]), ""),
                               "stage_b_policy_confirm_all": next((r["evidence_id"] for r in after_all["model_input"]["stage_b_clinician_confirmed"] if r["item_id"] == it["item_id"]), ""),
                               "confirm_all_blocking": ";".join((next(x for x in after_all["items"] if x["item_id"] == it["item_id"])["confirmation"]["stage_b"]["blocking_reasons"])),
                               "auto_applied": False})
        e2e.append({"case_id": c["id"], "set": c["set"], "type": c["type"], "text": text, "checks": c.get("checks"),
                    "schema_violations": sv, "packet_before_confirmation": packet, "confirmation_diff_policy_stage_a": diff_a,
                    "model_input_after_policy_stage_a": after_a["model_input"], "sections_after_policy_stage_a": after_a["sections"],
                    "confirm_all_stage_b": after_all["model_input"]["stage_b_clinician_confirmed"], "stage_b_product_contract": val,
                    "gold": ge, "blind_workflow": {k: v for k, v in bw.items()}})
    S.dump_json(S.OUT / "end_to_end_cases.json", {**S.RESEARCH_BANNER, "nlu_policy": S.NLU_POLICY, "cases": e2e})
    S.write_csv(S.OUT / "model_eligibility_audit.csv", audit_rows)
    S.write_csv(S.OUT / "gold_alignment.csv", [{**r, "expected_cats": "/".join(r["expected_cats"]), "expected_concepts": "/".join(r["expected_concepts"] or [])} for r in gold_rows])
    map_rows, map_sum = mapping_audit(all_items)
    S.write_csv(S.OUT / "evidence_mapping_audit.csv", map_rows)
    if map_sum["G8"] != "PASS":
        gate_hits["G8"].append(json.dumps(map_sum, ensure_ascii=False)[:300])
    m_new = metrics(gold_rows, cases_eval, "INTEGRATION_NEW")
    m_reg = metrics(gold_rows, cases_eval, "REGRESSION_EXPOSED")
    cat_counts = collections.Counter(it["category"] for it in all_items)
    adapter_validation = {**S.RESEARCH_BANNER, "cases": len(cases), "nlu_mentions": n_mentions, "packet_items": len(all_items),
                          "items_by_category": dict(sorted(cat_counts.items())),
                          "stage_a_items": sum(1 for it in all_items if it["eligibility"]["eligible"]),
                          "schema_violations_total": sum(len(x["schema_violations"]) for x in e2e),
                          "required_field_presence_in_nlu": {f: {"mentions_with_field": schema_field_presence[f], "mentions": n_mentions,
                                                                 "source": "NLU" if f in VS.NLU_NATIVE else "ADAPTER " + VS.ADAPTER_DERIVED.get(f, "")} for f in AD.REQUIRED_FIELDS},
                          "multi_span": {"cases_with_ge2_items": sum(1 for x in e2e if len(x["packet_before_confirmation"]["items"]) >= 2),
                                         "multi_expected_cases": sum(1 for c in cases if len(c["expect"]) >= 2),
                                         "multi_expected_all_matched_distinct": sum(1 for x, c in zip(e2e, cases) if len(c["expect"]) >= 2 and
                                                                                    len({r["item_id"] for r in x["gold"]["rows"] if r["item_id"]}) == sum(1 for r in x["gold"]["rows"] if r["item_id"]))},
                          "confirmation_policy_confirm_all": dict(conf_stats)}
    S.dump_json(S.OUT / "adapter_validation.json", adapter_validation)
    S.dump_json(S.OUT / "workflow_safety.json", {**S.RESEARCH_BANNER, "cases": len(blind_all),
                                                 "violations_total": sum(len(b["violations"]) for b in blind_all),
                                                 "stage2_locked_all": all(b["stage2_pending_assessment"] == "LOCKED" and b["stage2_pending_next_information"] == "LOCKED" for b in blind_all),
                                                 "stage4_inputs_equal_stage_b_all": all(b["stage4_inputs_equal_stage_b"] for b in blind_all),
                                                 "wd_unchanged_all": all(b["stage3_wd_unchanged"] for b in blind_all),
                                                 "note": "제품 doctor_view·DiagnosisEngine 을 in-process 로 읽기 호출(서버·세션 저장 없음). 질환 이름은 기록하지 않음.",
                                                 "per_case": blind_all})
    core = {**S.RESEARCH_BANNER, "freeze_verify": freeze, "gate_hits": {k: v for k, v in sorted(gate_hits.items())},
            "metrics_integration_new": m_new, "metrics_regression_exposed": m_reg, "mapping_summary": map_sum,
            "adapter_validation_summary": {k: adapter_validation[k] for k in ("cases", "nlu_mentions", "packet_items", "items_by_category", "stage_a_items", "schema_violations_total", "multi_span")}}
    S.dump_json(S.OUT / "evaluation_core.json", core)
    print(S.dumps({"gate_hits": {k: len(v) for k, v in gate_hits.items()}, "new": {k: m_new[k] for k in ("normal_transfer_rate", "missing_rate", "wrong_display_rate", "stage_a_marking_errors")},
                   "reg": {k: m_reg[k] for k in ("normal_transfer_rate", "stage_a_marking_errors")}, "G8": map_sum["G8"]}))


if __name__ == "__main__":
    main()
