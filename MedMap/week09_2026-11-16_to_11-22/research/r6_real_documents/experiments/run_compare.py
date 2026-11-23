"""Module (Baseline A) vs joint (Baseline B) comparison on REAL document conditions x SYNTHETIC patient windows.
Follows shared-variables/PROTOCOL_FROZEN_v1.md sections 3-4. Patient windows are synthetic; label/trial conditions are real
(curated openFDA reference labels + manually verified ClinicalTrials.gov eligibility). Computational correctness only.
Usage: python -I run_compare.py
"""
import csv, json, os, time, tracemalloc, collections, itertools

ROOT = os.path.expanduser('~/medmap-real-evidence-pilot')
OUTD = os.path.join(ROOT, 'results')
os.makedirs(OUTD, exist_ok=True)
INF = float('inf')
GRID = {'eGFR': ([c for c in range(10, 91)], 5.0, 0.01),
        'potassium': ([round(3.5 + 0.05 * i, 2) for i in range(51)], 0.2, 0.001),
        'LVEF': ([c for c in range(10, 71)], 5.0, 0.01)}
ALLOWED = {'ALLOWED', 'ALLOWED_DOSE_ADJ', 'ALLOWED_DOSE_LIMIT', 'ALLOWED_MONITOR'}
DISALLOW = {'CONTRAINDICATED', 'INIT_NOT_RECOMMENDED', 'NOT_RECOMMENDED', 'DO_NOT_INITIATE'}
# boundary overrides for '>' rules (protocol section 3)
OVR = {'FINE-K1': (5.0, False, INF, False), 'FINE-K2': (4.8, False, 5.0, True), 'FINE-K3': (-INF, True, 4.8, True),
       'EPLE-K': (5.5, False, INF, False)}


def fnum(s):
    return INF if s in ('inf', '999', '99') else (-INF if s == '-inf' else float(s))


def load_rules():
    R = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'shared-variables', 'CURATED_LABEL_RULES.csv'))):
        if r['lower_incl'] in ('UNKNOWN', 'NONE_NUMERIC'):
            continue
        lo, li, hi, hinc = fnum(r['lower_incl']), True, fnum(r['upper_excl']), False
        if r['rule_id'] in OVR:
            lo, li, hi, hinc = OVR[r['rule_id']]
        R[r['rule_id']] = dict(r, lo=lo, lo_inc=li, hi=hi, hi_inc=hinc)
    return R


def inside(x, lo, li, hi, hinc):
    a = x > lo or (li and x == lo)
    b = x < hi or (hinc and x == hi)
    return a and b


def label_status(x, rules):
    st = {r['label_status'] for r in rules if inside(x, r['lo'], r['lo_inc'], r['hi'], r['hi_inc'])}
    if not st:
        return 'UNKNOWN'
    return '|'.join(sorted(st))


def ev_status(x, iv):
    return 'IN' if inside(x, *iv) else 'OUT'


def kind(s):
    if s == 'UNKNOWN' or 'UNKNOWN' in s:
        return 'U'
    parts = s.split('|')
    if all(p in ALLOWED for p in parts):
        return 'A'
    if all(p in DISALLOW for p in parts):
        return 'D'
    return 'U'


def category(S):
    ks = {(kind(l), e) for l, e in S}
    if any(k == 'U' for k, _ in ks):
        return 'LABEL_UNKNOWN'
    if ks == {('A', 'IN')}:
        return 'OK_IN'
    if ks == {('A', 'OUT')}:
        return 'OK_OUT_EVIDENCE_GAP'
    if all(k == 'D' for k, _ in ks):
        return 'NOT_INITIATE'
    return 'HOLD'


def points(lo, hi, bounds):
    """Exact evaluation points: window ends, every boundary inside, midpoints between consecutive points."""
    b = sorted({lo, hi} | {x for x in bounds if lo < x < hi})
    pts = list(b)
    pts += [(b[i] + b[i + 1]) / 2 for i in range(len(b) - 1)]
    return pts


def joint_set(lo, hi, rules, iv):
    bounds = [r['lo'] for r in rules] + [r['hi'] for r in rules] + [iv[0], iv[2]]
    bounds = [x for x in bounds if abs(x) != INF]
    return {(label_status(x, rules), ev_status(x, iv)) for x in points(lo, hi, bounds)}


