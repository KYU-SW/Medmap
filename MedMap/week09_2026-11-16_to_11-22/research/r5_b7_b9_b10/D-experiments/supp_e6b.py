"""[합성] 보조 실험 E6b (사후 추가, 사전 동결 정답 아님): 동결 E6 은 근거 공백 상태가 많아 선호 범위 효과가 가려졌다
(results_extra_checks.json E6_by_r). 근거를 모두 지지로 두고 r 만 바꾼 family 에서 선호 효과를 본다.
정답은 동결 GT 코드(sha 일치 확인)로 계산. 출력: inputs/supp_e6b_instances.json, results_supp_e6b.csv
"""
import json, os, sys, random, hashlib, time, csv
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "methods")); sys.path.insert(0, HERE)
for f in ("gen_instances.py", "ground_truth.py"):
    assert hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest() == \
        hashlib.sha256(open(os.path.join(HERE, "frozen", f + ".frozen"), "rb").read()).hexdigest()
import gen_instances, ground_truth  # noqa
from evaluate import METHODS, score  # noqa

insts = []
for fam in range(40):
    for r in [F(0), F(1, 20), F(1, 10), F(1, 5), F(1, 3)]:
        rng = random.Random(16000 + fam)
        insts.append(gen_instances.gen_random(rng, f"e6b_f{fam}_r{str(r).replace('/', '_')}", "E6b", n_unknown=1, n_known=3,
                                              r=r, ev_mode="all_supported", n_rules=3, family=fam, level=str(r)))
json.dump({"note": "[합성] 사후 보조 실험", "instances": insts}, open(os.path.join(HERE, "inputs", "supp_e6b_instances.json"), "w"), indent=0)
rows = []
for inst in insts:
    gt = ground_truth.solve(inst)
    for m, fn in METHODS.items():
        t0 = time.perf_counter(); o = fn(inst); dt = time.perf_counter() - t0
        row = dict(id=inst["id"], r=inst["params"]["r"], family=inst["params"]["family"], method=m, gt_final=gt["final"],
                   m_final=o["final"], pref_states=sum(v[0] == "PREF" for v in gt["per_state"].values()), time_s=round(dt, 5))
        row.update(score(gt, o)); rows.append(row)
with open(os.path.join(HERE, "results_supp_e6b.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
import pandas as pd
d = pd.DataFrame(rows)
d = d[d.gt_final != "NO_GROUND_TRUTH"]
print(d[d.method == "B_joint"].groupby("r").agg(pref_states=("pref_states", "sum"), n=("id", "count")))
print(d.groupby(["r", "method"]).full_ok.mean().round(3).unstack())
print(d.groupby(["r", "method"]).F2_states.sum().unstack())
print(d.groupby(["r", "method"]).ewas_ok.apply(lambda s: pd.to_numeric(s, errors="coerce").mean()).round(3).unstack())
