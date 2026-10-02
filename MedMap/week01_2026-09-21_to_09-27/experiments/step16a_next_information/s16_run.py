"""STEP16A RUN1: 사전등록 SHA 검증 → VALIDATION 최초 1회 개봉 → 1Q/3Q 시뮬레이션 → 지표·bootstrap → strict audit → 산출물."""
import sys, os, json, time, pickle, hashlib, collections, subprocess
import numpy as np, pandas as pd
sys.path.insert(0, "exp/step16a_next_information"); import s16_core as c
O = c.O; t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
EXPECT = {"00_STEP16A_PREREGISTRATION.md": "31b30117a48c40a9b4a0f9b13a68910a041042b74912fecd29a5ce7c299a247d", "00_step16a_rules.json": "e260afd5127dc781e9bd24cd7e6319bc15cb0fd13a12e234bb5a46d16e839274"}
for f, h in EXPECT.items(): assert c.sha(f"{O}/{f}") == h, f"PREREG HASH MISMATCH {f}"
rules = json.load(open(f"{O}/00_step16a_rules.json")); integ = json.load(open(f"{O}/00_input_integrity.json"))
for p, v in integ.items():
    if isinstance(v, dict): assert c.sha(p) == v["sha256"], f"INPUT CHANGED {p}"
audit = {"prereg_sha_verified": EXPECT, "run_started": time.strftime("%Y-%m-%dT%H:%M:%S"), "test_reads": 0, "validation_opens": 0, "hidden_reads_before_selection": 0, "truth_in_selector_input": 0, "q1_pool_identity_violations": 0, "repeated_question": 0, "reveal_calls": 0, "model_fit_calls_after_prep": 0}
sem = c.Semantics("POST_FREEZE_APPROVED"); enc = c.Encoder(sem)
models = {k: pickle.load(open(f"{O}/model_k{k}.pkl", "rb")) for k in [3, 5, 10]}
for k in models: assert c.sha(f"{O}/model_k{k}.pkl") == rules["models"]["per_k"][str(k)]["sha256"]
npz = np.load(f"{O}/ig_table_train.npz", allow_pickle=True); classes = list(npz["classes"]); ig_table = {e: npz[e] for e in sem.qids}; cidx = {d: i for i, d in enumerate(classes)}
for k in models: assert list(models[k].classes_) == classes
PC = pd.read_csv(f"{O}/04b_pair_contrast_table_primary.csv", dtype={"priority": int}); CC = pd.read_csv(f"{O}/04c_pair_contrast_table_curated_secondary.csv", dtype={"priority": int})
PILOT = list({"Acute rhinosinusitis", "Chronic rhinosinusitis", "Acute laryngitis", "Viral pharyngitis", "Stable angina", "Unstable angina", "HIV (initial infection)", "Scombroid food poisoning", "Acute COPD exacerbation / infection", "PSVT"})
def table(df):
    t = collections.defaultdict(dict)
    for r in df.itertuples(): t[(r.disease_A, r.disease_B)][r.evidence_id] = max(int(r.priority), t[(r.disease_A, r.disease_B)].get(r.evidence_id, 0))
    return t
PRI = table(PC); CUR = table(CC)
def prio(tab, a, b, e): return tab.get((a, b), {}).get(e, 0) or tab.get((b, a), {}).get(e, 0)
fe = pd.read_csv(f"{O}/04_candidate_question_audit.csv", dtype=str).fillna("")
ALIAS = {"HIV (initial infection)": "Acute HIV infection", "Scombroid food poisoning": "Scombroid poisoning", "Acute COPD exacerbation / infection": "Acute COPD exacerbation"}
def pname(d): return ALIAS.get(d, d)
one_sided = collections.defaultdict(set)  # (disease, evidence) 존재 → one-sided secondary
for r in fe.itertuples(): one_sided[r.disease].add(r.evidence_id)
def prio_one_sided(a, b, e):
    p = prio(PRI, a, b, e)
    if p: return p
    return 1 if ((e in one_sided[pname(a)]) != (e in one_sided[pname(b)])) else 0
