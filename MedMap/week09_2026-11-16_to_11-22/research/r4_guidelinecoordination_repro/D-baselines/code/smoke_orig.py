import sys,os,time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orig_loader import *
an, z3e, lsh = load_pipeline_modules()
rules = load_rules(); preds = atomic_predicates(rules)
ra = an.RuleAnalyzer(rules, preds)
# prefix bug test
for c in ["pred.has_ckd AND pred.has_ckd_stage_4", "pred.has_ckd_stage_4 AND pred.has_ckd", "pred.has_ckd AND pred.on_metformin"]:
    print(repr(c), '->', ra._expand_condition(c))
    try:
        e=ra._expand_condition(c); ra.pred_analyzer.z3env.ensure_vars_for_expr(e); print('   parsed:', ra.pred_analyzer.z3env.expr(e))
    except Exception as ex: print('   PARSE ERROR', str(ex)[:120])
ids=[r['id'] for r in rules]
t=time.time(); n=0
for i in range(60):
    for j in range(i+1,60):
        ra.analyze_pair(ids[i],ids[j]); n+=1
print('pairs',n,'sec',round(time.time()-t,2))
