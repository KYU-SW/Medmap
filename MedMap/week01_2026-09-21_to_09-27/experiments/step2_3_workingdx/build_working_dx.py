"""Step 2+3: 부분 공개 환경 + 기본 진단 모델 → working diagnosis 생성.
- 특징: evidence 토큰(값 포함) 원핫 + AGE 10세 구간 + SEX
- 학습: train 각 환자 1개 부분 뷰(INITIAL + k개, k~U{3,5,10,all}), seed 42. 미노출=미질문(0)
- 모델: LogisticRegression(lbfgs, multinomial)
- 평가: validate, k∈{3,5,10,all} × seed{42,43,44} → working dx 정/오 + DDX 1위 대비
출력: exp/step2_3_workingdx/{model.pkl, vocab.json, metrics.json, val_working_dx.parquet}
"""
import json, time, pickle, sys
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.linear_model import LogisticRegression
D = "data/ddxplus/en"; O = "exp/step2_3_workingdx"
KS = [3, 5, 10, "all"]; SEEDS = [42, 43, 44]
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)

def load(split):
    df = pd.read_csv(f"{D}/release_{split}_patients")
    df["ev"] = df["EVIDENCES"].map(lambda s: json.loads(s.replace("'", '"')))
    return df

def partial_view(ev, init, k, rng):
    rest = [e for e in ev if e != init]
    if k == "all" or k >= len(rest): return ev
    idx = rng.choice(len(rest), size=k, replace=False)
    return [init] + [rest[i] for i in sorted(idx)]

def featurize(views, ages, sexes, vocab):
    rows, cols = [], []
    for i, v in enumerate(views):
        toks = set(v) | {f"AGE_{min(int(a)//10, 9)}" for a in [ages[i]]} | {f"SEX_{sexes[i]}"}
        for t in toks:
            j = vocab.get(t)
            if j is not None: rows.append(i); cols.append(j)
    return sp.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(views), len(vocab)))

log("load train"); tr = load("train"); log("train rows", len(tr))
vocab = {}
for v in tr["ev"]:
    for t in v: vocab.setdefault(t, len(vocab))
for a in range(10): vocab.setdefault(f"AGE_{a}", len(vocab))
for s in ["M", "F"]: vocab.setdefault(f"SEX_{s}", len(vocab))
classes = sorted(tr["PATHOLOGY"].unique()); cidx = {c: i for i, c in enumerate(classes)}
log("vocab", len(vocab), "classes", len(classes))
rng = np.random.default_rng(42)
kchoice = rng.choice(len(KS), size=len(tr))
views = [partial_view(ev, init, KS[kc], rng) for ev, init, kc in zip(tr["ev"], tr["INITIAL_EVIDENCE"], kchoice)]
Xtr = featurize(views, tr["AGE"].values, tr["SEX"].values, vocab); ytr = tr["PATHOLOGY"].map(cidx).values
del tr, views
log("Xtr", Xtr.shape, "nnz", Xtr.nnz)
clf = LogisticRegression(max_iter=300, C=1.0, n_jobs=4)
clf.fit(Xtr, ytr); log("fit done, train acc", round(clf.score(Xtr, ytr), 4))
pickle.dump(clf, open(f"{O}/model.pkl", "wb")); json.dump({"vocab": vocab, "classes": classes}, open(f"{O}/vocab.json", "w"))
del Xtr
log("load validate"); va = load("validate")
va["ddx"] = va["DIFFERENTIAL_DIAGNOSIS"].map(lambda s: json.loads(s.replace("'", '"')))
va["ddx1"] = va["ddx"].map(lambda d: d[0][0])
truth = va["PATHOLOGY"].map(cidx).values
metrics = {"train_n": int(len(ytr)), "vocab": len(vocab), "per_k": {}}; recs = []
for k in KS:
    for seed in (SEEDS if k != "all" else [42]):
        rng = np.random.default_rng(seed)
        views = [partial_view(ev, init, k, rng) for ev, init in zip(va["ev"], va["INITIAL_EVIDENCE"])]
        X = featurize(views, va["AGE"].values, va["SEX"].values, vocab)
        P = clf.predict_proba(X); wd = P.argmax(1)
        top3 = (np.argsort(-P, 1)[:, :3] == truth[:, None]).any(1)
        m = {"acc_working_dx": round(float((wd == truth).mean()), 4), "top3": round(float(top3.mean()), 4),
             "n_wrong": int((wd != truth).sum()), "n_exposed_mean": round(float(np.mean([len(v) for v in views])), 2)}
        metrics["per_k"][f"k{k}_s{seed}"] = m; log(k, seed, m)
        recs.append(pd.DataFrame({"idx": np.arange(len(va)), "k": str(k), "seed": seed, "truth": va["PATHOLOGY"].values,
            "working_dx": [classes[i] for i in wd], "wd_prob": P.max(1).round(4), "ddx1": va["ddx1"].values,
            "n_exposed": [len(v) for v in views], "exposed": [json.dumps(v) for v in views]}))
metrics["ddx1_acc"] = round(float((va["ddx1"] == va["PATHOLOGY"]).mean()), 4)
pd.concat(recs).to_parquet(f"{O}/val_working_dx.parquet", index=False)
json.dump(metrics, open(f"{O}/metrics.json", "w"), indent=1); log("DONE"); print(json.dumps(metrics, indent=1))
