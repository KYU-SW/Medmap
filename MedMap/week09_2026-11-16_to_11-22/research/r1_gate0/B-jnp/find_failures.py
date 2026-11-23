"""비정확 기준선의 실제 실패 사례 추출 (SYNTHETIC). results_main_*.csv 를 읽고, 방법×실패유형별로
가장 작은 인스턴스 하나를 골라 인스턴스 내용과 정답/오답 플래그를 출력한다. 출력: results_failure_examples.csv"""
import os
import pandas as pd
import gen_instances
import run_experiments as R
from make_tables import load, compare

D = os.path.dirname(os.path.abspath(__file__))
m = compare(load('results_main_*.csv'))
m['ftype'] = ''
m.loc[m.wrong_confirm, 'ftype'] = 'wrong_confirm'
m.loc[m.unneeded_hold, 'ftype'] = 'unneeded_hold'
m.loc[(m.ftype == '') & m.false_EwAs, 'ftype'] = 'false_EwAs'
m.loc[(m.ftype == '') & ~m.cat_ok, 'ftype'] = 'other_cat_error'
f = m[m.ftype != ''].copy()
# breakdown by (method, truth cat -> method cat)
tr = f.groupby(['method', 'ftype', 't_cat', 'cat']).size().reset_index(name='count')
tr.to_csv(os.path.join(D, 'results_failure_breakdown.csv'), index=False)
print(tr.to_string(index=False))
rows = []
for (meth, ft), g in f.groupby(['method', 'ftype']):
    r = g.sort_values(['value', 'seed']).iloc[0] if g.iloc[0].param != 'nU' else g.sort_values(['value', 'seed']).iloc[0]
    sweep, v, seed = r.sweep, r.value, int(r.seed)
    param = R.SWEEPS[sweep][0]
    cfg = dict(R.BASE); cfg[param] = type(R.SWEEPS[sweep][1][0])(v) if param != 'dep_density' else float(v)
    if param in ('nU', 'n', 'm', 'n_rules', 'n_wcons'):
        cfg[param] = int(v)
    if param == 'nU':
        cfg['k'] = max(10, int(v) + 2)
    if param == 'm':
        cfg['n_wcons'] = min(cfg['n_wcons'], 2 * int(v) - 2)
    inst = gen_instances.gen(seed, **cfg)
    rows.append(dict(method=meth, ftype=ft, sweep=sweep, value=v, seed=seed, option=int(r.option),
                     truth_flags=[int(r['t_' + c]) if pd.notna(r['t_' + c]) else None for c in ['AA', 'EE', 'AE', 'EA', 'EwAs']],
                     truth_cat=r.t_cat, got_flags=[int(r[c]) for c in ['AA', 'EE', 'AE', 'EA', 'EwAs']], got_cat=r['cat'],
                     obs=''.join(inst['obs']), deps=inst['deps'],
                     rules_of_option=[x[1] for x in inst['rules'] if x[0] == int(r.option)],
                     all_rules=inst['rules']))
ex = pd.DataFrame(rows)
ex.to_csv(os.path.join(D, 'results_failure_examples.csv'), index=False)
print(ex[['method', 'ftype', 'sweep', 'value', 'seed', 'option', 'truth_cat', 'got_cat', 'truth_flags', 'got_flags', 'obs']].to_string(index=False))
