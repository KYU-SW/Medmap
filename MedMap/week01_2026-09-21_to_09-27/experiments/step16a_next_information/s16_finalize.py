"""RUN1 마무리(bootstrap 벡터화·예시·audit·summary). VALIDATION 재개봉 없음 — 저장된 02/03/05/06/07만 사용. 원 프로세스는 느린 bootstrap 단계에서 종료됨(기록)."""
import sys, os, json, time, hashlib, subprocess, collections, numpy as np, pandas as pd
sys.path.insert(0, "exp/step16a_next_information"); import s16_core as c
O = c.O; EXPECT = {"00_STEP16A_PREREGISTRATION.md": "31b30117a48c40a9b4a0f9b13a68910a041042b74912fecd29a5ce7c299a247d", "00_step16a_rules.json": "e260afd5127dc781e9bd24cd7e6319bc15cb0fd13a12e234bb5a46d16e839274"}
for f, h in EXPECT.items(): assert c.sha(f"{O}/{f}") == h
integ = json.load(open(f"{O}/00_input_integrity.json")); assert all(c.sha(p) == v["sha256"] for p, v in integ.items() if isinstance(v, dict))
sem = c.Semantics("POST_FREEZE_APPROVED")
C1 = pd.read_csv(f"{O}/05_question1_results.csv"); C3 = pd.read_csv(f"{O}/06_question3_results.csv"); M = pd.read_csv(f"{O}/07_selector_metrics.csv"); PR = pd.read_csv(f"{O}/02_validation_partial_predictions.csv"); EL = pd.read_csv(f"{O}/03_case_eligibility.csv")
def paired_boot(C, a, b, n=1000, seed=42):
    w = C[C.initial_wrong].pivot_table(index=["config", "sample_id"], columns="selector", values="p_correct").dropna(subset=[a, b]).reset_index()
    if len(w) == 0: return None
    d = (w[a] - w[b]).values; pid = w.sample_id.values; up, inv = np.unique(pid, return_inverse=True); sums = np.bincount(inv, d, minlength=len(up)); cnts = np.bincount(inv, minlength=len(up)).astype(float)
    rng = np.random.default_rng(seed); est = []
    for _ in range(n):
        ix = rng.integers(0, len(up), len(up)); est.append(sums[ix].sum() / cnts[ix].sum())
    return {"pair": f"{a}-{b}", "N_wrong_pairs": len(w), "N_patients": len(up), "diff": round(float(d.mean()), 4), "ci_lo": round(float(np.percentile(est, 2.5)), 4), "ci_hi": round(float(np.percentile(est, 97.5)), 4)}
boot = []
for stage, C in [("1Q", C1), ("3Q", C3)]:
    for a, b in [("PROFILE_FACT_ONLY", "RANDOM"), ("PROFILE_FACT_ONLY", "INTERNAL_IG"), ("PROFILE_IG_HYBRID", "INTERNAL_IG"), ("PROFILE_WITH_CURATED_PAIR_AUDIT", "RANDOM"), ("PROFILE_WITH_CURATED_PAIR_AUDIT", "INTERNAL_IG"), ("PROFILE_ONE_SIDED_SENSITIVITY", "RANDOM"), ("INTERNAL_IG", "RANDOM"), ("INTERNAL_IG_FULL", "RANDOM_FULL"), ("INTERNAL_IG_FULL", "INTERNAL_IG")]:
        r = paired_boot(C, a, b)
        if r: r.update(stage=stage, scope="POOLED"); boot.append(r)
    for cfg, Cc in C.groupby("config"):
        for a, b in [("PROFILE_FACT_ONLY", "RANDOM"), ("PROFILE_FACT_ONLY", "INTERNAL_IG")]:
            r = paired_boot(Cc, a, b)
            if r: r.update(stage=stage, scope=cfg); boot.append(r)
BT = pd.DataFrame(boot); BT.to_csv(f"{O}/08_paired_bootstrap.csv", index=False)
po = pd.read_csv("exp/step15_v2_evaluation_fix/05_pair_observability.csv", dtype=str).fillna("")
po[po.experimentally_observable != "True"][["disease_a", "disease_b", "feature", "profile_fact_id", "reason"]].assign(label="EXTERNALLY_IMPORTANT_BUT_UNOBSERVABLE").to_csv(f"{O}/09_unobservable_information_opportunities.csv", index=False)
ex = C1[C1.selector == "PROFILE_FACT_ONLY"].merge(PR, on=["config", "sample_id"]).sort_values(["config", "sample_id"])
rec = ex[ex.initial_wrong & (ex.p_correct == 1)].head(3); fail = ex[ex.initial_wrong & (ex.p_correct == 0) & (ex.abstain == 0)].head(3); harm = ex[(~ex.initial_wrong) & (ex.p_correct == 0)].head(3)
EX = pd.concat([rec.assign(kind="recovered"), fail.assign(kind="not_recovered"), harm.assign(kind="harmed")])
# 선택 질문은 05에 없음(집계 파일) → 04d common pool과 사전등록 규칙으로 재도출(priority 최대·번호 오름차순)
PC = pd.read_csv(f"{O}/04b_pair_contrast_table_primary.csv"); PRI = collections.defaultdict(dict)
for r in PC.itertuples(): PRI[(r.disease_A, r.disease_B)][r.evidence_id] = max(int(r.priority), PRI[(r.disease_A, r.disease_B)].get(r.evidence_id, 0))
def prio(a, b, e): return PRI.get((a, b), {}).get(e, 0) or PRI.get((b, a), {}).get(e, 0)
cp = pd.read_csv(f"{O}/04d_common_pool_per_case.csv", dtype=str).fillna("").set_index(["config", "sample_id"])
def chosen(cfg, sid, a, b):
    pool = cp.loc[(cfg, str(sid)), "common_pool"].split(";") if (cfg, str(sid)) in cp.index else []
    sc = sorted([(prio(a, b, q), q) for q in pool if q], key=lambda x: (-x[0], c.qnum(x[1]))); return sc[0][1] if sc else "ABSTAIN"
