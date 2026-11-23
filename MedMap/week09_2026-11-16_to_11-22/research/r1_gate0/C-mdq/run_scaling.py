"""확장성: 항목 수 n 증가 시 계산 시간 (정확 유한 모델 = 연속 W 셀). SYNTHETIC."""
import sys, time
import numpy as np, pandas as pd
sys.path.insert(0, "/home/<user>/medmap-gate0-parallel/C-mdq")
from core import make_instance
import methods as Mt
import exact_grid as X
from mdq_candidate import ContModel
from pair_model import PairModel

rows = []
for n in [6, 7, 8, 9, 10, 11, 12]:
    for seed in range(3):
        I = make_instance(seed=7000 + 100 * n + seed, n=n, d=3, pref="pairs", n_deps=1)
        r = dict(n=n, seed=seed)
        t = time.time(); C = ContModel(I); r["t_cont_model"] = time.time() - t
        P = PairModel(C)
        r.update(n_pairs=P.nA, T=P.T)
        t = time.time(); Q, c, nc = Mt.hitting_set_milp(P); r.update(t_milp=time.time() - t, hs_cost=c, hs_cons=nc)
        t = time.time(); tr = Mt.build_tree(P, Mt.pol_greedy_count); r["t_greedy"] = time.time() - t
        r["greedy_worst"] = Mt.tree_metrics(P, tr)[0]["worst_cost"]
        t = time.time(); tr = Mt.build_tree(P, Mt.pol_ec2("u")); r["t_ec2"] = time.time() - t
        r["ec2_worst"] = Mt.tree_metrics(P, tr)[0]["worst_cost"]
        if n <= 9:
            t = time.time(); v, _, ns = X.adaptive_minimax(P); r.update(t_dp=time.time() - t, dp_worst=v, dp_states=ns)
            t = time.time(); v9, n9 = C.adaptive_opt(); r.update(t_9b=time.time() - t, mdq9b_worst=v9, states_9b=n9)
        rows.append(r)
        print(r, flush=True)
        pd.DataFrame(rows).to_csv("/home/<user>/medmap-gate0-parallel/C-mdq/results_scaling.csv", index=False)
print("DONE")
