"""주 인스턴스 실행: 판정표, B7 쌍 상태, B10 근거 상태, 단순 기준선의 허위 확정, MILP 대조.
[합성 실험] 실행: /home/<user>/ai_env/bin/python -I run_main.py
"""
import copy, csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrated_model as im

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
CERTAIN = {"ALWAYS_BEST", "NEVER_BEST", "HARD_EXCLUDED"}


def judgments(inst, norm):
    SP, SK = im.clinical_states(inst), im.know_states(inst)
    plans = im.all_plans(inst)
    return [im.categorize(inst, x, norm, plans, SP, SK) for x in plans], SP, SK, plans


def pair_status(inst, SP, SK):
    rows = []
    for r in inst["rules"]:
        hits = [im.lits_true(r["lits"], {**P, **K}) for P in SP for K in SK]
        info_vars = {v for v, _ in r["lits"] if v in inst["clin_vars"]}
        know_vars = {v for v, _ in r["lits"] if v in inst["know_vars"]}
        if all(hits):
            st = "ACTUAL_CONFLICT_ALL_STATES" if r["kind"] != "DUPLICATE" else "DUPLICATE"
        elif not any(hits):
            st = "NOT_TRIGGERED"
        elif know_vars:
            st = "UNDETERMINED_KNOWLEDGE (interaction evidence insufficient)"
        else:
            st = "CONDITIONAL_CONFLICT_INFO_DEPENDENT (unconfirmed: " + ",".join(sorted(info_vars)) + ")"
        rows.append({"item": r["name"], "kind": r["kind"], "patient_status": st,
                     "states_triggered": f"{sum(hits)}/{len(hits)}"})
    for sy in inst["synergy"]:
        L, U = sy["interval"]
        st = "COMPLEMENT_CERTAIN" if L > 0 else ("COMPLEMENT_POSSIBLE (L<=0<U)" if U > 0 else "NO_COMPLEMENT")
        rows.append({"item": "+".join(sy["pair"]), "kind": "SYNERGY", "patient_status": st,
                     "states_triggered": f"interval={sy['interval']}"})
    # guideline-level joint satisfiability
    plans = im.all_plans(inst); tot = 0; empty = 0
    for P in SP:
        for K in SK:
            for b in inst["bcap_options"]:
                tot += 1
                if not any(im.feasible(inst, x, P, K, b) for x in plans):
                    empty += 1
    rows.append({"item": "GA+GB jointly", "kind": "GUIDELINE_SET",
                 "patient_status": "JOINTLY_UNSATISFIABLE_ALL" if empty == tot else
                 ("JOINTLY_UNSATISFIABLE_SOME" if empty else "SATISFIABLE_ALL"),
                 "states_triggered": f"no feasible plan in {empty}/{tot} states"})
    return rows


def b10_status(inst, SP, norm):
    rows = []
    for d, crits in inst["effects"].items():
        for c in crits:
            per = [im.effect_interval(inst, d, c, P, norm) for P in SP]
            def agg(key):
                vals = sorted({p[3].get(key, "-") for p in per})
                return vals[0] + "_ALL_STATES" if len(vals) == 1 else "INFO_DEPENDENT{" + "|".join(vals) + "}"
            bots = [p[2] for p in per]
            rows.append({"drug": d, "criterion": c, "norm": norm,
                         "E1_eligibility": agg("E1"), "E2_similar_participants": agg("E2"),
                         "E3_generalization": agg("E3"),
                         "E4_info_insufficient": "YES" if len({str(p[3]) for p in per}) > 1 else "NO",
                         "E5_no_evidence": "ALL" if all(p[3].get("E1") == "NO_TRIAL" for p in per) else
                         ("SOME" if any(p[3].get("E1") == "NO_TRIAL" for p in per) else "NO"),
                         "effect_undefined(⊥)": "ALL" if all(bots) else ("SOME" if any(bots) else "NO"),
                         "intervals_by_state": ";".join(
                             ("⊥" if p[2] else f"[{p[0]:.2f},{p[1]:.2f}]") for p in per)})
    return rows


def naive_variant(inst, kind):
    v = copy.deepcopy(inst)
    if kind == "bottom_as_zero":     # ⊥ -> 0 (알 수 없음을 없음으로)
        for d, crits in v["effects"].items():
            for c, tab in crits.items():
                crits[c] = [(l, ("IV", 0.0, 0.0) if e[0] in ("NONE", "OUT", "PUB") else e, t) for l, e, t in tab]
    elif kind == "closed_world":     # U/C -> F
        v["obs"] = {k: ("F" if o in ("U", "C") else o) for k, o in v["obs"].items()}
    elif kind == "point_preference":  # 가중치를 W 중심 한 점으로 고정
        v["W"] = {"order": [], "lo": {"benA": 0.4, "benB": 0.3, "burden": 0.3},
                  "hi": {"benA": 0.4, "benB": 0.3, "burden": 0.3}}
    elif kind == "unknown_interaction_as_none":
        v["know_vars"] = []
        v["rules"] = [r for r in v["rules"] if r["kind"] != "UNKNOWN_INTERACTION"]
    elif kind == "eligible_means_applicable":  # E1 충족 => 근거 적용(지지 영역 무시)
        for d, crits in v["effects"].items():
            for c, tab in crits.items():
                new = []
                for l, e, t in tab:
                    if e[0] in ("OUT", "PUB") and t.get("E1") == "MET":
                        e = ("IV", 0.15, 0.35) if e[0] == "OUT" else ("IV", e[1], e[2])
                    new.append((l, e, t))
                crits[c] = new
    elif kind == "point_effect":     # 구간 대신 중점
        for d, crits in v["effects"].items():
            for c, tab in crits.items():
                crits[c] = [(l, ("IV", (e[1] + e[2]) / 2, (e[1] + e[2]) / 2) if e[0] == "IV" else e, t) for l, e, t in tab]
        for sy in v["synergy"]:
            m = sum(sy["interval"]) / 2; sy["interval"] = (m, m)
    elif kind == "bcap_assumed_3":
        v["bcap_options"] = [3]
    return v


