"""STEP21 평가: 4개 baseline(EXACT · FUZZY · COMBINED(exact→fuzzy) · MAPPER(현재 제품 매퍼, 읽기 전용)).

threshold(FUZZY·COMBINED)는 **dev split 에서만** 아래 규칙으로 고른 뒤 test 에 고정 적용한다(test 를 보고 고르지 않음).
  T_high  = grid(0.30~1.00, 0.05) 중 dev AUTO precision ≥ 0.95 이고 AUTO ≥ 5 건인 가장 작은 값(없으면 1.01 = 자동 수락 없음)
  T_low   = grid 중 T_high 이하에서 dev unknown F1(정답 없음 ↔ ABSTAIN) 최대값
  T_multi = grid 중 dev concept micro-F1 최대값(복수 증상 추출용)
정책: conf ≥ T_high → AUTO_ACCEPT, T_low ≤ conf < T_high → ASK_CONFIRMATION, conf < T_low → ABSTAIN.
EXACT·MAPPER 는 confidence 가 1/0 뿐이라 AUTO_ACCEPT 또는 ABSTAIN.
gate(엔지니어링 기준, 임상 기준 아님) 는 test split 으로 판정.
출력: outputs/metrics.json, outputs/error_analysis.csv, outputs/confidence_analysis.csv, outputs/schema_mapping_check.csv,
      outputs/combined_predictions.csv, outputs/manifest.json
"""
import json
from collections import Counter

import el_common as c

GRID = [round(0.30 + 0.05 * i, 2) for i in range(15)]
SUBSETS = {
    "all": lambda g: True, "tier_A": lambda g: g["tier"] == "A", "tier_AB": lambda g: g["tier"] in "AB",
    "tier_C": lambda g: g["tier"] == "C", "tier_D": lambda g: g["tier"] == "D",
    "tier_AB_seen": lambda g: g["tier"] in "AB" and g["lexical_exposure"] == "seen",
    "tier_AB_novel": lambda g: g["tier"] in "AB" and g["lexical_exposure"] == "novel",
}
_ALIAS_EVS = {e["evidence_id"] for e in json.load(open(c.REPO / "medmap/intake/aliases_ko.json", encoding="utf-8"))["entries"]}
MAPPER_COVERED = sorted({cpt for cpt, evs in c.PILOT.items() if set(evs) & _ALIAS_EVS})
SUBSETS["tier_AB_mapper_covered_concepts"] = lambda g: g["tier"] in "AB" and g["primary_concept"] in MAPPER_COVERED
SUBSETS["tier_AB_mapper_uncovered_concepts"] = lambda g: g["tier"] in "AB" and g["primary_concept"] not in MAPPER_COVERED
NEAR = {frozenset(p) for p in [("dizziness", "EV:E_82"), ("vomiting", "nausea"), ("hematemesis", "vomiting"),
                               ("fatigue", "limb_weakness"), ("cough", "hemoptysis"), ("loc", "dizziness"),
                               ("dyspnea", "EV:E_75"), ("fatigue", "EV:E_175"), ("hematemesis", "hemoptysis")]}
SITE = {frozenset(p) for p in [("pain", "sore_throat"), ("pain", "palpitations"), ("pain", "heartburn"),
                               ("sore_throat", "heartburn"), ("pain", "EV:E_30"), ("pain", "dizziness")]}


def load_preds():
    out = {}
    for name in ("exact", "mapper"):
        d = {}
        for r in c.read_csv(c.OUT / f"{name}_predictions.csv"):
            pm = json.loads(r["pred_mentions"])
            d[r["utterance_id"]] = {"ranked": [x for x in r["ranked_top5"].split(";") if x], "mentions": pm,
                                    "conf": float(r["confidence"])}
        out[name] = d
    fz = {}
    for r in c.read_csv(c.OUT / "fuzzy_predictions.csv"):
        top = json.loads(r["ranked_top5_scored"])
        fz[r["utterance_id"]] = {"ranked": [t["concept"] for t in top], "scored": top,
                                 "conf": float(r["confidence"]) if top else 0.0}
    out["fuzzy_raw"] = fz
    return out


