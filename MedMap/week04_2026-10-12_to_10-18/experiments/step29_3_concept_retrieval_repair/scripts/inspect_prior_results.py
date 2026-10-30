"""STEP29.3 §1·§18-4 기존 결과 확인 + STEP29.2 baseline 재현. 출력: outputs/baseline_reproduction.json
 1 STEP29.2 공식 판정·post_run_note 존재·SHA(읽기만)  2 STEP29.2 공식 eval_summary(V3_B0·V3_B3 의 HOLDOUT·노출 지표) vs 이번 단계에서 R0·R1 로 다시 계산한 값
   (outputs/dev_policy_metrics.json 또는 eval_summary.json 의 STEP29_2_HOLDOUT·EXPOSED) 비교 — 같으면 REPRODUCED."""
import s293_common as S

KEYS_H = ("CONCEPT_PRECISION", "CONCEPT_COVERAGE", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE", "PUNCTUATION_PAIR_CONSISTENCY", "RESOLUTION_LINKING", "PROPAGATION_ERRORS")
KEYS_X = ("reg_precision", "reg_coverage", "pilot_multi_retention", "pilot_assertion_agreement")


def main():
    off = S.load_json(S.S292_DIR / "outputs/eval_summary.json")["metrics"]
    src = S.OUT / "eval_summary.json" if (S.OUT / "eval_summary.json").exists() else S.OUT / "dev_policy_metrics.json"
    now = S.load_json(src)["metrics"]
    rows = {}
    for p, q in (("R0", "V3_B0"), ("R1", "V3_B3")):
        h = {k: (off[q]["HOLDOUT"][k], now[p]["STEP29_2_HOLDOUT"][k]) for k in KEYS_H}
        x = {k: (off[q]["EXPOSED"][k], now[p]["EXPOSED"][k]) for k in KEYS_X}
        rows[p] = {"step29_2_policy": q, "holdout(official, now)": h, "exposed(official, now)": x,
                   "REPRODUCED": all(a == b for a, b in list(h.values()) + list(x.values()))}
    v = S.load_json(S.S292_DIR / "outputs/step29_2_verdict.json")
    out = {"step29_2_official": {k: v[k] for k in ("STEP29_2_RESULT", "STEP30_READINESS", "SELECTED_POLICY")},
           "step29_2_verdict_sha256": S.sha256(S.S292_DIR / "outputs/step29_2_verdict.json"),
           "post_run_note_exists": (S.S292_DIR / "docs/post_run_note.md").exists(), "recomputed_from": src.name, "comparison": rows}
    S.dump_json(S.OUT / "baseline_reproduction.json", out)
    print(S.dumps({p: r["REPRODUCED"] for p, r in rows.items()}))


if __name__ == "__main__":
    main()
