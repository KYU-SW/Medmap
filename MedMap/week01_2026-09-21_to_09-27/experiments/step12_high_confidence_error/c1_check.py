"""STEP 12: C1 검증 — S2가 기본모델 confidence의 재표현인지. 기존 model.pkl(추론만)·scores.parquet·cond_token_logp.npz만 사용. 학습 없음."""
import json, pickle, time, collections
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from scipy.stats import spearmanr, pearsonr
D = "data/ddxplus/en"; W = "exp/step2_3_workingdx"; S = "exp/step5_7_discrepancy"; O = "exp/step12_high_confidence_error"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
vj = json.load(open(f"{W}/vocab.json")); vocab, classes = vj["vocab"], vj["classes"]; cidx = {c: i for i, c in enumerate(classes)}; V = len(vocab)
clf = pickle.load(open(f"{W}/model.pkl", "rb")); assert list(clf.classes_) == list(range(49))
npz = np.load(f"{S}/cond_token_logp.npz", allow_pickle=True); logP = npz["logP"]; assert list(npz["classes"]) == classes
ev_tok = {t: j for t, j in vocab.items() if t.startswith("E_")}
va = pd.read_csv(f"{D}/release_validate_patients"); va["ddx"] = va["DIFFERENTIAL_DIAGNOSIS"].map(lambda s: json.loads(s.replace("'", '"')))
wd = pd.read_parquet(f"{W}/val_working_dx.parquet"); sc = pd.read_parquet(f"{S}/scores.parquet")[["idx", "k", "seed", "S2_best_alt_lr", "REF_conf"]]
wd = wd.merge(sc, on=["idx", "k", "seed"]); log("rows", len(wd))
def featurize(views, ages, sexes):
    rows, cols = [], []
    for i, v in enumerate(views):
        toks = set(v) | {f"AGE_{min(int(ages[i])//10, 9)}", f"SEX_{sexes[i]}"}
        for t in toks:
            j = vocab.get(t)
            if j is not None: rows.append(i); cols.append(j)
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(views), V))
def ev_matrix(views):
    rows, cols = [], []
    for i, v in enumerate(views):
        for t in v:
            j = ev_tok.get(t)
            if j is not None: rows.append(i); cols.append(j)
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(views), V))
def s2_for(LL, d):
    own = LL[np.arange(len(d)), d]; LLm = LL.copy(); LLm[np.arange(len(d)), d] = -np.inf; return LLm.max(1) - own
out, stress = [], []
for (k, seed), g in wd.groupby(["k", "seed"], sort=False):
    g = g.sort_values("idx"); views = [json.loads(s) for s in g["exposed"]]; age = va.loc[g["idx"].values, "AGE"].values; sex = va.loc[g["idx"].values, "SEX"].values
    P = clf.predict_proba(featurize(views, age, sex)); srt = np.sort(P, 1); conf = srt[:, -1]; margin = srt[:, -1] - srt[:, -2]; ent = -(P * np.log(P + 1e-12)).sum(1)
    pred = P.argmax(1); truth = g["truth"].map(cidx).values; wdi = g["working_dx"].map(cidx).values; assert (pred == wdi).mean() > 0.999, "재추론 결과가 저장된 working_dx와 불일치"
    assert np.allclose(conf, g["wd_prob"].values, atol=2e-4)
    n_ev = np.array([sum(t in ev_tok for t in v) for v in views])
    out.append(pd.DataFrame({"sample_id": g["idx"].values, "k": k, "seed": seed, "truth": g["truth"].values, "predicted": g["working_dx"].values, "wrong": (wdi != truth).astype(int), "max_confidence": conf, "top1_top2_margin": margin, "entropy": ent, "S2": g["S2_best_alt_lr"].values, "n_evidence_exposed": n_ev, "set": "NATURAL"}))
    # STRESS: DDX(full-evidence)에서 정답 아닌 최상위 후보를 working dx로 강제 (별도 세트). 비교 baseline = 그 대안에 대한 모델 확률
    LL = ev_matrix(views) @ logP.T
    alt = np.array([next((cidx[n] for n, p in dd if n != tr), -1) for dd, tr in zip(va.loc[g["idx"].values, "ddx"], g["truth"].values)]); ok = alt >= 0
    s2_alt = s2_for(LL, np.where(ok, alt, 0)); s2_tru = s2_for(LL, truth); p_alt = P[np.arange(len(P)), np.where(ok, alt, 0)]; p_tru = P[np.arange(len(P)), truth]
    stress.append(pd.DataFrame({"sample_id": np.r_[g["idx"].values[ok], g["idx"].values], "k": k, "seed": seed, "truth": np.r_[g["truth"].values[ok], g["truth"].values], "working_dx": np.r_[[classes[i] for i in alt[ok]], g["truth"].values],
                                "wrong": np.r_[np.ones(ok.sum(), int), np.zeros(len(g), int)], "model_prob_of_wd": np.r_[p_alt[ok], p_tru], "S2": np.r_[s2_alt[ok], s2_tru], "ddx_rank_of_wd": np.r_[np.ones(ok.sum(), int), np.zeros(len(g), int)], "n_evidence_exposed": np.r_[n_ev[ok], n_ev], "set": "STRESS"}))
    log(k, seed, "done")
