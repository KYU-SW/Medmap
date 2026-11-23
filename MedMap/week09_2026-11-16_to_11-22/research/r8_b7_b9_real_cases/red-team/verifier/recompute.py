#!/usr/bin/env python3
"""독립 재계산(검증자 작성). 메인 코드(baselines/, experiments/*.py)를 import 하지 않는다.
입력(읽기 전용): experiments/results/run2/{item_results.csv, summary.csv, question_results.csv, method_outputs.json},
                evaluation/REF_R_v1.json, experiments/inputs/cases_input_v1.json
출력: red-team/verifier/recompute.csv, red-team/verifier/recompute_mismatches.txt
"""
import csv, json, os, sys
from collections import defaultdict

ROOT = os.path.expanduser('~/medmap-original-b7-b9-clinical-validation')
R2 = os.path.join(ROOT, 'experiments/results/run2')
OUT = os.path.join(ROOT, 'red-team/verifier')

ref = json.load(open(os.path.join(ROOT, 'evaluation/REF_R_v1.json')))['cases']
inp = json.load(open(os.path.join(ROOT, 'experiments/inputs/cases_input_v1.json')))['cases']
mo = json.load(open(os.path.join(R2, 'method_outputs.json')))
items = list(csv.DictReader(open(os.path.join(R2, 'item_results.csv'), encoding='utf-8')))
summ = list(csv.DictReader(open(os.path.join(R2, 'summary.csv'), encoding='utf-8')))
qres = list(csv.DictReader(open(os.path.join(R2, 'question_results.csv'), encoding='utf-8')))

CONFIRM = {'APPLY', 'NOT_APPLY', 'SDM_CONFLICT'}
mism = []

def cls(r, o):
    if r in CONFIRM:
        if o == r: return 'CC'
        if o == 'HOLD': return 'UD'
        return 'WC'
    # r == HOLD
    return 'AD' if o == 'HOLD' else 'WC'

# 1) item 단위: item_results 의 ref/out 이 원천 JSON 과 같은지, class 재계산
rows = defaultdict(list)  # (method) -> list of dict
for it in items:
    m, c, i = it['method'], it['case_id'], it['item']
    r_lab, r_cause = ref[c]['items'][i]
    o = mo[m][c]['items'][i]
    if it['ref'] != r_lab or set(filter(None, it['ref_cause'].replace('+','|').split('|'))) != set(r_cause):
        mism.append(f'REF mismatch {m} {c} {i}: csv={it["ref"]},{it["ref_cause"]} json={r_lab},{r_cause}')
    if it['out'] != o['label']:
        mism.append(f'OUT mismatch {m} {c} {i}: csv={it["out"]} json={o["label"]}')
    if it['case_type'] != inp[c]['case_type']:
        mism.append(f'case_type mismatch {c}')
    k = cls(r_lab, o['label'])
    if k != it['class']:
        mism.append(f'CLASS mismatch {m} {c} {i}: csv={it["class"]} mine={k}')
    cm = (k == 'AD' and set(o.get('cause', [])) == set(r_cause))
    rows[m].append({'case': c, 'type': inp[c]['case_type'], 'cls': k, 'cm': cm, 'ref': r_lab})

# 전 항목 커버 확인
n_items_input = sum(len(v['items']) for v in inp.values())
for m in rows:
    if len(rows[m]) != n_items_input:
        mism.append(f'{m}: item rows {len(rows[m])} != input items {n_items_input}')

STRATA = ['ALL', 'REAL_WITH_PREF', 'REAL_NO_PREF', 'GUIDELINE_VIGNETTE']

def counts(m, s):
    rs = [x for x in rows[m] if s == 'ALL' or x['type'] == s]
    d = {k: sum(1 for x in rs if x['cls'] == k) for k in ('CC', 'WC', 'AD', 'UD')}
    d['N'] = len(rs)
    d['cm'] = sum(1 for x in rs if x['cm'])
    d['ref_hold'] = sum(1 for x in rs if x['ref'] == 'HOLD')
    return d

def U(d, lw, lu):
    return (d['CC'] + d['AD'] - lw * d['WC'] - lu * d['UD']) / d['N']

