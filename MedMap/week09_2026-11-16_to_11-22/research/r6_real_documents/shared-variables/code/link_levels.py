"""Link drug-trial pairs and assign LEVEL 1-3 per variable, following PROTOCOL_FROZEN_v1.md.
LEVEL 4 is assigned later by experiments/run_compare.py. Read-only inputs; writes shared-variables/out/.
Usage: python -I link_levels.py [--resolutions RES.csv]
"""
import csv, json, os, re, sys, collections

ROOT = os.path.expanduser('~/medmap-real-evidence-pilot')
OUT = os.path.join(ROOT, 'shared-variables', 'out')
os.makedirs(OUT, exist_ok=True)
VARS = ['eGFR', 'potassium', 'LVEF']
DRUGMAP = {'lcz696': 'sacubitril/valsartan', 'sacubitril': 'sacubitril/valsartan', 'entresto': 'sacubitril/valsartan'}
HF_PAT = re.compile(r'heart failure|cardiac failure|HFrEF|HFpEF|\bHF\b', re.I)
CKD_PAT = re.compile(r'kidney|renal|nephropath|CKD|albuminuria', re.I)


def load_rules():
    rules = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(ROOT, 'shared-variables', 'CURATED_LABEL_RULES.csv'))):
        for d in r['drug'].split(';'):
            for v in r['clinical_variable'].split(';'):
                rr = dict(r); rr['drug'] = d; rr['clinical_variable'] = v
                rules[d].append(rr)
    return rules


def norm_drug(tok):
    cls, _, name = tok.partition(':')
    name = name.strip().lower()
    return DRUGMAP.get(name, name)


def num(x):
    try:
        return float(x)
    except Exception:
        return None


def trial_rows_level2(rows, v):
    """Return (usable_rows, status) per protocol section 2."""
    use = []
    for x in rows:
        thr = x['threshold']; unit = x['unit'] or ''
        if x['operator'] in ('UNKNOWN', '') or thr in ('UNKNOWN', ''):
            continue
        if x['operator'] == 'BETWEEN':
            a, _, b = thr.partition('-'); vals = [num(a), num(b)]
            if None in vals: continue
        else:
            vals = [num(thr)]
            if vals[0] is None: continue
        if v == 'eGFR':
            if any(val < 10 for val in vals): continue
            if '1.73' in unit:
                use.append(x)
            elif unit == 'UNKNOWN':
                use.append(dict(x, _unknown_unit=True))
        elif v == 'potassium':
            if unit.lower().replace(' ', '') in ('mmol/l', 'meq/l'):
                use.append(x)
        elif v == 'LVEF':
            if unit == '%':
                use.append(x)
    # unknown-unit eGFR rows only if same threshold appears with 1.73 in this trial
    if v == 'eGFR':
        explicit = {x['threshold'] for x in use if not x.get('_unknown_unit')}
        use = [x for x in use if not x.get('_unknown_unit') or x['threshold'] in explicit]
    return use


def interval_from_rows(use):
    """Eligibility interval [lo, hi] (lo inclusive flag, hi inclusive flag). Returns (lo, lo_inc, hi, hi_inc, ambiguous)."""
    lows, highs = [], []
    for x in use:
        op, loc = x['operator'], x['condition_location']
        if op == 'BETWEEN':
            a, _, b = x['threshold'].partition('-')
            if loc == 'inclusion':
                lows.append((float(a), True)); highs.append((float(b), True))
            continue
        t = float(x['threshold'])
        if loc == 'inclusion':
            if op in ('>=',): lows.append((t, True))
            elif op == '>': lows.append((t, False))
            elif op == '<=': highs.append((t, True))
            elif op == '<': highs.append((t, False))
        elif loc == 'exclusion':
            if op == '<': lows.append((t, True))
            elif op == '<=': lows.append((t, False))
            elif op == '>': highs.append((t, True))
            elif op == '>=': highs.append((t, False))
    amb = len({l for l, _ in lows}) > 1 or len({h for h, _ in highs}) > 1
    lo = max(lows) if lows else (float('-inf'), True)
    hi = min(highs) if highs else (float('inf'), True)
    return lo[0], lo[1], hi[0], hi[1], amb


def scope_for(drug, rule_scope, conds):
    if rule_scope in ('ALL', 'T2DM_ANY'):
        return True
    if rule_scope == 'HF':
        return bool(HF_PAT.search(conds))
    if rule_scope == 'CKD_HF_OTHER':
        return bool(HF_PAT.search(conds) or CKD_PAT.search(conds))
    if rule_scope == 'T2DM_GLYCEMIC':
        return not (HF_PAT.search(conds) or CKD_PAT.search(conds))
    return False  # LABEL_EVIDENCE_STATEMENT etc.