# ---------------- VALIDATION 개봉 (1회)
va = c.load_patients(c.VAL_PATH, "POST_FREEZE_APPROVED"); audit["validation_opens"] = 1; log("VALIDATION opened once", len(va))
truth_all = va.PATHOLOGY.values; ages = va.AGE.values; sexes = va.SEX.values; tokens = va.tokens.tolist(); inits = va.INITIAL_EVIDENCE.values
def predict_states(k, states, idxs):
    P = models[k].predict_proba(enc.transform(states, ages[idxs], sexes[idxs])); return P
def reveal(i, q):  # 시뮬레이터 전용: 선택 이후에만 호출
    audit["reveal_calls"] += 1; return sem.reconstruct(q, tokens[i])
RSEEDS = list(range(1000, 1050)); BSEED = 42
preds, elig_rows, q1_rows, q3_rows, cand_rows = [], [], [], [], []
SEL = ["RANDOM", "INTERNAL_IG", "PROFILE_FACT_ONLY", "PROFILE_IG_HYBRID", "PROFILE_WITH_CURATED_PAIR_AUDIT", "PROFILE_ONE_SIDED_SENSITIVITY", "RANDOM_FULL", "INTERNAL_IG_FULL"]
for k in [3, 5, 10]:
    for seed in [42, 43, 44]:
        cfg = f"k{k}_s{seed}"; views = [c.make_view(sem, tokens[i], inits[i], k, "validate", seed, i) for i in range(len(va))]
        P0 = predict_states(k, views, np.arange(len(va))); order0 = np.argsort(-P0, 1); top1 = order0[:, 0]; truth = np.array([cidx[t] for t in truth_all]); rank0 = np.argmax(order0 == truth[:, None], 1) + 1
        wrong = top1 != truth; log(cfg, "views+predict done; initial acc", round(float((~wrong).mean()), 4))
        for i in range(len(va)):
            a, b = classes[order0[i, 0]], classes[order0[i, 1]]; fullp = c.full_pool(sem, views[i]); commonp = [q for q in fullp if prio(PRI, a, b, q) > 0]; curp = [q for q in fullp if (prio(PRI, a, b, q) > 0 or prio(CUR, a, b, q) > 0)]; onep = [q for q in fullp if prio_one_sided(a, b, q) > 0]
            pilot_pair = (a in PILOT) and (b in PILOT); reachable = pilot_pair and any(v > 0 for v in {**PRI.get((a, b), {}), **PRI.get((b, a), {})}.values()); simulatable = pilot_pair and len(commonp) > 0
            preds.append({"config": cfg, "sample_id": i, "truth": truth_all[i], "top1": a, "top2": b, "top3": classes[order0[i, 2]], "p_top1": float(P0[i, order0[i, 0]]), "truth_rank": int(rank0[i]), "wrong": bool(wrong[i]), "n_visible": len(views[i])})
            elig_rows.append({"config": cfg, "sample_id": i, "ALL_VALIDATION": True, "PILOT_TRUE": truth_all[i] in PILOT, "PILOT_PAIR": pilot_pair, "PROFILE_REACHABLE": reachable, "SIMULATABLE": simulatable, "n_full_pool": len(fullp), "n_common_pool": len(commonp), "n_curated_pool": len(curp), "n_one_sided_pool": len(onep), "wrong": bool(wrong[i])})
            if not simulatable: continue
            # ---- Q1~Q3 trajectories. 각 agent: (name, draw_seed)
            agents = [("RANDOM", s) for s in RSEEDS] + [("INTERNAL_IG", None), ("PROFILE_FACT_ONLY", None), ("PROFILE_IG_HYBRID", None), ("PROFILE_WITH_CURATED_PAIR_AUDIT", None), ("PROFILE_ONE_SIDED_SENSITIVITY", None)] + [("RANDOM_FULL", s) for s in RSEEDS[:10]] + [("INTERNAL_IG_FULL", None)]
            states = {ag: dict(views[i]) for ag in agents}; asked = {ag: [] for ag in agents}; post = {ag: P0[i] for ag in agents}; top = {ag: (a, b) for ag in agents}; q1_pool_check = None
            for step in (1, 2, 3):
                chosen = {}
                for ag in agents:
                    name, s = ag; st = states[ag]; A, B = top[ag]; fp = c.full_pool(sem, st)
                    if name in ("RANDOM_FULL", "INTERNAL_IG_FULL"): pool = fp
                    elif name == "PROFILE_WITH_CURATED_PAIR_AUDIT": pool = [q for q in fp if (prio(PRI, A, B, q) > 0 or prio(CUR, A, B, q) > 0)]
                    elif name == "PROFILE_ONE_SIDED_SENSITIVITY": pool = [q for q in fp if prio_one_sided(A, B, q) > 0]
                    else: pool = [q for q in fp if prio(PRI, A, B, q) > 0]
                    if step == 1 and name in ("RANDOM", "INTERNAL_IG", "PROFILE_FACT_ONLY", "PROFILE_IG_HYBRID"):
                        if q1_pool_check is None: q1_pool_check = pool
                        elif pool != q1_pool_check: audit["q1_pool_identity_violations"] += 1
                    c.selector_input(st, post[ag], list(top[ag]), pool, s)  # 스키마 검사(truth 없음)
                    if not pool: chosen[ag] = None; continue
                    if name.startswith("RANDOM"): chosen[ag] = pool[np.random.default_rng([s, step, i]).integers(len(pool))]
                    elif name.startswith("INTERNAL_IG"): chosen[ag] = c.select_ig(pool, post[ag], ig_table)
                    elif name == "PROFILE_FACT_ONLY": chosen[ag] = sorted([(prio(PRI, A, B, q), q) for q in pool], key=lambda x: (-x[0], c.qnum(x[1])))[0][1]
                    elif name == "PROFILE_IG_HYBRID": chosen[ag] = c.select_ig(pool, post[ag], ig_table)
                    elif name == "PROFILE_WITH_CURATED_PAIR_AUDIT": chosen[ag] = sorted([(max(prio(PRI, A, B, q), prio(CUR, A, B, q)), q) for q in pool], key=lambda x: (-x[0], c.qnum(x[1])))[0][1]
                    else: chosen[ag] = sorted([(prio_one_sided(A, B, q), q) for q in pool], key=lambda x: (-x[0], c.qnum(x[1])))[0][1]
                # reveal (선택 이후) + 재예측(배치)
                upd = [ag for ag in agents if chosen[ag] is not None]
                for ag in upd:
                    q = chosen[ag]
                    if q in asked[ag] or q in states[ag]: audit["repeated_question"] += 1
                    states[ag][q] = reveal(i, q); asked[ag].append(q)
                if upd:
                    Pn = predict_states(k, [states[ag] for ag in upd], np.full(len(upd), i))
                    for j, ag in enumerate(upd): post[ag] = Pn[j]; o = np.argsort(-Pn[j]); top[ag] = (classes[o[0]], classes[o[1]])
                for ag in agents:
                    o = np.argsort(-post[ag]); rec = {"config": cfg, "sample_id": i, "selector": ag[0], "draw_seed": ag[1], "step": step, "question": chosen[ag] or "ABSTAIN", "initial_wrong": bool(wrong[i]), "top1_after": classes[o[0]], "correct_after": classes[o[0]] == truth_all[i], "truth_rank_after": int(np.where(o == truth[i])[0][0]) + 1, "n_asked": len(asked[ag])}
                    (q1_rows if step == 1 else q3_rows).append(rec) if step in (1, 3) else None
            cand_rows.append({"config": cfg, "sample_id": i, "top1": a, "top2": b, "common_pool": ";".join(commonp), "n_common": len(commonp), "n_full": len(fullp)})
        log(cfg, "simulation done; simulatable", int(sum(1 for r in elig_rows if r["config"] == cfg and r["SIMULATABLE"])))
