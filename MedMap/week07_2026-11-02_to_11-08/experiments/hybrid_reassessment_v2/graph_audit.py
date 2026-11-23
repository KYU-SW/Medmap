"""그래프 스냅샷 재현·비교(읽기 전용). 기록된 138 노드와 현재 94 노드의 차이 확인. 결과 outputs/graph_audit.json"""
import json,subprocess,sys,tempfile
from pathlib import Path
H=Path(__file__).parent; EXP=H.parent; ROOT=EXP.parent
CODE=r'''
import sys,json
from collections import Counter
sys.path.insert(0,sys.argv[1])
import knowledge_real_kg as K, ddxplus_adapter as AD
m=AD.build_mapping()
used=sorted({h for v in m.values() if v.get("used") for h in v["hp_ids"]})
allhp=sorted({h for v in m.values() for h in v.get("hp_ids",[])})
def st(**k):
    try: g,meta=K.build_real_graph(**k)
    except TypeError as e: return {"error":str(e)}
    es=[e for n in g.nodes for e in g.out_edges(n)]
    return {"nodes":len(g.nodes),"edges":len(es),"kinds":dict(Counter(g.nodes[n].kind for n in g.nodes)),"rels":dict(Counter(e.rel for e in es)),"node_ids":sorted(g.nodes),"edge_keys":sorted(f"{e.src}|{e.rel}|{e.dst}" for e in es)}
print(json.dumps({"n_used_hp":len(used),"n_any_hp":len(allhp),"no_extra":st(),"mapping_used":st(extra_hp_nodes=used),"mapping_any":st(extra_hp_nodes=allhp)}))
'''
out={}
for name,d in (('current',EXP/'exp01b_graph_engine'),('explore1_archive',ROOT/'archive/exp01b_explore1_modules'),('pre35_archive',ROOT/'archive/exp01b_pre35_modules')):
    if not d.exists(): out[name]={'error':'missing'}; continue
    p=subprocess.run([sys.executable,'-B','-c',CODE,str(d)],capture_output=True,text=True,cwd=d,env={**__import__('os').environ,'PYTHONPATH':str(EXP/'main_ai')})
    out[name]=json.loads(p.stdout) if p.returncode==0 else {'error':p.stderr[-300:]}
cur=out['current']
sys.path.insert(0,str(EXP/'exp01b_graph_engine'))
from knowledge_real_kg import build_real_graph
from collections import Counter
g,meta=build_real_graph(extra_hp_nodes=("HP:0410174","HP:0033106","HP:0003565"),discriminators=True)
es=[e for n in g.nodes for e in g.out_edges(n)]
run={"nodes":len(g.nodes),"edges":len(es),"kinds":dict(Counter(g.nodes[n].kind for n in g.nodes)),"rels":dict(Counter(e.rel for e in es)),"ev_class":dict(Counter(getattr(e,'spec',{}).get('evidence_class','') if isinstance(getattr(e,'spec',None),dict) else '' for e in es)),"hsdn_edges":sum('HSDN' in str(e.source) for e in es)}
pe=[(e.src,e.rel,str(e.source)[:70]) for n in g.nodes for e in g.out_edges(n) if e.dst=='DX:Pulmonary embolism']
run['pe_incoming']=len(pe); run['pe_rel']=dict(Counter(x[1] for x in pe)); run['pe_from_hsdn_only']=sum('HSDN' in x[2] for x in pe)
run['weakening_edges']=sum(e.rel in('ARGUES_AGAINST','WEAKENS','EXCLUDES') for e in es); run['roles_absent']=meta.get('relation_roles_absent')
cur_ids=set(cur.get('mapping_used',{}).get('node_ids',[])) if 'mapping_used' in cur else set()
res={'snapshots':{k:{kk:vv if not isinstance(vv,dict) or 'node_ids' not in vv else {x:vv[x] for x in('nodes','edges','kinds','rels')} for kk,vv in v.items()} for k,v in out.items()},'runtime_used_by_exp03_hybrid':run}
for a,b,lab in (('pre35_archive','current','pre35_vs_current_mapping_used'),):
    if 'mapping_used' in out[a] and 'mapping_used' in out[b]:
        A,B=set(out[a]['mapping_used']['node_ids']),set(out[b]['mapping_used']['node_ids']); res[lab]={'only_old':sorted(A-B)[:40],'n_only_old':len(A-B),'only_new':sorted(B-A)[:40],'n_only_new':len(B-A)}
(H/'outputs/graph_audit.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')
for k,v in res['snapshots'].items(): print(k,json.dumps(v,ensure_ascii=False)[:650])
print(json.dumps(run,ensure_ascii=False)[:800]); print(json.dumps(res.get('pre35_vs_current_mapping_used'),ensure_ascii=False)[:400])