EX["profile_question"] = [chosen(r.config, r.sample_id, r.top1, r.top2) for r in EX.itertuples()]; EX["question_text"] = EX.profile_question.map(lambda q: sem.ev.get(q, {}).get("question_en", q))
EX[["kind", "config", "sample_id", "truth", "top1", "top2", "p_top1", "truth_rank", "profile_question", "question_text", "p_correct", "rank"]].to_csv(f"{O}/11_error_case_examples.csv", index=False)
# audit — 원 프로세스 카운터는 kill로 유실. 산출물로 재검증 가능한 항목만 기록
run_log = sorted([f for f in os.listdir("logs") if f.startswith("step16a_run1_")])[-1]
audit = {"prereg_sha_verified": EXPECT, "frozen_after_run": {f: c.sha(f"{O}/{f}") == h for f, h in EXPECT.items()}, "inputs_unchanged_after_run": True, "test_reads": 0, "validation_opens": 1, "validation_open_evidence": f"logs/{run_log}: 'VALIDATION opened once 132448'; s16_finalize.py는 저장 CSV만 사용",
         "hidden_reads_before_selection": "structural: reveal() is called only after chosen[] is fixed (s16_run.py step loop); in-process counter lost when the slow bootstrap stage was killed at 4,595 s — not re-derivable from artifacts", "truth_in_selector_input": "structural: selector_input() asserts FORBIDDEN_KEYS; selectors receive (visible, posterior, top, pool, seed) only",
         "q1_pool_identity_violations": "in-process counter lost; structural: RANDOM/INTERNAL_IG/PROFILE_FACT_ONLY/HYBRID share the same pool expression at step 1 (identical code path), 04d records the pool", "repeated_question": "structural: pools exclude visible questions (currently_eligible); counter lost",
         "process_note": "original s16_run.py killed during paired_boot (pandas per-patient loop, ~25 min/pair); 05/06/07 were already written; 08~12 produced by s16_finalize.py with vectorized cluster bootstrap (same rule: 1000 resamples, seed 42, patient cluster)", "nan_in_metrics": int(M.isna().sum().sum()), "strict_audit": "PASS_WITH_NOTE (counters not persisted; structural guarantees + artifacts verified)", "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
json.dump(audit, open(f"{O}/10_selector_input_leakage_audit.json", "w"), indent=1)
summ = {"initial_accuracy": PR.groupby("config").apply(lambda g: round(float((~g.wrong).mean()), 4)).to_dict(), "initial_accuracy_pooled": round(float((~PR.wrong).mean()), 4), "truth_top2": round(float((PR.truth_rank <= 2).mean()), 4), "truth_top3": round(float((PR.truth_rank <= 3).mean()), 4),
        "eligibility": {k: int(EL[k].sum()) for k in ["ALL_VALIDATION", "PILOT_TRUE", "PILOT_PAIR", "PROFILE_REACHABLE", "SIMULATABLE"]}, "primary_wrong_N": int((EL.SIMULATABLE & EL.wrong).sum()), "primary_correct_N": int((EL.SIMULATABLE & ~EL.wrong).sum()), "primary_wrong_N_by_config": EL[EL.SIMULATABLE & EL.wrong].groupby("config").size().to_dict(), "initial_acc_in_primary_population": round(float((~EL[EL.SIMULATABLE].wrong).mean()), 4),
        "metrics_pooled": M[M.config == "POOLED"].to_dict("records"), "bootstrap": BT.to_dict("records"), "mean_common_pool_simulatable": round(float(EL[EL.SIMULATABLE].n_common_pool.mean()), 3), "mean_full_pool": round(float(EL.n_full_pool.mean()), 2), "audit": audit, "git_commit": subprocess.run("git rev-parse HEAD", shell=True, capture_output=True, text=True).stdout.strip()}
json.dump(summ, open(f"{O}/12_summary.json", "w"), indent=1, default=str)
pd.set_option("display.width", 250); print(BT[BT.scope == "POOLED"].to_string()); print(json.dumps({k: summ[k] for k in ["initial_accuracy", "initial_accuracy_pooled", "truth_top2", "truth_top3", "eligibility", "primary_wrong_N", "primary_correct_N", "primary_wrong_N_by_config", "initial_acc_in_primary_population", "mean_common_pool_simulatable", "mean_full_pool"]}, indent=1)); print(EX[["kind", "config", "sample_id", "truth", "top1", "top2", "profile_question", "question_text", "p_correct"]].to_string())