# 2) 질문 재현율·정밀도: method_outputs 의 questions 와 REF required/acceptable 로 직접
def qstats(m, s):
    nq = nr = hit = ina = 0
    for c in inp:
        if s != 'ALL' and inp[c]['case_type'] != s: continue
        Q = set(mo[m][c].get('questions', []))
        R = set(ref[c]['required_confirm']); A = set(ref[c]['acceptable_confirm'])
        nq += len(Q); nr += len(R); hit += len(Q & R); ina += len(Q & A)
    rec = hit / nr if nr else None
    prec = ina / nq if nq else None
    bur = nq / nr if nr else None
    return rec, prec, bur, nq, nr, hit, ina

# question_results.csv 행 단위 대조
for q in qres:
    m, c = q['method'], q['case_id']
    Q = set(mo[m][c].get('questions', []))
    R = set(ref[c]['required_confirm']); A = set(ref[c]['acceptable_confirm'])
    mine = (len(Q), len(R), len(Q & R), len(Q & A))
    theirs = (int(q['n_q']), int(q['n_R']), int(q['hit_R']), int(q['in_A']))
    if mine != theirs:
        mism.append(f'QROW mismatch {m} {c}: csv={theirs} mine={mine}')
    if set(filter(None, q['questions_ranked'].split('|'))) != Q:
        mism.append(f'QLIST mismatch {m} {c}')

def fmt(x, nd=4):
    return 'NA' if x is None else round(x, nd)

out = []
methods = ['B', 'A', 'C', 'D', 'ALL_HOLD', 'GUIDELINE_ONLY']
sidx = {(r['stratum'], r['lambda_W'], r['lambda_U'], r['method']): r for r in summ}
for lw, lu in [(5, 1), (2, 0.5), (2, 1), (2, 2), (5, 0.5), (5, 2), (10, 0.5), (10, 1), (10, 2)]:
    for s in STRATA:
        uref = max(U(counts('ALL_HOLD', s), lw, lu), U(counts('GUIDELINE_ONLY', s), lw, lu))
        for m in methods:
            d = counts(m, s)
            u = U(d, lw, lu)
            S = None if abs(1 - uref) < 1e-12 else (u - uref) / (1 - uref)
            rec, prec, bur, *_ = qstats(m, s)
            key = (s, str(lw), str(lu), m)
            sr = sidx.get(key)
            def eq(a, b, tol=6e-4):
                if b is None or b == '': return False
                if a is None: return b == 'NA'
                if b == 'NA': return False
                return abs(float(a) - float(b)) <= tol
            chk = {}
            if sr:
                for name, mine in [('CC', d['CC']), ('WC', d['WC']), ('AD', d['AD']), ('UD', d['UD']), ('n_items', d['N']),
                                   ('cause_match_in_AD', d['cm']), ('U', u), ('U_ref', uref), ('S', S),
                                   ('q_recall', rec), ('q_precision', prec), ('q_burden_ratio', bur),
                                   ('ref_hold_share', d['ref_hold'] / d['N']), ('wrong_confirm_rate', d['WC'] / d['N'])]:
                    chk[name] = eq(mine, sr[name])
                    if not chk[name]:
                        mism.append(f'SUMMARY mismatch {key} {name}: csv={sr[name]} mine={mine}')
            else:
                mism.append(f'SUMMARY row missing {key}')
            out.append({'stratum': s, 'lambda_W': lw, 'lambda_U': lu, 'method': m, 'N': d['N'],
                        'CC': d['CC'], 'WC': d['WC'], 'AD': d['AD'], 'UD': d['UD'], 'cause_match_in_AD': d['cm'],
                        'U': fmt(u), 'U_ref': fmt(uref), 'S': fmt(S),
                        'q_recall': fmt(rec), 'q_precision': fmt(prec), 'q_burden_ratio': fmt(bur),
                        'summary_U': sr['U'] if sr else '', 'summary_S': sr['S'] if sr else '',
                        'all_fields_match': all(chk.values()) if chk else False})

with open(os.path.join(OUT, 'recompute.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
with open(os.path.join(OUT, 'recompute_mismatches.txt'), 'w', encoding='utf-8') as f:
    f.write(f'mismatches: {len(mism)}\n' + '\n'.join(mism) + '\n')
print('rows', len(out), 'mismatches', len(mism))
for x in mism[:40]: print(x)
