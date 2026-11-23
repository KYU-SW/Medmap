"""이미 노출된 1·2차 문장을 P1·P2 로 재생. 회귀 확인 전용, 독립 평가 아님. 기존 결과 파일은 읽기만. 결과 outputs/p2_replay_regression.json
조건: P1_ASSUMED(P1 실행 가정, 기준선) / P2_CLINICAL_NO_CONTEXT(기본 경로) / P2_CLINICAL_UNSOURCED(같은 가정값, 출처 미지정) / P2_SYNTHETIC(가정값 명시 모드)"""
import json
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).parents[1]
sys.path.insert(0, str(H))
from hybrid2_p1 import pipeline as P1  # noqa: E402
from hybrid2_p2 import pipeline as P2  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, Provenance  # noqa: E402

ASSUMED = {"pretest": "INTERMEDIATE", "suspected": True}
COND = {"P1_ASSUMED": (P1, ASSUMED), "P2_CLINICAL_NO_CONTEXT": (P2, {}), "P2_CLINICAL_UNSOURCED": (P2, ASSUMED), "P2_SYNTHETIC": (P2, {**ASSUMED, "mode": "SYNTHETIC_ASSUMPTION"})}
SETS = {"run1_exposed": ("eval/public_sentences_run1.jsonl", "eval/gold_public_run1.json"), "run2_exposed": ("eval/public_sentences.jsonl", "eval/gold_public.json")}
WEAK_F, SUP_F = {"DDIMER_NORMAL", "CTPA_NORMAL", "PERFUSION_SCAN_NORMAL"}, {"CTPA_REPORTS_PE", "PROXIMAL_DVT_ON_ULTRASOUND"}
INTENDED = {"pretest": "C", "suspected": "C", "clinical_phase": "B", "ddimer_assay": "A", "ddimer_cutoff": "A"}
h = DiagnosisAssertion("h", "c", "Pulmonary embolism", DxStatus.WORKING_DIAGNOSIS, AssertedBy.SIMULATED, 0.0, Provenance("t", "t", DataClass.PUBLIC_OPEN), concept_id="DX:Pulmonary embolism")


def run(P, ctx, S, gold):
    rows, dirs, wrong = {}, Counter(), []
    for r in S:
        want = {gold.get(str(r["id"]), {}).get(k) for k in ("finding", "finding2")} - {None}
        outs = [P.assess_record(x, h, ctx) for x in P.extract(r["sentence"], "")]
        rows[r["id"]] = [{k: o.get(k) for k in ("extracted_surface", "concept", "assertion", "direction", "relation_id", "abstain_reason", "missing_context")} for o in outs]
        for o in outs:
            dirs[o["direction"]] += 1
            if (o["direction"] == "WEAKEN" and not want & WEAK_F) or (o["direction"] == "SUPPORT" and not want & SUP_F):
                wrong.append({"id": r["id"], "direction": o["direction"], "relation": o["relation_id"]})
    return rows, {"n_outputs": sum(dirs.values()), "directions": dict(dirs), "wrong_direction": wrong}


res = {"label": "REGRESSION_REPLAY_ON_EXPOSED_SENTENCES_NOT_INDEPENDENT_EVALUATION", "conditions": {k: v[1] for k, v in COND.items()}, "sets": {}}
for name, (sf, gf) in SETS.items():
    S = [json.loads(x) for x in (H / sf).read_text(encoding="utf-8").splitlines()]
    gold = json.loads((H / gf).read_text(encoding="utf-8"))["items"]
    runs = {c: run(P, ctx, S, gold) for c, (P, ctx) in COND.items()}
    base = runs["P1_ASSUMED"][0]
    changes = {}
    for c in COND:
        if c == "P1_ASSUMED":
            continue
        ch = []
        for r in S:
            for a, b in zip(base[r["id"]], runs[c][0][r["id"]]):
                if (a["direction"], a["relation_id"], a["abstain_reason"], a["assertion"]) != (b["direction"], b["relation_id"], b["abstain_reason"], b["assertion"]):
                    cause = sorted({INTENDED.get(k, "?") for k in (b["missing_context"] or [])}) or (["B"] if b["direction"] == "NOT_APPLICABLE" else ["?"])
                    ch.append({"id": r["id"], "surface": a["extracted_surface"], "relation": b["relation_id"] or a["relation_id"], "before": a["direction"], "after": b["direction"],
                               "missing_context": b["missing_context"], "assertion_changed": a["assertion"] != b["assertion"], "cause": cause, "sentence": r["sentence"][:200]})
            if len(base[r["id"]]) != len(runs[c][0][r["id"]]):
                ch.append({"id": r["id"], "error": "OUTPUT_COUNT_CHANGED"})
        changes[c] = ch
    res["sets"][name] = {"n_sentences": len(S), "n_documents": len({r["pmcid"] for r in S}), "summary": {c: v[1] for c, v in runs.items()}, "changed_vs_P1": changes}
p1 = json.loads((H / "outputs/p1_replay_regression.json").read_text(encoding="utf-8"))
res["p1_baseline_matches_stored"] = {n: res["sets"][n]["summary"]["P1_ASSUMED"]["directions"] == p1["sets"][n]["after"]["directions"] for n in SETS}
(H / "outputs/p2_replay_regression.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for n, s in res["sets"].items():
    print("==", n, s["n_sentences"], "문장", s["n_documents"], "문서")
    for c, v in s["summary"].items():
        print(f"  {c}: {v['n_outputs']} {v['directions']} wrong={v['wrong_direction']}")
    for c, ch in s["changed_vs_P1"].items():
        print(f"  changed {c}: {len(ch)}", [(x.get("id"), x.get("relation"), x.get("before"), x.get("after"), x.get("cause"), x.get("assertion_changed")) for x in ch])
print(res["p1_baseline_matches_stored"])
