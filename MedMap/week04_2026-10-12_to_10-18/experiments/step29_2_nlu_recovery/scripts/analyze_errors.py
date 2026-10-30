"""STEP29.2 오류·비교 분석(공식 평가 뒤, 판정에 영향 없음). 입력 = outputs/eval_summary.json · eval_errors.csv + HOLDOUT 재실행(S29·S291·선택 정책, 결정적).
출력: outputs/{policy_comparison.csv, b4_guard_ablation.csv, punctuation_pair_results.csv, negation_scope_analysis.csv, resolution_analysis.csv,
 multi_span_analysis.csv, concept_error_analysis.csv, unsupported_auto_link_analysis.csv, error_summary.json}"""
from __future__ import annotations

import collections
import json

import s292_common as S
from contract_check_v3 import EXISTING, align, concept_view, signature, status_view

SKIP = ("by_category_pass", "errors_by_type", "metamorphic", "ASR_SENTENCE_SEGMENTATION")


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    sel = S.load_json(S.DATA / "policy_freeze.json")["SELECTED_POLICY"]
    pols = list(ev)
    rows = []
    for st in ("HOLDOUT", "DEV", "EXPOSED", "WEAK"):
        keys = [k for k in ev[sel][st] if k not in SKIP]
        for k in keys:
            rows.append({"set": st, "metric": k, **{p: ev[p][st].get(k) for p in pols}})
        if st in ("HOLDOUT", "DEV"):
            for sub in ("f1", "precision", "recall"):
                rows.append({"set": st, "metric": f"ASR_SENTENCE_SEGMENTATION_{sub}", **{p: ev[p][st]["ASR_SENTENCE_SEGMENTATION"][sub] for p in pols}})
            for k in ev[sel][st]["metamorphic"]:
                rows.append({"set": st, "metric": f"METAMORPHIC_{k}", **{p: ev[p][st]["metamorphic"].get(k) for p in pols}})
            for k in ev[sel][st]["by_category_pass"]:
                rows.append({"set": st, "metric": f"CATEGORY_PASS_{k}", **{p: ev[p][st]["by_category_pass"].get(k) for p in pols}})
    S.wcsv(S.OUT / "policy_comparison.csv", rows)
    errs = S.read_csv(S.OUT / "eval_errors.csv")
    # B4 가드 ablation
    prior = S.load_json(S.OUT / "prior_results.json")["b4_only_guard_blocks_pilot"]["rows"]
    import nlu_pipeline_v3 as N
    b4 = []
    for p in pols:
        b4.append({"row": "SUMMARY", "policy": p, "holdout_correct_blocks(오답 차단)": ev[p]["HOLDOUT"]["B4_GUARD_CORRECT_BLOCKS"],
                   "holdout_wrong_blocks(정답 차단)": ev[p]["HOLDOUT"]["B4_GUARD_WRONG_BLOCKS"],
                   "pilot_correct_blocks": ev[p]["EXPOSED"]["B4_GUARD_CORRECT_BLOCKS(pilot)"], "pilot_wrong_blocks": ev[p]["EXPOSED"]["B4_GUARD_WRONG_BLOCKS(pilot)"],
                   "holdout_precision": ev[p]["HOLDOUT"]["CONCEPT_PRECISION"], "holdout_coverage": ev[p]["HOLDOUT"]["CONCEPT_COVERAGE"],
                   "reg_precision": ev[p]["EXPOSED"]["reg_precision"], "reg_coverage": ev[p]["EXPOSED"]["reg_coverage"],
                   "pilot_multi": ev[p]["EXPOSED"]["pilot_multi_retention"]})
    for r in prior:
        row = {"row": "STEP29_1_BLOCKED_25", "text": r["text"], "unit": r["unit"], "blocked_concept": r["blocked_concept"],
               "step29_1_block_was": "정답 차단" if r["blocked_was_correct"] else "오답 차단"}
        for p in ("V3_B0", "V3_B1", "V3_B2", "V3_B3"):
            ms = [m for m in N.analyze(r["text"], p)["mentions"] if (m.get("unit_text") == r["unit"])]
            row[p] = ";".join(f"{m['status']}:{m.get('canonical_id') or m.get('guard_blocked_concept')}:{'/'.join(m.get('guard_reasons') or [])}" for m in ms)
        b4.append(row)
    S.wcsv(S.OUT / "b4_guard_ablation.csv", b4)
    hold = json.loads((S.DATA / "frozen_holdout_pairs.json").read_text(encoding="utf-8"))["cases"]
    outs = {p: {c["id"]: N.analyze(c["text"], p) for c in hold} for p in ("S29", "S291", sel)}
    pr = {}
    for c in hold:
        if c["variant"] == "BASE":
            pr.setdefault(c["pair_id"], {})[c["punct"]] = c
    prow = []
    for pid, d in sorted(pr.items()):
        if "P" not in d or "N" not in d:
            continue
        row = {"pair_id": pid, "category": d["P"]["category"], "text_P": d["P"]["text"], "text_N": d["N"]["text"]}
        for p in ("S29", "S291", sel):
            a, b = signature(outs[p][d["P"]["id"]]), signature(outs[p][d["N"]["id"]])
            row[f"{p}_equal"] = a == b
            if a != b:
                row[f"{p}_P"], row[f"{p}_N"] = json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False)
        prow.append(row)
    S.wcsv(S.OUT / "punctuation_pair_results.csv", prow)
    rrow, mrow = [], []
    for c in hold:
        for p in ("S29", "S291", sel):
            o = outs[p][c["id"]]
            for g, idx in align(c, o["mentions"]):
                cs = set(g.get("current_status_any") or [])
                x = o["mentions"][idx] if idx is not None else None
                if cs and (cs <= {"RESOLVED", "IMPROVING"} or c["category"] in ("RESOLUTION", "TEMPORAL_CONTROL")):
                    rrow.append({"id": c["id"], "category": c["category"], "structure": c["structure"], "text": c["text"], "policy": p, "anchor": g["anchor"],
                                 "gold_status": "/".join(sorted(cs)), "got_status": status_view(x) if x else "NOT_ALIGNED", "got_assertion": x["assertion"] if x else "",
                                 "got_temporality": x.get("temporality") if x else "", "resolution": json.dumps(x.get("resolution"), ensure_ascii=False) if x and x.get("resolution") else "",
                                 "ok": bool(x) and status_view(x) in cs})
            req = [g for g in c["mentions"] if not g.get("optional") and any(cc for cc in g["concept_any"])]
            if len(req) >= 2:
                got = sum(1 for g, idx in align(c, o["mentions"]) if g in req and idx is not None and o["mentions"][idx].get("status") in EXISTING
                          and o["mentions"][idx].get("canonical_id") in g["concept_any"])
                mrow.append({"id": c["id"], "category": c["category"], "punct": c["punct"], "variant": c["variant"], "text": c["text"], "policy": p, "gold_n": len(req),
                             "retained": got, "concepts": ";".join(str(concept_view(m)) for m in o["mentions"] if m.get("status") != "NON_SYMPTOM")})
    S.wcsv(S.OUT / "resolution_analysis.csv", rrow)
    S.wcsv(S.OUT / "multi_span_analysis.csv", mrow)
    pick = lambda types, sets=("HOLDOUT",): [e for e in errs if e["type"] in types and e.get("set") in sets]  # noqa: E731
    S.wcsv(S.OUT / "negation_scope_analysis.csv", pick(("ASSERTION", "SYMPTOM_NEGATION_CREATED", "MODEL_POSITIVE_FORBIDDEN")) +
           [e for e in errs if e.get("set") == "PILOT" and e["type"] == "NEGATION"])
    S.wcsv(S.OUT / "concept_error_analysis.csv", pick(("WRONG_CONCEPT", "EXTRA_WRONG_CONCEPT", "FORBIDDEN_CONCEPT", "NOT_EXTRACTED")) +
           [e for e in errs if e.get("set") == "PILOT" and e["type"] in ("WRONG_CONCEPT", "MISSED_OR_UNMAPPED")])
    S.wcsv(S.OUT / "unsupported_auto_link_analysis.csv", pick(("EXISTING_LINK_FORBIDDEN", "UNEXPECTED_SYMPTOM")))
    summ = collections.Counter((e["policy"], e.get("set") or "", e["type"]) for e in errs)
    ex = collections.defaultdict(list)
    for e in errs:
        if e["policy"] == sel and e.get("set") == "HOLDOUT" and len(ex[e["type"]]) < 8:
            ex[e["type"]].append({k: e.get(k) for k in ("id", "category", "text", "anchor", "got", "want")})
    S.dump_json(S.OUT / "error_summary.json", {"selected_policy": sel, "counts": [{"policy": a, "set": b, "type": c, "n": n} for (a, b, c), n in sorted(summ.items())],
                                               "selected_holdout_examples": ex})
    print(S.dumps({"pairs": len(prow), "resolution_rows": len(rrow), "multi_rows": len(mrow), "selected_holdout_error_types": {k: len(v) for k, v in ex.items()}}))


if __name__ == "__main__":
    main()
