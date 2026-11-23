"""이미 노출된 1·2차 문장을 수정 전(hybrid2)·후(hybrid2_p1)로 재생. 회귀 확인 전용, 독립 평가 아님. 기존 결과 파일은 읽기만 한다.
임상 확률·의심 여부는 run_public.py 와 같은 실행 가정. 결과 outputs/p1_replay_regression.json"""
import json
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).parents[1]
sys.path.insert(0, str(H))
from hybrid2 import pipeline as OLD  # noqa: E402
from hybrid2_p1 import pipeline as NEW  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, Provenance  # noqa: E402

PILOT = {"PE_DIAGNOSIS", "DDIMER", "DVT", "CTPA_STUDY", "PERFUSION_SCAN", "FILLING_DEFECT"}
CTX = {"pretest": "INTERMEDIATE", "suspected": True}
WEAK_F = {"DDIMER_NORMAL", "CTPA_NORMAL", "PERFUSION_SCAN_NORMAL"}
SUP_F = {"CTPA_REPORTS_PE", "PROXIMAL_DVT_ON_ULTRASOUND"}
h = DiagnosisAssertion("h", "c", "Pulmonary embolism", DxStatus.WORKING_DIAGNOSIS, AssertedBy.SIMULATED, 0.0, Provenance("t", "t", DataClass.PUBLIC_OPEN), concept_id="DX:Pulmonary embolism")
SETS = {"run1_exposed": ("eval/public_sentences_run1.jsonl", "eval/gold_public_run1.json"), "run2_exposed": ("eval/public_sentences.jsonl", "eval/gold_public.json")}
KEYS = ("extracted_surface", "concept", "assertion", "assertion_cue", "direction", "relation_id", "abstain_reason", "missing_context")


def evaluate(P, S, gold):
    m = dict(n_sentences=len(S), n_documents=len({r["pmcid"] for r in S}))
    g_tot = g_found = asg_tot = asg_ok = extra = f_gold = f_hit = f_extra = 0
    dirs, reasons, asg_err, wrong_w, wrong_s, rows = Counter(), Counter(), [], [], [], {}
    phases, prov_ok, prov_tot = Counter(), 0, 0
    for r in S:
        g = gold.get(str(r["id"]), {})
        recs = P.extract(r["sentence"], "")
        got = {}
        for x in recs:
            if x["link_status"] == "LINKED" and x["concept"] in PILOT:
                got.setdefault(x["concept"], []).append(x["assertion"])
        for c, a in g.get("concepts", {}).items():
            g_tot += 1
            if c in got:
                g_found += 1
                asg_tot += 1
                if a in got[c]:
                    asg_ok += 1
                else:
                    asg_err.append(dict(id=r["id"], concept=c, want=a, got=got[c]))
        extra += sum(c not in g.get("concepts", {}) for c in got)
        out = [P.assess_record(x, h, CTX) for x in recs]
        want_f = {g[k] for k in ("finding", "finding2") if k in g}
        fs = {P.finding_state(x).get("finding") for x in recs} - {None}
        f_gold += len(want_f)
        f_hit += len(want_f & fs)
        f_extra += len(fs - want_f)
        for o in out:
            dirs[o["direction"]] += 1
            if o["abstain_reason"]:
                reasons[o["abstain_reason"]] += 1
            if o["direction"] != "ABSTAIN":
                prov_tot += 1
                prov_ok += bool(o["sources"] and all(s.get("quote") and s.get("url") for s in o["sources"]))
            if o.get("clinical_context"):
                phases[o["clinical_context"]["phase"]] += 1
            if o["direction"] == "WEAKEN" and not (want_f & WEAK_F):
                wrong_w.append(dict(id=r["id"], relation=o["relation_id"], sentence=r["sentence"][:200]))
            if o["direction"] == "SUPPORT" and not (want_f & SUP_F):
                wrong_s.append(dict(id=r["id"], relation=o["relation_id"], sentence=r["sentence"][:200]))
        rows[r["id"]] = [{k: o[k] for k in KEYS} | {"clinical_context": o.get("clinical_context")} for o in out]
    m.update(n_outputs=sum(dirs.values()), directions=dict(dirs), n_abstain=dirs["ABSTAIN"], n_nonabstain=sum(dirs.values()) - dirs["ABSTAIN"], abstain_reasons=dict(reasons),
             concept_mentions_gold=g_tot, concept_found=g_found, unsupported_mapping=extra, assertion_compared=asg_tot, assertion_agree=asg_ok, assertion_mismatch=asg_err,
             relation_paths_gold=f_gold, relation_paths_found=f_hit, relation_paths_extra=f_extra, wrong_weaken=wrong_w, wrong_support=wrong_s, provenance=f"{prov_ok}/{prov_tot}", clinical_phase_outputs=dict(phases))
    return m, rows


old_rows = {}
res = {"label": "REGRESSION_REPLAY_ON_EXPOSED_SENTENCES_NOT_INDEPENDENT_EVALUATION", "execution_context_assumed": CTX, "sets": {}}
for name, (sf, gf) in SETS.items():
    S = [json.loads(x) for x in (H / sf).read_text(encoding="utf-8").splitlines()]
    gold = json.loads((H / gf).read_text(encoding="utf-8"))["items"]
    mo, ro = evaluate(OLD, S, gold)
    mn, rn = evaluate(NEW, S, gold)
    old_rows[name] = ro
    changes = []
    for r in S:
        a, b = ro[r["id"]], rn[r["id"]]
        for x, y in zip(a, b):
            if any(x[k] != y[k] for k in KEYS):
                changes.append(dict(id=r["id"], surface=x["extracted_surface"], concept=x["concept"], before={k: x[k] for k in KEYS[2:]}, after={k: y[k] for k in KEYS[2:]}, clinical_context=y["clinical_context"], sentence=r["sentence"][:220]))
        if len(a) != len(b):
            changes.append(dict(id=r["id"], error="OUTPUT_COUNT_CHANGED", before=len(a), after=len(b)))
    res["sets"][name] = dict(before=mo, after=mn, changed_outputs=changes)
stored = json.loads((H / "outputs/public_linking_results_run2.json").read_text(encoding="utf-8"))
b2 = res["sets"]["run2_exposed"]["before"]
_K = ("extracted_surface", "direction", "relation_id", "abstain_reason", "missing_context")
res["baseline_matches_stored_run2"] = dict(directions=b2["directions"] == stored["directions"], abstain_reasons=b2["abstain_reasons"] == stored["abstain_reasons"],
                                           outputs=all([{k: o[k] for k in _K} for o in x["outputs"]] == [{k: o[k] for k in _K} for o in old_rows["run2_exposed"][x["id"]]] for x in stored["rows"]))
(H / "outputs/p1_replay_regression.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for n, s in res["sets"].items():
    print("==", n)
    for v in ("before", "after"):
        m = s[v]
        print(v, {k: m[k] for k in ("n_sentences", "n_documents", "n_outputs", "directions", "concept_found", "concept_mentions_gold", "unsupported_mapping", "assertion_agree", "assertion_compared", "relation_paths_found", "relation_paths_gold", "relation_paths_extra", "provenance", "clinical_phase_outputs")}, "wrong_W", len(m["wrong_weaken"]), "wrong_S", len(m["wrong_support"]))
    print("changed", len(s["changed_outputs"]))
print(res["baseline_matches_stored_run2"])
