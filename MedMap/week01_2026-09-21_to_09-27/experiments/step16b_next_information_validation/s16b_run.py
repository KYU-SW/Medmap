"""STEP16B run: STEP16B_HOLDOUT 1회 평가. 사전등록 SHA 검증 → 초기예측(전수) → SIM_COHORT 시뮬레이션 → 지표·bootstrap·감사.
원본 VALIDATION/TEST 접근 없음(코어 가드). HOLDOUT은 이 실행에서 처음 사용."""
import sys, json, time, pickle, collections
import numpy as np, pandas as pd
sys.path.insert(0, ".")
import s16b_core as c

T0 = time.time()
def log(m): print(f"[{time.time()-T0:7.0f}s] {m}", flush=True)
AUD = collections.Counter()
EXPECT = json.load(open("00_preregistration_sha256.json"))
for f in ["00_STEP16B_PREREGISTRATION.md", "00_STEP16B_RULES.json"]:
    assert c.sha(f) == EXPECT[f], f"PREREG SHA MISMATCH {f}"
RULES = json.load(open("00_STEP16B_RULES.json"))
import os
SMOKE = os.environ.get("STEP16B_SMOKE") == "1"
N_COHORT = 200 if SMOKE else 10000; STEPS = 3
OUT = "_smoke_" if SMOKE else ""
RSEEDS = list(range(1000, 1050)); BSEEDS = list(range(1000, 1010))

df = c.load_train(); log(f"loaded {len(df)}")
MAN = json.load(open("01_split_manifest.json")); classes = MAN["classes"]
ho = df[df.holdout].sort_values("split_key").reset_index(drop=True)
assert len(ho) == MAN["holdout_rows"]
cohort = ho.head(N_COHORT).reset_index(drop=True)
del df
sem = c.Semantics(); enc = c.Encoder(sem)
Z = np.load("ig_table_step16b_train.npz", allow_pickle=True)
ig_table = {e: Z[e] for e in sem.qids}
assert list(Z["__classes__"]) == classes
qs, qpos, MIG, grp = c.pack_ig(sem, ig_table); NQ = len(qs)
QNUM = {q: c.qnum(q) for q in sem.qids}
BIN = {q for q in sem.qids if sem.dtype[q] == "B" and sem.safe[q]}
models = {k: pickle.load(open(f"model_k{k}.pkl", "rb")) for k in (3, 5, 10)}
for k, m in models.items(): assert list(m.classes_) == classes, f"class order mismatch k{k}"
CI = {cc: i for i, cc in enumerate(classes)}
# profile contrast table (STEP16A, 읽기 전용)
PT = pd.read_csv(f"{c.A16}/04b_pair_contrast_table_primary.csv")
PRI = {}
for r in PT.itertuples():
    PRI[(r.disease_A, r.disease_B, r.evidence_id)] = max(PRI.get((r.disease_A, r.disease_B, r.evidence_id), 0), r.priority)
    PRI[(r.disease_B, r.disease_A, r.evidence_id)] = max(PRI.get((r.disease_B, r.disease_A, r.evidence_id), 0), r.priority)
PAIRS = {(a, b) for a, b, _ in PRI}
def prio(A, B, q): return PRI.get((A, B, q), 0)

AGENTS = [("RANDOM", s) for s in RSEEDS] + [("INTERNAL_IG", 0), ("PROFILE_FACT_ONLY", 0)] + [("BINARY_ONLY_RANDOM", s) for s in BSEEDS] + [("BINARY_ONLY_IG", 0)]
SELECTORS = ["RANDOM", "INTERNAL_IG", "PROFILE_FACT_ONLY", "BINARY_ONLY_RANDOM", "BINARY_ONLY_IG"]

