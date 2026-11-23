"""실험 러너 (SYNTHETIC). 같은 입력 인스턴스에서 모든 방법 비교. 결과: results_methods.csv, results_instances.csv"""
import sys, time, argparse, os
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/<user>/medmap-gate0-parallel/C-mdq")
from core import GridModel, make_instance
import methods as Mt
import exact_grid as X
from mdq_candidate import ContModel
from pair_model import PairModel

OUT = "/home/<user>/medmap-gate0-parallel/C-mdq"

SCEN = {
    # 확인 항목 수 증가
    "N3": dict(n=3), "N4": dict(n=4), "N5": dict(n=5), "N6": dict(n=6), "N7": dict(n=7),
    # 선호 질문 수 증가 (n=4)
    "P0": dict(n=4, pref="none"), "P1": dict(n=4, pref="one"), "P3": dict(n=4, pref="pairs"),
    "P6": dict(n=4, pref="pairs+ratio"),
    # 비용 편차 (검사 4 / 기록 1)
    "COSTH": dict(n=5, cost="hetero"),
    # 안전 조건 영향
    "SAFE0": dict(n=5, contra_p=0.0), "SAFE6": dict(n=5, contra_p=0.6),
    # 조건 의존성
    "DEP0": dict(n=5, n_deps=0), "DEP3": dict(n=5, n_deps=3),
    # 묶음 검사
    "BUNDLE": dict(n=5, cost="hetero", bundles=2),
    # 기준 4개 (선호 질문 6개)
    "D4": dict(n=4, d=4, pref="pairs", grid_r=12),
    # 격자 해상도 민감도 (이산화 오차)
    "R5": dict(n=4, grid_r=5), "R10": dict(n=4, grid_r=10), "R20": dict(n=4, grid_r=20), "R40": dict(n=4, grid_r=40),
}
DEFAULT_R = {3: 30, 4: 12}


