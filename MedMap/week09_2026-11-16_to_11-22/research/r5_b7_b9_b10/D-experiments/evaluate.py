"""[합성] 실험 1~10 + 손 사례 채점. 동결 정답(frozen/ground_truth.json) 은 읽기만 한다.
사용: python -I evaluate.py [--mem]   (--mem: tracemalloc 별도 패스 포함)
출력: results_per_instance.csv, results_summary_by_exp.csv, results_summary_overall.csv, results_cases.csv,
      results_stability.csv, results_bvsbp.csv, results_situations.json
"""
import json, os, sys, time, tracemalloc, hashlib, csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "methods"))
from strong import run_B, run_Bp, run_V  # noqa: E402
from weak import run_A, run_C  # noqa: E402

METHODS = {"A_mitplan_style": run_A, "B_joint": run_B, "Bp_modular": run_Bp, "C_naive": run_C, "V_exclude_variant": run_V}
CONFIRM = {"CONVERGED", "CONFIRMED_PLAN", "CONDITIONAL_PLAN"}
STATE_DEP = {"CONDITIONAL_CONFLICT", "CONDITIONAL_PLAN", "INFO_HOLD"}
STATE_INDEP_CONF = {"CONVERGED", "CONFIRMED_PLAN", "REAL_CONFLICT"}
BANNED_WORDS = ("금기", "CONTRAINDICAT")


def check_freeze():
    m = json.load(open(os.path.join(HERE, "frozen", "FREEZE_MANIFEST.json")))
    for f, h in m["sha256"].items():
        assert hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest() == h, f"frozen file changed: {f}"
    return m


def pl(x):
    return sorted(tuple(t) for t in x)


def state_match(kind_t, pay_t, kind_m, pay_m, single):
    if kind_t != kind_m:
        return False
    if kind_t not in ("CONFIRMED", "PREF"):
        return True
    if single:
        return len(pay_m) == 1 and tuple(pay_m[0]) in set(pl(pay_t))
    return pl(pay_t) == pl(pay_m)


def score(gt, out):
    ps_t, ps_m = gt["per_state"], out["per_state"]
    assert set(ps_t) == set(ps_m), (set(ps_t), set(ps_m))
    sm = {k: state_match(ps_t[k][0], ps_t[k][1], ps_m[k][0], list(ps_m[k][1]), out["single_plan"]) for k in ps_t}
    r = {}
    r["label_ok"] = int(gt["final"] == out["final"])
    r["state_ok"] = int(all(sm.values()))
    r["full_ok"] = int(r["label_ok"] and r["state_ok"])
    r["wrong_confirm"] = int(out["final"] in CONFIRM and not r["full_ok"])
    hold_t = {k for k in ps_t if ps_t[k][0] != "CONFIRMED"}
    hold_m = {k for k in ps_m if ps_m[k][0] != "CONFIRMED"}
    r["hold_set_ok"] = int(hold_t == hold_m)
    r["ewas_ok"] = "" if out["ewas"] is None else int(sorted(out["ewas"]) == sorted(gt["ewas"]))
    r["fsew_ok"] = "" if out["fsew"] is None else int(sorted(out["fsew"]) == sorted(gt["fsew"]))
    r["app_ok"] = int(list(out["app"]) == list(gt["app"]))
    r["rule_ok"] = int(list(out["rules"]) == list(gt["rules"]))
    f1 = f2 = f4 = 0
    for k in ps_t:
        kt, km = ps_t[k][0], ps_m[k][0]
        if kt in ("EVIDENCE_GAP", "KNOWLEDGE_GAP") and km in ("CONFIRMED", "PREF"):
            f1 += 1
        if kt == "PREF" and km == "CONFIRMED":
            f2 += 1
        if kt == "EVIDENCE_GAP" and km == "CONFLICT":
            f4 += 1
    r["F1_states"] = f1; r["F2_states"] = f2
    r["F3"] = int(gt["final"] in STATE_DEP and out["final"] in STATE_INDEP_CONF)
    r["F4_states"] = f4 + (1 if (out.get("excluded_out_of_support") and any(ps_t[k][0] == "EVIDENCE_GAP" for k in ps_t)) else 0)
    txt = json.dumps(out, ensure_ascii=False)
    r["F5"] = int(any(b in txt for b in BANNED_WORDS))
    return r