def fuzzy_view(fz, t_multi):
    return {u: {"ranked": v["ranked"], "conf": v["conf"],
                "mentions": [{"concept": t["concept"], "status": "present"} for t in v["scored"] if t["score"] >= t_multi]}
            for u, v in fz.items()}


def combined_view(ex, fz, t_multi):
    out = {}
    for u in ex:
        if ex[u]["mentions"]:
            rk = ex[u]["ranked"] + [x for x in fz[u]["ranked"] if x not in ex[u]["ranked"]]
            out[u] = {"ranked": rk[:5], "conf": 1.0, "mentions": ex[u]["mentions"], "via": "exact"}
        else:
            out[u] = {"ranked": fz[u]["ranked"], "conf": fz[u]["conf"], "via": "fuzzy",
                      "mentions": [{"concept": t["concept"], "status": "present"} for t in fz[u]["scored"] if t["score"] >= t_multi]}
    return out


def policy(conf, th):
    if th is None:
        return "AUTO_ACCEPT" if conf >= 1.0 else "ABSTAIN"
    if conf >= th["T_high"]:
        return "AUTO_ACCEPT"
    if conf >= th["T_low"]:
        return "ASK_CONFIRMATION"
    return "ABSTAIN"


def pred_status(p, concept):
    for m in p["mentions"]:
        if m["concept"] == concept:
            return m["status"]
    return None


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return p, r, f


def rnd(x):
    return None if x is None else round(x, 4)


def metrics(gold, preds, th):
    n = len(gold)
    link = [g for g in gold if g["should_link"] == "True"]
    top1 = sum(1 for g in link if preds[g["utterance_id"]]["ranked"][:1] and preds[g["utterance_id"]]["ranked"][0] in c.patient_concepts(g))
    rec = {k: sum(1 for g in link if c.patient_concepts(g) & set(preds[g["utterance_id"]]["ranked"][:k])) for k in (1, 3, 5)}
    tp = fp = fn = 0
    stp = sfp = sfn = 0
    exact_set = 0
    for g in gold:
        p = preds[g["utterance_id"]]
        ps = {m["concept"] for m in p["mentions"]}
        gs = c.patient_concepts(g)
        tp += len(ps & gs); fp += len(ps - gs); fn += len(gs - ps)
        exact_set += ps == gs
        gp = {(m["concept"], m["status"]) for m in g["gold_mentions"] if m["subject"] == "patient"}
        pp = {(m["concept"], m["status"]) for m in p["mentions"]}
        stp += len(gp & pp); sfp += len(pp - gp); sfn += len(gp - pp)
    neg = [(g, m) for g in gold for m in g["gold_mentions"] if m["subject"] == "patient" and m["status"] == "absent"]
    tmp = [(g, m) for g in gold for m in g["gold_mentions"] if m["subject"] == "patient" and m["status"] == "historical"]
    oth = [(g, m) for g in gold for m in g["gold_mentions"] if m["subject"] == "other" and m["concept"] not in c.patient_concepts(g)]

    def detect(lst):
        det = [(g, m) for g, m in lst if pred_status(preds[g["utterance_id"]], m["concept"]) is not None]
        ok = [(g, m) for g, m in det if pred_status(preds[g["utterance_id"]], m["concept"]) == m["status"]]
        return {"n_mentions": len(lst), "concept_detection_rate": rnd(len(det) / len(lst)) if lst else None,
                "status_accuracy_given_detected": rnd(len(ok) / len(det)) if det else None,
                "end_to_end_correct_rate": rnd(len(ok) / len(lst)) if lst else None}
    pol = {g["utterance_id"]: policy(preds[g["utterance_id"]]["conf"], th) for g in gold}
    gu = {g["utterance_id"] for g in gold if g["should_link"] != "True"}
    pu = {u for u, v in pol.items() if v == "ABSTAIN"}
    auto = [g for g in gold if pol[g["utterance_id"]] == "AUTO_ACCEPT"]
    auto_ok = [g for g in auto if g["should_link"] == "True" and preds[g["utterance_id"]]["ranked"][:1]
               and preds[g["utterance_id"]]["ranked"][0] in c.patient_concepts(g)]
    ask = [g for g in gold if pol[g["utterance_id"]] == "ASK_CONFIRMATION"]
    ask_hit = [g for g in ask if g["should_link"] == "True" and g["primary_concept"] in preds[g["utterance_id"]]["ranked"][:3]]
    P, R, F = prf(tp, fp, fn)
    SP, SR, SF = prf(stp, sfp, sfn)
    up = len(gu & pu) / len(pu) if pu else None
    ur = len(gu & pu) / len(gu) if gu else None
    return {
        "n_utterances": n, "n_should_link": len(link),
        "top1_accuracy": rnd(top1 / len(link)) if link else None,
        "recall_at_1": rnd(rec[1] / len(link)) if link else None, "recall_at_3": rnd(rec[3] / len(link)) if link else None,
        "recall_at_5": rnd(rec[5] / len(link)) if link else None,
        "concept_micro_precision": rnd(P), "concept_micro_recall": rnd(R), "concept_micro_f1": rnd(F),
        "exact_set_match": rnd(exact_set / n) if n else None,
        "status_aware_micro_f1": rnd(SF), "status_aware_micro_precision": rnd(SP), "status_aware_micro_recall": rnd(SR),
        "negation": detect(neg), "temporal_historical": detect(tmp),
        "other_person": {"n_mentions": len(oth), "leak_rate": rnd(sum(1 for g, m in oth if pred_status(preds[g["utterance_id"]], m["concept"]) is not None) / len(oth)) if oth else None},
        "unknown_rejection": {"n_gold_unknown": len(gu), "n_pred_abstain": len(pu), "precision": rnd(up), "recall": rnd(ur)},
        "policy": {"auto_accept_rate": rnd(len(auto) / n) if n else None, "auto_accept_precision": rnd(len(auto_ok) / len(auto)) if auto else None,
                   "n_auto": len(auto), "n_wrong_auto": len(auto) - len(auto_ok),
                   "n_auto_on_should_not_link": sum(1 for g in auto if g["should_link"] != "True"),
                   "ask_confirmation_rate": rnd(len(ask) / n) if n else None,
                   "ask_top3_contains_primary": rnd(len(ask_hit) / sum(1 for g in ask if g["should_link"] == "True")) if any(g["should_link"] == "True" for g in ask) else None,
                   "abstention_rate": rnd(len(pu) / n) if n else None},
    }


