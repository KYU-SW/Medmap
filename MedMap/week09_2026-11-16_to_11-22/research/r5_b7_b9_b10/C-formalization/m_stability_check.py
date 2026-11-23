"""⊥=±M 표현의 M 안정성 확인(전수 열거만). [합성 실험]"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrated_model as im
from run_validate import random_inst, v2
def cats(inst, norm):
    SP, SK, plans = im.clinical_states(inst), im.know_states(inst), im.all_plans(inst)
    if not SP: return {}
    return {x: (im.categorize(inst, x, norm, plans, SP, SK)["category"],
                tuple(sorted(im.categorize(inst, x, norm, plans, SP, SK)["flags"].items()))) for x in plans}
rng = random.Random(7); insts = [("MAIN", im.MAIN), ("V2", v2())] + [(f"R{i}", random_inst(rng)) for i in range(15)]
diff = tot = 0
for name, inst in insts:
    for norm in im.NORMS:
        im.M_BOT = 10.0; a = cats(inst, norm)
        im.M_BOT = 1000.0; b = cats(inst, norm)
        for x in a:
            tot += 1
            if a[x] != b[x]:
                diff += 1; print("DIFF", name, norm, sorted(x), a[x][0], b[x][0])
print(f"plans compared={tot}, category/flag differences M=10 vs M=1000: {diff}")
