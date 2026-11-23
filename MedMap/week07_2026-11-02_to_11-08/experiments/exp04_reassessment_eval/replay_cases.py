"""EXP-04 B: 공개 증례 재현(질적). 엔진·v3b 수정 없음. 저자 서술 기준 — 정확도 아님. 판독 문장은 동결 v3b 로 분류."""
import json,sys
from pathlib import Path
HERE=Path(__file__).parent; EXP03=HERE.parent/'exp03_reassessment'; sys.path[:0]=[str(EXP03)]
import reassess as RA
from ct_bridge import classify
PE=RA.PE
# 사건: (종류, concept, 상태, 근거 문장/메모). IMG=영상 판독 원문 문장, X=엔진 표현 불가 사건. 'H:…'=가설 설정 시점. CH=저자가 판단을 바꾼 근거 사건
C={
'PMC7253721':('A',[('SYMPTOM','HP:0002094','POSITIVE','dyspnea'),('LAB','HP:0033106','POSITIVE','D-dimer 1.13'),('H',PE),('IMG','However, no signs of pulmonary embolism, thrombosis in the leg veins, or patchy lung consolidation were observed','CH'),('X','colon between liver and diaphragm (Chilaiditi)')]),
'PMC10826807':('A',[('SYMPTOM','HP:0002105','POSITIVE','hemoptysis'),('SYMPTOM','HP:0002094','POSITIVE','exertional dyspnea'),('IMG','Chest CTA revealed ill-defined hypodense areas predominantly in the right upper lobe pulmonary artery'),('H',PE),('SIGN','HP:0002625','NEGATIVE','no DVT on ultrasound'),('IMG','The interventional radiologist thereby recognized bronchopulmonary artery fistula while ruling out pulmonary embolism','CH')]),
'PMC11308721':('A',[('SYMPTOM','HP:0002105','POSITIVE','blood-tinged sputum'),('SYMPTOM','HP:0033771','POSITIVE','pleuritic chest pain'),('SYMPTOM','HP:0002094','POSITIVE','dyspnea'),('SIGN','HP:0001649','POSITIVE','HR 104'),('SIGN','HP:0012418','POSITIVE','SpO2 86%'),('H',PE),('IMG','It was negative for pulmonary embolism, and echocardiogram was normal','CH'),('X','hypoplastic left pulmonary artery, Swyer-James-Macleod')]),
'PMC9670361':('A',[('X','dilated right ventricle on TTE'),('IMG','The thorax CT-scan showed a massive bilateral pulmonary embolism'),('H',PE),('IMG','On the same night, a CT-scan revealed a mass in the pulmonary artery, RVOT, and pulmonary valve','CH'),('X','tumor found at surgery')]),
'PMC12584563':('A',[('SYMPTOM','HP:0002094','POSITIVE','dyspnea'),('SYMPTOM','HP:0100749','POSITIVE','chest pain'),('LAB','HP:0033106','POSITIVE','D-dimer 6531'),('X','V/Q scan concerning for large PE (not CTA)'),('H',PE),('X','acute-onset anemia and continued distress despite anticoagulation','CH'),('IMG','A CT angiography of the chest with pulmonary embolism protocol, which was performed immediately after noting the acute‐onset anemia, revealed an increase in size of the ascending thoracic aorta with an aneurysmal dilation measuring up to 6.1 cm with an associated focal dissection flap (Figure 1)')]),
'PMC12867922':('A',[('SYMPTOM','HP:0100749','POSITIVE','chest tightness and pain'),('LAB','HP:0033106','NEGATIVE','D-dimer normal'),('IMG','The presence of a filling defect in the main pulmonary artery on CTA was interpreted as supporting a diagnosis of PE'),('H',PE),('X','no improvement on anticoagulant'),('X','multidisciplinary review: insidious onset, normal D-dimer, main trunk only — inconsistent with PE','CH')]),
'PMC3002912':('B',[('SYMPTOM','HP:0100749','POSITIVE','chest pain'),('SYMPTOM','HP:0002094','POSITIVE','difficult breathing'),('X','ST elevation V1-V4'),('H','DX:ST elevation myocardial infarction'),('X','coronary angiography without atherosclerotic occlusion'),('LAB','HP:0033106','POSITIVE','D-dimer 1172'),('IMG','With bedside transesophageal echocardiography pulmonary embolism was confirmed; thrombi were seen in both pulmonary arteries','CH')]),
'PMC6288948':('B',[('SYMPTOM','HP:0002094','POSITIVE','shortness of breath'),('X','ST elevation, troponin raised'),('H','DX:Acute myocardial infarction'),('X','stable coronary plaques on angiography; biomarkers rule out initial diagnosis','CH')]),
'PMC6946195':('B',[('SYMPTOM','HP:0002027','POSITIVE','abdominal pain'),('SIGN','HP:0001945','POSITIVE','low fever'),('X','chest radiograph infiltration and effusion'),('H','DX:Pneumonia'),('SIGN','HP:0012418','POSITIVE','SpO2 92%, PE suspected','CH'),('LAB','HP:0033106','POSITIVE','D-dimer 8.8'),('IMG','Further examination with computed tomography pulmonary angiography (CTPA) revealed multiple embolism in bilateral pulmonary artery trunk')]),
'PMC6392842':('B',[('SYMPTOM','HP:0033771','POSITIVE','pleuritic chest pain'),('X','CT ground-glass opacities and pleural effusion'),('H','DX:Pneumonia'),('X','migrating pain and new right effusion despite antibiotics','CH'),('IMG','Findings were consistent with a PE in the right pulmonary artery')]),
'PMC10612150':('B',[('SYMPTOM','HP:0002094','POSITIVE','dyspnea'),('X','bilateral infiltrates on chest X-ray'),('H','DX:Pneumonia'),('SIGN','HP:0002625','POSITIVE','left femoral vein thrombosis'),('IMG','Computed tomography pulmonary angiography (CT-PA) identified rounded nodular opacities in both lungs most of which are cavitary with the largest measuring 4 cm, with no evidence of massive pulmonary embolism','CH')]),
}
rows=[]
for pid,(grp,ev) in C.items():
    tl=RA.Timeline(pid); steps=[]; ch=None; t=0.0; expr=tot=0; cls=[]
    for x in ev:
        t+=1.0
        if x[0]=='H':
            tl.set_hypothesis(RA.HypothesisEvent('h1',pid,x[1],t)); steps.append((t,'H')); continue
        tot+=1
        eid=f'e{int(t)}'; src=f'PMC:{pid}#{eid}'
        if x[0]=='X':
            if len(x)>2: ch=t
            steps.append((t,'X')); continue
        expr+=1
        if x[0]=='IMG':
            pc,_=classify(x[1],'v3b'); cls.append(pc)
            tl.add(RA.Evidence(eid,pid,'IMAGING_REPORT','case_report',src,t,t,t,{'NEGATIVE':'NEGATIVE','UNCERTAIN':'UNCERTAIN','NO_MENTION':'NOT_ASSESSABLE'}.get(pc,'POSITIVE'),concept=RA.CTPA_CONCEPT,pe_class=pc))
            if len(x)>2: ch=t
        else:
            tl.add(RA.Evidence(eid,pid,'SYMPTOM' if x[0]!='LAB' else 'LAB','case_report',src,t,t,t,x[2],concept=x[1]))
            if len(x)>4: ch=t
        steps.append((t,x[0]))
    seq=[];first=None;src_ok=True
    for T,_ in steps:
        a=RA.assess(tl,T); seq.append(a.summary)
        if a.alerts and first is None:
            first=T; src_ok=all(z.get('source_reference') for z in a.alerts)
    rel='NO_ALERT' if first is None else 'SAME' if first==ch else 'EARLIER' if first<ch else 'LATER'
    rows.append(dict(pmcid=pid,group=grp,events=tot,expressible=expr,author_change_step=ch,first_alert_step=first,relation_to_author=rel,alert_has_source=src_ok if first else None,v3b_classes=cls,states=seq))
A=[r for r in rows if r['group']=='A'];B=[r for r in rows if r['group']=='B']
from collections import Counter
s=dict(n=len(rows),events=sum(r['events'] for r in rows),expressible=sum(r['expressible'] for r in rows),group_A=dict(Counter(r['relation_to_author'] for r in A)),group_B=dict(Counter(r['relation_to_author'] for r in B)),note='저자 사후 서술 기준·선택된 보고 — 정확도 아님, 일반화 금지')
(HERE/'outputs/case_replay_results.json').write_text(json.dumps(dict(summary=s,cases=rows),ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps(s,ensure_ascii=False))
for r in rows: print(r['pmcid'],r['group'],f"{r['expressible']}/{r['events']}",r['author_change_step'],r['first_alert_step'],r['relation_to_author'],r['v3b_classes'],r['states'])
