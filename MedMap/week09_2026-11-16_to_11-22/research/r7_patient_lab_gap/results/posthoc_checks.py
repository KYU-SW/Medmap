"""POST-HOC (outside frozen protocol): (1) recompute key summary numbers from CSVs; (2) recorded-MDRD sensitivity; (3) exclude age-uncertain patients."""
import pandas as pd, json, os
R = os.path.expanduser('~/medmap-patient-lab-gap-pilot/')
S = json.load(open(R + 'results/summary.json'))
C = pd.read_csv(R + 'comparison/comparison_rows.csv'); c = C[C.computable == 1]
EP = pd.read_csv(R + 'timeline/evaluation_points.csv')
chk = dict(pair_evals=len(c) == S['comparison']['pair_evaluations'], with_spurious=int((c.n_spurious > 0).sum()) == S['comparison']['with_spurious'],
           spurious_allowed_out=int(c.spurious_allowed_out.sum()) == S['comparison']['spurious_allowed_out'], cat_change=int(c.cat_change.sum()) == S['comparison']['cat_change'],
           realized_outside_J=int((c.realized_in_J == 0).sum()) == S['comparison']['realized_outside_J'],
           eGFR_status_changed=int(EP[(EP['var'] == 'eGFR')].status_changed_vs_realized.fillna(False).astype(bool).sum()) == S['L1_evaluation_points']['eGFR']['status_changed_vs_realized'])
md = pd.read_csv(R + 'labs/egfr_mdrd_recorded_parsed.csv')
mv = md[md.mdrd_kind == 'value']
T = [20, 25, 30, 45, 50, 60]
near = mv.mdrd.apply(lambda x: any(abs(x - t) <= 5 for t in T))
mdrd = dict(rows=len(md), numeric=len(mv), censored_gt75=int((md.mdrd_kind == 'censored_gt').sum()), unparsed=int((md.mdrd_kind == 'unparsed').sum()),
            numeric_patients=int(mv.subject_id.nunique()), near_abs_obs=int(near.sum()), near_abs_patients=int(mv[near].subject_id.nunique()))
E = pd.read_csv(R + 'labs/egfr_ckdepi2021_derived.csv'); au = set(E[E.age_uncertain].subject_id)
c2 = c[~c.subject_id.isin(au)]
age = dict(age_uncertain_patients=len(au), pair_evals_excl=len(c2), with_spurious_excl=int((c2.n_spurious > 0).sum()), cat_change_excl=int(c2.cat_change.sum()),
           eval_points_eGFR_excl=int(EP[(EP['var'] == 'eGFR') & ~EP.subject_id.isin(au)].shape[0]))
# check-item difference: for single-variable windows, the variable to re-check is the same under both methods by construction
out = dict(recompute_matches=chk, POSTHOC_recorded_MDRD=mdrd, POSTHOC_exclude_age_uncertain=age)
json.dump(out, open(R + 'results/posthoc_checks.json', 'w'), indent=1, default=int); print(json.dumps(out, indent=1, default=int))
