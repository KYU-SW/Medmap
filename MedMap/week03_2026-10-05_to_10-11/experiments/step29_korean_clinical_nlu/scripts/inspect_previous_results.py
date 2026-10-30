"""STEP29 §1 — STEP28.7·28.8 기준값을 산출 파일에서 다시 읽어 기록(손으로 옮기지 않음). 출력: outputs/previous_results.json"""
import s29_common as S

v = S.load_json(S.S288_DIR / "outputs/step28_8_verdict.json")
v7 = S.load_json(S.S287_DIR / "outputs/step28_7_verdict.json")
x7 = S.load_json(S.S287_DIR / "outputs/exploratory_v2.json")
out = {"STEP28_7": {"official": v7["STEP28_7_RESULT"], "step29": v7["STEP29_ENTRY"], "exploratory_v2": x7["STEP28_7_RESULT_EXPLORATORY_V2"]},
       "STEP28_8": {k: v[k] for k in ("STEP28_8_RESULT", "STEP29_READINESS", "SUPPORTED_AUTO_PRECISION", "SUPPORTED_AUTO_COVERAGE", "SUBSTRING_FALSE_MATCH",
                                       "WEAK_NEGATIVE_AUTO_MAP", "SEMANTIC_DISTINCTION_VIOLATIONS", "WRONG_CANDIDATE_DISPLAY", "RAW_PRESERVATION")},
       "p5_source_sha256": {p.name: S.sha256(p) for p in (S.S288_DIR / "scripts/policies.py", S.S288_DIR / "scripts/repair_korean_matching.py", S.S288_DIR / "scripts/evaluator.py")}}
S.dump_json(S.OUT / "previous_results.json", out)
print(S.dumps(out))
