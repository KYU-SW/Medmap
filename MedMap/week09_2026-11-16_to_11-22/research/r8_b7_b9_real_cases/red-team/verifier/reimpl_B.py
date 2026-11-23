#!/usr/bin/env python3
"""방법 B 독립 재구현(검증자 작성, baselines/methods_v1.py 를 보지 않고 작성).
규칙: 미확인 변수(known=null) 전수 열거(constraints 만족 조합만) -> 항목 상태 집합
  상태: applies=False 또는 contra=True -> NOT_APPLY
        그 외: prefs 가 모두 요구값과 같으면 APPLY, 하나라도 다르면 SDM_CONFLICT
  상태 집합 크기 1 -> 확정, 아니면 HOLD + cause = 상태를 바꾸는 변수(다른 변수 고정, 이 변수만 바꿔 상태가 달라지는 조합이 존재)의 group 집합
  질문 = HOLD 항목들의 relevant 변수 중 group P/Q (K 는 물어서 닫히지 않으므로 제외)
출력: red-team/verifier/reimpl_B_output.json, reimpl_B_compare.csv
"""
import csv, itertools, json, os

ROOT = os.path.expanduser('~/medmap-original-b7-b9-clinical-validation')
OUT = os.path.join(ROOT, 'red-team/verifier')
inp = json.load(open(os.path.join(ROOT, 'experiments/inputs/cases_input_v1.json')))['cases']
mo = json.load(open(os.path.join(ROOT, 'experiments/results/run2/method_outputs.json')))['B']
ref = json.load(open(os.path.join(ROOT, 'evaluation/REF_R_v1.json')))['cases']


def state(item, v):
    if not eval(item['applies'], {}, {'v': v}) or eval(item['contra'], {}, {'v': v}):
        return 'NOT_APPLY'
    for var, want in item['prefs']:
        if v[var] != want:
            return 'SDM_CONFLICT'
    return 'APPLY'


res = {}
rows = []
for cid, case in inp.items():
    vars_ = case['vars']
    unknown = [k for k, x in vars_.items() if x['known'] is None]
    base = {k: x['known'] for k, x in vars_.items() if x['known'] is not None}
    cons = case.get('constraints', [])
    worlds = []
    for combo in itertools.product(*[vars_[k]['domain'] for k in unknown]):
        v = dict(base); v.update(zip(unknown, combo))
        if all(eval(c, {}, {'v': v}) for c in cons):
            worlds.append(v)
    wset = {tuple(w[k] for k in unknown) for w in worlds}
    out_items, qs = {}, set()
    for iid, it in case['items'].items():
        states = {state(it, w) for w in worlds}
        if len(states) == 1:
            out_items[iid] = {'label': states.pop(), 'cause': [], 'relevant': []}
            continue
        relevant = set()
        for w in worlds:
            s0 = state(it, w)
            for j, k in enumerate(unknown):
                for val in vars_[k]['domain']:
                    if val == w[k]: continue
                    w2 = dict(w); w2[k] = val
                    if tuple(w2[x] for x in unknown) not in wset: continue
                    if state(it, w2) != s0:
                        relevant.add(k)
        cause = sorted({vars_[k]['group'] for k in relevant})
        out_items[iid] = {'label': 'HOLD', 'cause': cause, 'relevant': sorted(relevant)}
        qs |= {k for k in relevant if vars_[k]['group'] in ('P', 'Q')}
    res[cid] = {'items': out_items, 'questions': sorted(qs)}
    for iid, o in out_items.items():
        b = mo[cid]['items'][iid]
        rows.append({'case_id': cid, 'item': iid,
                     'reimpl_label': o['label'], 'reimpl_cause': '+'.join(o['cause']), 'reimpl_relevant': '|'.join(o['relevant']),
                     'run2_B_label': b['label'], 'run2_B_cause': '+'.join(sorted(b.get('cause', []))),
                     'run2_B_relevant': '|'.join(sorted(b.get('relevant', []))),
                     'ref_label': ref[cid]['items'][iid][0], 'ref_cause': '+'.join(sorted(ref[cid]['items'][iid][1])),
                     'label_match': o['label'] == b['label'],
                     'cause_match': o['cause'] == sorted(b.get('cause', [])),
                     'relevant_match': o['relevant'] == sorted(b.get('relevant', []))})
    rows.append({'case_id': cid, 'item': '_QUESTIONS', 'reimpl_label': '', 'reimpl_cause': '',
                 'reimpl_relevant': '|'.join(sorted(qs)), 'run2_B_label': '', 'run2_B_cause': '',
                 'run2_B_relevant': '|'.join(sorted(mo[cid]['questions'])), 'ref_label': '', 'ref_cause': '',
                 'label_match': '', 'cause_match': '',
                 'relevant_match': sorted(qs) == sorted(mo[cid]['questions'])})

json.dump(res, open(os.path.join(OUT, 'reimpl_B_output.json'), 'w'), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, 'reimpl_B_compare.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
it_rows = [r for r in rows if r['item'] != '_QUESTIONS']
q_rows = [r for r in rows if r['item'] == '_QUESTIONS']
print('items', len(it_rows), 'label_match', sum(r['label_match'] for r in it_rows),
      'cause_match', sum(r['cause_match'] for r in it_rows), 'relevant_match', sum(r['relevant_match'] for r in it_rows),
      'question_set_match', sum(r['relevant_match'] for r in q_rows), '/', len(q_rows),
      'reimpl==REF label', sum(r['reimpl_label'] == r['ref_label'] for r in it_rows),
      'reimpl==REF cause(HOLD)', sum(r['reimpl_cause'] == r['ref_cause'] for r in it_rows if r['ref_label'] == 'HOLD'))
for r in rows:
    if r['label_match'] is False or r['cause_match'] is False or r['relevant_match'] is False:
        print('DIFF', r)
