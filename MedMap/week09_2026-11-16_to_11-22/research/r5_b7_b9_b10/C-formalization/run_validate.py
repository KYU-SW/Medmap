"""(1) 변형 인스턴스 V2 판정표  (2) 무작위 합성 인스턴스에서 MILP(AA, EE, CLOSE_P) vs 전수 열거 대조.
[합성 실험] seed 고정. 실행: /home/<user>/ai_env/bin/python -I run_validate.py [n_inst]
"""
import copy, csv, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrated_model as im
from run_main import judgments

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def v2():
    v = copy.deepcopy(im.MAIN)
    v["name"] = "V2_SYNTH"
    v["obs"]["age75"] = "U"                       # 나이 기록 미확인
    v["effects"]["S"]["benB"] = [([("ckd", 0)], ("IV", 0.00, 0.20), {"E1": "MET", "E2": "IN", "E3": "UNASSESSED"}),
                                 ([("ckd", 1)], ("IV", -0.05, 0.15), {"E1": "NOT_MET", "E2": "OUT", "E3": "INDIRECT"})]
    return v


def random_inst(rng):
    v = copy.deepcopy(im.MAIN)
    v["name"] = "RAND"
    for k in ("ckd", "hk", "age75"):
        v["obs"][k] = rng.choice(["T", "F", "U", "U", "C"])
    def iv():
        a = round(rng.uniform(-0.1, 0.4), 2); return (a, round(a + rng.uniform(0.0, 0.25), 2))
    for d, crits in v["effects"].items():
        for c, tab in crits.items():
            new = []
            for lits, ent, tags in tab:
                t = rng.choices(["IV", "OUT", "PUB", "NONE"], weights=[6, 2, 1, 1])[0]
                L, U = iv()
                ent = ("IV", L, U) if t == "IV" else (("PUB", L, U) if t == "PUB" else (t,))
                new.append((lits, ent, tags))
            crits[c] = new
    v["synergy"][0]["interval"] = iv()
    lo_b = round(rng.uniform(0.0, 0.3), 2)
    v["W"] = {"order": [("benA", "benB")] if rng.random() < 0.6 else [],
              "lo": {"burden": lo_b}, "hi": {"burden": round(lo_b + rng.uniform(0.05, 0.6), 2)}}
    v["bcap_options"] = rng.choice([[2, 3], [3], [2], [3, 4]])
    v["pills"]["B2"] = rng.choice([1, 2])
    return v


def main():
    n_inst = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    t0 = time.time()
    # (1) V2
    inst = v2()
    allrec = {}
    for norm in im.NORMS:
        recs, SP, SK, plans = judgments(inst, norm)
        allrec[norm] = {r["plan"]: r for r in recs}
    rows = []
    for p in allrec["NORM_A"]:
        a, b = allrec["NORM_A"][p], allrec["NORM_B"][p]
        rows.append({"plan": p, "cat_NORM_A": a["category"], "cat_NORM_B": b["category"],
                     "final": "EXPERT_JUDGMENT_REQUIRED" if a["category"] != b["category"] else a["category"],
                     **{f"A_{k}": int(x) for k, x in a.get("flags", {}).items()}})
    with open(os.path.join(OUT, "v2_plan_judgments.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"V2 |S_P|={len(SP)}")
    for r in rows:
        if r["final"] != "HARD_EXCLUDED":
            print(f"  {r['plan']:<12} A={r['cat_NORM_A']:<30} B={r['cat_NORM_B']:<30} final={r['final']}")
    # (2) random MILP vs brute
    rng = random.Random(20261118)
    mrows, dis, ncheck, cats = [], 0, 0, {}
    for i in range(n_inst):
        inst = random_inst(rng)
        norm = rng.choice(list(im.NORMS))
        SP, SK = im.clinical_states(inst), im.know_states(inst)
        if not SP:
            cats["DATA_CONFLICT"] = cats.get("DATA_CONFLICT", 0) + 1
            continue
        plans = im.all_plans(inst)
        for x in plans:
            rec = im.categorize(inst, x, norm, plans, SP, SK)
            cats[rec["category"]] = cats.get(rec["category"], 0) + 1
            fl = rec["flags"]
            m_aa = im.milp_AA(inst, x, norm)
            m_ee = im.milp_exists(inst, x, norm, plans, ())
            m_cp = im.milp_exists(inst, x, norm, plans, ("K", "Q"))
            ag = (m_aa == fl["AA"], m_ee == fl["PKQ"], m_cp == fl["P"])
            ncheck += 3; dis += 3 - sum(ag)
            mrows.append({"inst": i, "norm": norm, "plan": rec["plan"], "category": rec["category"],
                          "brute_AA": int(fl["AA"]), "milp_AA": int(m_aa), "brute_EE": int(fl["PKQ"]),
                          "milp_EE": int(m_ee), "brute_CLOSE_P": int(fl["P"]), "milp_CLOSE_P": int(m_cp),
                          "agree_all": int(all(ag))})
        if time.time() - t0 > 100:
            print(f"time budget hit after {i+1} instances"); break
    with open(os.path.join(OUT, "random_milp_vs_brute.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mrows[0].keys())); w.writeheader(); w.writerows(mrows)
    print(f"random instances checked={len(set(r['inst'] for r in mrows))}, flag checks={ncheck}, disagreements={dis}")
    print(f"category distribution (random): {dict(sorted(cats.items()))}")
    print(f"elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
