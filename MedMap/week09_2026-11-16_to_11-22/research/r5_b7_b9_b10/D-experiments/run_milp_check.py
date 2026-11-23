"""[합성] (a) B_milp(단일 MILP + CEGAR) 의 ∃w∀s / 지침 적용 출력을 동결 정답과 대조 (전 인스턴스)
(b) E8b 확장성: 미확인 변수 수 증가 시 B(상태 열거) vs B_milp 시간. 큰 크기는 동결 정답 없음 —
    n_unknown<=10 은 동결 GT 코드(frozen/ground_truth.py.frozen 과 동일 내용)로 사후 계산해 대조(사전 동결 정답 아님).
출력: results_milp_check.csv, results_scaling_e8b.csv, inputs/scaling_instances.json
"""
import json, os, sys, time, csv, random, hashlib
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "methods")); sys.path.insert(0, HERE)
from b_milp import run_Bmilp  # noqa
from strong import run_B  # noqa
import gen_instances  # noqa
import ground_truth  # noqa

for f in ("gen_instances.py", "ground_truth.py"):
    a = hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
    b = hashlib.sha256(open(os.path.join(HERE, "frozen", f + ".frozen"), "rb").read()).hexdigest()
    assert a == b, f"{f} differs from frozen copy"


def part_a():
    insts = json.load(open(os.path.join(HERE, "inputs", "instances.json")))["instances"]
    GT = json.load(open(os.path.join(HERE, "frozen", "ground_truth.json")))["gt"]
    rows = []
    for inst in insts:
        gt = GT[inst["id"]]
        if gt["final"] == "NO_GROUND_TRUTH":
            continue
        t0 = time.perf_counter(); o = run_Bmilp(inst); dt = time.perf_counter() - t0
        rows.append(dict(id=inst["id"], exp=inst["exp"], ewas_ok=int(sorted(o["ewas"]) == sorted(gt["ewas"])),
                         app_ok=int(o["app"] == gt["app"]), gt_ewas_size=len(gt["ewas"]), cegar_iters=o["meta"]["iters"],
                         time_s=round(dt, 5)))
    with open(os.path.join(HERE, "results_milp_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    n = len(rows)
    print("part_a n=%d ewas_ok=%d app_ok=%d nonempty_ewas=%d" % (n, sum(r["ewas_ok"] for r in rows),
          sum(r["app_ok"] for r in rows), sum(r["gt_ewas_size"] > 0 for r in rows)), flush=True)


def part_b():
    insts = []
    for nu in [2, 4, 6, 8, 10, 12, 14, 16, 20]:
        for rep in range(3):
            rng = random.Random(90000 + 100 * nu + rep)
            insts.append(gen_instances.gen_random(rng, f"e8b_u{nu}_{rep}", "E8b", n_unknown=nu, n_known=1, G=4,
                                                  opts=(2, 3), n_rules=5, p_rule_cond=1.0, rule_on_unknown=1.0,
                                                  r=F(1, 10), ev_mode="all_supported", app_on_unknown=0.8, p_dep=0.0,
                                                  family="E8b", level=nu))
    json.dump({"note": "[합성] 확장성 전용, 사전 동결 정답 없음", "instances": insts},
              open(os.path.join(HERE, "inputs", "scaling_instances.json"), "w"), indent=0)
    rows = []
    for inst in insts:
        nu = inst["params"]["n_unknown"]
        t0 = time.perf_counter(); om = run_Bmilp(inst); tm = time.perf_counter() - t0
        row = dict(id=inst["id"], n_unknown=nu, n_plans=0, t_milp_s=round(tm, 4), milp_ewas=len(om["ewas"]),
                   cegar_iters=om["meta"]["iters"], t_B_enum_s="", B_agree="", t_gt_s="", gt_agree_milp="", gt_agree_B="")
        import itertools
        row["n_plans"] = len(list(itertools.product(*[g["options"] for g in inst["guidelines"]])))
        if nu <= 10:
            t0 = time.perf_counter(); ob = run_B(inst); tb = time.perf_counter() - t0
            row["t_B_enum_s"] = round(tb, 4); row["B_agree"] = int(sorted(ob["ewas"]) == sorted(om["ewas"]))
            t0 = time.perf_counter(); g = ground_truth.solve(inst); tg = time.perf_counter() - t0
            row["t_gt_s"] = round(tg, 4)
            row["gt_agree_milp"] = int(sorted(g["ewas"]) == sorted(om["ewas"]))
            row["gt_agree_B"] = int(sorted(g["ewas"]) == sorted(ob["ewas"]))
        rows.append(row)
        print(row, flush=True)
    with open(os.path.join(HERE, "results_scaling_e8b.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in which:
        part_a()
    if "b" in which:
        part_b()
