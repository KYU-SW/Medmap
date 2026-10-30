"""STEP29 §12 — 검사기 v4 정답 대조(STEP28.8 정답 쌍 재사용) + 필수 사례 → outputs/evaluator_v4_validation.json(SHA 고정)."""
import s29_common as S
from evaluator_v4 import EVALUATOR_VERSION, evaluator_sha, violations
from validate_evaluator import MUST_FLAG, MUST_PASS, gold_pairs

V4_FLAG = MUST_FLAG + [("토할 것 같아요", ["vomiting"]), ("손이 떨려요", ["chills"]), ("심장 부분", ["palpitations"])]
V4_PASS = MUST_PASS + [("추워서 몸이 덜덜 떨려요", ["chills"]), ("손이 떨려요", []), ("토할 것 같다가 결국 토했어요", ["nausea", "vomiting"]),
                       ("심장이 두근거려요", ["palpitations"])]


def main():
    pairs = gold_pairs()
    fp = [(s, t, cs, violations(t, cs)) for s, t, cs in pairs if violations(t, cs)]
    mf = [(t, cs) for t, cs in V4_FLAG if not violations(t, cs)]
    mp = [(t, cs, violations(t, cs)) for t, cs in V4_PASS if violations(t, cs)]
    ok = not fp and not mf and not mp
    out = {"EVALUATOR_FIXED": "PASS" if ok else "FAIL", "evaluator_version": EVALUATOR_VERSION, "evaluator_sha256": evaluator_sha(),
           "gold_pairs": len(pairs), "gold_pairs_flagged": len(fp), "examples": fp[:20], "must_flag_missed": mf, "must_pass_flagged": mp,
           "note": "정답 쌍 = STEP28.8 과 같음(합성·감사 표현, 사람 검증 임상 Gold 아님). 필수 사례 = 노출 사례"}
    S.dump_json(S.OUT / "evaluator_v4_validation.json", out)
    print(S.dumps({k: out[k] for k in ("EVALUATOR_FIXED", "gold_pairs", "gold_pairs_flagged", "must_flag_missed", "must_pass_flagged")}))
    for e in fp[:10]:
        print(" FP", e)


if __name__ == "__main__":
    main()