T = pd.concat(out); T.to_csv(f"{O}/01_sample_table.csv", index=False); ST = pd.concat(stress); ST.to_csv(f"{O}/05_stress_errors.csv", index=False)
def tpr_at(y, s, f):
    fpr, tpr, _ = roc_curve(y, s); return float(np.interp(f, fpr, tpr))
METHODS = {"A_max_confidence": lambda d: -d["max_confidence"], "B_margin": lambda d: -d["top1_top2_margin"], "C_entropy": lambda d: d["entropy"], "D_S2": lambda d: d["S2"]}
STRATA = [("ALL", 0), ("conf>=0.8", .8), ("conf>=0.9", .9), ("conf>=0.95", .95)]
strata_rows, comp_rows, corr_rows, hc_rows = [], [], [], []
for (k, seed), g in T.groupby(["k", "seed"], sort=False):
    w = g[g.wrong == 1]; c = w["max_confidence"]
    strata_rows.append({"k": k, "seed": seed, "n_samples": len(g), "n_wrong": len(w), "wrong_rate": round(len(w) / len(g), 4), "wrong_conf_median": round(c.median(), 4), "wrong_conf_mean": round(c.mean(), 4), **{f"wrong_conf>={t}": int((c >= t).sum()) for t in (.8, .9, .95)}, **{f"wrong_conf>={t}_frac": round(float((c >= t).mean()), 4) for t in (.8, .9, .95)}, "correct_conf_median": round(g[g.wrong == 0]["max_confidence"].median(), 4)})
    # 경고 임계값: ALL 층 정답군 FPR 5%에서 S2 임계
    thr = np.quantile(g[g.wrong == 0]["S2"], 0.95)
    for name, lo in STRATA:
        d = g[g.max_confidence >= lo]; y = d["wrong"].values; npos, nneg = int(y.sum()), int((1 - y).sum())
        for mn, fn in METHODS.items():
            r = {"k": k, "seed": seed, "stratum": name, "method": mn, "n": len(d), "n_wrong": npos, "n_correct": nneg}
            if npos >= 20 and nneg >= 20:
                s = fn(d).values; r.update({"auroc": round(roc_auc_score(y, s), 4), "auprc": round(average_precision_score(y, s), 4), "auprc_baseline": round(npos / len(d), 4), "tpr@fpr5": round(tpr_at(y, s, .05), 4), "tpr@fpr10": round(tpr_at(y, s, .10), 4), "tpr@fpr20": round(tpr_at(y, s, .20), 4)})
            else: r.update({"auroc": "", "note": f"insufficient sample (pos={npos}, neg={nneg})"})
            comp_rows.append(r)
        if len(d) >= 10:
            sp_, pr_ = spearmanr(d["S2"], -d["max_confidence"]), pearsonr(d["S2"], -d["max_confidence"])
            corr_rows.append({"k": k, "seed": seed, "stratum": name, "n": len(d), "spearman_S2_vs_negconf": round(float(sp_[0]), 4), "pearson_S2_vs_negconf": round(float(pr_[0]), 4), "spearman_S2_vs_entropy": round(float(spearmanr(d["S2"], d["entropy"])[0]), 4), "spearman_S2_vs_negmargin": round(float(spearmanr(d["S2"], -d["top1_top2_margin"])[0]), 4)})
    hc = g[(g.wrong == 1) & (g.max_confidence >= .9)].copy(); hc["S2_warned_at_FPR5_threshold"] = hc["S2"] > thr; hc["S2_threshold_used"] = thr
    hc_rows.append(hc[["sample_id", "k", "seed", "truth", "predicted", "max_confidence", "top1_top2_margin", "S2", "S2_warned_at_FPR5_threshold", "S2_threshold_used", "n_evidence_exposed"]])
