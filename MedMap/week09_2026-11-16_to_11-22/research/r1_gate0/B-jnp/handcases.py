"""손계산 소형 사례 대조 (SYNTHETIC). 기대값은 handcases_expected.json (코드 실행 전에 작성)."""
import json
import os
import exact_enum, ror_combo, milp_solver, jnp_candidate, naive_baselines

D = os.path.dirname(os.path.abspath(__file__))
inst_all = json.load(open(os.path.join(D, 'handcases_instances.json')))
exp_all = json.load(open(os.path.join(D, 'handcases_expected.json')))
methods = {
    'exact_enum': exact_enum.solve, 'milp': milp_solver.solve, 'jnp_candidate': jnp_candidate.solve,
    'ror_lp_combo': lambda x: ror_combo.solve(x, 'lp'), 'ror_pw_combo': lambda x: ror_combo.solve(x, 'pw'),
    'closed_world': naive_baselines.closed_world, 'ignore_unknown': naive_baselines.ignore_unknown,
    'penalty_P0.3': lambda x: naive_baselines.penalty(x, 0.3), 'penalty_P1': lambda x: naive_baselines.penalty(x, 1.0),
    'penalty_P10': lambda x: naive_baselines.penalty(x, 10.0), 'vertex_only': naive_baselines.vertex_only,
}
n_ok = n_tot = 0
for hc, inst in inst_all.items():
    exp = exp_all[hc]
    print(f"== {hc}")
    for mname, f in methods.items():
        r = f(inst)
        cells = []
        for o in range(inst['n']):
            key = f"O{o+1}"
            fl = r['flags'][o]; c = r['cat'][o]
            match = (fl == exp[key]['flags'] and c == exp[key]['cat'])
            cells.append(f"{key}:{fl}/{c}{'' if match else ' <-MISMATCH'}")
            if mname in ('exact_enum', 'milp', 'jnp_candidate'):
                n_tot += 1; n_ok += match
        print(f"  {mname:15s} " + " | ".join(cells))
print(f"\nexact_enum+milp+jnp_candidate vs hand-computed expectations: {n_ok}/{n_tot} option-results match")
