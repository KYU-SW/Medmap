"""구현 결함이 테스트에 잡히는지 임시 사본으로 확인(원본 무수정). outputs/mutation_results.json"""
import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
H=Path(__file__).parent
M={'purpose_treated_as_present':('hybrid2/parser.py','    if c.section in PURPOSE_SECTIONS or R_PURPOSE.search(before):','    if False:'),
'history_treated_as_present':('hybrid2/parser.py','if c.section in HISTORY_SECTIONS or R_HIST.search(before) or','if False and'),
'negation_ignored':('hybrid2/parser.py','    if negs and not R_BREAK.search(before[negs[-1].end():]):','    if False:'),
'order_treated_as_result':('hybrid2/parser.py','    if R_ORDER.search(t):','    if False:'),
'other_person_ignored':('hybrid2/parser.py','    if c.section == "family history" or R_OTHER.search(t):','    if False:'),
'abbrev_pe_always_linked':('hybrid2/pipeline.py','if surface.lower() == "pe" and has_ctpa:','if surface.lower() == "pe":'),
'v3b_conflict_ignored':('hybrid2/pipeline.py','return {"finding": "CTPA_NORMAL", "v3b": ag} if not ag["conflict"] else {"reason": "EXTRACTOR_CONFLICT", "v3b": ag}','return {"finding": "CTPA_NORMAL", "v3b": ag}'),
'dd_window_removed':('hybrid2/pipeline.py','w = _dd_window(t, rec["surface"])','w = t'),
'dd_elevated_supports':('knowledge/evidence_relations.json','"relation": "EVALUATES_HYPOTHESIS",\n   "by_context": [{"when": {}, "direction": "NO_CLEAR_EFFECT"','"relation": "SUPPORTS_HYPOTHESIS",\n   "by_context": [{"when": {}, "direction": "SUPPORT"'),
'filling_defect_supports':('knowledge/evidence_relations.json','"relation": "UNCERTAIN_RELATIONSHIP",\n   "by_context": [{"when": {}, "direction": "UNCERTAIN"','"relation": "SUPPORTS_HYPOTHESIS",\n   "by_context": [{"when": {}, "direction": "SUPPORT"'),
'context_not_required':('hybrid2/relations.py','    if miss:\n        return {"direction": "INSUFFICIENT_EVIDENCE"','    if False:\n        return {"direction": "INSUFFICIENT_EVIDENCE"'),
'graph_edge_gives_support':('hybrid2/pipeline.py','        if out["graph_edges_shown"] and fs["reason"] == "NO_VERIFIED_RELATION":\n            out["abstain_reason"] = "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION"\n        return out','        if out["graph_edges_shown"] and fs["reason"] == "NO_VERIFIED_RELATION":\n            out["direction"] = "SUPPORT"\n        return out'),
'hypothesis_outside_graph_allowed':('hybrid2/pipeline.py','    if not h or h not in LX.lexicon()[1]:','    if False:'),
'quote_check_off':('hybrid2/relations.py','if e["source"] not in src or not e.get("location") or not e.get("quote") or not e.get("summary"):','if False:'),
'modifier_terms_linked':('hybrid2/lexicon.py','    return {k: v for k, v in out.items() if keep[v]}','    return out'),
'future_doc_used':('hybrid2/pipeline.py','vis = T1.visible_evidence(self.items, as_of)','vis = list(self.items)'),
'corrected_doc_kept':('hybrid2/pipeline.py','polarity=Polarity.UNKNOWN, supersedes=doc.supersedes))','polarity=Polarity.UNKNOWN))'),
'pending_treated_as_result':('hybrid2/parser.py','    if R_PEND.search(t):','    if False:')}
env=dict(os.environ,HYBRID_EXP_ROOT=str(H.parent),OMP_NUM_THREADS='1'); res={}
for n,(f,a,b) in M.items():
    with tempfile.TemporaryDirectory() as t:
        d=Path(t)/'c'; shutil.copytree(H,d,ignore=shutil.ignore_patterns('outputs','__pycache__','docs','eval'))
        s=(d/f).read_text(encoding='utf-8'); assert s.count(a)==1,n
        (d/f).write_text(s.replace(a,b,1),encoding='utf-8')
        p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests'],cwd=d,env=env,capture_output=True,text=True,timeout=120)
        res[n]='DETECTED' if p.returncode else 'SURVIVED'; print(n,res[n],flush=True)
out=dict(n=len(res),survived=[k for k,v in res.items() if v=='SURVIVED'],results=res)
(H/'outputs/mutation_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8');print(out['n'],out['survived'])