def main():
    man = check_freeze()
    do_mem = "--mem" in sys.argv
    insts = json.load(open(os.path.join(HERE, "inputs", "instances.json")))["instances"]
    GT = json.load(open(os.path.join(HERE, "frozen", "ground_truth.json")))["gt"]
    rows, outs = [], {}
    t_all = time.time()
    for inst in insts:
        gt = GT[inst["id"]]
        for mname, fn in METHODS.items():
            t0 = time.perf_counter(); out = fn(inst); dt = time.perf_counter() - t0
            mem = ""
            if do_mem:
                tracemalloc.start(); fn(inst); mem = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
            outs[(inst["id"], mname)] = out
            row = dict(id=inst["id"], exp=inst["exp"], method=mname, gt_final=gt["final"], m_final=out["final"],
                       n_states=gt["n_states"], n_plans=gt["n_plans"], family=inst["params"].get("family", ""),
                       level=inst["params"].get("level", ""), time_s=round(dt, 6), peak_mem_bytes=mem,
                       nogt=int(gt["final"] == "NO_GROUND_TRUTH"))
            row.update(score(gt, out))
            rows.append(row)
    print("eval elapsed %.1fs" % (time.time() - t_all))
    keys = list(rows[0].keys())
    with open(os.path.join(HERE, "results_per_instance.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

    metrics = ["label_ok", "state_ok", "full_ok", "wrong_confirm", "hold_set_ok", "ewas_ok", "fsew_ok", "app_ok",
               "rule_ok", "F1_states", "F2_states", "F3", "F4_states", "F5"]

    def summarize(sel):
        out = {"n": len(sel)}
        for m in metrics:
            vals = [r[m] for r in sel if r[m] != ""]
            out[m] = (round(sum(vals) / len(vals), 4) if m.endswith("_ok") or m in ("wrong_confirm", "F3") else sum(vals)) if vals else ""
        gd = [r for r in sel if r["gt_final"] in ("INFO_HOLD", "EVIDENCE_SCOPE_INSUFFICIENT", "KNOWLEDGE_GAP")]
        out["gap_distinction_acc"] = round(sum(r["label_ok"] for r in gd) / len(gd), 4) if gd else ""
        out["gap_n"] = len(gd)
        ts = sorted(r["time_s"] for r in sel)
        out["time_median_s"] = round(ts[len(ts) // 2], 6) if ts else ""
        out["time_max_s"] = round(ts[-1], 6) if ts else ""
        ms = [r["peak_mem_bytes"] for r in sel if r["peak_mem_bytes"] != ""]
        out["mem_peak_max_bytes"] = max(ms) if ms else ""
        return out

    valid = [r for r in rows if not r["nogt"]]
    summ_exp = []
    for exp in sorted({r["exp"] for r in rows}):
        for mname in METHODS:
            sel = [r for r in valid if r["exp"] == exp and r["method"] == mname]
            if sel:
                summ_exp.append(dict(exp=exp, method=mname, **summarize(sel)))
    with open(os.path.join(HERE, "results_summary_by_exp.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ_exp[0].keys())); w.writeheader(); w.writerows(summ_exp)
    summ_all = [dict(method=m, **summarize([r for r in valid if r["method"] == m and r["exp"] != "case"])) for m in METHODS]
    with open(os.path.join(HERE, "results_summary_overall.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ_all[0].keys())); w.writeheader(); w.writerows(summ_all)

    # 손 사례
    cases = [r for r in rows if r["exp"] == "case"]
    with open(os.path.join(HERE, "results_cases.csv"), "w", newline="") as f:
        cols = ["id", "method", "gt_final", "m_final", "label_ok", "state_ok", "full_ok", "ewas_ok", "F1_states", "F2_states", "F3", "F4_states"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(cases)

    # 안정성 (E5/E6/E7 family, 인접 수준)
    stab = []
    for exp in ("E5", "E6", "E7"):
        fam = defaultdict(list)
        for r in rows:
            if r["exp"] == exp:
                fam[(r["family"], r["method"])].append(r)
        order = {"E6": ["0", "1/20", "1/10", "1/5", "1/3"]}
        agg = defaultdict(lambda: [0, 0, 0])
        for (fa, m), lst in fam.items():
            if exp == "E6":
                lst.sort(key=lambda r: order["E6"].index(str(r["level"])))
            else:
                lst.sort(key=lambda r: int(r["level"]))
            for a, b in zip(lst, lst[1:]):
                if a["nogt"] or b["nogt"]:
                    continue
                t_same = a["gt_final"] == b["gt_final"]; m_same = a["m_final"] == b["m_final"]
                agg[m][0] += 1
                agg[m][1] += int(t_same and not m_same)
                agg[m][2] += int((not t_same) and m_same)
        for m, (n, unn, ins) in agg.items():
            stab.append(dict(exp=exp, method=m, adjacent_pairs=n, unnecessary_change=unn, insensitive=ins))
    with open(os.path.join(HERE, "results_stability.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stab[0].keys())); w.writeheader(); w.writerows(stab)

    # B vs B' 차이 원인 분리
    by = defaultdict(dict)
    for r in rows:
        by[r["id"]][r["method"]] = r
    instd = {i["id"]: i for i in insts}
    diffs = []
    for iid, d in by.items():
        b, bp = d["B_joint"], d["Bp_modular"]
        if b["nogt"]:
            continue
        if (b["full_ok"], b["ewas_ok"]) != (bp["full_ok"], bp["ewas_ok"]):
            ob, obp = outs[(iid, "B_joint")], outs[(iid, "Bp_modular")]
            st_diff = [k for k in ob["per_state"] if ob["per_state"][k] != obp["per_state"][k]]
            inst = instd[iid]
            xv = inst["patient_cov"]["x1_var"]
            shared = xv is not None and inst["obs"][xv] == "U"
            cause = []
            if st_diff:
                cause.append("shared_variable_lost_in_module_combination" if shared else "per_state_other")
            if b["ewas_ok"] != bp["ewas_ok"] and not st_diff:
                cause.append("mixed_quantifier_EwAs_vs_AsEw")
            diffs.append(dict(id=iid, exp=b["exp"], gt_final=b["gt_final"], B_final=b["m_final"], Bp_final=bp["m_final"],
                              B_full_ok=b["full_ok"], Bp_full_ok=bp["full_ok"], B_ewas_ok=b["ewas_ok"], Bp_ewas_ok=bp["ewas_ok"],
                              states_differ=";".join(st_diff), shared_var=int(shared), cause="|".join(cause)))
    with open(os.path.join(HERE, "results_bvsbp.csv"), "w", newline="") as f:
        cols = ["id", "exp", "gt_final", "B_final", "Bp_final", "B_full_ok", "Bp_full_ok", "B_ewas_ok", "Bp_ewas_ok", "states_differ", "shared_var", "cause"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(diffs)

    # 상황 분류 (1)~(5)
    sit = {"1_A_fails_B_succeeds": [], "2_B_and_Bp_both_fail": [], "2b_B_fails_any": [], "4_knowledge_gap_truth": [],
           "5_no_ground_truth": [], "Bp_fails_B_succeeds": []}
    for iid, d in by.items():
        a, b, bp = d["A_mitplan_style"], d["B_joint"], d["Bp_modular"]
        if a["nogt"]:
            sit["5_no_ground_truth"].append(iid); continue
        if a["gt_final"] == "KNOWLEDGE_GAP":
            sit["4_knowledge_gap_truth"].append(iid)
        bok = b["full_ok"] and b["ewas_ok"] == 1
        bpok = bp["full_ok"] and bp["ewas_ok"] == 1
        if not a["full_ok"] and bok:
            sit["1_A_fails_B_succeeds"].append(iid)
        if not bok and not bpok:
            sit["2_B_and_Bp_both_fail"].append(iid)
        if not bok:
            sit["2b_B_fails_any"].append(iid)
        if bok and not bpok:
            sit["Bp_fails_B_succeeds"].append(iid)
    # (5) 정답 없음 인스턴스에서 각 방법의 출력
    nogt_out = defaultdict(lambda: defaultdict(int))
    for iid in sit["5_no_ground_truth"]:
        for m in METHODS:
            nogt_out[m][by[iid][m]["m_final"]] += 1
    res = {k: {"count": len(v), "ids_head": sorted(v)[:15]} for k, v in sit.items()}
    res["no_ground_truth_method_outputs"] = {m: dict(v) for m, v in nogt_out.items()}
    res["freeze_manifest"] = man
    json.dump(res, open(os.path.join(HERE, "results_situations.json"), "w"), indent=1, ensure_ascii=False)
    for r in summ_all:
        print(r)
    print(json.dumps({k: len(v) for k, v in sit.items()}))
    print("B vs Bp diffs:", len(diffs))


if __name__ == "__main__":
    main()