PR = pd.DataFrame(preds); PR.to_csv(f"{O}/02_validation_partial_predictions.csv", index=False); EL = pd.DataFrame(elig_rows); EL.to_csv(f"{O}/03_case_eligibility.csv", index=False)
Q1 = pd.DataFrame(q1_rows); Q3 = pd.DataFrame(q3_rows); pd.DataFrame(cand_rows).to_csv(f"{O}/04d_common_pool_per_case.csv", index=False)
# Random: draw 평균 → patient/view level
def collapse(Q):
    g = Q.groupby(["config", "sample_id", "selector"]).agg(initial_wrong=("initial_wrong", "first"), p_correct=("correct_after", "mean"), rank=("truth_rank_after", "mean"), abstain=("question", lambda s: float((s == "ABSTAIN").mean())), n_asked=("n_asked", "mean")).reset_index(); return g
C1, C3 = collapse(Q1), collapse(Q3); C1.to_csv(f"{O}/05_question1_results.csv", index=False); C3.to_csv(f"{O}/06_question3_results.csv", index=False)
# ---------------- metrics
def metrics(C, tag):
    rows = []
    for (cfg, sel), g in C.groupby(["config", "selector"]):
        w = g[g.initial_wrong]; r = g[~g.initial_wrong]
        rows.append({"stage": tag, "config": cfg, "selector": sel, "N_wrong": len(w), "recovery": round(float(w.p_correct.mean()), 4) if len(w) else None, "N_correct": len(r), "correct_to_wrong": round(float(1 - r.p_correct.mean()), 4) if len(r) else None, "net_acc_change": round(float(g.p_correct.mean() - (~g.initial_wrong).mean()), 4), "mean_truth_rank_after": round(float(g["rank"].mean()), 3), "abstain_rate": round(float(g.abstain.mean()), 4), "mean_questions": round(float(g.n_asked.mean()), 3)})
    for sel, g in C.groupby("selector"):
        w = g[g.initial_wrong]; r = g[~g.initial_wrong]
        rows.append({"stage": tag, "config": "POOLED", "selector": sel, "N_wrong": len(w), "recovery": round(float(w.p_correct.mean()), 4) if len(w) else None, "N_correct": len(r), "correct_to_wrong": round(float(1 - r.p_correct.mean()), 4) if len(r) else None, "net_acc_change": round(float(g.p_correct.mean() - (~g.initial_wrong).mean()), 4), "mean_truth_rank_after": round(float(g["rank"].mean()), 3), "abstain_rate": round(float(g.abstain.mean()), 4), "mean_questions": round(float(g.n_asked.mean()), 3)})
    return pd.DataFrame(rows)
