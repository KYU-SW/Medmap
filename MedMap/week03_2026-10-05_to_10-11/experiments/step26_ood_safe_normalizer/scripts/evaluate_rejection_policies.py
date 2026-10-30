"""STEP26 Baseline B(B1–B4) + Baseline C(LIGHTWEIGHT_GATE) — DEV 로만 임계값·선택, HELD_OUT·regression 은 1회 적용(보고 전용).
규칙은 policy_lib 문서열(실행 전 고정).
출력: outputs/policy_selection.json · rejection_policy_comparison.csv · policy_tradeoff_curve.csv · regression_utility_analysis.csv
      weak_negative_analysis.csv · weak_symptom_analysis.csv · disagreement_analysis.csv · outputs/final_decisions.csv
"""
import collections

import policy_lib as P
import s26_common as S


def main():
    rows = P.load_rows()
    cl = {r["row_id"]: r["cluster"] for r in S.read_csv(S.DATA / "weak_label_inventory.csv")}
    dev = [r for r in rows if r["set"] in ("EXT_DEV", "INT_DEV_CORE")]
    ev = [r for r in rows if r["set"] in ("EXT_EVAL", "INT_REGRESSION_CORE", "KMC_COMPLEX_STRESS")]
    sel = {"rules": P.__doc__, "policies": {}}
    curve = []
    for pol in P.ORDER:
        p, gate, m_in = P.fit_policy(pol, dev)
        cv = P.cross_validate(pol, dev, cl)
        gp = P.gate_probs(gate, ev)
        m_ev = P.metrics(ev, {r["row_id"]: P.decide(pol, p, r, gp) for r in ev})
        sel["policies"][pol] = {"params": p, "dev_in_sample": m_in, "dev_cv": cv, "cv_feasible": P.feasible(cv), "eval_report_only": m_ev,
                                "gate_coef": dict(zip(P.GATE_FEATS, [round(float(c), 4) for c in gate[-1].coef_[0]])) if gate is not None else None}
        gpd = P.gate_probs(gate, dev)
        for gi, gpar in enumerate(P.GRIDS[pol]):
            md = P.metrics(dev, {r["row_id"]: P.decide(pol, gpar, r, gpd) for r in dev})
            curve.append({"policy": pol, "grid_index": gi, "params": S.dumps(gpar), "dev_WN_auto": md["WEAK_NON_SYMPTOM_auto_rate"],
                          "dev_WS_auto": md["WEAK_SYMPTOM_auto_rate"], "dev_core_prec": md.get("INT_DEV_CORE_auto_precision"),
                          "dev_core_cov": md.get("INT_DEV_CORE_auto_coverage"), "dev_disagree_auto": md["ext_disagreement_auto_count"],
                          "feasible": P.feasible(md), "selected": gpar == p})
        print(pol, p, "CV WN", cv["WEAK_NON_SYMPTOM_auto_rate"], "CV core P/C", cv.get("INT_DEV_CORE_auto_precision"), cv.get("INT_DEV_CORE_auto_coverage"),
              "feasible", P.feasible(cv), flush=True)
    # BEST_POLICY
    rule = [p for p in ("B1", "B2", "B3", "B4") if sel["policies"][p]["cv_feasible"]]
    best_rule = None
    if rule:
        mn = min(sel["policies"][p]["dev_cv"]["WEAK_NON_SYMPTOM_auto_rate"] for p in rule)
        best_rule = next(p for p in rule if sel["policies"][p]["dev_cv"]["WEAK_NON_SYMPTOM_auto_rate"] <= mn + 0.005)
    g = sel["policies"]["LIGHTWEIGHT_GATE"]
    gate_ok = g["cv_feasible"] and (best_rule is None or g["dev_cv"]["WEAK_NON_SYMPTOM_auto_rate"]
                                    <= sel["policies"][best_rule]["dev_cv"]["WEAK_NON_SYMPTOM_auto_rate"] - 0.02)
    best = "LIGHTWEIGHT_GATE" if gate_ok else (best_rule or "NONE")
    sel["BEST_POLICY"] = best
    sel["best_rule_policy"] = best_rule
    sel["gate_promoted"] = gate_ok
    S.dump_json(S.OUT / "policy_selection.json", sel)
    S.write_csv(S.OUT / "policy_tradeoff_curve.csv", curve)

    base = S.load_json(S.OUT / "baseline_metrics.json")
    comp = []
    for name in ("LINEAR_ONLY", "HYBRID_B") + tuple(P.ORDER):
        m = base[name]["EVAL"] if name in base else sel["policies"][name]["eval_report_only"]
        dcv = None if name in base else sel["policies"][name]["dev_cv"]
        comp.append({"policy": name, "is_best": name == best,
                     "EVAL_WN_auto_rate": m["WEAK_NON_SYMPTOM_auto_rate"], "EVAL_WS_auto_rate": m["WEAK_SYMPTOM_auto_rate"],
                     "EVAL_MIXED_auto_rate": m["WEAK_MIXED_auto_rate"], "EVAL_disagree_auto": m["ext_disagreement_auto_count"],
                     "EVAL_unknown_rate": m["ext_unknown_rate"], "REG_auto_precision": m.get("INT_REGRESSION_CORE_auto_precision"),
                     "REG_auto_coverage": m.get("INT_REGRESSION_CORE_auto_coverage"), "REG_known_recall": m.get("INT_REGRESSION_CORE_known_recall"),
                     "KMC_auto_rate": m.get("KMC_auto_rate", base[name]["KMC"].get("KMC_auto_rate") if name in base else None),
                     "DEV_CV_WN_auto": dcv["WEAK_NON_SYMPTOM_auto_rate"] if dcv else "", "DEV_CV_core_prec": dcv.get("INT_DEV_CORE_auto_precision") if dcv else "",
                     "DEV_CV_core_cov": dcv.get("INT_DEV_CORE_auto_coverage") if dcv else "", "params": S.dumps(sel["policies"][name]["params"]) if name in sel["policies"] else "frozen"})
    S.write_csv(S.OUT / "rejection_policy_comparison.csv", comp)

    # 최종 결정(BEST + baseline) 행 단위 저장 → 분석 파일
    pb, gate, _ = P.fit_policy(best, dev) if best != "NONE" else (None, None, None)
    allr = dev + ev
    gp = P.gate_probs(gate, allr)
    fin = []
    for r in allr:
        hb, ha = P.baseline("HYBRID_B", r)
        lb, la = P.baseline("LINEAR_ONLY", r)
        nb, na = P.decide(best, pb, r, gp) if best != "NONE" else (hb, ha)
        fin.append({"row_id": r["row_id"], "set": r["set"], "weak_label": r["weak_label"], "gold_concept": r["gold_concept"], "text": r["text"],
                    "lin_top1": r["lin_top1"], "koe_top1": r["koe_top1"], "agree": r["agree"], "lin_margin": r["lin_margin"], "koe_conf": r["koe_conf"],
                    "train_sim": r["train_sim"], "complex_flags": r["complex_flags"], "linear_only": lb, "linear_only_auto": la, "hybrid_b": hb,
                    "hybrid_b_auto": ha, "new_policy": best, "new_label": nb, "new_auto": na, "gate_prob": round(gp.get(r["row_id"], -1), 6)})
    S.write_csv(S.OUT / "final_decisions.csv", fin)
    ext_ev = [f for f in fin if f["set"] == "EXT_EVAL"]
    wn = [f for f in ext_ev if f["weak_label"] == "WEAK_NON_SYMPTOM"]
    ws = [f for f in ext_ev if f["weak_label"] == "WEAK_SYMPTOM"]
    S.write_csv(S.OUT / "weak_negative_analysis.csv", [
        {"slice": k, "n": len(v), "linear_auto": sum(f["linear_only_auto"] for f in v), "hybrid_b_auto": sum(f["hybrid_b_auto"] for f in v),
         "new_auto": sum(f["new_auto"] for f in v)}
        for k, v in [("ALL", wn)] + sorted(collections.defaultdict(list, {c: [f for f in wn if c in cats_of(f, rows)] for c in ("BERT_NER_KO:DS", "BERT_NER_KO:BD", "KBMC:Body", "KBMC:Treatment")}).items())])
    S.write_csv(S.OUT / "weak_symptom_analysis.csv", [
        {"slice": k, "n": len(v), "linear_auto": sum(f["linear_only_auto"] for f in v), "hybrid_b_auto": sum(f["hybrid_b_auto"] for f in v),
         "new_auto": sum(f["new_auto"] for f in v), "new_auto_pilot20": sum(f["new_auto"] and f["new_label"] in S.TARGET20 for f in v)}
        for k, v in [("ALL", ws), ("agree", [f for f in ws if f["agree"]]), ("disagree", [f for f in ws if not f["agree"]])]])
    dis = []
    for st in ("EXT_EVAL", "INT_REGRESSION_CORE"):
        rs = [f for f in fin if f["set"] == st]
        for a in (True, False):
            sub = [f for f in rs if f["agree"] == a]
            row = {"set": st, "agree": a, "n": len(sub), "hybrid_b_auto": sum(f["hybrid_b_auto"] for f in sub), "new_auto": sum(f["new_auto"] for f in sub)}
            if st == "INT_REGRESSION_CORE":
                row["linear_correct_rate"] = S.rnd(sum(f["lin_top1"] == f["gold_concept"] for f in sub) / len(sub)) if sub else None
                row["hybrid_b_correct_rate"] = S.rnd(sum(f["hybrid_b"] == f["gold_concept"] for f in sub) / len(sub)) if sub else None
            else:
                row["weak_non_symptom_share"] = S.rnd(sum(f["weak_label"] == "WEAK_NON_SYMPTOM" for f in sub) / len(sub)) if sub else None
            dis.append(row)
    S.write_csv(S.OUT / "disagreement_analysis.csv", dis, ["set", "agree", "n", "hybrid_b_auto", "new_auto", "weak_non_symptom_share",
                                                          "linear_correct_rate", "hybrid_b_correct_rate"])
    reg = []
    for name in ("LINEAR_ONLY", "HYBRID_B") + tuple(P.ORDER):
        m = base[name]["EVAL"] if name in base else sel["policies"][name]["eval_report_only"]
        reg.append({"policy": name, "REG_n": m.get("INT_REGRESSION_CORE_n"), "auto_precision": m.get("INT_REGRESSION_CORE_auto_precision"),
                    "auto_coverage": m.get("INT_REGRESSION_CORE_auto_coverage"), "known_recall": m.get("INT_REGRESSION_CORE_known_recall")})
    S.write_csv(S.OUT / "regression_utility_analysis.csv", reg)
    print("BEST_POLICY", best, "best_rule", best_rule, "gate_promoted", gate_ok)
    for c in comp:
        print({k: c[k] for k in ("policy", "EVAL_WN_auto_rate", "EVAL_WS_auto_rate", "EVAL_disagree_auto", "REG_auto_precision", "REG_auto_coverage", "DEV_CV_WN_auto")})


_CATS = {}


def cats_of(f, rows):
    if not _CATS:
        for r in S.read_csv(S.DATA / "weak_label_inventory.csv"):
            _CATS[r["row_id"]] = r["categories"]
    return _CATS.get(f["row_id"], "")


if __name__ == "__main__":
    main()
