"""P1 수정을 되돌리면 P1 테스트가 잡는지 임시 사본으로 확인(원본 무수정). outputs/mutation_results_p1.json"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).parent
PS, PL, CC, KB = "hybrid2_p1/parser.py", "hybrid2_p1/pipeline.py", "hybrid2_p1/clinical_context.py", "knowledge/evidence_relations_p1.json"
M = {
    "phase_rule_removed": (KB, '{"when": {"clinical_phase": ["CONFIRMED_PE", "UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP"]}, "direction": "NOT_APPLICABLE"', '{"when": {"clinical_phase": ["__NEVER__"]}, "direction": "NOT_APPLICABLE"'),
    "weaken_without_phase": (KB, '{"when": {"clinical_phase": ["SUSPECTED_ACUTE_PE_EVALUATION"], "pretest": ["LOW", "INTERMEDIATE"]}, "direction": "WEAKEN"', '{"when": {"pretest": ["LOW", "INTERMEDIATE"]}, "direction": "WEAKEN"'),
    "recurrence_as_weaken": (KB, '{"when": {"clinical_phase": ["RECURRENCE_EVALUATION"]}, "direction": "UNCERTAIN"', '{"when": {"clinical_phase": ["__NEVER__"]}, "direction": "UNCERTAIN"'),
    "poc_rule_removed": (KB, '{"when": {"assay": ["POINT_OF_CARE"], "pretest": ["INTERMEDIATE"]}', '{"when": {"assay": ["__NEVER__"], "pretest": ["INTERMEDIATE"]}'),
    "pipeline_skips_phase": (PL, 'if "clinical_phase" in rel.get("requires_context", ()):', 'if False:'),
    "unknown_phase_passed_as_value": (PL, 'c["clinical_phase"] = None if cc["phase"] == CC.UNKNOWN else cc["phase"]', 'c["clinical_phase"] = CC.SUSPECTED'),
    "case_signals_retroactive": (PL, 'if d.available_at is None or doc.available_at is None or d.available_at > doc.available_at:', 'if False:'),
    "case_signals_ignored": (PL, 'c2 = {**ctx, "case_phase_signals": self._case_phase_signals(vis, d)}', 'c2 = dict(ctx)'),
    "hypothesis_status_ignored": (CC, 'elif hypothesis_status == "CONFIRMED_DIAGNOSIS":', 'elif False:'),
    "inconclusive_treated_suspected": (CC, 'elif sig["inconclusive"]:', 'elif False:'),
    "negated_treatment_counts": (CC, 'return any(not R_TX_NOT_GIVEN_BEFORE.search(s[:m.start()]) and not R_TX_NOT_GIVEN_AFTER.search(s[m.end():]) for m in R_TX.finditer(s))', 'return bool(R_TX.search(s))'),
    "negated_recurrence_counts": (CC, 'and not R_RECUR_ABSENT.search(s))', ')'),
    "value_sets_phase": (CC, '    phase = None\n    if recur:', '    phase = CONFIRMED if re.search(r"\\d", s) else None\n    if recur:'),
    "neg_scope_off": (PS, 'scope = _neg_scope(before[negs[-1].end():])', 'scope = "NEGATED"'),
    "neg_scope_or_list_off": (PS, 'if any(m.group(0).lower() in ("or", "nor") for m in seps):', 'if False:'),
    "neg_scope_unclear_off": (PS, 'return "NEGATED" if all(len(x.split()) <= 4 for x in conj) else "UNCLEAR"', 'return "ENDED"'),
    "adverb_gap_off": (PS, 'r"\\b(was|were|is|are|has been|had been|have been)?\\s*" + _ADV + r"(not (?:seen', 'r"\\b(was|were|is|are|has been|had been|have been)?\\s*(not (?:seen'),
    "test_result_negation_off": (PS, 'if R_NEG_POST_TEST.match(after):', 'if False:'),
    "prior_exclusion_off": (PS, 'if R_PRIOR_EXCLUSION.search(t):', 'if False:'),
    "result_after_order_off": (PS, 'if m_order and not R_RESULT_AFTER_ORDER.search(t[m_order.end():]):', 'if m_order:'),
    "order_ignored": (PS, 'if m_order and not R_RESULT_AFTER_ORDER.search(t[m_order.end():]):', 'if False:'),
    "to_show_counts_as_result": (PS, 'r"(?<!to )\\b(?:returned', 'r"\\b(?:show|returned'),
    "decision_order_cue_removed": (PS, '|(?:decision (?:was made )?to|decided to)\\s+(?:proceed with|perform|obtain|order|get)|to proceed with)', ')'),
    "purpose_cues_removed": (PS, '|to investigate|to confirm|', '|'),
    "legend_counts_as_study": (PL, 'm[3] == "CTPA_STUDY" and not _abbreviation_legend(c.sentence, m[0], m[1]) for m', 'm[3] == "CTPA_STUDY" for m'),
    "v3b_conflict_ignored": (PL, 'return {"finding": "CTPA_NORMAL", "v3b": ag} if not ag["conflict"] else {"reason": "EXTRACTOR_CONFLICT", "v3b": ag}', 'return {"finding": "CTPA_NORMAL", "v3b": ag}'),
}
env = dict(os.environ, HYBRID_EXP_ROOT=str(H.parent), OMP_NUM_THREADS="1")
res = {}
for n, (f, a, b) in M.items():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "c"
        shutil.copytree(H, d, ignore=shutil.ignore_patterns("outputs", "__pycache__", "docs", "eval", "patches"))
        (d / "outputs").mkdir()
        s = (d / f).read_text(encoding="utf-8")
        assert s.count(a) == 1, n
        (d / f).write_text(s.replace(a, b, 1), encoding="utf-8")
        p = subprocess.run([sys.executable, "-B", "run_regression_p1.py"], cwd=d, env=env, capture_output=True, text=True, timeout=180)
        res[n] = "DETECTED" if p.returncode else "SURVIVED"
        print(n, res[n], flush=True)
out = dict(n=len(res), survived=[k for k, v in res.items() if v == "SURVIVED"], results=res)
(H / "outputs/mutation_results_p1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(out["n"], out["survived"])
