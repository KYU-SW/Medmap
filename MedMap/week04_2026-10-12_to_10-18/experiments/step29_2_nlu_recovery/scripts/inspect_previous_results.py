"""STEP29.2 §1·§2 — 이전 결과 확인과 실패 원인 재현(읽기만, 원본 무수정). 출력: outputs/prior_results.json
 1 STEP29·STEP29.1 공식 판정·지표(분모·평가 데이터)를 원본 산출물에서 읽는다(손으로 쓰지 않음).
 2 실패 재현(STEP29.1 P5 = nlu_pipeline_v2 'P5' 그대로): 마침표 쌍 6 · 평가형 부정 5 · 검사기 v5 수식어 2 · B4 단독 가드 차단(pilot 274 재계산: 정답/오답 수)."""
from __future__ import annotations

import json

import s292_common as S
import mention_context_validator as MCV
from evaluator_v5 import mention_violations as v5
from nlu_pipeline_v2 import analyze

PAIRS = ["열이 났어요 오늘은 괜찮아요", "열이 났어요. 오늘은 괜찮아요.", "기침이 나요 숨도 차요", "기침이 나요. 숨도 차요.", "어제부터 기침하고 오늘은 열이 나요",
         "기침은 없어요 숨은 차요"]
EVAL = ["머리는 괜찮은데 배가 아파요.", "입맛은 괜찮아요.", "검사 결과는 괜찮아요.", "어제는 배가 아팠어요 오늘은 괜찮아요.", "머리는 괜찮은지 모르겠어요."]
MODS = [("박동성 두통", "pain"), ("회전성 어지럼증", "dizziness")]


def brief(o):
    return [{k: m.get(k) for k in ("raw_span", "status", "canonical_id", "guard_blocked_concept", "assertion", "assertion_basis", "temporality", "experiencer")}
            for m in o["mentions"]]


def main():
    v29 = S.load_json(S.S29_DIR / "outputs/step29_verdict.json")
    v291 = S.load_json(S.S291_DIR / "outputs/step29_1_verdict.json")
    pc = {r["metric"]: r for r in S.read_csv(S.S291_DIR / "outputs/policy_comparison.csv")}
    keys = ("pilot_multi_retention", "pilot_assertion_agreement", "reg_precision", "reg_coverage", "pilot_unsupported_auto", "pilot_unsupported_n")
    official = {"STEP29": {k: v29.get(k) for k in ("STEP29_RESULT", "STEP30_READINESS", "MULTI_SPAN_RETENTION", "CONCEPT_PRECISION", "CONCEPT_COVERAGE")},
                "STEP29_1": {k: v291.get(k) for k in ("STEP29_1_RESULT", "STEP30_READINESS", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE", "CONCEPT_PRECISION",
                                                       "CONCEPT_COVERAGE", "UNSUPPORTED_AUTO_LINK", "RAW_PRESERVATION", "CPU_P95_MS")},
                "STEP29_1_policy_comparison(P1=STEP29 NLU, P5=STEP29.1)": {k: {"P1": pc[k]["P1"], "P5": pc[k]["P5"]} for k in keys if k in pc},
                "denominators": {"pilot_multi_retention": "pilot_gold 274 중 gold mention ≥2(77 concept) 발화의 mention 80",
                                 "reg_precision/coverage": "REGRESSION168(pilot 부분집합) 첫 EXISTING mention, coverage 분모 168",
                                 "pilot_assertion_agreement": "pilot 대응 mention 의 assertion 일치", "pilot_unsupported_auto": "should_link False 발화 28 중 EXISTING 있는 발화"}}
    repro = {"punctuation_pairs": {t: brief(analyze(t, "P5")) for t in PAIRS}, "evaluative": {t: brief(analyze(t, "P5")) for t in EVAL}}
    mods = []
    for t, c in MODS:
        m = {"source_text": t, "raw_span": t, "span_start": 0, "span_end": len(t), "unit_text": t, "source_sentence": t, "status": "EXISTING_CANONICAL", "canonical_id": c}
        mods.append({"text": t, "concept": c, "evaluator_v5_violations": v5(m)})
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    blocked = []
    for r in pilot:
        gset = {g["concept"] for g in json.loads(r["gold_mentions"] or "[]")}
        for x in analyze(r["text_ko"], "P5")["mentions"]:
            if x.get("guard_blocked_concept") and "MODEL_ONLY_NO_CUE" in (x.get("guard_reasons") or []):
                blocked.append({"text": r["text_ko"], "unit": x.get("unit_text"), "raw_span": x["raw_span"], "blocked_concept": x["guard_blocked_concept"],
                                "gold_concepts": sorted(gset), "blocked_was_correct": x["guard_blocked_concept"] in gset})
    out = {"official": official, "reproduction": repro, "evaluator_v5_modifier_check": mods,
           "b4_only_guard_blocks_pilot": {"n": len(blocked), "blocked_correct": sum(b["blocked_was_correct"] for b in blocked),
                                          "blocked_wrong": sum(not b["blocked_was_correct"] for b in blocked), "rows": blocked},
           "note": "재현 = STEP29.1 동결 코드(nlu_pipeline_v2 P5) 그대로 실행. pilot 은 노출 자료(합성 Gold). MCV 규칙 문서: " + (MCV.__doc__ or "")[:120]}
    S.dump_json(S.OUT / "prior_results.json", out)
    print(S.dumps({"official": official, "b4_blocks": {k: v for k, v in out["b4_only_guard_blocks_pilot"].items() if k != "rows"},
                   "mods": mods}))
    for t, ms in repro["punctuation_pairs"].items():
        print(" ", t, [(m["raw_span"], m["canonical_id"], m["assertion"], m["temporality"]) for m in ms])
    for t, ms in repro["evaluative"].items():
        print(" ", t, [(m["raw_span"], m["canonical_id"], m["assertion"], m["assertion_basis"]) for m in ms])


if __name__ == "__main__":
    main()