M = pd.concat([metrics(C1, "1Q"), metrics(C3, "3Q")]); M.to_csv(f"{O}/07_selector_metrics.csv", index=False)
# paired bootstrap (patient cluster, 1000, seed 42)
def paired_boot(C, a, b, n=1000, seed=BSEED):
    w = C[C.initial_wrong].pivot_table(index=["config", "sample_id"], columns="selector", values="p_correct").dropna(subset=[a, b]).reset_index()
    if len(w) == 0: return None
    pids = w.sample_id.unique(); by = {p: g for p, g in w.groupby("sample_id")}; rng = np.random.default_rng(seed); diffs = []
    for _ in range(n):
        samp = rng.choice(pids, len(pids), replace=True); d = np.concatenate([(by[p][a] - by[p][b]).values for p in samp]); diffs.append(d.mean())
    obs = float((w[a] - w[b]).mean()); return {"pair": f"{a}-{b}", "N_wrong_pairs": len(w), "N_patients": len(pids), "diff": round(obs, 4), "ci_lo": round(float(np.percentile(diffs, 2.5)), 4), "ci_hi": round(float(np.percentile(diffs, 97.5)), 4)}
boot = []
for stage, C in [("1Q", C1), ("3Q", C3)]:
    for a, b in [("PROFILE_FACT_ONLY", "RANDOM"), ("PROFILE_FACT_ONLY", "INTERNAL_IG"), ("PROFILE_IG_HYBRID", "INTERNAL_IG"), ("PROFILE_WITH_CURATED_PAIR_AUDIT", "RANDOM"), ("PROFILE_WITH_CURATED_PAIR_AUDIT", "INTERNAL_IG"), ("INTERNAL_IG", "RANDOM"), ("INTERNAL_IG_FULL", "RANDOM_FULL")]:
        r = paired_boot(C, a, b)
        if r: r["stage"] = stage; r["scope"] = "POOLED"; boot.append(r)
    for cfg, Cc in C.groupby("config"):
        r = paired_boot(Cc, "PROFILE_FACT_ONLY", "RANDOM")
        if r: r["stage"] = stage; r["scope"] = cfg; boot.append(r)
        r = paired_boot(Cc, "PROFILE_FACT_ONLY", "INTERNAL_IG")
        if r: r["stage"] = stage; r["scope"] = cfg; boot.append(r)
