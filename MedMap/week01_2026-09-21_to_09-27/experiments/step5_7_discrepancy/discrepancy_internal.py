"""Step 5+6+7: 실험 A(내부 지식). train에서 P(소견|질환) 추정 → 불일치 점수 → 오답 working dx 탐지 평가.
점수(높을수록 재검토):
  S1 surprise      = -(1/|F|) Σ_f log P(f|d)                      현재 진단에서 소견들이 드묾
  S2 best_alt_lr   = max_{d'≠d} Σ_f [log P(f|d') - log P(f|d)]    소견 전체를 더 잘 설명하는 대안 존재 (v5 §9)
  S3 max_single_lr = max_f max_{d'} [log P(f|d') - log P(f|d)]    단일 소견 하나가 다른 질환에서 훨씬 흔함
  S2p              = S2 + log prior 차이 (기저율 반영)
  REF_conf         = 1 - P_model(d)  기본 진단모델 자기 확신 (참고 baseline, 같은 모델이라 유리)
평가: k∈{3,5,10} × seed{42,43,44}, label=working dx≠정답. AUROC/AUPRC/TPR@FPR 5,10,20%.
출력: exp/step5_7_discrepancy/{cond_token_logp.npz, metrics.json, scores.parquet}
"""
import json, time, pickle
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
D = "data/ddxplus/en"; W = "exp/step2_3_workingdx"; O = "exp/step5_7_discrepancy"; ALPHA = 0.5
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)
vj = json.load(open(f"{W}/vocab.json")); vocab, classes = vj["vocab"], vj["classes"]; cidx = {c: i for i, c in enumerate(classes)}
ev_tok = {t: j for t, j in vocab.items() if t.startswith("E_")}  # 소견 토큰만 (AGE/SEX 제외)
V = len(vocab)
# Step 5: train 전체(모든 소견)로 count
log("load train"); tr = pd.read_csv(f"{D}/release_train_patients", usecols=["PATHOLOGY", "EVIDENCES"])
y = tr["PATHOLOGY"].map(cidx).values
rows, cols = [], []
for i, s in enumerate(tr["EVIDENCES"]):
    for t in json.loads(s.replace("'", '"')):
        j = vocab.get(t)
        if j is not None: rows.append(i); cols.append(j)
X = sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(tr), V)); del rows, cols, tr
Y = sp.csr_matrix((np.ones(len(y), np.float32), (np.arange(len(y)), y)), shape=(len(y), len(classes)))
cnt = (Y.T @ X).toarray(); n_d = np.asarray(Y.sum(0)).ravel()
logP = np.log((cnt + ALPHA) / (n_d[:, None] + 2 * ALPHA))  # 49×V, 이항 add-alpha
log_prior = np.log(n_d / n_d.sum())
np.savez(f"{O}/cond_token_logp.npz", logP=logP, log_prior=log_prior, classes=np.array(classes), n_d=n_d)
log("P(f|d) done", logP.shape, "train n", len(y)); del X, Y
# Step 6: 점수
clf = pickle.load(open(f"{W}/model.pkl", "rb"))
wd = pd.read_parquet(f"{W}/val_working_dx.parquet")
wd["label_wrong"] = (wd["working_dx"] != wd["truth"]).astype(int)
d = wd["working_dx"].map(cidx).values
ev_lists = [[vocab[t] for t in json.loads(s) if t in ev_tok] for s in wd["exposed"]]
R = logP.max(0)[None, :] - logP  # 49×V: 토큰별 최대 대안 log ratio
S1 = np.array([-logP[di, f].mean() for di, f in zip(d, ev_lists)])
S3 = np.array([R[di, f].max() for di, f in zip(d, ev_lists)])
Xv = sp.csr_matrix((np.ones(sum(map(len, ev_lists)), np.float32),
     (np.repeat(np.arange(len(wd)), [len(f) for f in ev_lists]), np.concatenate(ev_lists))), shape=(len(wd), V))
LL = Xv @ logP.T  # n×49 소견 로그우도
own = LL[np.arange(len(wd)), d]
LLm = LL.copy(); LLm[np.arange(len(wd)), d] = -np.inf
S2 = LLm.max(1) - own
LLp = LL + log_prior[None, :]; ownp = LLp[np.arange(len(wd)), d]; LLp[np.arange(len(wd)), d] = -np.inf
S2p = LLp.max(1) - ownp
wd["S1_surprise"], wd["S2_best_alt_lr"], wd["S3_max_single_lr"], wd["S2p_prior"] = S1, S2, S3, S2p
wd["REF_conf"] = 1 - wd["wd_prob"].values
wd["alt_S2"] = [classes[i] for i in LLm.argmax(1)]
wd["alt_S2_is_truth"] = (wd["alt_S2"] == wd["truth"]).astype(int)
log("scores done")
# Step 7: 평가
def tpr_at(yt, s, fpr_t):
    fpr, tpr, _ = roc_curve(yt, s); return float(np.interp(fpr_t, fpr, tpr))
SC = ["S1_surprise", "S2_best_alt_lr", "S3_max_single_lr", "S2p_prior", "REF_conf"]
metrics = {"alpha": ALPHA, "per_config": {}}
for (k, seed), g in wd.groupby(["k", "seed"]):
    yt = g["label_wrong"].values; m = {"n": len(g), "n_wrong": int(yt.sum()), "wrong_rate": round(float(yt.mean()), 4),
        "alt_S2_recovers_truth_among_wrong": round(float(g.loc[yt == 1, "alt_S2_is_truth"].mean()), 4)}
    for s in SC:
        v = g[s].values
        m[s] = {"auroc": round(roc_auc_score(yt, v), 4), "auprc": round(average_precision_score(yt, v), 4),
                **{f"tpr@fpr{f}": round(tpr_at(yt, v, f / 100), 4) for f in (5, 10, 20)}}
    metrics["per_config"][f"k{k}_s{seed}"] = m
# seed 평균
agg = {}
for k in ["3", "5", "10", "all"]:
    cfg = [v for kk, v in metrics["per_config"].items() if kk.startswith(f"k{k}_")]
    if not cfg: continue
    agg[f"k{k}"] = {"n_seeds": len(cfg), "wrong_rate": round(np.mean([c["wrong_rate"] for c in cfg]), 4),
        "alt_S2_recovers_truth_among_wrong": round(np.mean([c["alt_S2_recovers_truth_among_wrong"] for c in cfg]), 4)}
    for s in SC:
        agg[f"k{k}"][s] = {m_: round(float(np.mean([c[s][m_] for c in cfg])), 4) for m_ in cfg[0][s]}
metrics["seed_mean"] = agg
wd.drop(columns=["exposed"]).to_parquet(f"{O}/scores.parquet", index=False)
json.dump(metrics, open(f"{O}/metrics.json", "w"), indent=1)
for k, v in agg.items():
    print(f"\n== k={k}  wrong_rate={v['wrong_rate']}  alt_S2 recovers truth(among wrong)={v['alt_S2_recovers_truth_among_wrong']}")
    print(f"{'score':18s} auroc  auprc  tpr@5  tpr@10 tpr@20")
    for s in SC: r = v[s]; print(f"{s:18s} {r['auroc']:.4f} {r['auprc']:.4f} {r['tpr@fpr5']:.4f} {r['tpr@fpr10']:.4f} {r['tpr@fpr20']:.4f}")
log("DONE")