pd.DataFrame(strata_rows).to_csv(f"{O}/02_confidence_strata.csv", index=False); CMP = pd.DataFrame(comp_rows); CMP.to_csv(f"{O}/03_method_comparison.csv", index=False)
HC = pd.concat(hc_rows); HC.to_csv(f"{O}/04_high_confidence_errors.csv", index=False)
# stress 세트 성능/상관
for (k, seed), g in ST.groupby(["k", "seed"], sort=False):
    y = g["wrong"].values
    for mn, s in {"A_model_prob_of_wd": -g["model_prob_of_wd"].values, "D_S2": g["S2"].values}.items():
        comp_rows.append({"k": k, "seed": seed, "stratum": "STRESS_ERROR(ddx-alt vs truth)", "method": mn, "n": len(g), "n_wrong": int(y.sum()), "n_correct": int((1 - y).sum()), "auroc": round(roc_auc_score(y, s), 4), "auprc": round(average_precision_score(y, s), 4), "auprc_baseline": round(y.mean(), 4), "tpr@fpr5": round(tpr_at(y, s, .05), 4), "tpr@fpr10": round(tpr_at(y, s, .10), 4), "tpr@fpr20": round(tpr_at(y, s, .20), 4)})
    hcs = g[(g.wrong == 1) & (g.model_prob_of_wd >= .9)]
    corr_rows.append({"k": k, "seed": seed, "stratum": "STRESS_ERROR", "n": len(g), "spearman_S2_vs_negconf": round(float(spearmanr(g["S2"], -g["model_prob_of_wd"])[0]), 4), "pearson_S2_vs_negconf": round(float(pearsonr(g["S2"], -g["model_prob_of_wd"])[0]), 4), "n_stress_wrong_modelprob>=0.9": len(hcs)})
pd.DataFrame(comp_rows).to_csv(f"{O}/03_method_comparison.csv", index=False); pd.DataFrame(corr_rows).to_csv(f"{O}/06_correlations.csv", index=False)
# 고신뢰 오답 층에서 S2 증분: conf 조건부 (conf>=0.9 층 내부) + 결합 검사
summ = {"n_rows": len(T), "strata": strata_rows, "hc_warned": {f"k{k}_s{seed}": {"n_hc_wrong": len(h), "S2_warned": int(h.S2_warned_at_FPR5_threshold.sum())} for (k, seed), h in HC.groupby(["k", "seed"])}}
json.dump(summ, open(f"{O}/summary.json", "w"), indent=1, default=str)
pd.set_option("display.width", 250); C = pd.DataFrame(comp_rows)
print(C[(C.seed == 42)][["k", "stratum", "method", "n", "n_wrong", "auroc", "auprc", "auprc_baseline", "tpr@fpr5", "tpr@fpr10"]].to_string()); print(pd.DataFrame(corr_rows)[lambda d: d.seed == 42].to_string()); print(pd.DataFrame(strata_rows)[lambda d: d.seed == 42].to_string()); log("DONE")
