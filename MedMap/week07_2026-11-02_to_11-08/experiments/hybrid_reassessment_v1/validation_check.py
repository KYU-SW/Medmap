"""IMPLEMENTATION CHECK — 구조 연결 확인만. 전문가 판단 성능·임상 정확도가 아니다. 실제 제한 자료·외부 호출 없음.
산출: outputs/validation_results.json, docs/VALIDATION_RESULTS.md"""
import json,sys,tempfile,csv,subprocess,hashlib
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).parent; sys.path.insert(0,str(HERE))
import pandas as pd
from hybrid import adapters as AD, er_reason as ER, metrics as M, temporal as T
from hybrid.schema import *
ARMS=[AD.BaselineEngineAdapter(),AD.RulesReasoner(),AD.GraphReasoner(),AD.LLMReasoner(),AD.HybridReasoner()]
res={"label":"IMPLEMENTATION_CHECK","created":datetime.now().isoformat(timespec="seconds")}
# 1) SCT 공개 174문항(EXP-04 에서 이미 사용·열람, 독립 평가 아님)
X=HERE.parent/'exp04_reassessment_eval'
d=pd.read_csv(X/'data/raw/sct_cleaned_full.csv').merge(pd.read_csv(X/'data/annot/annotations.csv'),on='question_id')
inp,refs,tied=[],[],0
for r in d.itertuples(index=False):
    c=hashlib.sha256(str(r.sct_stem).encode()).hexdigest()[:10]; w=[getattr(r,f'_{i}') if False else 0 for i in ()]
    vals=[float(d.loc[d.question_id==r.question_id,k].iloc[0]) for k in('-2','-1','0','1','2')]; m=max(vals)
    if sum(v==m for v in vals)>1: tied+=1; continue
    p=Provenance('public.sct',f'sct:{r.question_id}',DataClass.PUBLIC_OPEN)
    st=DxStatus.DIFFERENTIAL_DIAGNOSIS if r.hyp_type=='DIAGNOSIS' else DxStatus.UNKNOWN
    h=DiagnosisAssertion(f'h{r.question_id}',c,str(r.question),st,AssertedBy.DATASET_ANNOTATION,0.0,p)
    e=EvidenceItem(f'e{r.question_id}',c,EvidenceKind.OTHER,str(r.additional_info),p,available_at=1.0)
    inp.append(ReasonerInput(str(r.question_id),c,h,e,str(r.sct_stem),(),1.0,DataClass.PUBLIC_OPEN)); refs.append(ReferenceLabel(str(r.question_id),c,vals.index(m)-2,group=r.hyp_type))
sct={}
for a in ARMS:
    o={i.item_id:a.assess(i) for i in inp}; v=M.evaluate(refs,o)
    sct[a.name]={k:v[k] for k in('n_items','coverage','abstention_rate','not_implemented_rate','direction_agreement_all_items')}
res['sct_public']={'data_status':'PUBLIC_ALREADY_USED_IN_EXP04','n_total':len(d),'n_excluded_tied_modal_grade':tied,'arms':sct,'note':'진단 가설을 엔진 개념으로 연결하는 구성요소가 없어 기권이 정상. 성능 아님'}
# 2) 합성 PE 타임라인: 시간·정정·검사 상태·엔진 대조
PE='DX:Pulmonary embolism'; P_=lambda r:Provenance('synthetic',r,DataClass.SYNTHETIC)
h=DiagnosisAssertion('h1','S1','PE',DxStatus.WORKING_DIAGNOSIS,AssertedBy.SIMULATED,0.0,P_('h1'),concept_id=PE)
ev=[EvidenceItem('sym','S1',EvidenceKind.SYMPTOM,'dyspnea',P_('sym'),observed_at=1.,available_at=1.,polarity=Polarity.PRESENT,concept_id='HP:0002094'),
    EvidenceItem('cta1','S1',EvidenceKind.IMAGING_REPORT,'IMPRESSION: No evidence of pulmonary embolism.',P_('cta1'),observed_at=2.,available_at=4.,polarity=Polarity.UNKNOWN),
    EvidenceItem('cta2','S1',EvidenceKind.IMAGING_REPORT,'FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism.',P_('cta2'),observed_at=2.,available_at=7.,polarity=Polarity.UNKNOWN,supersedes='cta1')]
