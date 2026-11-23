#!/usr/bin/env python3
"""검증자 민감도 분석: REF-R 중 검증자가 '논쟁 가능'으로 표시한 항목을 대안 판독으로 바꿨을 때
run2 방법 출력(method_outputs.json, 변경 없음)의 점수가 어떻게 달라지는지. 대안 판독은 정답이 아니라 원문 근거상 가능한 해석의 예시.
출력: red-team/verifier/sensitivity_altref.csv
"""
import csv, json, os
ROOT = os.path.expanduser('~/medmap-original-b7-b9-clinical-validation')
ref = json.load(open(os.path.join(ROOT, 'evaluation/REF_R_v1.json')))['cases']
inp = json.load(open(os.path.join(ROOT, 'experiments/inputs/cases_input_v1.json')))['cases']
mo = json.load(open(os.path.join(ROOT, 'experiments/results/run2/method_outputs.json')))
CONF = {'APPLY', 'NOT_APPLY', 'SDM_CONFLICT'}

SCEN = {
    'S0_REF_R_as_is': {},
    # 사실 감사: CASE_07 혈당강하제 복용 근거 없음 -> 확인 필요(보류)
    'S1_CASE07_I1_HOLD': {('CASE_07', 'I1'): 'HOLD'},
    # VA CKD CPG 부록 '국소 포함 NSAID 회피(가능하면)' -> CASE_04 I2 비적용
    'S2_CASE04_I2_NOT_APPLY': {('CASE_04', 'I2'): 'NOT_APPLY'},
    # VA 원문은 EDKA 후 SGLT2i 영구 금기를 명시하지 않음 -> 보류
    'S3_CASE08_I2_HOLD': {('CASE_08', 'I2'): 'HOLD'},
    # CKD14 'unless intolerance' 를 반증 조건으로 읽음 -> 지속 적용
    'S4_CKD14_defeater_APPLY': {('CASE_02', 'I3'): 'APPLY', ('CASE_04', 'I5'): 'APPLY'},
    # MGCDS Case1 선택지 3개, 선호 없음 -> 보류
    'S5_CASE13_I3_HOLD': {('CASE_13', 'I3'): 'HOLD'},
}
SCEN['S6_all_above'] = {k: v for s in list(SCEN.values()) for k, v in s.items()}

def cls(r, o):
    if r in CONF:
        return 'CC' if o == r else ('UD' if o == 'HOLD' else 'WC')
    return 'AD' if o == 'HOLD' else 'WC'

rows = []
for sname, ch in SCEN.items():
    for m in ['B', 'A', 'C', 'D', 'ALL_HOLD', 'GUIDELINE_ONLY']:
        c = {'CC': 0, 'WC': 0, 'AD': 0, 'UD': 0}
        for cid, case in inp.items():
            for iid in case['items']:
                r = ch.get((cid, iid), ref[cid]['items'][iid][0])
                c[cls(r, mo[m][cid]['items'][iid]['label'])] += 1
        n = sum(c.values())
        u = (c['CC'] + c['AD'] - 5 * c['WC'] - c['UD']) / n
        rows.append({'scenario': sname, 'method': m, **c, 'N': n, 'U_5_1': round(u, 4), 'B_agree_rate': round((c['CC'] + c['AD']) / n, 4)})
with open(os.path.join(ROOT, 'red-team/verifier/sensitivity_altref.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows:
    if r['method'] in ('B', 'C', 'D', 'A'): print(r)
