"""STEP28.8 §4·§6 오류 분석(평가 후 — 규칙 변경 없음). 출력: outputs/{error_analysis.csv, negative_risk_analysis.csv, error_summary.json}

비증상 위험 원인(사전 순서, STEP28.7 과 같은 틀 + B4): HEAD/NON_TYPE_CUE(질환·약물·치료·검사 접미) → BODY_PART_ONLY → SUBSTRING(경계 비정렬) →
 SPAN_EXTRACTION(구문 2개 이상) → MODEL_B4(STEP27 모델 자동수락) → SYMPTOM_TERM_WEAK_LABEL_CONFLICT(STEP28.6 두 작성자 모두 증상형) → OTHER
"""
import collections
import json

import s288_common as S


def main():
    rows = S.read_csv(S.DATA / "eval_rows.csv")
    links = {S.ko_key(r["korean"]): r for r in S.read_csv(S.S286_DIR / "data/ontology_links.csv")}
    bp = set(S.S28.body_parts())
    neg = []
    for r in rows:
        if r["set"] != "WEAKNON903" or r["policy"] not in ("P0", "P2", "P5") or r["positive"] != "True":
            continue
        l = links.get(S.ko_key(r["input"]), {})
        nt = S.S28.non_type(r["input"])
        cause = (f"NON_TYPE_CUE:{nt}" if nt else "BODY_PART_ONLY" if S.stem_key(r["input"]) in bp else "SUBSTRING" if int(r["substring_false_match"]) else
                 "SPAN_EXTRACTION" if int(r["n_units"]) > 1 else "MODEL_B4" if "MODEL_B4" in r["ko_tiers"] else
                 "SYMPTOM_TERM_WEAK_LABEL_CONFLICT" if l.get("A_type") == l.get("B_type") == "SYMPTOM_OR_SIGN" else "OTHER")
        neg.append({"policy": r["policy"], "input": r["input"], "statuses": r["statuses"], "canonicals": r["canonicals"], "ontology_ids": r["ontology_ids"],
                    "ko_tiers": r["ko_tiers"], "evidence": r["evidence"][:160], "A_type": l.get("A_type", ""), "B_type": l.get("B_type", ""), "cause": cause,
                    "weak_label_note": "약한 비증상 라벨 — 실제 증상어일 수 있음" if cause == "SYMPTOM_TERM_WEAK_LABEL_CONFLICT" else ""})
    S.wcsv(S.OUT / "negative_risk_analysis.csv", neg, ["policy", "input", "statuses", "canonicals", "ontology_ids", "ko_tiers", "evidence", "A_type", "B_type", "cause", "weak_label_note"])
    err = []
    for r in rows:
        if r["policy"] not in ("P2", "P5"):
            continue
        kind = ""
        if r["set"] == "REGRESSION168" and r["first_auto"] and r["first_auto"] != r["gold"]:
            kind = "REGRESSION_WRONG_FIRST_AUTO"
        elif r["set"] == "REGRESSION168" and not r["first_auto"]:
            kind = "REGRESSION_NOT_AUTO"
        elif r["violations_auto"] or r["violations_display"]:
            kind = "SEMANTIC_VIOLATION"
        elif int(r["substring_false_match"]):
            kind = "SUBSTRING_FALSE_MATCH"
        elif r["set"] in ("PROBES", "SUPPORTED12"):
            kind = "PROBE"
        if kind:
            err.append({"policy": r["policy"], "set": r["set"], "kind": kind, "input": r["input"], "gold": r["gold"], "statuses": r["statuses"],
                        "canonicals": r["canonicals"], "display": r["display"], "reasons": r["reasons"][:200], "ko_tiers": r["ko_tiers"], "evidence": r["evidence"][:160]})
    S.wcsv(S.OUT / "error_analysis.csv", err)
    c = {p: dict(collections.Counter(x["cause"] for x in neg if x["policy"] == p)) for p in ("P0", "P2", "P5")}
    k = {p: dict(collections.Counter(x["kind"] for x in err if x["policy"] == p and x["kind"] != "PROBE")) for p in ("P2", "P5")}
    p5n = [f"{x['input']}→{x['canonicals'] or x['ontology_ids']}({x['cause']})" for x in neg if x["policy"] == "P5"]
    p5w = [f"{x['input']}(gold {x['gold']}→{x['canonicals']})" for x in err if x["policy"] == "P5" and x["kind"] == "REGRESSION_WRONG_FIRST_AUTO"]
    gone = sorted({x["input"] for x in err if x["policy"] == "P2" and x["kind"] == "REGRESSION_WRONG_FIRST_AUTO"} -
                  {x["input"] for x in err if x["policy"] == "P5" and x["kind"] == "REGRESSION_WRONG_FIRST_AUTO"})
    md = (f"- 비증상 위험 원인: {json.dumps(c, ensure_ascii=False)}\n- P5 비증상 위험 입력: {'; '.join(p5n) or '없음'}\n"
          f"- 오류 종류(P2 → P5): {json.dumps(k, ensure_ascii=False)}\n- P5 REGRESSION168 오답(첫 auto): {'; '.join(p5w) or '없음'}\n"
          f"- P2 오답 중 P5 에서 사라진 것: {', '.join(gone) or '없음'}")
    S.dump_json(S.OUT / "error_summary.json", {"negative_causes": c, "error_kinds": k, "p5_negative": p5n, "p5_regression_wrong": p5w, "fixed_from_p2": gone, "report_md": md})
    print(md)


if __name__ == "__main__":
    main()
