"""STEP29.3 공식 평가 뒤 비교 표(판정에 영향 없음). 입력 = outputs/eval_summary.json · eval_errors.csv + FROZEN29_3 재실행(R0·선택 정책, 결정적).
출력: outputs/{policy_comparison.csv, normalization_ablation.csv, precision_coverage_tradeoff.csv, semantic_disambiguation.csv, unsupported_input_analysis.csv,
 multi_span_regression.csv, error_summary.json}"""
import collections
import json

import s293_common as S
from contract_check_v3 import EXISTING, align, concept_view
from gates293 import f1

SETS = ("FROZEN29_3", "DEV29_3", "STEP29_2_HOLDOUT", "EXPOSED", "REGRESSION_CASES", "WEAK")
SKIP = ("errors_by_type", "morph_by_variant", "by_category_pass", "metamorphic", "ASR_SENTENCE_SEGMENTATION")


def main():
    M = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    sel = S.load_json(S.DATA / "policy_freeze.json")["SELECTED_POLICY"]
    pols = list(M)
    rows = []
    for st in SETS:
        for k in M[sel][st]:
            if k in SKIP or isinstance(M[sel][st][k], (dict, list)):
                continue
            rows.append({"set": st, "metric": k, **{p: M[p][st].get(k) for p in pols}})
        if "morph_by_variant" in M[sel][st]:
            for v in M[sel][st]["morph_by_variant"]:
                rows.append({"set": st, "metric": f"MORPH_{v}", **{p: M[p][st]["morph_by_variant"].get(v) for p in pols}})
    S.wcsv(S.OUT / "policy_comparison.csv", rows)
    keys = ("CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE", "MORPHOLOGICAL_VARIANT_SUCCESS", "UNKNOWN_RATE", "UNCERTAIN_RATE", "WRONG_CONCEPT_AUTO_ACCEPT",
            "SEMANTIC_AMBIGUITY_ERRORS", "MULTI_SPAN_RETENTION")
    S.wcsv(S.OUT / "normalization_ablation.csv", [{"policy": p, "set": st, **{k: M[p][st][k] for k in keys}} for p in ("R0", "N1", "N2", "R2", "N4")
                                                   for st in ("FROZEN29_3", "DEV29_3")])
    tr = []
    for p in pols:
        for st, pk, ck in (("FROZEN29_3", "CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE"), ("DEV29_3", "CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE"),
                           ("STEP29_2_HOLDOUT", "CONCEPT_PRECISION", "CONCEPT_COVERAGE"), ("EXPOSED", "reg_precision", "reg_coverage")):
            pr, cv = M[p][st][pk], M[p][st][ck]
            tr.append({"policy": p, "set": st, "precision": pr, "coverage": cv, "f1": round(f1(pr, cv), 4),
                       "coverage_definition": "첫 EXISTING 연결 시도(정답 무관)" if st == "EXPOSED" else "정답 concept 연결"})
    S.wcsv(S.OUT / "precision_coverage_tradeoff.csv", tr)
    import step29_2_adapter as A
    fro = S.load_json(S.DATA / "frozen_evaluation_cases.json")["cases"]
    sd, un, ms_rows = [], [], []
    for c in fro:
        o0, o1 = A.analyze(c["text"], "R0"), A.analyze(c["text"], sel)
        if c.get("ambiguity"):
            for p, o in (("R0", o0), (sel, o1)):
                sd.append({"id": c["id"], "ambiguity": c["ambiguity"], "text": c["text"], "policy": p, "gold": "/".join(map(str, c["mentions"][0]["concept_any"])) if c["mentions"] else "(EXISTING 금지)",
                           "forbid": "/".join(c["mentions"][0].get("forbid") or []) if c["mentions"] else "",
                           "got": ";".join(f"{x['raw_span']}:{x['status']}:{concept_view(x)}:{(x.get('retrieval') or {}).get('via', '')}:{(x.get('retrieval') or {}).get('basis', '')}"
                                           for x in o["mentions"] if x["status"] != "NON_SYMPTOM"),
                           "conflict_hold": any("SEMANTIC_CONFLICT_HOLD" in (x.get("guard_reasons") or []) for x in o["mentions"])})
        if c["category"] in ("UNSUPPORTED", "SILVER", "NON_SYMPTOM"):
            for p, o in (("R0", o0), (sel, o1)):
                un.append({"id": c["id"], "category": c["category"], "text": c["text"], "policy": p,
                           "statuses": ";".join(f"{x['raw_span']}:{x['status']}:{concept_view(x)}:{x.get('reason')}" for x in o["mentions"]),
                           "existing_auto": any(x["status"] in EXISTING for x in o["mentions"]), "model_eligible": any(x["model_input"]["eligible"] for x in o["mentions"])})
        req = [g for g in c["mentions"] if not g.get("optional") and any(g["concept_any"])]
        if len(req) >= 2:
            for p, o in (("R0", o0), (sel, o1)):
                got = sum(1 for g, i in align(c, o["mentions"]) if g in req and i is not None and o["mentions"][i]["status"] in EXISTING
                          and o["mentions"][i].get("canonical_id") in g["concept_any"])
                ms_rows.append({"id": c["id"], "category": c["category"], "text": c["text"], "policy": p, "gold_n": len(req), "retained": got})
    S.wcsv(S.OUT / "semantic_disambiguation.csv", sd)
    S.wcsv(S.OUT / "unsupported_input_analysis.csv", un)
    S.wcsv(S.OUT / "multi_span_regression.csv", ms_rows)
    errs = S.read_csv(S.OUT / "eval_errors.csv")
    ex = collections.defaultdict(list)
    for e in errs:
        if e["policy"] == sel and e["set"] == "FROZEN29_3" and len(ex[e["type"]]) < 10:
            ex[e["type"]].append({k: e.get(k) for k in ("id", "category", "text", "anchor", "got")})
    cnt = collections.Counter((e["policy"], e["set"], e["type"]) for e in errs)
    S.dump_json(S.OUT / "error_summary.json", {"selected_policy": sel, "frozen_examples": ex,
                                               "counts": [{"policy": a, "set": b, "type": t, "n": n} for (a, b, t), n in sorted(cnt.items())]})
    ov = {c[0] for c in S.load_json(S.OUT / "frozen_exposure_overlap.json")["frozen_cases_overlapping_spec_examples_or_regression_cases"]}
    from evaluate_retrieval import new_metrics
    keep = [c for c in fro if c["id"] not in ov]
    sens = {}
    for p in ("R0", sel):
        r, _ = new_metrics(keep, [A.analyze(c["text"], p) for c in keep], S.models())
        sens[p] = {k: r[k] for k in ("n_inputs", "CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE", "MULTI_SPAN_RETENTION", "MORPHOLOGICAL_VARIANT_SUCCESS",
                                     "UNKNOWN_RATE", "WRONG_CONCEPT_AUTO_ACCEPT", "SEMANTIC_AMBIGUITY_ERRORS")}
    S.dump_json(S.OUT / "frozen_sensitivity_excluding_exposed.json", {"label": "EXPLORATORY_SENSITIVITY(공식 판정 아님) — 지시문 예시와 겹친 FROZEN 3건 제외",
                                                                      "excluded_ids": sorted(ov), "metrics": sens})
    print(S.dumps({"rows": len(rows), "sd": len(sd), "unsup": len(un), "multi": len(ms_rows), "frozen_error_types": {k: len(v) for k, v in ex.items()}}))


if __name__ == "__main__":
    main()