def choose_thresholds(dev, fz_raw):
    best_multi = max(GRID, key=lambda t: (metrics(dev, fuzzy_view(fz_raw, t), {"T_high": 9, "T_low": 0})["concept_micro_f1"] or 0, -t))
    view = fuzzy_view(fz_raw, best_multi)
    t_high = 1.01
    for t in GRID:
        m = metrics(dev, view, {"T_high": t, "T_low": 0})["policy"]
        if m["n_auto"] >= 5 and (m["auto_accept_precision"] or 0) >= 0.95:
            t_high = t
            break

    def unk_f1(t):
        u = metrics(dev, view, {"T_high": max(t_high, t), "T_low": t})["unknown_rejection"]
        p, r = u["precision"] or 0, u["recall"] or 0
        return 2 * p * r / (p + r) if p + r else 0
    t_low = max([t for t in GRID if t <= t_high], key=lambda t: (unk_f1(t), -t))
    return {"T_high": t_high, "T_low": t_low, "T_multi": best_multi,
            "rule": "chosen on dev only (see module docstring)", "dev_unknown_f1_at_T_low": round(unk_f1(t_low), 4)}


def gate(m_test):
    ab, al = m_test["tier_AB"], m_test["all"]
    t1, r3, ap = ab["top1_accuracy"] or 0, ab["recall_at_3"] or 0, al["policy"]["auto_accept_precision"]
    if t1 >= 0.90 and (ap or 0) >= 0.95 and r3 >= 0.97:
        v = "GO"
    elif (0.75 <= t1 < 0.90) or (ap is not None and 0.85 <= ap < 0.95):
        v = "CONDITIONAL"
    else:
        v = "NO_GO"
    return {"verdict": v, "tier_AB_top1": t1, "tier_AB_recall_at_3": r3, "auto_accept_precision": ap,
            "n_wrong_auto": al["policy"]["n_wrong_auto"]}