def run_instance(scen, seed, kw):
    kw = dict(kw)
    kw.setdefault("grid_r", DEFAULT_R.get(kw.get("d", 3)))
    # 같은 문제(같은 seed)를 해상도만 바꿔 비교하도록 R* 는 공통 seed 사용
    base_id = 99 if scen.startswith("R") else (list(SCEN).index(scen) + 1)
    I = make_instance(seed=1000 * base_id + seed, **kw)
    t0 = time.time()
    M = GridModel(I)
    t_model = time.time() - t0
    C = ContModel(I)
    rows = []
    inst_row = dict(scen=scen, seed=seed, n=I.n, d=I.d, T=M.T, n_worlds=len(M.worlds), n_atoms=M.nA,
                    n_cells_cont=len(C.cells), n_pairs_cont=len(C.pairs), dropped_cells=C.dropped_cells,
                    undet_frac_grid=float(M.w_unif[np.array(M.g) == "UNDET"].sum()),
                    undet_frac_cont=C.undet_frac(), t_model=t_model)

    t = time.time(); v8, ch8, nstates = X.adaptive_minimax(M); t8 = time.time() - t
    t = time.time(); ve_u, che_u = X.adaptive_expected(M, M.w_unif); te = time.time() - t
    ve_s, che_s = X.adaptive_expected(M, M.w_skew)
    t = time.time(); Q7, c7 = X.batch_bruteforce(M); t7 = time.time() - t
    t = time.time(); Q6, c6, ncons = Mt.hitting_set_milp(M); t6 = time.time() - t
    t = time.time(); axp, _ = X.axp_lower_bound(M); tax = time.time() - t
    t = time.time(); v9, n9 = C.adaptive_opt(); t9 = time.time() - t
    w9, e9 = C.adaptive_tree_stats()
    t = time.time(); Q9, c9 = C.batch_opt(); t9a = time.time() - t
    inst_row.update(opt_adaptive_worst=v8, opt_exp_u=ve_u, opt_exp_s=ve_s, opt_batch_brute=c7, hs_milp=c6,
                    hs_constraints=ncons, axp_lb=axp, cont_adaptive_worst=v9, cont_batch=c9, dp_states=nstates,
                    cont_states=n9, t_dp=t8, t_brute=t7, t_milp=t6, t_axp=tax, t_cont_adapt=t9, t_cont_batch=t9a,
                    t_expdp=te, batch_Q=str(Q7), milp_Q=str(Q6), cont_Q=str(Q9))

    pols = [
        ("0_naive_point", lambda: Mt.build_tree(M, Mt.pol_naive, stop=Mt.naive_stop)),
        ("1_random", lambda: Mt.build_tree(M, Mt.pol_random(seed))),
        ("2_fixed", lambda: Mt.build_tree(M, Mt.pol_fixed)),
        ("3_greedy_count", lambda: Mt.build_tree(M, Mt.pol_greedy_count)),
        ("4_voi_unif", lambda: Mt.build_tree(M, Mt.pol_voi("u"))),
        ("4s_voi_skew", lambda: Mt.build_tree(M, Mt.pol_voi("s"))),
        ("5_minimax_regret", lambda: Mt.build_tree(M, Mt.pol_regret())),
        ("6a_hs_batch", lambda: Mt.chain_tree(M, sorted(Q6, key=lambda q: (M.cost[q], q)))),
        ("6b_hs_ordered", lambda: Mt.build_tree(M, Mt.pol_ordered(sorted(Q6, key=lambda q: (M.cost[q], q))))),
        ("7_opt_batch", lambda: Mt.chain_tree(M, sorted(Q7, key=lambda q: (M.cost[q], q)))),
        ("8_opt_adaptive_worst", lambda: Mt.build_tree(M, ch8)),
        ("8e_opt_expected_unif", lambda: Mt.build_tree(M, che_u)),
        ("EC2_unif", lambda: Mt.build_tree(M, Mt.pol_ec2("u"))),
        ("EC2_skew", lambda: Mt.build_tree(M, Mt.pol_ec2("s"))),
    ]
    for name, fn in pols:
        t = time.time()
        tree = fn()
        tt = time.time() - t
        met, _ = Mt.tree_metrics(M, tree)
        ce = C.eval_grid_tree(tree)
        rows.append(dict(scen=scen, seed=seed, method=name, time=tt, **met, **ce,
                         gap_worst=met["worst_cost"] - v8, gap_exp_u=met["exp_cost_u"] - ve_u,
                         gap_exp_s=met["exp_cost_s"] - ve_s))
    rows.append(dict(scen=scen, seed=seed, method="9b_mdq_cont_adaptive", time=t9, worst_cost=w9,
                     exp_cost_c=e9, gap_worst=w9 - v8))
    rows.append(dict(scen=scen, seed=seed, method="9a_mdq_cont_batch", time=t9a, worst_cost=c9,
                     gap_worst=c9 - v8))
    # ---- 정확 유한 모델(연속 W 셀) 위 대조 및 기준선 ----
    P = PairModel(C)
    t = time.time(); v8x, ch8x, _ = X.adaptive_minimax(P); t8x = time.time() - t
    vex, chex = X.adaptive_expected(P, P.w_unif)
    Q7x, c7x = X.batch_bruteforce(P)
    Q6x, c6x, _ = Mt.hitting_set_milp(P)
    axpx, _ = X.axp_lower_bound(P)
    inst_row.update(x_opt_adaptive_worst=v8x, x_opt_exp_u=vex, x_opt_batch_brute=c7x, x_hs_milp=c6x, x_axp_lb=axpx,
                    t_dp_x=t8x)
    xp = [("X1_random", lambda: Mt.build_tree(P, Mt.pol_random(seed))),
          ("X2_fixed", lambda: Mt.build_tree(P, Mt.pol_fixed)),
          ("X3_greedy_count", lambda: Mt.build_tree(P, Mt.pol_greedy_count)),
          ("X6a_hs_batch", lambda: Mt.chain_tree(P, sorted(Q6x, key=lambda q: (P.cost[q], q)))),
          ("X6b_hs_ordered", lambda: Mt.build_tree(P, Mt.pol_ordered(sorted(Q6x, key=lambda q: (P.cost[q], q))))),
          ("X7_opt_batch", lambda: Mt.chain_tree(P, sorted(Q7x, key=lambda q: (P.cost[q], q)))),
          ("X8_opt_adaptive_worst", lambda: Mt.build_tree(P, ch8x)),
          ("X8e_opt_expected_unif", lambda: Mt.build_tree(P, chex)),
          ("XEC2_unif", lambda: Mt.build_tree(P, Mt.pol_ec2("u"))),
          ("XEC2_skew", lambda: Mt.build_tree(P, Mt.pol_ec2("s")))]
    for name, fn in xp:
        t = time.time()
        tree = fn()
        tt = time.time() - t
        met, _ = Mt.tree_metrics(P, tree)
        rows.append(dict(scen=scen, seed=seed, method=name, time=tt, **met,
                         gap_worst=met["worst_cost"] - v8x, gap_exp_u=met["exp_cost_u"] - vex))
    return inst_row, rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scen", default=",".join(SCEN))
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--tag", default="main")
    a = ap.parse_args()
    IR, MR = [], []
    for sc in a.scen.split(","):
        for s in range(a.seeds):
            t = time.time()
            ir, mr = run_instance(sc, s, SCEN[sc])
            IR.append(ir); MR.extend(mr)
            print(f"{sc} seed={s} atoms={ir['n_atoms']} T={ir['T']} opt8={ir['opt_adaptive_worst']} "
                  f"batch={ir['opt_batch_brute']} milp={ir['hs_milp']} cont9b={ir['cont_adaptive_worst']} "
                  f"X8={ir['x_opt_adaptive_worst']} X7={ir['x_opt_batch_brute']} 9a={ir['cont_batch']} axp={ir['axp_lb']} undet_g={ir['undet_frac_grid']:.2f} {time.time()-t:.1f}s", flush=True)
        pd.DataFrame(IR).to_csv(f"{OUT}/results_instances_{a.tag}.csv", index=False)
        pd.DataFrame(MR).to_csv(f"{OUT}/results_methods_{a.tag}.csv", index=False)
    print("DONE")