init_rows = []; elig_rows = []; q1_rows = []; q3_rows = []
KS = (3,) if SMOKE else (3, 5, 10)
SEEDS = (42,) if SMOKE else (42, 43, 44)
for k in KS:
    model = models[k]
    for seed in SEEDS:
        cfg = f"k{k}_s{seed}"; t = time.time()
        # ---- 전수 holdout 초기 예측 ----
        toks = ho.tokens.tolist(); ini = ho.INITIAL_EVIDENCE.values; ridx = ho.row_index.values
        NHO = 1000 if SMOKE else len(ho)
        views = [c.make_view(sem, toks[i], ini[i], k, "step16b_holdout", seed, int(ridx[i])) for i in range(NHO)]
        P = model.predict_proba(enc.transform(views, ho.AGE.values[:NHO], ho.SEX.values[:NHO]))
        order = np.argsort(-P, 1); truth = np.array([CI[p] for p in ho.PATHOLOGY.values[:NHO]])
        rank = np.argmax(order == truth[:, None], 1) + 1; wrong = order[:, 0] != truth
        init_rows.append(pd.DataFrame({"config": cfg, "row_index": ridx[:NHO], "truth": ho.PATHOLOGY.values[:NHO],
            "top1": [classes[j] for j in order[:, 0]], "top2": [classes[j] for j in order[:, 1]],
            "p_top1": P[np.arange(len(P)), order[:, 0]].astype(np.float32), "truth_rank": rank, "wrong": wrong,
            "n_visible": [len(v) for v in views]}))
        log(f"{cfg} initial acc {(~wrong).mean():.4f} ({time.time()-t:.0f}s)")
        # ---- SIM_COHORT ----
        n = len(cohort); cv = views[:n]; cP = P[:n]; ctruth = truth[:n]; cwrong = wrong[:n]
        ctop = order[:n, :2]
        base_pool = [sorted([q for q in sem.qids if sem.currently_eligible(q, v)], key=QNUM.get) for v in cv]
        children = collections.defaultdict(list)
        for ch, par in sem.parent.items():
            if sem.safe[ch]: children[par].append(ch)
        elig_rows.append(pd.DataFrame({"config": cfg, "row_index": cohort.row_index.values,
            "n_safe_full_pool": [len(p) for p in base_pool], "n_safe_binary_pool": [sum(q in BIN for q in p) for p in base_pool],
            "wrong": cwrong, "pilot_pair": [(classes[a], classes[b]) in PAIRS for a, b in ctop]}))
        st = {}; pl = {}; post = {}; asked = {}; abst = {}
        for ag in AGENTS:
            st[ag] = [dict(v) for v in cv]
            pl[ag] = [[q for q in base_pool[i] if (q in BIN or not ag[0].startswith("BINARY"))] for i in range(n)]
            post[ag] = cP.copy(); asked[ag] = np.zeros(n, int); abst[ag] = np.zeros(n, int)
        pair_ok = np.array([(classes[a], classes[b]) in PAIRS for a, b in ctop])
        # step1 pool 동일성 assert (RANDOM vs INTERNAL_IG vs PROFILE)
        for i in range(n):
            if not (pl[("RANDOM", RSEEDS[0])][i] == pl[("INTERNAL_IG", 0)][i] == pl[("PROFILE_FACT_ONLY", 0)][i]): AUD["q1_pool_identity_violations"] += 1
        snap = {}
        for step in range(1, STEPS + 1):
            chosen = {}
            igc = {}
            for ag in AGENTS:
                name, s = ag; ch = [None] * n
                is_ig = name.endswith("_IG"); is_rand = "RANDOM" in name
                u = np.random.default_rng([s, step]).random(n) if is_rand else None
                for i in range(n):
                    pool = pl[ag][i]
                    if not pool: continue
                    if is_rand:
                        ch[i] = pool[int(u[i] * len(pool))]
                    elif is_ig:
                        ig = c.ig_all(post[ag][i].astype(np.float64), MIG, grp, NQ)
                        idx = np.fromiter((qpos[q] for q in pool), int, len(pool))
                        ch[i] = qs[idx[int(np.argmax(np.round(ig[idx], 12)))]]
                    else:  # PROFILE_FACT_ONLY
                        if not pair_ok[i]: continue
                        A, B = classes[ctop[i, 0]], classes[ctop[i, 1]]
                        best = max(pool, key=lambda q: (prio(A, B, q), -QNUM[q]))
                        if prio(A, B, best) > 0: ch[i] = best
                chosen[ag] = ch
            # reveal (선택 확정 이후에만) + 배치 재예측
            batch_states = []; batch_idx = []
            for ag in AGENTS:
                for i in range(n):
                    q = chosen[ag][i]
                    if q is None: abst[ag][i] += 1; continue
                    if q in st[ag][i]: AUD["repeated_question"] += 1; continue
                    if not sem.safe[q]: AUD["unsafe_question_access"] += 1; continue
                    ans = sem.reconstruct(q, cohort.tokens.values[i]); AUD["reveal_calls"] += 1
                    st[ag][i][q] = ans; asked[ag][i] += 1
                    pl[ag][i].remove(q)
                    if ans == ("POS",) and q in children and not ag[0].startswith("BINARY"):
                        pl[ag][i] = sorted(set(pl[ag][i]) | {ch2 for ch2 in children[q] if ch2 not in st[ag][i]}, key=QNUM.get)
                    batch_states.append(st[ag][i]); batch_idx.append((ag, i))
            if batch_states:
                ags_i = np.array([j for j, _ in enumerate(batch_idx)])
                Xb = enc.transform(batch_states, np.array([cohort.AGE.values[i] for _, i in batch_idx]), np.array([cohort.SEX.values[i] for _, i in batch_idx]))
                Pb = model.predict_proba(Xb).astype(np.float32)
                for j, (ag, i) in enumerate(batch_idx): post[ag][i] = Pb[j]
            if step in (1, STEPS):
                rec = []
                for ag in AGENTS:
                    o = np.argsort(-post[ag], 1)
                    rec.append(pd.DataFrame({"config": cfg, "row_index": cohort.row_index.values, "selector": ag[0], "draw": ag[1],
                        "initial_wrong": cwrong, "pilot_pair": pair_ok, "correct_after": o[:, 0] == ctruth,
                        "rank_after": (np.argmax(o == ctruth[:, None], 1) + 1), "top3_after": (o[:, :3] == ctruth[:, None]).any(1),
                        "abstain": abst[ag] > 0, "n_asked": asked[ag]}))
                (q1_rows if step == 1 else q3_rows).append(pd.concat(rec, ignore_index=True))
            log(f"{cfg} step{step} done ({time.time()-t:.0f}s)")
        del views, P, order, st, pl, post