def failure_categories(g, p, pol):
    cats = []
    pc = c.patient_concepts(g)
    ps = {m["concept"] for m in p["mentions"]}
    if g["should_link"] != "True":
        if pol != "ABSTAIN" and (ps or p["ranked"]):
            cats.append("unknown_forced_mapping")
            if "disease" in g["reason"]:
                cats.append("disease_symptom_confusion")
            if "only" in g["reason"] and ("quality" in g["reason"] or "site" in g["reason"] or "onset" in g["reason"]):
                cats.append("attribute_symptom_confusion")
        if any(m["subject"] == "other" and m["concept"] in ps for m in g["gold_mentions"]):
            cats.append("other_person_failure")
        return cats
    for m in g["gold_mentions"]:
        st = pred_status(p, m["concept"])
        if m["subject"] == "other" and m["concept"] not in pc and st is not None:
            cats.append("other_person_failure")
        if m["subject"] == "patient" and m["status"] == "absent" and st != "absent":
            cats.append("negation_failure")
        if m["subject"] == "patient" and m["status"] == "historical" and st is not None and st != "historical":
            cats.append("temporal_failure")
    if g["is_multi"] == "True" and not pc <= ps:
        cats.append("multi_symptom_failure")
    top = p["ranked"][0] if p["ranked"] else ""
    if top not in pc:
        if not top:
            cats.append("spelling_variation" if g["utt_type"] == "S" else
                        "colloquial_expression" if g["tier"] == "B" else "synonym_unseen")
        else:
            pair = frozenset((g["primary_concept"], top))
            cats.append("site_confusion" if pair in SITE else "overly_broad_or_specific" if pair in NEAR
                        else "spelling_variation" if g["utt_type"] == "S" else "lexical_false_match")
            if "disease" in g["reason"]:
                cats.append("disease_symptom_confusion")
    return sorted(set(cats))


SCHEMA = {"site": "site", "laterality": "laterality", "onset": "onset", "duration": "duration", "severity": "severity",
          "quality": "quality", "frequency": "frequency", "temporal": "temporal_pattern", "position": "position",
          "aggravating": "aggravating_factors", "trigger": "aggravating_factors", "context": "context",
          "rate": "quality", "rhythm": "quality", "pattern": "temporal_pattern"}


