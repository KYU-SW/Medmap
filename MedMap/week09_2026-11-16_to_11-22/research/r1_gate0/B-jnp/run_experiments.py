"""실험 실행기 (SYNTHETIC). 모든 방법: 같은 언어(Python 3, CPython), 같은 장비, 단일 스레드 환경변수.

사용:
  python run_experiments.py --sweep nU --n_inst 8 --out results_main_nU.csv
  python run_experiments.py --sweep scale --n_inst 3 --out results_scaling.csv --mem
"""
import argparse
import csv
import json
import os
import time
import tracemalloc
import traceback

import gen_instances
import exact_enum, milp_solver, jnp_candidate, ror_combo, naive_baselines

D = os.path.dirname(os.path.abspath(__file__))
BASE = dict(k=10, nU=6, n=6, m=4, n_rules=6, dep_density=0.3, conflict_rate=0.1, n_wcons=2, n_mods=3,
            missing_rate=0.0)
SWEEPS = {
    'nU': ('nU', [0, 2, 4, 6, 8, 10, 12]),
    'm': ('m', [2, 3, 4, 5]),
    'wcons': ('n_wcons', [0, 1, 2, 3, 4]),
    'n': ('n', [3, 6, 9, 12]),
    'rules': ('n_rules', [0, 3, 6, 9, 12]),
    'deps': ('dep_density', [0.0, 0.3, 0.6, 1.0]),
    'conflict': ('conflict_rate', [0.0, 0.25, 0.5, 1.0]),
    'missing': ('missing_rate', [0.0, 0.1]),
    'scale': ('nU', [4, 8, 12, 14, 16, 18, 20]),
    'stress': ('nU', [8, 12, 14, 16, 18, 20]),  # rules=nU, mods=nU//2 (관련 변수 수도 함께 증가)
}
METHODS_MAIN = {
    'exact_enum': exact_enum.solve,
    'milp': milp_solver.solve,
    'jnp_candidate': jnp_candidate.solve,
    'ror_lp_combo': lambda x: ror_combo.solve(x, 'lp'),
    'ror_pw_combo': lambda x: ror_combo.solve(x, 'pw'),
    'closed_world': naive_baselines.closed_world,
    'ignore_unknown': naive_baselines.ignore_unknown,
    'penalty_P1': lambda x: naive_baselines.penalty(x, 1.0),
    'penalty_P10': lambda x: naive_baselines.penalty(x, 10.0),
    'vertex_only': naive_baselines.vertex_only,
}
METHODS_SCALE = ['exact_enum', 'ror_lp_combo', 'milp', 'jnp_candidate']
SCALE_LIMIT = {'exact_enum': 14, 'ror_lp_combo': 14}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sweep', required=True)
    ap.add_argument('--n_inst', type=int, default=8)
    ap.add_argument('--out', required=True)
    ap.add_argument('--mem', action='store_true')
    args = ap.parse_args()
    param, values = SWEEPS[args.sweep]
    methods = METHODS_MAIN if args.sweep not in ('scale', 'stress') else {k: METHODS_MAIN[k] for k in METHODS_SCALE}
    out_opt = os.path.join(D, args.out)
    out_time = out_opt.replace('.csv', '_time.csv')
    fo = open(out_opt, 'w', newline=''); wo = csv.writer(fo)
    ft = open(out_time, 'w', newline=''); wt = csv.writer(ft)
    wo.writerow(['sweep', 'param', 'value', 'seed', 'method', 'option', 'AA', 'EE', 'AE', 'EA', 'EwAs', 'cat'])
    wt.writerow(['sweep', 'param', 'value', 'seed', 'method', 'time_s', 'peak_mem_mb', 'n_worlds',
                 'n_signatures', 'n_lp', 'milp_iters', 'error'])
    sweep_idx = list(SWEEPS).index(args.sweep)
    for vi, v in enumerate(values):
        for r in range(args.n_inst):
            seed = 100000 * (sweep_idx + 1) + 1000 * vi + r
            cfg = dict(BASE); cfg[param] = v
            if param == 'nU':
                cfg['k'] = max(10, v + 2)
            if args.sweep == 'stress':
                cfg['n_rules'] = v; cfg['n_mods'] = v // 2
            if param == 'm':
                cfg['n_wcons'] = min(cfg['n_wcons'], 2 * v - 2)
            inst = gen_instances.gen(seed, **cfg)
            truth = None
            for mname, f in methods.items():
                if args.sweep in ('scale', 'stress') and v > SCALE_LIMIT.get(mname, 99):
                    continue
                err = ''
                try:
                    t0 = time.perf_counter()
                    res = f(inst)
                    dt = time.perf_counter() - t0
                    peak = ''
                    if args.mem:
                        tracemalloc.start()
                        f(inst)
                        peak = tracemalloc.get_traced_memory()[1] / 1e6
                        tracemalloc.stop()
                except Exception as ex:  # record, never hide
                    err = repr(ex)[:200]
                    print(f"ERROR {args.sweep} {v} {seed} {mname}: {err}", flush=True)
                    traceback.print_exc()
                    wt.writerow([args.sweep, param, v, seed, mname, '', '', '', '', '', '', err])
                    continue
                st = res.get('stats', {})
                wt.writerow([args.sweep, param, v, seed, mname, f"{dt:.6f}", peak if peak == '' else f"{peak:.3f}",
                             res.get('n_worlds', ''), st.get('n_signatures', ''), st.get('n_lp', ''),
                             res.get('iters', ''), err])
                for o in range(inst['n']):
                    fl = res['flags'][o]
                    wo.writerow([args.sweep, param, v, seed, mname, o] + ['' if x is None else x for x in fl]
                                + [res['cat'][o]])
                if mname == 'exact_enum':
                    truth = res
                elif truth is not None and mname in ('milp', 'jnp_candidate'):
                    bad = [o for o in range(inst['n'])
                           if res['cat'][o] != truth['cat'][o] or any(
                               a is not None and a != b for a, b in zip(truth['flags'][o], res['flags'][o]))]
                    if bad:
                        fn = os.path.join(D, 'instances', f"disagree_{mname}_{args.sweep}_{seed}.json")
                        json.dump(dict(inst=inst, truth=truth['flags'], got=res['flags'], options=bad),
                                  open(fn, 'w'), default=str)
                        print(f"DISAGREE {mname} seed={seed} options={bad}", flush=True)
            fo.flush(); ft.flush()
        print(f"done {args.sweep} {param}={v}", flush=True)
    print("MILP status4 retries:", milp_solver.STATS['status4_retries'])
    fo.close(); ft.close()


if __name__ == '__main__':
    main()