def main():
    res_path = None
    if '--resolutions' in sys.argv:
        res_path = sys.argv[sys.argv.index('--resolutions') + 1]
    resolutions = {}
    if res_path:
        for r in csv.DictReader(open(res_path)):
            resolutions[(r['nct_id'], r['variable'])] = r
    rules = load_rules()
    trials = {x['nct_id']: x for x in csv.DictReader(open(os.path.join(ROOT, 'clinicaltrials/structured/trials.csv')))}
    conds = collections.defaultdict(list)
    for x in csv.DictReader(open(os.path.join(ROOT, 'clinicaltrials/structured/trial_conditions.csv'))):
        if x['source_type'] == 'TRIAL_ELIGIBILITY' and x['clinical_variable'] in VARS:
            conds[(x['source_document_id'], x['clinical_variable'])].append(x)
    pairs, excluded = [], collections.Counter()
    for nct, t in sorted(trials.items()):
        toks = [s for s in t['scope_drugs_in_interventions'].split(';') if s.strip()]
        seen = set()
        for tok in toks:
            if tok.strip() == 'NONE_MATCHED':
                excluded['NONE_MATCHED'] += 1; continue
            d = norm_drug(tok)
            if d not in rules:
                excluded['no_curated_label:' + d] += 1; continue
            if d in seen: continue
            seen.add(d); pairs.append((nct, d))
    rows, amb_list = [], []
    for nct, d in pairs:
        t = trials[nct]; ctext = t['conditions'] + ' ' + t.get('title', '')
        for v in VARS:
            trows = conds.get((nct, v), [])
            lrules = [r for r in rules[d] if r['clinical_variable'] == v]
            L1 = bool(trows) and bool(lrules)
            numeric_rules = [r for r in lrules if r['lower_incl'] not in ('UNKNOWN', 'NONE_NUMERIC') and r['indication_scope'] != 'LABEL_EVIDENCE_STATEMENT']
            use = trial_rows_level2(trows, v) if L1 else []
            lo = lo_inc = hi = hi_inc = None; amb = False; L2 = False; note = ''
            if L1 and use and numeric_rules:
                lo, lo_inc, hi, hi_inc, amb = interval_from_rows(use)
                key = (nct, v)
                if key in resolutions:  # manual resolution / correction from raw text (ambiguous or regex error)
                    rz = resolutions[key]
                    if rz['resolved'] == 'yes':
                        lo, lo_inc, hi, hi_inc = float(rz['lo']), rz['lo_inc'] == '1', float(rz['hi']), rz['hi_inc'] == '1'
                        amb = False; note = 'ambiguity resolved manually: ' + rz['note']
                    else:
                        note = 'ambiguity unresolved: ' + rz['note']
                if amb:
                    amb_list.append((nct, v, [(x['condition_location'], x['operator'], x['threshold'], x['unit'], x['matched_span']) for x in use]))
                L2 = not amb
            elif L1 and not numeric_rules:
                note = 'label rule has no numeric threshold (MONITOR_ONLY/UNKNOWN)'
            elif L1 and not use:
                note = 'trial rows not unit-compatible (e.g. mL/min without 1.73, unknown unit)'
            applicable = [r for r in numeric_rules if scope_for(d, r['indication_scope'], ctext)] if L2 else []
            L3 = L2 and bool(applicable)
            if L2 and not applicable:
                note = (note + '; ' if note else '') + 'indication scope not compatible with trial context'
            rows.append(dict(nct_id=nct, drug=d, variable=v, L1=int(L1), L2=int(L2), L3=int(L3),
                             trial_lo=lo, trial_lo_inc=lo_inc, trial_hi=hi, trial_hi_inc=hi_inc,
                             label_rule_ids='|'.join(r['rule_id'] for r in applicable),
                             n_trial_rows=len(trows), n_trial_rows_level2=len(use), note=note,
                             trial_conditions=t['conditions'][:150]))
    with open(os.path.join(OUT, 'pair_levels.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump({'n_pairs': len(pairs), 'excluded': excluded, 'n_pair_variable': len(rows),
               'ambiguous': [(a, b) for a, b, _ in amb_list]}, open(os.path.join(OUT, 'link_summary.json'), 'w'), indent=1)
    with open(os.path.join(OUT, 'ambiguous_for_review.txt'), 'w') as f:
        for a, b, c in amb_list:
            f.write(f'{a} {b} {c}\n')
    print('pairs', len(pairs), 'excluded', dict(excluded))
    for v in VARS:
        rv = [r for r in rows if r['variable'] == v]
        print(v, 'L1', sum(r['L1'] for r in rv), 'L2', sum(r['L2'] for r in rv), 'L3', sum(r['L3'] for r in rv), 'of', len(rv))
    print('ambiguous', len(amb_list))


if __name__ == '__main__':
    main()
