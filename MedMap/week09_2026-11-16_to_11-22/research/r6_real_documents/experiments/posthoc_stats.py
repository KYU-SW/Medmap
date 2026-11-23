"""POST-HOC (not in frozen protocol): proportions with Wilson CI from result CSVs, and window half-width sensitivity (h=2,10)."""
import csv, json, math, os, sys, importlib.util
ROOT = os.path.expanduser('~/medmap-real-evidence-pilot')
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); s = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (round((c - s)/d, 4), round((c + s)/d, 4))
PL = list(csv.DictReader(open(f'{ROOT}/shared-variables/out/pair_levels.csv')))
L4 = list(csv.DictReader(open(f'{ROOT}/results/pairs_level4.csv')))
npairs = len({(r['nct_id'], r['drug']) for r in PL}); npv = len(PL)
out = {'n_drug_trial_pairs': npairs, 'n_pair_variable': npv}
for v in ['eGFR', 'potassium', 'LVEF']:
    rv = [r for r in PL if r['variable'] == v]
    for L in ['L1', 'L2', 'L3']:
        k = sum(int(r[L]) for r in rv); out[f'{v}_{L}'] = [k, len(rv), wilson(k, len(rv))]
    k4 = sum(int(r['LEVEL4']) for r in L4 if r['variable'] == v); out[f'{v}_L4'] = [k4, len(rv), wilson(k4, len(rv))]
pairs_any = {(r['nct_id'], r['drug']) for r in L4 if r['LEVEL4'] == '1'}
pairs_l1 = {(r['nct_id'], r['drug']) for r in PL if r['L1'] == '1'}
out['pairs_any_L1'] = [len(pairs_l1), npairs, wilson(len(pairs_l1), npairs)]
out['pairs_any_L4'] = [len(pairs_any), npairs, wilson(len(pairs_any), npairs)]
k3 = sum(1 for r in L4); out['L4_given_L3_pairvar'] = [sum(int(r['LEVEL4']) for r in L4), k3, wilson(sum(int(r['LEVEL4']) for r in L4), k3)]
trials = {r['nct_id'] for r in PL}; tr4 = {t for t, _ in pairs_any}
out['trials_with_drug_pair'] = len(trials); out['trials_any_L4'] = [len(tr4), len(trials), wilson(len(tr4), len(trials))]
# sensitivity on half-width
spec = importlib.util.spec_from_file_location('rc', f'{ROOT}/experiments/run_compare.py'); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
R = rc.load_rules(); P3 = [r for r in PL if r['L3'] == '1']; sens = {}
for v, hs in [('eGFR', [2, 5, 10]), ('potassium', [0.1, 0.2, 0.4])]:
    for h in hs:
        cnt = 0
        for p in [x for x in P3 if x['variable'] == v]:
            rules = [R[i] for i in p['label_rule_ids'].split('|') if i in R]
            iv = (rc.fnum(p['trial_lo']), p['trial_lo_inc'] == 'True', rc.fnum(p['trial_hi']), p['trial_hi_inc'] == 'True')
            hit = False
            for c in rc.GRID[v][0]:
                J = rc.joint_set(c - h, c + h, rules, iv); M = rc.modular_set(c - h, c + h, rules, iv)
                st = rc.spurious_types(M - J)
                if st['SPURIOUS_ALLOWED_OUT'] + st['SPURIOUS_DISALLOWED_IN'] > 0: hit = True; break
            cnt += hit
        sens[f'{v}_h{h}'] = [cnt, len([x for x in P3 if x['variable'] == v])]
out['POSTHOC_sensitivity_L4_by_halfwidth'] = sens
json.dump(out, open(f'{ROOT}/results/posthoc_stats.json', 'w'), indent=1); print(json.dumps(out, indent=1))
