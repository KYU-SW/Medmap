"""검증기 검증: (1) 연속 라벨(꼭짓점 인증)을 무작위 표본으로 독립 확인, (2) 변이 시험: 라벨 1개를 바꾸면 X8(DP)=9b 대조가 깨지는지."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/<user>/medmap-gate0-parallel/C-mdq")
from core import make_instance
from mdq_candidate import ContModel, NAMES
from pair_model import PairModel
import exact_grid as X

rng = np.random.default_rng(12345)
rows = []
cert_viol = 0; cert_checked = 0; undet_found = 0; undet_total = 0
for seed in range(20):
    I = make_instance(seed=5000 + seed, n=4, d=3, pref="pairs+ratio" if seed % 2 else "pairs")
    C = ContModel(I)
    prefs = [(I.tests[t]["j"], I.tests[t]["k"], I.tests[t]["rho"]) for t in C.pref_t]
    Wsamp = rng.dirichlet(np.ones(I.d), 20000)
    sig = np.array([[int(w[j] >= r * w[k]) for (j, k, r) in prefs] for w in Wsamp]) if prefs else np.zeros((len(Wsamp), 0), int)
    for p, (wi, ci) in enumerate(C.pairs):
        vec = np.array(C.cells[ci][0])
        inside = (sig == vec).all(axis=1) if len(vec) else np.ones(len(Wsamp), bool)
        ws = Wsamp[inside]
        if len(ws) == 0:
            continue
        s = C.worlds[wi]
        S = I.base + I.delta @ s.astype(float)
        feas = np.array([all(s[i] != v for (i, v) in I.contra[a]) for a in range(I.m)])
        lab = C.labels[p]
        if lab == "NONE":
            continue
        U = np.where(feas, ws @ S.T, -np.inf)
        am = set(U.argmax(axis=1).tolist())
        if lab == "UNDET":
            undet_total += 1
            undet_found += int(len(am) >= 2)
        else:
            cert_checked += 1
            cert_viol += int(am != {NAMES.index(lab)})
print(f"[label-check] certified pairs checked={cert_checked} violations(sample argmax != cert)={cert_viol}")
print(f"[label-check] UNDET pairs={undet_total} with >=2 sampled argmax={undet_found}")

# 변이 시험
changed = 0; tried = 0
for seed in range(20):
    I = make_instance(seed=6000 + seed, n=4, d=3)
    C = ContModel(I)
    v9, _ = C.adaptive_opt()
    P = PairModel(C)
    labs = sorted(set(P.g))
    a = int(rng.integers(P.nA))
    newlab = [l for l in labs + ["MUT"] if l != P.g[a]][0]
    P.g[a] = newlab
    P.label_mask = {}
    for k in range(P.nA):
        P.label_mask[P.g[k]] = P.label_mask.get(P.g[k], 0) | (1 << k)
    v8m, _, _ = X.adaptive_minimax(P)
    tried += 1
    changed += int(abs(v8m - v9) > 1e-9)
print(f"[mutation] one-label mutations={tried}, X8(mutated) != 9b in {changed}")
pd.DataFrame([dict(cert_checked=cert_checked, cert_viol=cert_viol, undet_total=undet_total, undet_found=undet_found,
                   mut_tried=tried, mut_detected=changed)]).to_csv(
    "/home/<user>/medmap-gate0-parallel/C-mdq/results_validation_checks.csv", index=False)
