"""STEP26 우선 점검 사례 + illustrative smoke(정답셋 아님, 임계값 조정에 사용하지 않음).

A. 외부 데이터에 실제로 있는 사례: 지정 용어(고혈압·결핵·코피·호흡곤란·기침·발열·오심·구토)와 stem 이 같은 EXT 단위(빈도 최고 1개),
   신체부위 단독(BD/Body 최빈 3) · 치료명 단독(Treatment 최빈 3).
B. ILLUSTRATIVE_SMOKE: 지시문 예시 문장 4개를 SafeNormalizer 로 실행(데이터에 없는 문장 — 평가 지표에 넣지 않음).
출력: outputs/priority_cases.csv · outputs/illustrative_smoke.json
"""
import json

import numpy as np

import s26_common as S
from safe_normalizer import SafeNormalizer

TERMS = ["고혈압", "결핵", "코피", "호흡곤란", "기침", "발열", "오심", "구토"]
SMOKE = ["숨이 차요", "코피가 나요", "고혈압", "몸이 좀 이상해요"]


def main():
    pred = [p for p in S.read_csv(S.OUT / "predictions.csv") if p["set"] in ("EXT_DEV", "EXT_EVAL")]
    inv = {r["row_id"]: r for r in S.read_csv(S.DATA / "weak_label_inventory.csv")}
    rows = []

    def add(kind, p):
        rows.append({"kind": kind, "set": p["set"], "text": p["text"], "weak_label": p["weak_label"], "categories": inv[p["row_id"]]["categories"],
                     "freq": inv[p["row_id"]]["freq"], "linear": p["lin_top1"], "koelectra": p["koe_top1"],
                     "hybrid_b": p["hybrid_b"] + (" (auto)" if p["hybrid_b_auto"] == "True" else ""), "new_auto": p["new_auto"],
                     "non_symptom_score": p["non_symptom_score"], "status": p["status"], "decision": p["decision"], "candidates": p["candidate_ids"]})

    for t in TERMS:
        cand = [p for p in pred if S.stem_key(p["text"]) == t]
        if not cand:
            rows.append({"kind": f"TERM:{t}", "text": "(외부 데이터에 동일 stem 없음 — 새 정답으로 추가하지 않음)"})
            continue
        add(f"TERM:{t}", max(cand, key=lambda p: (int(inv[p["row_id"]]["freq"]), p["row_id"])))
    for cat, kind in (("BD", "BODY_PART_ALONE"), ("Body", "BODY_PART_ALONE"), ("Treatment", "TREATMENT_ALONE")):
        cand = [p for p in pred if p["weak_label"] == "WEAK_NON_SYMPTOM" and any(c.endswith(":" + cat) for c in inv[p["row_id"]]["categories"].split(";"))]
        for p in sorted(cand, key=lambda p: (-int(inv[p["row_id"]]["freq"]), p["row_id"]))[:3]:
            add(f"{kind}({cat})", p)
    S.write_csv(S.OUT / "priority_cases.csv", rows, ["kind", "set", "text", "weak_label", "categories", "freq", "linear", "koelectra", "hybrid_b",
                                                    "new_auto", "non_symptom_score", "status", "decision", "candidates"])
    sn = SafeNormalizer()
    smoke = []
    for t in SMOKE:
        o = sn(t)
        s = np.sort(sn.lin.decision_function([S.norm(t)])[0])
        fast = s[-1] - s[-2] >= S.T_LIN
        hb = o["model_evidence"]["linear_top1"] if fast else o["model_evidence"]["transformer_top1"]
        smoke.append({"ILLUSTRATIVE_SMOKE": True, "input": t, "existing_hybrid_b": hb, "existing_hybrid_b_auto": bool(fast or o["model_evidence"]["transformer_score"] >= S.T_KOE),
                      "new_output": o})
    S.dump_json(S.OUT / "illustrative_smoke.json", smoke)
    for r in rows:
        print({k: r.get(k) for k in ("kind", "text", "linear", "koelectra", "hybrid_b", "status", "candidates")})
    for s in smoke:
        print(s["input"], "| HB", s["existing_hybrid_b"], s["existing_hybrid_b_auto"], "| NEW", s["new_output"]["status"], s["new_output"]["candidate_ids"], s["new_output"]["reason"])


if __name__ == "__main__":
    main()