def modular_set(lo, hi, rules, iv):
    bounds_l = [x for r in rules for x in (r['lo'], r['hi']) if abs(x) != INF]
    bounds_e = [x for x in (iv[0], iv[2]) if abs(x) != INF]
    SL = {label_status(x, rules) for x in points(lo, hi, bounds_l)}  # label module alone (exact)
    SE = {ev_status(x, iv) for x in points(lo, hi, bounds_e)}        # evidence module alone (exact)
    return set(itertools.product(SL, SE))


def dense_set(lo, hi, rules, iv, step):
    n = int(round((hi - lo) / step))
    return {(label_status(lo + i * step, rules), ev_status(lo + i * step, iv)) for i in range(n + 1)}


def spurious_types(diff):
    t = collections.Counter()
    for l, e in diff:
        k = kind(l)
        if k == 'A' and e == 'OUT':
            t['SPURIOUS_ALLOWED_OUT'] += 1
        elif k == 'D' and e == 'IN':
            t['SPURIOUS_DISALLOWED_IN'] += 1
        else:
            t['SPURIOUS_OTHER'] += 1
    return t


def main():
    t0 = time.time(); tracemalloc.start()
    R = load_rules()
    pairs = [r for r in csv.DictReader(open(os.path.join(ROOT, 'shared-variables/out/pair_levels.csv'))) if r['L3'] == '1']
    win_rows, pair_rows = [], []
    dense_mismatch = 0; dense_checked = 0
    for p in pairs:
        v = p['variable']; centers, h, step = GRID[v]
        rules = [R[i] for i in p['label_rule_ids'].split('|') if i in R]
        iv = (fnum(p['trial_lo']), p['trial_lo_inc'] == 'True', fnum(p['trial_hi']), p['trial_hi_inc'] == 'True')
        n_diff = n_cat = n_wrong = n_unnec = 0; spur = collections.Counter()
        for c in centers:
            lo, hi = c - h, c + h
            J = joint_set(lo, hi, rules, iv); M = modular_set(lo, hi, rules, iv)
            Dn = dense_set(lo, hi, rules, iv, step); dense_checked += 1
            if not Dn <= J:
                dense_mismatch += 1
            assert J <= M, (p, c)
            cj, cm = category(J), category(M)
            diff = M - J; st = spurious_types(diff)
            wrong = cm in ('OK_IN', 'OK_OUT_EVIDENCE_GAP', 'NOT_INITIATE') and cm != cj
            unnec = cj != 'HOLD' and cm == 'HOLD'
            if diff: n_diff += 1
            if cj != cm: n_cat += 1
            n_wrong += wrong; n_unnec += unnec; spur.update(st)
            win_rows.append(dict(nct_id=p['nct_id'], drug=p['drug'], variable=v, center=c, half_width=h,
                                 joint=sorted(J), modular=sorted(M), cat_joint=cj, cat_modular=cm,
                                 n_spurious=len(diff), **{k: st.get(k, 0) for k in ('SPURIOUS_ALLOWED_OUT', 'SPURIOUS_DISALLOWED_IN', 'SPURIOUS_OTHER')},
                                 wrong_confirm=int(wrong), unnecessary_hold=int(unnec)))
        relevant = spur['SPURIOUS_ALLOWED_OUT'] + spur['SPURIOUS_DISALLOWED_IN']
        pair_rows.append(dict(nct_id=p['nct_id'], drug=p['drug'], variable=v, rules=p['label_rule_ids'],
                              trial_interval=f"{'[' if iv[1] else '('}{iv[0]},{iv[2]}{']' if iv[3] else ')'}",
                              n_windows=len(centers), windows_diff=n_diff, windows_cat_change=n_cat,
                              wrong_confirm=n_wrong, unnecessary_hold=n_unnec,
                              spurious_allowed_out=spur['SPURIOUS_ALLOWED_OUT'], spurious_disallowed_in=spur['SPURIOUS_DISALLOWED_IN'],
                              spurious_other=spur['SPURIOUS_OTHER'], LEVEL4=int(relevant > 0)))
    # secondary: drug-drug sharing eGFR within the same trial (B7-type, label x label)
    sec = []
    byt = collections.defaultdict(list)
    for p in pairs:
        if p['variable'] == 'eGFR':
            byt[p['nct_id']].append(p)
    centers, h, _ = GRID['eGFR']
    for nct, ps in byt.items():
        for a, b in itertools.combinations(ps, 2):
            ra = [R[i] for i in a['label_rule_ids'].split('|') if i in R]; rb = [R[i] for i in b['label_rule_ids'].split('|') if i in R]
            nd = 0; nsp = 0; ncat = 0
            for c in centers:
                lo, hi = c - h, c + h
                bounds = [x for r in ra + rb for x in (r['lo'], r['hi']) if abs(x) != INF]
                J = {(label_status(x, ra), label_status(x, rb)) for x in points(lo, hi, bounds)}
                SA = {label_status(x, ra) for x in points(lo, hi, bounds)}; SB = {label_status(x, rb) for x in points(lo, hi, bounds)}
                M = set(itertools.product(SA, SB))
                if M != J: nd += 1; nsp += len(M - J)
            sec.append(dict(nct_id=nct, drug_a=a['drug'], drug_b=b['drug'], rules_a=a['label_rule_ids'], rules_b=b['label_rule_ids'],
                            n_windows=len(centers), windows_diff=nd, spurious_combos_total=nsp))
    # tertiary: same label, use rule vs label-stated trial enrollment range
    ter = []
    allr = list(csv.DictReader(open(os.path.join(ROOT, 'shared-variables', 'CURATED_LABEL_RULES.csv'))))
    for drug in sorted({r['drug'] for r in allr}):
        E = [r for r in allr if r['drug'] == drug and r['indication_scope'] == 'LABEL_EVIDENCE_STATEMENT']
        if not E: continue
        e = E[0]; iv = (fnum(e['lower_incl']), True, fnum(e['upper_excl']), False)
        for scope in sorted({r['indication_scope'] for r in allr if r['drug'] == drug and r['indication_scope'] != 'LABEL_EVIDENCE_STATEMENT'}):
            rules = [R[r['rule_id']] for r in allr if r['drug'] == drug and r['indication_scope'] == scope and r['rule_id'] in R]
            if not rules:
                ter.append(dict(drug=drug, scope=scope, evidence_rule=e['rule_id'], note='label use rule UNKNOWN for this scope; not computed')); continue
            nd = 0; spur = collections.Counter(); cats = collections.Counter()
            for c in centers:
                lo, hi = c - h, c + h
                J = joint_set(lo, hi, rules, iv); M = modular_set(lo, hi, rules, iv)
                if M != J: nd += 1; spur.update(spurious_types(M - J))
                cats[category(J)] += 1
            ter.append(dict(drug=drug, scope=scope, evidence_rule=e['rule_id'], windows_diff=nd,
                            spurious_allowed_out=spur['SPURIOUS_ALLOWED_OUT'], spurious_disallowed_in=spur['SPURIOUS_DISALLOWED_IN'],
                            joint_categories=dict(cats), note=''))
    cur, peak = tracemalloc.get_traced_memory(); el = time.time() - t0
    def dump(name, rows):
        if not rows: return
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(os.path.join(OUTD, name), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    dump('windows.csv', win_rows); dump('pairs_level4.csv', pair_rows); dump('secondary_drug_drug.csv', sec); dump('tertiary_label_internal.csv', ter)
    summ = dict(n_level3_pair_variables=len(pairs), n_windows=len(win_rows), dense_checked=dense_checked, dense_mismatch=dense_mismatch,
                level4_pairs=sum(r['LEVEL4'] for r in pair_rows),
                windows_diff=sum(r['windows_diff'] for r in pair_rows), windows_cat_change=sum(r['windows_cat_change'] for r in pair_rows),
                wrong_confirm=sum(r['wrong_confirm'] for r in pair_rows), unnecessary_hold=sum(r['unnecessary_hold'] for r in pair_rows),
                spurious_allowed_out=sum(r['spurious_allowed_out'] for r in pair_rows), spurious_disallowed_in=sum(r['spurious_disallowed_in'] for r in pair_rows),
                secondary_pairs=len(sec), secondary_pairs_with_diff=sum(1 for r in sec if r['windows_diff'] > 0),
                elapsed_s=round(el, 2), peak_mem_bytes=peak)
    json.dump(summ, open(os.path.join(OUTD, 'summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