log("simulation done")

pd.concat(init_rows, ignore_index=True).to_csv(OUT + "02_holdout_initial_predictions.csv", index=False)
pd.concat(elig_rows, ignore_index=True).to_csv(OUT + "03_case_eligibility.csv", index=False)
def collapse(rows):
    Q = pd.concat(rows, ignore_index=True)
    return Q.groupby(["config", "row_index", "selector"], as_index=False).agg(
        initial_wrong=("initial_wrong", "first"), pilot_pair=("pilot_pair", "first"), p_correct=("correct_after", "mean"),
        rank=("rank_after", "mean"), top3=("top3_after", "mean"), abstain=("abstain", "mean"), n_asked=("n_asked", "mean"))
C1 = collapse(q1_rows); C3 = collapse(q3_rows)
C1.to_csv(OUT + "05_question1_results.csv", index=False); C3.to_csv(OUT + "06_question3_results.csv", index=False)
log("collapsed")

INI = pd.concat(init_rows, ignore_index=True)
def metrics(C, tag):
    out = []
    for sel, g in C.groupby("selector"):
        gg = g[g.pilot_pair] if sel == "PROFILE_FACT_ONLY" else g
        w = gg[gg.initial_wrong]; r = gg[~gg.initial_wrong]
        out.append({"endpoint": tag, "selector": sel, "n_wrong": len(w), "n_correct": len(r),
                    "recovery": float(w.p_correct.mean()), "correct_to_wrong": float(1 - r.p_correct.mean()),
                    "acc_after": float(gg.p_correct.mean()), "acc_before": float((~gg.initial_wrong).mean()),
                    "net_acc_change": float(gg.p_correct.mean() - (~gg.initial_wrong).mean()),
                    "rank_mean": float(gg["rank"].mean()), "rank_median": float(gg["rank"].median()),
                    "top3": float(gg.top3.mean()), "abstain": float(gg.abstain.mean()), "mean_questions": float(gg.n_asked.mean())})
    return pd.DataFrame(out)
M = pd.concat([metrics(C1, "1Q"), metrics(C3, "3Q")], ignore_index=True)
M.to_csv(OUT + "07_selector_metrics.csv", index=False)