def main():
    t0 = time.time()
    inst = im.MAIN
    log = []
    allrec = {}
    for norm in im.NORMS:
        recs, SP, SK, plans = judgments(inst, norm)
        allrec[norm] = {r["plan"]: r for r in recs}
    log.append(f"clinical states |S_P|={len(SP)}: {SP}")
    log.append(f"knowledge states |S_K|={len(SK)}, bcap options {inst['bcap_options']}, plans={len(plans)}")
    # 판정표 + 규범 비교
    rows = []
    for p in allrec["NORM_A"]:
        a, b = allrec["NORM_A"][p], allrec["NORM_B"][p]
        expert = a["category"] != b["category"]
        fl = a.get("flags", {})
        rows.append({"plan": p, "cat_NORM_A": a["category"], "cat_NORM_B": b["category"],
                     "final": "EXPERT_JUDGMENT_REQUIRED" if expert else a["category"],
                     **{f"A_{k}": int(v) for k, v in fl.items()},
                     **{f"B_{k}": int(v) for k, v in b.get("flags", {}).items()}})
    with open(os.path.join(OUT, "main_plan_judgments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    ps = pair_status(inst, SP, SK)
    with open(os.path.join(OUT, "main_b7_pair_status.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ps[0].keys())); w.writeheader(); w.writerows(ps)
    b10 = b10_status(inst, SP, "NORM_A") + b10_status(inst, SP, "NORM_B")
    with open(os.path.join(OUT, "main_b10_evidence_status.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(b10[0].keys())); w.writeheader(); w.writerows(b10)
    # 단순 기준선: 허위 확정
    nrows = []
    for kind in ["bottom_as_zero", "closed_world", "point_preference", "unknown_interaction_as_none",
                 "eligible_means_applicable", "point_effect", "bcap_assumed_3"]:
        v = naive_variant(inst, kind)
        recs, _, _, _ = judgments(v, "NORM_A")
        nmap = {r["plan"]: r["category"] for r in recs}
        false_cert, changed, examples = 0, 0, []
        for p, r in allrec["NORM_A"].items():
            honest = r["category"]
            if allrec["NORM_A"][p]["category"] != allrec["NORM_B"][p]["category"]:
                honest = "EXPERT_JUDGMENT_REQUIRED"
            nv = nmap[p]
            if nv != honest:
                changed += 1
                if nv in CERTAIN and honest not in CERTAIN:
                    false_cert += 1
                    examples.append(f"{p}:{honest}->{nv}")
        nrows.append({"naive": kind, "plans": len(nmap), "category_changed": changed,
                      "false_certain": false_cert, "examples": " ; ".join(examples[:6])})
    with open(os.path.join(OUT, "main_naive_false_certainty.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(nrows[0].keys())); w.writeheader(); w.writerows(nrows)
    # MILP 대조 (주 인스턴스, 두 규범)
    mrows, dis = [], 0
    for norm in im.NORMS:
        for x in plans:
            p = "+".join(sorted(x)) or "(none)"
            fl = allrec[norm][p]["flags"]
            m_aa = im.milp_AA(inst, x, norm)
            m_ee = im.milp_exists(inst, x, norm, plans, ())
            m_cp = im.milp_exists(inst, x, norm, plans, ("K", "Q"))
            agree = (m_aa == fl["AA"]) and (m_ee == fl["PKQ"]) and (m_cp == fl["P"])
            dis += (not agree)
            mrows.append({"norm": norm, "plan": p, "brute_AA": int(fl["AA"]), "milp_AA": int(m_aa),
                          "brute_EE": int(fl["PKQ"]), "milp_EE": int(m_ee),
                          "brute_CLOSE_P": int(fl["P"]), "milp_CLOSE_P": int(m_cp), "agree": int(agree)})
    with open(os.path.join(OUT, "main_milp_vs_brute.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mrows[0].keys())); w.writeheader(); w.writerows(mrows)
    log.append(f"MILP vs brute disagreements (main, 2 norms x {len(plans)} plans x 3 flags): {dis}")
    cats = {}
    for r in rows:
        cats[r["final"]] = cats.get(r["final"], 0) + 1
    log.append(f"final category counts: {cats}")
    for r in rows:
        if r["final"] not in ("HARD_EXCLUDED",):
            log.append(f"  {r['plan']:<12} A={r['cat_NORM_A']:<32} B={r['cat_NORM_B']:<32} final={r['final']}")
    for r in ps:
        log.append(f"  B7 {r}")
    for r in nrows:
        log.append(f"  naive {r}")
    log.append(f"elapsed {time.time()-t0:.2f}s")
    print("\n".join(log))


if __name__ == "__main__":
    main()
