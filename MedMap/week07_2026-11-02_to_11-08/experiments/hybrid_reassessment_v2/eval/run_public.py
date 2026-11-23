"""동결 코드 + 사전 고정 기준으로 1회 실행. 임상 정답 아님. 결과 outputs/public_linking_results.json"""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
H=Path(__file__).parents[1]; sys.path.insert(0,str(H))
fz=json.loads((H/'eval/FREEZE.json').read_text())['frozen_before_sampling']
files=sorted(list((H/'hybrid2').glob('*.py'))+[H/'knowledge/evidence_relations.json'])
assert {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}==fz,'코드가 동결 후 바뀜'
from hybrid2 import pipeline as P
from hybrid.schema import AssertedBy,DataClass,DiagnosisAssertion,DxStatus,Provenance
S=[json.loads(l) for l in (H/'eval/public_sentences.jsonl').read_text(encoding='utf-8').splitlines()]
gold=json.loads((H/'eval/gold_public.json').read_text(encoding='utf-8'))['items']
PILOT={'PE_DIAGNOSIS','DDIMER','DVT','CTPA_STUDY','PERFUSION_SCAN','FILLING_DEFECT'}
h=DiagnosisAssertion('h','c','Pulmonary embolism',DxStatus.WORKING_DIAGNOSIS,AssertedBy.SIMULATED,0.0,Provenance('t','t',DataClass.PUBLIC_OPEN),concept_id='DX:Pulmonary embolism')
ctx={'pretest':'INTERMEDIATE','suspected':True}  # 실행 조건 확인용 가정 — 문장에서 얻은 값 아님
g_tot=g_found=asg_ok=asg_tot=fp=0; rows=[]; errs=[]; dirs=Counter(); reasons=Counter(); hp=[]; find_gold=find_hit=find_extra=0; prov_ok=prov_tot=0; amb=0
for r in S:
    g=gold.get(str(r['id']),{})
    recs=P.extract(r['sentence'],'')
    linked=[x for x in recs if x['link_status']=='LINKED']; amb+=sum(x['link_status']=='AMBIGUOUS' for x in recs)
    got={}
    for x in linked:
        if x['concept'] in PILOT: got.setdefault(x['concept'],[]).append(x['assertion'])
        elif x['lexicon']=='HPO': hp.append((r['id'],x['surface'],x['concept'],x['assertion'],bool(x['graph_node'])))
    want=g.get('concepts',{})
    for c,a in want.items():
        g_tot+=1
        if c in got:
            g_found+=1; asg_tot+=1
            if a in got[c]: asg_ok+=1
            else: errs.append(dict(id=r['id'],type='ASSERTION_DIFF',concept=c,want=a,got=got[c]))
        else: errs.append(dict(id=r['id'],type='MISSED_CONCEPT',concept=c))
    for c in got:
        if c not in want: fp+=1; errs.append(dict(id=r['id'],type='UNSUPPORTED_MAPPING',concept=c,got=got[c]))
    out=[P.assess_record(x,h,ctx) for x in recs]
    for o in out:
        dirs[o['direction']]+=1
        if o['abstain_reason']: reasons[o['abstain_reason']]+=1
        if o['direction'] not in('ABSTAIN',):
            prov_tot+=1; prov_ok+=bool(o['sources'] and all(s.get('quote') and s.get('url') for s in o['sources']))
    fs={P.finding_state(x).get('finding') for x in recs}-{None}
    wantf={g[k] for k in('finding','finding2') if k in g}
    find_gold+=len(wantf); find_hit+=len(wantf&fs); find_extra+=len(fs-wantf)
    for f in wantf-fs: errs.append(dict(id=r['id'],type='MISSED_RELATION_PATH',finding=f))
    for f in fs-wantf: errs.append(dict(id=r['id'],type='EXTRA_RELATION_PATH',finding=f))
    rows.append(dict(id=r['id'],sentence=r['sentence'],gold=g,records=[{k:x[k] for k in('surface','concept','assertion','cue','link_status','graph_node')} for x in recs],findings=sorted(fs),outputs=[{k:o[k] for k in('extracted_surface','direction','relation_id','abstain_reason','missing_context')} for o in out]))
n_with_gold=sum(1 for r in S if str(r['id']) in gold)
res=dict(label='IMPLEMENTATION_CHECK_ON_UNSEEN_PUBLIC_SENTENCES',gold_note='세션 1인 주석, 의료 전문가 아님. 정답률 아님',n_sentences=len(S),n_sentences_with_target_concept=n_with_gold,n_gold_concept_mentions=g_tot,concept_extraction_coverage=g_found/g_tot,n_linked_gold=g_found,assertion_agreement_with_annotation=asg_ok/asg_tot,n_assertion=asg_tot,unsupported_mapping_count=fp,unsupported_mapping_per_found=fp/(g_found+fp),n_gold_relation_paths=find_gold,relation_path_found=find_hit,relation_path_coverage=find_hit/find_gold,extra_relation_paths=find_extra,directions=dict(dirs),abstain_reasons=dict(reasons),provenance_complete=f'{prov_ok}/{prov_tot}',ambiguous_mentions=amb,hpo_links=len(hp),hpo_in_graph=sum(x[4] for x in hp),pretest_assumed_for_execution=ctx,errors=errs,hpo_link_list=hp,rows=rows)
(H/'outputs/public_linking_results.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps({k:v for k,v in res.items() if k not in('errors','rows','hpo_link_list')},ensure_ascii=False,indent=0))
for e in errs: print(e, '|', next(r['sentence'][:110] for r in S if r['id']==e['id']))
print(hp)
