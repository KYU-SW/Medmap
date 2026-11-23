"""EXP-04 A: SCT 공개 문항 분석(PROTOCOL_EXP04.md). 호출 없음, 기존 파일만 읽음."""
import glob,hashlib,json,re,sys
from pathlib import Path
import numpy as np,pandas as pd
H=Path(__file__).parent
d=pd.read_csv(H/'data/raw/sct_cleaned_full.csv').merge(pd.read_csv(H/'data/annot/annotations.csv')[['question_id','hyp_type','dx_node','ev_type','polarity']],on='question_id')
w=d[['-2','-1','0','1','2']].astype(float).div(d[['-2','-1','0','1','2']].astype(float).sum(axis=1),axis=0)
d['p_dec'],d['p_zero'],d['p_inc']=w['-2']+w['-1'],w['0'],w['1']+w['2']
def ref(r):
    v=[r.p_dec,r.p_zero,r.p_inc]; m=max(v)
    return 'NO_CONSENSUS' if sum(abs(x-m)<1e-9 for x in v)>1 else ['DEC','ZERO','INC'][v.index(m)]
d['ref']=d.apply(ref,axis=1); d['agree']=d[['p_dec','p_zero','p_inc']].max(axis=1)
d['split']=['dev' if hashlib.sha256(str(s).encode()).digest()[0]<77 else 'eval' for s in d.sct_stem]
D=d[d.hyp_type=='DIAGNOSIS']; E=D[D.split=='eval']
def boot(frame,fn,n=2000):
    g=[x for _,x in frame.groupby('sct_stem')]; rng=np.random.default_rng(0); out=[]
    for _ in range(n):
        s=pd.concat([g[i] for i in rng.integers(0,len(g),len(g))]); v=fn(s)
        if v is not None and not np.isnan(v): out.append(v)
    return [round(float(np.percentile(out,2.5)),3),round(float(np.percentile(out,97.5)),3)] if out else None
def acc(f,col):
    k=f[(f.ref!='NO_CONSENSUS')&f[col].notna()]; return float((k.ref==k[col]).mean()) if len(k) else float('nan')
res={'n_items':len(d),'by_source':d.source.value_counts().to_dict(),'by_hyp_type':d.hyp_type.value_counts().to_dict(),'split_diag':D.split.value_counts().to_dict()}
res['Q1']={'n_diag':len(D),'share_diag':round(len(D)/len(d),3),'n_graph_hypothesis':int(D.dx_node.notna().sum()),'engine_output_not_no_knowledge':0}
res['Q2']={'direction_all_diag':D.ref.value_counts().to_dict(),'direction_eval':E.ref.value_counts().to_dict(),'agreement_median':round(float(D.agree.median()),3),'agreement_iqr':[round(float(D.agree.quantile(q)),3) for q in(.25,.75)],'share_agree_ge_0.8':round(float((D.agree>=.8).mean()),3)}
neg=D[D.polarity=='NEGATIVE']; res['Q3']={'n_negative_items':len(neg),'ref':neg.ref.value_counts().to_dict(),'note':'n=2 — 해석 불가'}
dec=D[D.ref=='DEC']; res['Q4']={'n_panel_decrease':len(dec),'engine_can_express_conflict':0,'share_positive_finding(Q4b)':round(float((dec.polarity=='POSITIVE').mean()),3) if len(dec) else None,'n_positive_finding':int((dec.polarity=='POSITIVE').sum())}
base=D[(D.split=='dev')&(D.ref!='NO_CONSENSUS')].ref.value_counts(); maj=base.index[0]
d['p_major']=maj; d['p_rule']=d.polarity.map({'POSITIVE':'INC','NEGATIVE':'ZERO'})
qid=d.question_id.tolist()
def parse(t):
    m=re.search(r'Rating:\s*\**\s*([+-]?\d)',str(t)); return None if not m else int(m.group(1))
llm={}
root=Path(sys.argv[1]) if len(sys.argv)>1 else None
if root:
    for f in sorted(root.glob('w_reason_zero-shot/*.json')):
        x=json.load(open(f,encoding='utf-8')); key=['response']
        m={r['sct_stem']+'|'+r['question']+'|'+r['additional_info']:parse(r[key[0]]) for r in x} if key else {}
        name=re.search(r'responses_(\w+?)_(.*?)_20',f.name).group(2); ks=d.sct_stem+'|'+d.question+'|'+d.additional_info
        vals=ks.map(m); d['p_'+name]=vals.map(lambda v:None if pd.isna(v) else ('DEC' if v<0 else 'ZERO' if v==0 else 'INC'))
        llm[name]={'parsed':int(vals.notna().sum()),'keys':key[:1]}
D=d[d.hyp_type=='DIAGNOSIS']; E=D[D.split=='eval']
tab={}
for c in [x for x in d.columns if x.startswith('p_') and x not in('p_dec','p_zero','p_inc')]:
    tab[c[2:]]={'eval_acc':round(acc(E,c),3),'eval_ci':boot(E,lambda s:acc(s,c)),'eval_n':int(((E.ref!='NO_CONSENSUS')&E[c].notna()).sum()),'all_diag_acc':round(acc(D,c),3)}
res['Q5']={'majority_class_from_dev':maj,'dev_n':int(base.sum()),'direction_agreement':tab,'llm_files':llm,'note':'규칙은 소견 유무만 사용. 엔진 자체는 이 문항들에 답할 지식 없음(Q1).'}
res['clinical_metrics']='NOT_EVALUABLE'
res['sensitivity_excl_seen_1_101']='문항 1·101 은 hyp_type OTHER 라 DIAGNOSIS 지표에 영향 없음'
(H/'outputs/sct_results.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8'); print(json.dumps(res,ensure_ascii=False,indent=1))
