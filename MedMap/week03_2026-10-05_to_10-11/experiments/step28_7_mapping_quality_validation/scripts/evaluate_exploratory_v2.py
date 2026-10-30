"""STEP28.7 탐색적 v2(EXPLORATORY_POST_HOC — 1차 평가 결과를 본 뒤 작성, 공식 판정에 쓰지 않음). 모델 재실행 없음(data/eval_rows.csv 재채점).

사후 발견(2026-10-11, 1차 결과 확인 후):
 사전 고정 구별 검사기(evaluate_mapping_safety.violations)가 STEP28.6 규칙(구토|토하|토했)에 '토할·토해' 를, 떨림 규칙에 동사형 '떨려·떨리' 를 넣었다.
 REGRESSION168 의 '토할 것 같아요'(gold nausea)·'몸이 덜덜 떨려요'(gold chills)가 정답 연결인데 위반으로 잡혀 G3 FAIL.
v2 검사기: 구토 규칙 = STEP28.6 원형(구토|토하|토했) · 떨림 규칙 = 명사 '떨림'(이전 문제 = 명사 떨림 → 오한) · 나머지 동일.
추가 진단(판정 미사용): REGRESSION168 'gold 가 어느 자동 구문에든 있음' 비율(1차 지표는 첫 자동 구문만 봄 — 다구문 입력 불리).
v2 판정은 build_report 와 같은 게이트·판정 규칙에 G3·10·11 만 v2 값으로 바꿔 계산 → 'STEP28_7_RESULT_EXPLORATORY_V2'.
출력: outputs/exploratory_v2.json
"""
from __future__ import annotations

import collections
import re

import s287_common as S


def violations_v2(text: str, concepts) -> list[str]:
    x = S.nospace(text)
    cs = set(c for c in concepts if c)
    v = []
    if "코피" in x and {"hemoptysis", "hematemesis"} & cs:
        v.append("EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS")
    if re.search(r"(구토|토하|토했)", x) and "nausea" in cs and "vomiting" not in cs:
        v.append("VOMITING_AS_NAUSEA")
    if re.search(r"(메스꺼|메스껍|오심|구역)", x) and "vomiting" in cs and "nausea" not in cs:
        v.append("NAUSEA_AS_VOMITING")
    if "떨림" in x and not re.search(r"(오한|춥|추워|으슬)", x) and "chills" in cs:
        v.append("TREMOR_AS_CHILLS")
    if "고혈압" in x and cs:
        v.append("HYPERTENSION_AS_SYMPTOM")
    if re.search(r"(억제제|기침약|진해제)", x) and "cough" in cs:
        v.append("ANTITUSSIVE_AS_COUGH")
    return v


def main():
    rows = S.read_csv(S.DATA / "eval_rows.csv")
    res = {}
    for p in sorted({r["policy"] for r in rows}):
        R = [r for r in rows if r["policy"] == p]
        va = [(r["set"], r["input"], violations_v2(r["input"], [r["auto_canonical"]]), violations_v2(r["input"], r["display"].split(";"))) for r in R]
        rg = [r for r in R if r["set"] == "REGRESSION168"]
        any_auto = [r for r in rg if r["gold"] in {c for c, s in zip(r["canonicals"].split(";"), r["statuses"].split(";")) if s in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")}]
        res[p] = {"10_wrong_candidate_display_inputs_v2": sum(bool(d) for _, _, _, d in va), "11_semantic_violation_inputs_v2": sum(bool(a or d) for _, _, a, d in va),
                  "violations_v2": [(s, t, a, d) for s, t, a, d in va if a or d],
                  "diag_regression_gold_in_any_auto_span": S.rnd(len(any_auto) / len(rg))}
    ev = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    fin = S.load_json(S.OUT / "step28_7_verdict.json")
    g = {k: v == "PASS" for k, v in fin["gates"].items()}
    D, C = res["D_STEP28_7"], res["C_STEP28_6"]
    g["G3"] = D["11_semantic_violation_inputs_v2"] == 0
    hard = all(g[k] for k in ("G1", "G2", "G3", "G8", "G9", "G10"))
    better = {"weaknon_risk": ev["D_STEP28_7"]["7_weaknon_auto_link_risk"] < ev["C_STEP28_6"]["7_weaknon_auto_link_risk"],
              "semantic_violations": D["11_semantic_violation_inputs_v2"] < C["11_semantic_violation_inputs_v2"],
              "wrong_display": D["10_wrong_candidate_display_inputs_v2"] < C["10_wrong_candidate_display_inputs_v2"]}
    worse = ev["D_STEP28_7"]["7_weaknon_auto_link_risk"] > ev["C_STEP28_6"]["7_weaknon_auto_link_risk"] and D["11_semantic_violation_inputs_v2"] > C["11_semantic_violation_inputs_v2"]
    verdict = ("REGRESSION" if not hard or worse else "QUALITY_GATE_PASS" if all(g.values()) else "PARTIAL_IMPROVEMENT" if any(better.values()) else "NO_GAIN")
    out = {"label": "EXPLORATORY_POST_HOC(공식 판정 아님)", "STEP28_7_RESULT_EXPLORATORY_V2": verdict, "gates_v2": {k: "PASS" if v else "FAIL" for k, v in g.items()},
           "safety_better_than_C_v2": better, "STEP29_ENTRY_EXPLORATORY_V2": "CONDITIONAL_GO" if hard else "NO_GO", "per_policy": res, "rules": __doc__}
    S.dump_json(S.OUT / "exploratory_v2.json", out)
    print(S.dumps({k: out[k] for k in ("STEP28_7_RESULT_EXPLORATORY_V2", "gates_v2", "safety_better_than_C_v2")}))
    print(S.dumps({p: {k: v for k, v in r.items() if k != "violations_v2"} for p, r in res.items()}))


if __name__ == "__main__":
    main()