ra=AD._ra(); tl=ra.Timeline('S1'); tl.set_hypothesis(ra.HypothesisEvent('h1','S1',PE,0.0))
tl.add(ra.Evidence('sym','S1','SYMPTOM','syn','syn:sym',1.,1.,1.,'POSITIVE',concept='HP:0002094'))
from ct_bridge import classify
tl.add(ra.Evidence('cta1','S1','IMAGING_REPORT','syn','syn:cta1',2.,4.,4.,'NEGATIVE',concept=ra.CTPA_CONCEPT,pe_class=classify(ev[1].text,'v3b')[0]))
tl.add(ra.Evidence('cta2','S1','IMAGING_REPORT','syn','syn:cta2',2.,7.,7.,'POSITIVE',concept=ra.CTPA_CONCEPT,pe_class=classify(ev[2].text,'v3b')[0],supersedes='cta1'))
tests=[TestEvent('cta','S1','ORDER',1.5,P_('o')),TestEvent('cta','S1','COLLECT',2.,P_('c')),TestEvent('cta','S1','RESULT',4.,P_('r')),TestEvent('cta','S1','CORRECT',7.,P_('k')),TestEvent('cta','S1','REVIEW',8.,P_('v'))]
tr=[];mis=0
for t in (0.5,1.,2.,4.,5.,7.,8.):
    vis=T.visible_evidence(ev,t); a=ra.assess(tl,t); engine={e.event_id for e in ra.effective_evidence(tl,t)[0]}
    mis+=({e.evidence_id for e in vis}!=engine)
    outs=[AD.HybridReasoner().assess(ReasonerInput(f'{e.evidence_id}@{t}','S1',h,e,'',tuple(vis),t)) for e in vis]
    tr.append(dict(T=t,visible=[e.evidence_id for e in vis],engine_summary=a.summary,hybrid=[o.effect.value if o.effect else o.status.value for o in outs],test_status=T.test_status(tests,'cta',t).value,duplicate_candidate=T.is_duplicate_candidate(tests,'cta',t)))
res['synthetic_timeline']={'steps':tr,'visible_set_differs_from_engine':mis,'note':'지어낸 사례. 임상 의미 없음'}
# 3) ER-Reason 형식 시험(지어낸 자리표시자, 가짜 승인 파일은 임시 폴더에만) — 실제 자료 아님
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp); cols=[f'differential_{i}' for i in range(1,6)]+[f'evidence_{i}' for i in range(1,6)]
    T_=[];R_=[]
    for k in range(40):
        key=f'SYNTHKEY{k}'; base={c:'' for c in cols}; base.update(differential_1=f'SYNTH_DX_{k}_A',differential_2=f'SYNTH_DX_{k}_B',evidence_1=f'SYNTH_EVID_{k}_1',evidence_2=f'SYNTH_EVID_{k}_2')
        T_.append(dict(encounterkey=key,One_Sentence_Extracted='SYNTH',**base))
        for s in (1,2):
            for dx in 'AB': R_.append(dict(encounterkey=key,differential=f'SYNTH_DX_{k}_{dx}',evidence=f'SYNTH_EVID_{k}_{s}',dxupdate=(k+s)%5-2,rationale='SYNTH',dxtrajectory='{}'))
    for n,rows in (('t.csv',T_),('r.csv',R_)):
        with open(tmp/n,'w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (tmp/'a.json').write_text(json.dumps(dict(physionet_access_granted_on='SYNTH',version='1.1.0',dua_reviewed_on='SYNTH',external_llm_allowed=False,approved_by_user=True)))
    ins,rf,st=ER.build_items(tmp/'t.csv',tmp/'r.csv',tmp/'a.json')
    outs={a.name:{i.item_id:a.assess(i) for i in ins} for a in ARMS}
    er={a:{k:M.evaluate(rf,o)[k] for k in('n_items','coverage','abstention_rate','not_implemented_rate','direction_agreement_all_items','weighted_kappa_conditional')} for a,o in outs.items()}
    from collections import Counter
    res['er_reason_format_dry_run']={'data_status':'SYNTHETIC_PLACEHOLDER_NOT_ER_REASON','stats':st,'split_counts':dict(Counter(r.split for r in rf)),'cases_in_two_splits':sum(1 for c,g in pd.DataFrame([(r.case_id,r.split) for r in rf]).groupby(0) if g[1].nunique()>1),'arms':er}
# 4) 원본 무수정 확인
ROOT=HERE.parents[1]
chk=subprocess.run(['sha256sum','-c','archive/final_20261029_0925_SHA256SUMS'],cwd=ROOT,capture_output=True,text=True).stdout
sys.path.insert(0,str(HERE.parent/'exp03_reassessment/time_v2'))
import run_time_policy_audit_v2 as RT
frozen=json.loads((RT.HERE/'outputs/CODE_SHA256_20261104_112542.json').read_text()); now=RT.code_sha()
res['preservation']={'exp01_final_ok':chk.count(': OK'),'exp02_frozen_ok':bool(RT.frozen_ok()),'time_v2_code_vs_freeze_diff':sorted(k for k in frozen if frozen[k]!=now.get(k)),'test_used_exists':(RT.EXP02/'outputs/EXT_PE_V3B_TEST_USED').exists(),'counted_marker_exists':RT.COUNTED_MARKER.exists()}
(HERE/'outputs/validation_results.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=0)[:3800])
