"""구조 확인: 정확 유한 모델에서 hitting set 최소 제약(구분 테스트 집합)의 크기 분포.
모든 최소 제약이 단일 원소면 일괄 MDQ = g 의 '본질 변수(관련 테스트)' 집합 -> 조합 최적화 불필요."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/<user>/medmap-gate0-parallel/C-mdq")
from core import make_instance
from run_experiments import SCEN, DEFAULT_R
from mdq_candidate import ContModel
from pair_model import PairModel

rows = []
for sc, kw in SCEN.items():
    if sc.startswith("R"):
        continue
    for seed in range(10):
        k = dict(kw); k.setdefault("grid_r", DEFAULT_R.get(k.get("d", 3)))
        I = make_instance(seed=1000 * (list(SCEN).index(sc) + 1) + seed, **k)
        P = PairModel(ContModel(I))
        labs = np.array(P.g); T = P.T; seps = set()
        for a in range(P.nA):
            diff = np.nonzero(labs[a + 1:] != labs[a])[0] + a + 1
            if len(diff) == 0:
                continue
            sepm = (P.ans[:, diff] != P.ans[:, [a]])
            codes = (sepm.T.astype(np.int64) * (1 << np.arange(T, dtype=np.int64))).sum(axis=1)
            seps.update(np.unique(codes).tolist())
        mins = [s for s in seps if not any((o != s) and (o & s) == o for o in seps)]
        sizes = [bin(s).count("1") for s in mins]
        rows.append(dict(scen=sc, seed=seed, n_min_cons=len(mins), max_size=max(sizes) if sizes else 0,
                         all_singleton=int(all(z == 1 for z in sizes))))
df = pd.DataFrame(rows)
df.to_csv("/home/<user>/medmap-gate0-parallel/C-mdq/results_struct_hitting.csv", index=False)
print(df.groupby("scen", sort=False).agg(all_singleton=("all_singleton", "sum"), max_size=("max_size", "max")).to_string())
print("TOTAL all_singleton", int(df.all_singleton.sum()), "/", len(df))
