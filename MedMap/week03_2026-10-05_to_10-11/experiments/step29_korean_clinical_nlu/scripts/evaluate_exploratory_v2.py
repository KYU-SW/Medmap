"""STEP29 탐색 v2(EXPLORATORY_POST_HOC — 공식 평가 결과를 본 뒤 작성, 판정에 쓰지 않음). 동결 파일은 바꾸지 않고 실행 중에만 덮어쓴다.

사후 발견(공식 1회 평가 후):
 (a) G3 2건은 검사기 v4 의 문장 단위 적용 결함 — NLU 가 '고혈압'(NON)·'머리 통증', '기침약'(NON)·'기침'을 올바로 분리했는데 문장에 '고혈압'·'기침약'이 있어 위반.
     v2 검사: v4 규칙을 mention 단위(unit_text + 그 mention 의 EXISTING concept·표시 후보)로 적용.
 (b) G4 1건 '입맛은 괜찮아요'(gold decreased_appetite absent) → PRESENT: 평가형 술어 '괜찮다' 를 부정으로 보지 않음.
     v2 규칙: 부정 표지가 없고 '괜찮' 이 있으면 ABSENT(EVALUATIVE_NEGATION).
지표(NLU_P5 와 같은 정의, 주요 지표만) → outputs/exploratory_v2.json
"""
from __future__ import annotations

import json

import clinical_nlu_pipeline as PL
import negation_scope as NS
import s29_common as S
from contract_check import check, load
from evaluator_v4 import violations

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
EXP_ASSERT = {"present": "PRESENT", "absent": "ABSENT", "uncertain": "POSSIBLE", "historical": "PRESENT"}
_orig = NS.assertion


def assertion_v2(toks):
    a, b = _orig(toks)
    if a == "PRESENT" and any(t.form == "괜찮" for t in toks):
        return "ABSENT", "EVALUATIVE_NEGATION:괜찮"
    return a, b


def mention_viol(o):
    return sum(bool(violations(m.get("unit_text") or m["raw_span"], ([m["canonical_id"]] if m["status"] in EXISTING else []) + list(m.get("display") or [])))
               for m in o["mentions"])


def metrics(an):
    con = load()["contracts"]
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    regg = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    g3s = g3m = g4 = 0
    failed = 0
    for c in con:
        o = an(c["text"])
        g3s += bool(violations(c["text"], [m["canonical_id"] for m in o["mentions"] if m["status"] in EXISTING] + [x for m in o["mentions"] for x in (m.get("display") or [])]))
        g3m += mention_viol(o) > 0
        e = check(c, o)
        failed += bool(e)
        g4 += sum(1 for x in e if x["type"] == "NEGATION" and x.get("unsafe"))
    n = mt = aok = 0
    ra = rc = 0
    for r in pilot:
        o = an(r["text_ko"])
        g3s += bool(violations(r["text_ko"], [m["canonical_id"] for m in o["mentions"] if m["status"] in EXISTING]))
        g3m += mention_viol(o) > 0
        ex = [m for m in o["mentions"] if m["status"] in EXISTING]
        used = set()
        for g in json.loads(r["gold_mentions"] or "[]"):
            if g["concept"] not in models:
                continue
            n += 1
            i = next((k for k, m in enumerate(ex) if k not in used and m["canonical_id"] == g["concept"]), None)
            if i is None:
                continue
            used.add(i)
            mt += 1
            aok += ex[i]["assertion"] == EXP_ASSERT.get(g.get("status"), "PRESENT")
            g4 += g.get("status") == "absent" and ex[i]["assertion"] == "PRESENT" and ex[i]["model_input"]["polarity"] == "POSITIVE"
        if r["text_ko"] in regg and ex:
            ra += 1
            rc += ex[0]["canonical_id"] == regg[r["text_ko"]]
    for t in sil + wn:
        o = an(t)
        g3s += bool(violations(t, [m["canonical_id"] for m in o["mentions"] if m["status"] in EXISTING]))
        g3m += mention_viol(o) > 0
    return {"G3_sentence_level(v4 공식 방식)": g3s, "G3_mention_level(v2)": g3m, "G4_neg_safety_errors": g4, "contract_failed_cases": failed,
            "pilot_retention": S.rnd(mt / n), "pilot_assertion_agreement": S.rnd(aok / mt), "reg_precision": S.rnd(rc / ra), "reg_coverage": S.rnd(ra / len(regg))}


def main():
    base = metrics(lambda t: PL.analyze(t, "NLU_P5"))
    NS.assertion = assertion_v2
    PL.assertion = assertion_v2
    v2 = metrics(lambda t: PL.analyze(t, "NLU_P5"))
    off = S.load_json(S.OUT / "step29_verdict.json")
    hard = dict(off["hard_gates"])
    hard["G3"] = "PASS" if v2["G3_mention_level(v2)"] == 0 else "FAIL"
    hard["G4"] = "PASS" if v2["G4_neg_safety_errors"] == 0 else "FAIL"
    soft = off["soft_gates"]
    allhard = all(v == "PASS" for v in hard.values())
    verdict = ("REGRESSION" if not allhard else "NLU_FEASIBLE" if all(v == "PASS" for v in soft.values()) else "PARTIAL_IMPROVEMENT")
    out = {"label": "EXPLORATORY_POST_HOC(공식 판정 아님)", "rules": __doc__, "NLU_P5_official_rescored": base, "NLU_P5_v2": v2, "hard_gates_v2": hard,
           "soft_gates(공식 값 재사용 — v2 로 재계산 안 함)": soft, "STEP29_RESULT_EXPLORATORY_V2": verdict,
           "STEP30_READINESS_EXPLORATORY_V2": "GO_FOR_RESEARCH" if verdict == "NLU_FEASIBLE" else "CONDITIONAL_GO" if allhard else "NO_GO"}
    S.dump_json(S.OUT / "exploratory_v2.json", out)
    print(S.dumps({k: out[k] for k in ("NLU_P5_official_rescored", "NLU_P5_v2", "hard_gates_v2", "STEP29_RESULT_EXPLORATORY_V2", "STEP30_READINESS_EXPLORATORY_V2")}))


if __name__ == "__main__":
    main()
