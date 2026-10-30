"""STEP28.8 §2 — 검사기 v3 를 정책 평가 전에 정답 세트와 대조하고 SHA 를 고정한다(LLM 없음).

정답 쌍(텍스트, 정답 concept 집합) — '정답 연결을 위반으로 판정하지 않는가':
 PILOT_GOLD274  STEP21 pilot_gold.csv gold_mentions 의 concept 전부(합성·Claude 작성, 사람 검증 아님 — REGRESSION168 포함)
 STEP23_TRAIN   expanded_train_expressions.csv(1,119, canonical_id — STEP22/23 감사 VALID)
 STEP21_DICT    dictionary_expressions.csv(294, concept_id)
 STEP23_T20_C57 target20·confuser57 표현(canonical_id)
필수 단위 사례(지시문 §2): 위반이어야 함 = 코피→hemoptysis · 코피→hematemesis · 토했어요→nausea · 떨림→chills(+ 기침 억제제→cough · 고혈압→dizziness)
                          위반 아님 = 토할 것 같아요→nausea · 몸이 덜덜 떨려요→chills · 발열→fever · 두통→pain
PASS = 정답 쌍 위반 0 AND 필수 위반 사례 전부 탐지 AND 필수 정상 사례 위반 0. v1(STEP28.7 공식)·v2 의 같은 지표를 함께 기록.
출력: outputs/evaluator_validation.json
"""
from __future__ import annotations

import json

import s288_common as S
from evaluator import EVALUATOR_VERSION, evaluator_sha, violations

MUST_FLAG = [("코피", ["hemoptysis"]), ("코피", ["hematemesis"]), ("코피가 나요", ["hemoptysis"]), ("토했어요", ["nausea"]), ("떨림", ["chills"]),
             ("기침 억제제", ["cough"]), ("고혈압", ["dizziness"])]
MUST_PASS = [("토할 것 같아요", ["nausea"]), ("몸이 덜덜 떨려요", ["chills"]), ("발열", ["fever"]), ("두통", ["pain"]), ("코피가 나요", []),
             ("토했어요", ["vomiting"]), ("메스꺼워요", ["nausea"])]


def gold_pairs():
    out = []
    for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv"):
        cs = sorted({m["concept"] for m in json.loads(r["gold_mentions"] or "[]")})
        out.append(("PILOT_GOLD274", r["text_ko"], cs))
    out += [("STEP23_TRAIN", r["expression"], [r["canonical_id"]]) for r in S.read_csv(S.S23_DIR / "data/expanded_train_expressions.csv")]
    out += [("STEP21_DICT", r["expression"], [r["concept_id"]]) for r in S.read_csv(S.S21_DIR / "data/dictionary_expressions.csv")]
    for f in ("target20_expressions.csv", "confuser57_expressions.csv"):
        out += [("STEP23_T20_C57", r["expression"], [r["canonical_id"]]) for r in S.read_csv(S.S23_DIR / "data" / f)]
    return out


def main():
    sys_path = str(S.S287_DIR / "scripts")
    import importlib
    import sys
    sys.path.insert(0, sys_path)
    v1 = importlib.import_module("evaluate_mapping_safety").violations
    v2 = importlib.import_module("evaluate_exploratory_v2").violations_v2
    pairs = gold_pairs()
    res = {}
    for name, fn in (("v1_step28_7_official", v1), ("v2_step28_7_exploratory", v2), (EVALUATOR_VERSION, violations)):
        fp = [(src, t, cs, fn(t, cs)) for src, t, cs in pairs if fn(t, cs)]
        mf = [(t, cs) for t, cs in MUST_FLAG if not fn(t, cs)]
        mp = [(t, cs, fn(t, cs)) for t, cs in MUST_PASS if fn(t, cs)]
        res[name] = {"gold_pairs": len(pairs), "gold_pairs_flagged(false_violation)": len(fp), "examples": fp[:15],
                     "must_flag_missed": mf, "must_pass_flagged": mp, "PASS": not fp and not mf and not mp}
    out = {"EVALUATOR_FIXED": "PASS" if res[EVALUATOR_VERSION]["PASS"] else "FAIL", "evaluator_version": EVALUATOR_VERSION, "evaluator_sha256": evaluator_sha(),
           "gold_sources": {s: sum(1 for x in pairs if x[0] == s) for s in ("PILOT_GOLD274", "STEP23_TRAIN", "STEP21_DICT", "STEP23_T20_C57")},
           "gold_note": "합성·Claude 작성 및 STEP22/23 감사 표현 — 사람 검증 임상 Gold 아님. 이미 노출된 사례는 단위·회귀 테스트일 뿐",
           "results": res}
    S.dump_json(S.OUT / "evaluator_validation.json", out)
    print(S.dumps({k: {x: v[x] for x in ("gold_pairs_flagged(false_violation)", "must_flag_missed", "must_pass_flagged", "PASS")} for k, v in res.items()}))
    for e in res[EVALUATOR_VERSION]["examples"]:
        print("  v3 FP", e)


if __name__ == "__main__":
    main()
