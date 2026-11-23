"""실제 End-to-End 실행 예(합성 문장). 임상 검증 아님. outputs/end_to_end_trace.json"""
import json,sys
from pathlib import Path
H=Path(__file__).parent; sys.path.insert(0,str(H))
from hybrid2 import pipeline as P
from hybrid2.pipeline import Document,CaseTimeline
PE='DX:Pulmonary embolism'
tl=CaseTimeline('SYNTH-1')
tl.set_hypothesis('h1','Pulmonary embolism',PE,0.0)
tl.add_test_event('ctpa','ORDER',1.0); tl.add_test_event('ctpa','COLLECT',2.0); tl.add_test_event('ctpa','RESULT',4.0); tl.add_test_event('ctpa','CORRECT',7.0)
tl.add_document(Document('order','CTPA was ordered to rule out pulmonary embolism.','NOTE',1.0,1.0))
tl.add_document(Document('ctpa1','IMPRESSION: No evidence of pulmonary embolism.','CTPA_REPORT',2.0,4.0))
tl.add_document(Document('ctpa2','IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries.','CTPA_REPORT',2.0,7.0,supersedes='ctpa1'))
ctx={'pretest':'INTERMEDIATE','suspected':True}
tr=[tl.state(t,ctx) for t in (0.5,1.0,2.0,4.0,7.0)]
(H/'outputs/end_to_end_trace.json').write_text(json.dumps(tr,ensure_ascii=False,indent=1),encoding='utf-8')
for s in tr:
    print('T',s['as_of'],s['visible_documents'],s['tests'],s['hypotheses'])
print(json.dumps({k:v for k,v in tr[3]['results'][-1].items() if k not in('graph_edges_shown',)},ensure_ascii=False,indent=0)[:1400])