def main():
    gold = c.load_gold()
    for g in gold:
        for k in ("should_link", "is_multi"):
            g[k] = str(g[k])
    P = load_preds()
    dev = [g for g in gold if g["split"] == "dev"]
    test = [g for g in gold if g["split"] == "test"]
    th = choose_thresholds(dev, P["fuzzy_raw"])
    views = {
        "BASELINE_EXACT": (P["exact"], None),
        "BASELINE_FUZZY": (fuzzy_view(P["fuzzy_raw"], th["T_multi"]), th),
        "BASELINE_COMBINED_EXACT_THEN_FUZZY": (combined_view(P["exact"], P["fuzzy_raw"], th["T_multi"]), th),
        "BASELINE_MEDMAP_INTAKE_MAPPER_v1_2": (P["mapper"], None),
    }
    comb = views["BASELINE_COMBINED_EXACT_THEN_FUZZY"][0]
    c.write_csv(c.OUT / "combined_predictions.csv", [
        {"utterance_id": g["utterance_id"], "split": g["split"], "text_ko": g["text_ko"], "via": comb[g["utterance_id"]]["via"],
         "ranked_top5": ";".join(comb[g["utterance_id"]]["ranked"]), "confidence": comb[g["utterance_id"]]["conf"],
         "pred_concepts": ";".join(m["concept"] for m in comb[g["utterance_id"]]["mentions"]),
         "policy": policy(comb[g["utterance_id"]]["conf"], th)} for g in gold])
    res = {"thresholds_fuzzy_family": th, "mapper_alias_covered_pilot_concepts": MAPPER_COVERED, "baselines": {}}
    errors = []
    for name, (pv, t) in views.items():
        block = {}
        for sp_name, sp in (("dev", dev), ("test", test), ("all", gold)):
            block[sp_name] = {k: metrics([g for g in sp if f(g)], pv, t) for k, f in SUBSETS.items()}
        block["gate_on_test"] = gate(block["test"])
        res["baselines"][name] = block
        for g in gold:
            pol = policy(pv[g["utterance_id"]]["conf"], t)
            cats = failure_categories(g, pv[g["utterance_id"]], pol)
            if cats:
                errors.append({"baseline": name, "utterance_id": g["utterance_id"], "split": g["split"], "tier": g["tier"],
                               "text_ko": g["text_ko"], "gold": g["patient_concepts"] or "(none)",
                               "gold_mentions": json.dumps(g["gold_mentions"], ensure_ascii=False),
                               "pred_top3": ";".join(pv[g["utterance_id"]]["ranked"][:3]),
                               "pred_set": ";".join(m["concept"] + ":" + m["status"] for m in pv[g["utterance_id"]]["mentions"]),
                               "policy": pol, "categories": ";".join(cats)})
    c.write_csv(c.OUT / "error_analysis.csv", errors)
    res["error_category_counts_test"] = {
        b: dict(Counter(cat for e in errors if e["baseline"] == b and e["split"] == "test" for cat in e["categories"].split(";")))
        for b in views}
    # confidence 분석: fuzzy 점수 grid × split
    conf_rows = []
    for name in ("BASELINE_FUZZY", "BASELINE_COMBINED_EXACT_THEN_FUZZY"):
        pv = views[name][0]
        for sp_name, sp in (("dev", dev), ("test", test)):
            for t in GRID + [1.01]:
                m = metrics(sp, pv, {"T_high": t, "T_low": min(th["T_low"], t)})["policy"]
                conf_rows.append({"baseline": name, "split": sp_name, "T_high": t, "T_low": min(th["T_low"], t),
                                  "chosen": t == th["T_high"], "n_auto": m["n_auto"], "auto_accept_rate": m["auto_accept_rate"],
                                  "auto_accept_precision": m["auto_accept_precision"], "ask_confirmation_rate": m["ask_confirmation_rate"],
                                  "abstention_rate": m["abstention_rate"]})
    c.write_csv(c.OUT / "confidence_analysis.csv", conf_rows)
    # schema 연결 확인(21절)
    sch = []
    for g in gold:
        for concept, attrs in g["attributes"].items():
            for k, v in attrs.items():
                sch.append({"utterance_id": g["utterance_id"], "text_ko": g["text_ko"], "concept": concept, "attribute": k,
                            "value": v, "schema_field": SCHEMA.get(k, ""),
                            "fits_draft_schema": k in SCHEMA})
    c.write_csv(c.OUT / "schema_mapping_check.csv", sch)
    res["schema_check"] = {"attribute_values": len(sch), "fit_draft_schema": sum(1 for s in sch if s["fits_draft_schema"]),
                           "need_concept_specific_fields": sorted({s["attribute"] for s in sch if not s["fits_draft_schema"]}),
                           "utterances_with_attributes": len({s["utterance_id"] for s in sch})}
    # 판정
    fam = ["BASELINE_EXACT", "BASELINE_FUZZY", "BASELINE_COMBINED_EXACT_THEN_FUZZY"]
    gates = {b: res["baselines"][b]["gate_on_test"]["verdict"] for b in views}
    order = {"GO": 0, "CONDITIONAL": 1, "NO_GO": 2}
    best = min(views, key=lambda b: (order[gates[b]], -(res["baselines"][b]["test"]["tier_AB"]["top1_accuracy"] or 0)))
    ab_novel = {b: res["baselines"][b]["test"]["tier_AB_novel"]["top1_accuracy"] for b in views}
    ab_seen = {b: res["baselines"][b]["test"]["tier_AB_seen"]["top1_accuracy"] for b in views}
    status_ok = {b: (res["baselines"][b]["all"]["all"]["negation"]["end_to_end_correct_rate"],
                     res["baselines"][b]["all"]["all"]["temporal_historical"]["end_to_end_correct_rate"],
                     res["baselines"][b]["all"]["all"]["other_person"]["leak_rate"]) for b in views}
    res["decisions"] = {
        "gates_on_test": gates, "best_baseline": best, "KOREAN_ENTITY_LINKING": gates[best],
        "DICTIONARY_BASELINE": "PASS" if gates["BASELINE_EXACT"] == "GO" else "FAIL",
        "FUZZY_BASELINE": "PASS" if gates["BASELINE_FUZZY"] == "GO" else "FAIL",
        "pass_definition": "PASS only when the engineering gate on test is GO",
        "tier_AB_top1_seen_vs_novel_test": {b: {"seen": ab_seen[b], "novel": ab_novel[b]} for b in views},
        "LEARNED_LINKER_NEEDED": "YES" if max(ab_novel[b] or 0 for b in fam + ["BASELINE_MEDMAP_INTAKE_MAPPER_v1_2"]) < 0.90 else "NO",
        "learned_linker_rule": "YES if every baseline's test Tier A+B novel-expression Top-1 < 0.90",
        "negation_temporal_otherperson_all_splits": {b: {"negation_correct": v[0], "historical_correct": v[1], "other_person_leak": v[2]} for b, v in status_ok.items()},
        "NLU_NEEDED": "YES" if all((v[1] or 0) < 0.90 or (v[2] or 0) > 0.10 or (v[0] or 0) < 0.90 for v in status_ok.values()) else "NO",
        "nlu_rule": "YES if no baseline reaches negation≥0.90, historical≥0.90 and other-person leak≤0.10 together",
        "BASELINE_3_EMBEDDING": "NOT_EVALUATED - only local multilingual encoder is xlm-roberta-base (MLM, no sentence-similarity training); "
                                "no SapBERT / sentence-transformers download per instructions",
    }
    json.dump(res, open(c.OUT / "metrics.json", "w"), ensure_ascii=False, indent=1)
    files = sorted(list(c.DATA.glob("*")) + [p for p in c.OUT.glob("*") if p.name != "manifest.json"])
    man = {"inputs": {str(p): c.sha256(p) for p in (c.TERMINOLOGY_KO, c.INITIAL_KO, c.QLABELS_KO, c.DDX_EVIDENCES,
                                                     c.STEP20 / "curation/curated_mappings.tsv", c.REPO / "medmap/intake/aliases_ko.json",
                                                     c.REPO / "medmap/intake/mapper.py")},
           "files": [{"file": str(p.relative_to(c.STEP)), "sha256": c.sha256(p),
                      "rows": (sum(1 for _ in open(p, encoding="utf-8")) - 1) if p.suffix in (".csv", ".tsv") else None} for p in files],
           "determinism": "no randomness; rerun via run_all.sh should reproduce identical SHA256",
           "provenance": "all 274 gold utterances are synthetic (Claude-authored); gold labels by Claude, not clinician-reviewed"}
    json.dump(man, open(c.OUT / "manifest.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(th))
    for b in views:
        t = res["baselines"][b]["test"]
        print(b, gates[b], "AB top1", t["tier_AB"]["top1_accuracy"], "R@3", t["tier_AB"]["recall_at_3"],
              "F1", t["all"]["concept_micro_f1"], "auto P", t["all"]["policy"]["auto_accept_precision"],
              "ask", t["all"]["policy"]["ask_confirmation_rate"], "abst", t["all"]["policy"]["abstention_rate"],
              "unk P/R", t["all"]["unknown_rejection"]["precision"], t["all"]["unknown_rejection"]["recall"])
    print({k: v for k, v in res["decisions"].items() if k not in ("tier_AB_top1_seen_vs_novel_test", "negation_temporal_otherperson_all_splits")})


if __name__ == "__main__":
    main()
