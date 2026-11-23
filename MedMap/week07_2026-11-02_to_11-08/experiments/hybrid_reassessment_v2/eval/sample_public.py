"""코드 동결 후 신규 CC BY 증례에서 문장 표본 추출. 이전 EXP-04 11건·후보는 제외. 기준 표시 전 파이프라인 실행 안 함."""
import hashlib,json,random,re,time,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
H=Path(__file__).parents[1]
files=sorted(list((H/'hybrid2').glob('*.py'))+[H/'knowledge/evidence_relations.json'])
(H/'eval/FREEZE.json').write_text(json.dumps({'frozen_before_sampling':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}},indent=1))
seen=set(json.load(open(H.parent/'exp04_reassessment_eval/cases/fulltext_case_sections.json')))|{json.loads(l)['pmcid'] for l in (H/'eval/public_sentences_run1.jsonl').read_text(encoding='utf-8').splitlines()}|set(json.load(open(H/'eval/source_docs_run1.json')))
q='("pulmonary embolism" AND ("D-dimer" OR "CT pulmonary angiography" OR "computed tomography pulmonary angiography")) AND PUB_TYPE:"Case Reports" AND LICENSE:"cc by" AND OPEN_ACCESS:y AND FIRST_PDATE:[2022-01-01 TO 2025-12-31]'
u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode(dict(query=q,format='json',pageSize=100))
hits=None
for _try in range(5):
    try:
        hits=json.load(urllib.request.urlopen(u,timeout=40))['resultList']['result']; break
    except Exception:
        time.sleep(10)
assert hits
docs={}
for h in hits:
    p=h.get('pmcid')
    if not p or p in seen: continue
    try: x=urllib.request.urlopen(f'https://www.ebi.ac.uk/europepmc/webservices/rest/{p}/fullTextXML',timeout=40).read()
    except Exception: continue
    r=ET.fromstring(x); href=' '.join(v for e in r.iter('license') for k,v in e.attrib.items() if 'href' in k); ltext=' '.join(''.join(e.itertext()) for e in r.iter('license'))[:300]
    if not re.search(r'creativecommons\.org/licenses/by/',href+' '+ltext): continue
    if re.search(r'by-nc|by-nd',href+' '+ltext,re.I): continue
    secs=[(''.join(s.find('title').itertext()) if s.find('title') is not None else '',' '.join(''.join(q2.itertext()) for q2 in s.findall('.//p'))) for s in r.findall('.//body/sec')]
    t=' '.join(b for n,b in secs if re.search('case|patient|present',n,re.I))
    if len(t)<800: continue
    docs[p]=dict(license=href[:80],text=t,title=h.get('title')); time.sleep(.2)
    if len(docs)>=24: break
TARGET=re.compile(r'pulmonary embol|\bPE\b|d-?\s?dimer|ctpa|ct pulmonary|pulmonary angiogra|filling defect|\bdvt\b|deep ve|perfusion scan|v/q',re.I)
rows=[]
for p,d in docs.items():
    for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])',d['text']):
        s=s.strip()
        if 25<=len(s)<=320: rows.append(dict(pmcid=p,sentence=s,target=bool(TARGET.search(s))))
rng=random.Random(202611052)
T=[r for r in rows if r['target']];O=[r for r in rows if not r['target']]
rng.shuffle(T);rng.shuffle(O)
pick=T[:50]+O[:15]; rng.shuffle(pick)
for i,r in enumerate(pick): r['id']=i
(H/'eval/public_sentences.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in pick)+'\n',encoding='utf-8')
(H/'eval/source_docs.json').write_text(json.dumps({p:dict(license=d['license'],title=d['title']) for p,d in docs.items()},ensure_ascii=False,indent=0),encoding='utf-8')
print(len(hits),len(docs),len(rows),len(T),len(O),len(pick))
for r in pick: print(r['id'],'|',r['sentence'][:300])