BT = pd.DataFrame(boot); BT.to_csv(f"{O}/08_paired_bootstrap.csv", index=False)
# unobservable opportunities (curated 05_pair_observability NO_MATCH rows)
po = pd.read_csv("exp/step15_v2_evaluation_fix/05_pair_observability.csv", dtype=str).fillna("")
po[po.experimentally_observable != "True"][["disease_a", "disease_b", "feature", "profile_fact_id", "reason"]].assign(label="EXTERNALLY_IMPORTANT_BUT_UNOBSERVABLE").to_csv(f"{O}/09_unobservable_information_opportunities.csv", index=False)
# examples (deterministic order)
ex = C1[C1.selector == "PROFILE_FACT_ONLY"].merge(PR, on=["config", "sample_id"]); rec = ex[ex.initial_wrong & (ex.p_correct == 1)].head(3); fail = ex[ex.initial_wrong & (ex.p_correct == 0) & (ex.abstain == 0)].head(3); harm = ex[(~ex.initial_wrong) & (ex.p_correct == 0)].head(3)
EX = pd.concat([rec.assign(kind="recovered"), fail.assign(kind="not_recovered"), harm.assign(kind="harmed")]); q1p = Q1[Q1.selector == "PROFILE_FACT_ONLY"][["config", "sample_id", "question", "top1_after"]]; EX = EX.merge(q1p, on=["config", "sample_id"], how="left"); EX["question_text"] = EX.question.map(lambda q: sem.ev.get(q, {}).get("question_en", q)); EX.to_csv(f"{O}/11_error_case_examples.csv", index=False)
# leakage audit + strict audit
audit["frozen_after_run"] = {f: c.sha(f"{O}/{f}") == h for f, h in EXPECT.items()}; audit["inputs_unchanged_after_run"] = all(c.sha(p) == v["sha256"] for p, v in integ.items() if isinstance(v, dict)); audit["nan_in_metrics"] = int(M.isna().sum().sum()); audit["run_finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
audit["strict_audit"] = "PASS" if (audit["test_reads"] == 0 and audit["validation_opens"] == 1 and audit["q1_pool_identity_violations"] == 0 and audit["repeated_question"] == 0 and all(audit["frozen_after_run"].values()) and audit["inputs_unchanged_after_run"]) else "FAIL"
json.dump(audit, open(f"{O}/10_selector_input_leakage_audit.json", "w"), indent=1)
summ = {"initial_accuracy": PR.groupby("config").apply(lambda g: round(float((~g.wrong).mean()), 4)).to_dict(), "initial_accuracy_pooled": round(float((~PR.wrong).mean()), 4), "truth_top2": round(float((PR.truth_rank <= 2).mean()), 4), "truth_top3": round(float((PR.truth_rank <= 3).mean()), 4),
        "eligibility": {k: int(EL[k].sum()) for k in ["ALL_VALIDATION", "PILOT_TRUE", "PILOT_PAIR", "PROFILE_REACHABLE", "SIMULATABLE"]}, "primary_wrong_N": int((EL.SIMULATABLE & EL.wrong).sum()), "primary_correct_N": int((EL.SIMULATABLE & ~EL.wrong).sum()), "primary_wrong_N_by_config": EL[EL.SIMULATABLE & EL.wrong].groupby("config").size().to_dict(),
        "metrics_pooled": M[M.config == "POOLED"].to_dict("records"), "bootstrap": BT.to_dict("records"), "mean_common_pool_simulatable": round(float(EL[EL.SIMULATABLE].n_common_pool.mean()), 3), "audit": audit, "git_commit": subprocess.run("git rev-parse HEAD", shell=True, capture_output=True, text=True).stdout.strip()}
json.dump(summ, open(f"{O}/12_summary.json", "w"), indent=1, default=str)
pd.set_option("display.width", 250); print(M[M.config == "POOLED"].to_string()); print(BT.to_string()); print(json.dumps({k: summ[k] for k in ["initial_accuracy", "initial_accuracy_pooled", "truth_top2", "truth_top3", "eligibility", "primary_wrong_N", "primary_correct_N", "primary_wrong_N_by_config", "mean_common_pool_simulatable"]}, indent=1)); print(json.dumps(audit, indent=1)); log("DONE")