def paired_boot(C, a, b, n_boot=1000, seed=42, restrict_pair=False):
    g = C[C.initial_wrong]
    if restrict_pair: g = g[g.pilot_pair]
    A = g[g.selector == a][["row_index", "config", "p_correct"]].rename(columns={"p_correct": "a"})
    B = g[g.selector == b][["row_index", "config", "p_correct"]].rename(columns={"p_correct": "b"})
    m = A.merge(B, on=["row_index", "config"]); assert len(m) == len(A) == len(B)
    pid, inv = np.unique(m.row_index.values, return_inverse=True)
    d = (m.a.values - m.b.values)
    s = np.bincount(inv, weights=d, minlength=len(pid)); cnt = np.bincount(inv, minlength=len(pid))
    rng = np.random.default_rng(seed); out = np.empty(n_boot)
    for t in range(n_boot):
        idx = rng.integers(0, len(pid), len(pid)); out[t] = s[idx].sum() / cnt[idx].sum()
    return {"comparison": f"{a}-{b}", "point": float(d.mean()), "ci_lo": float(np.percentile(out, 2.5)), "ci_hi": float(np.percentile(out, 97.5)), "n_views": int(len(m)), "n_patients": int(len(pid))}
BT = [paired_boot(C1, "INTERNAL_IG", "RANDOM"), paired_boot(C3, "INTERNAL_IG", "RANDOM"),
      paired_boot(C1, "BINARY_ONLY_IG", "BINARY_ONLY_RANDOM"), paired_boot(C3, "BINARY_ONLY_IG", "BINARY_ONLY_RANDOM"),
      paired_boot(C1, "PROFILE_FACT_ONLY", "RANDOM", restrict_pair=True), paired_boot(C1, "PROFILE_FACT_ONLY", "INTERNAL_IG", restrict_pair=True)]
for i, tag in enumerate(["1Q", "3Q", "1Q", "3Q", "1Q", "1Q"]): BT[i]["endpoint"] = tag
pd.DataFrame(BT).to_csv(OUT + "08_paired_bootstrap.csv", index=False)
log("bootstrap done")

ex = C1[(C1.initial_wrong) & (C1.selector == "INTERNAL_IG")].head(20)
ex.to_csv(OUT + "11_error_case_examples.csv", index=False)
AUDIT = {"prereg_sha_verified": EXPECT, "original_validation_reads": 0, "test_reads": 0,
         "read_log_unique": sorted(set(c.READ_LOG)), "unsafe_state_encounters": dict(sem.unsafe_encounters),
         "unsafe_question_access": int(AUD["unsafe_question_access"]), "repeated_question": int(AUD["repeated_question"]),
         "q1_pool_identity_violations": int(AUD["q1_pool_identity_violations"]), "reveal_calls": int(AUD["reveal_calls"]),
         "hidden_read_before_selection": 0, "hidden_read_rule": "reconstruct() called only after chosen[] fixed; counters persisted here",
         "excluded_questions": list(c.EXCLUDED), "sim_cohort": N_COHORT, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
json.dump(AUDIT, open(OUT + "10_audit.json", "w"), indent=1)
summ = {"split": {kk: MAN[kk] for kk in ["source_rows", "train_rows", "holdout_rows", "holdout_fraction", "split_key_stream_sha256"]},
        "initial_accuracy": {cfg: float(1 - g.wrong.mean()) for cfg, g in INI.groupby("config")},
        "initial_accuracy_pooled": float(1 - INI.wrong.mean()),
        "cohort_wrong_views": int((C1.initial_wrong & (C1.selector == "RANDOM")).sum()),
        "cohort_correct_views": int(((~C1.initial_wrong) & (C1.selector == "RANDOM")).sum()),
        "metrics": json.loads(M.to_json(orient="records")), "bootstrap": BT,
        "mean_safe_full_pool": float(pd.concat(elig_rows).n_safe_full_pool.mean()),
        "mean_safe_binary_pool": float(pd.concat(elig_rows).n_safe_binary_pool.mean()),
        "audit": AUDIT}
json.dump(summ, open(OUT + "12_summary.json", "w"), indent=1, default=str)
log("RUN_DONE")
