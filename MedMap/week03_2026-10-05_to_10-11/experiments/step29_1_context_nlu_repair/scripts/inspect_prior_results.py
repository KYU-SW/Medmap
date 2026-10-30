"""STEP29.1 §1·§2 — STEP29 공식 결과·핵심 수치를 산출 파일에서 다시 읽고, 공식 오류 3건(G3 2·G4 1)을 STEP29 코드(무수정)로 재현. 출력: outputs/prior_results.json"""
import s291_common as S
from clinical_nlu_pipeline import analyze
from evaluator_v4 import violations

v = S.load_json(S.S29_DIR / "outputs/step29_verdict.json")
x = S.load_json(S.S29_DIR / "outputs/exploratory_v2.json")
rep = {}
for t in ("고혈압이 있고 머리가 아파요", "기침약을 먹었는데 기침이 계속 나요", "입맛은 괜찮아요"):
    o = analyze(t, "NLU_P5")
    ex = [m["canonical_id"] for m in o["mentions"] if m["status"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")]
    rep[t] = {"mentions": [(m["raw_span"], m["status"], m["canonical_id"], m["assertion"]) for m in o["mentions"]], "v4_sentence_violations": violations(t, ex)}
out = {"STEP29": {k: v[k] for k in ("STEP29_RESULT", "STEP30_READINESS", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE_RESULT", "TEMPORALITY_RESULT", "EXPERIENCER_RESULT",
                                     "CONCEPT_MAPPING_RESULT", "SEMANTIC_VIOLATIONS", "UNSUPPORTED_CONCEPT_PRESERVATION", "RAW_PRESERVATION", "CPU_P95_MS")},
       "STEP29_exploratory_v2": x["STEP29_RESULT_EXPLORATORY_V2"], "official_error_reproduction": rep}
S.dump_json(S.OUT / "prior_results.json", out)
print(S.dumps(out))
