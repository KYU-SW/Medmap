"""테스트가 결함을 잡는지 임시 사본에서 확인(원본 무수정). 결과 outputs/mutation_results.json"""
import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).parent
M={'future_visible':('hybrid/temporal.py','e.available_at <= as_of\n','True\n'),
'unknown_time_visible':('hybrid/temporal.py','if e.available_at is not None and e.available_at <= as_of','if (e.available_at is None or e.available_at <= as_of)'),
'correction_retroactive':('hybrid/temporal.py','corrected = {e.supersedes for e in usable if e.supersedes}','corrected = {e.supersedes for e in items if e.supersedes}'),
'no_record_means_not_ordered':('hybrid/temporal.py','    if not ev:\n        return TestStatus.UNKNOWN','    if not ev:\n        return TestStatus.NOT_ORDERED'),
'leak_guard_off':('hybrid/adapters.py','    if leakage_violations(inp):','    if False:'),
'model_candidate_usable':('hybrid/schema.py','if self.asserted_by == AssertedBy.MODEL_EXTRACTED and not self.provenance.physician_confirmed:','if False:'),
'ruled_out_usable':('hybrid/schema.py','if self.status in (DxStatus.RULED_OUT_DIAGNOSIS, DxStatus.HISTORICAL_DIAGNOSIS, DxStatus.UNKNOWN):','if False:'),
'restricted_sent':('hybrid/adapters.py','if inp.data_class == DataClass.RESTRICTED and not (self.policy.is_local_runtime and self.policy.restricted_data_approval_ref):','if False:'),
'llm_quote_unchecked':('hybrid/adapters.py','if not quote or quote not in inp.evidence.text:','if False:'),
'hybrid_conflict_ignored':('hybrid/adapters.py','if len(dirs) > 1:','if False:'),
'abstain_removed_from_denominator':('hybrid/metrics.py','"coverage": _d(len(ans), n)','"coverage": _d(len(ans), len(ans))'),
'all_items_uses_answered':('hybrid/metrics.py','"direction_agreement_all_items": _d(correct, n)','"direction_agreement_all_items": _d(correct, len(ans))'),
'kappa_unweighted':('hybrid/metrics.py','w = abs(i - j) / (k - 1)','w = float(i != j)'),
'ontology_promoted':('hybrid/knowledge.py','if self.source_kind in ("ONTOLOGY", "COOCCURRENCE"):','if False:'),
'proposed_used':('hybrid/knowledge.py','self.review_status in ("SOURCE_QUOTE_CHECKED", "CLINICIAN_REVIEWED")','True'),
'ai_confirm_without_record':('hybrid/diagnosis_input.py','    if not confirm_ref:','    if False:'),
'approval_skipped':('hybrid/er_reason.py','    check_approval(approval)\n','    pass\n'),
'rationale_in_input':('hybrid/er_reason.py','inputs.append(ReasonerInput(iid, key, h, e, t["One_Sentence_Extracted"], prior','inputs.append(ReasonerInput(iid, key, h, e, t["One_Sentence_Extracted"] + r["rationale"], prior'),
'future_prior_in_input':('hybrid/er_reason.py','for i in range(1, step) if','for i in range(1, 6) if'),
'graph_negative_supports':('hybrid/adapters.py','        if e.polarity != Polarity.PRESENT:\n            return abstain(inp.item_id, self.name, "NEGATIVE_OR_UNKNOWN_NOT_DEFINED_IN_GRAPH")\n',''),
}
env=dict(os.environ,HYBRID_EXP_ROOT=str(HERE.parent),OMP_NUM_THREADS='1')
res={}
for n,(f,a,b) in M.items():
    with tempfile.TemporaryDirectory() as t:
        d=Path(t)/'c'; shutil.copytree(HERE,d,ignore=shutil.ignore_patterns('outputs','__pycache__','docs'))
        s=(d/f).read_text(encoding='utf-8'); assert s.count(a)==1,n
        (d/f).write_text(s.replace(a,b,1),encoding='utf-8')
        p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests'],cwd=d,env=env,capture_output=True,text=True,timeout=120)
        res[n]='DETECTED' if p.returncode else 'SURVIVED'; print(n,res[n],flush=True)
out=dict(n=len(res),survived=[k for k,v in res.items() if v=='SURVIVED'],results=res,equivalent_note={'ai_confirm_without_record':'동치 변이 — 빈 confirm_ref 는 Provenance 검사가 같은 ValueError 로 거부(이중 방어)'})
(HERE/'outputs/mutation_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8'); print(out['n'],out['survived'])
