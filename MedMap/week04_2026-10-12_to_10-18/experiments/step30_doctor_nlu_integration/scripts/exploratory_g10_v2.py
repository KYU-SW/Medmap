"""EXPLORATORY(공식 판정 변경 없음) — G10 검사기 v2 재확인.
공식 G10 은 FORBIDDEN_KEYS 의 'candidates' 가 NLU 원본(nlu_original)의 증상 concept 후보 키(예: Tremor HP:0001337)까지 잡아 R10 에서 FAIL.
v2: 질환 예측 키 검사는 어댑터가 만든 필드(nlu_original·nlu_context 바깥)에만, 49질환 코드 값 검사는 전체(NLU 원본 포함)에 적용.
검사기를 먼저 주입 사례로 확인(오판 0)한 뒤 공식 산출물(end_to_end_cases.json)에 적용. 출력: outputs/exploratory_g10_v2.json"""
from __future__ import annotations

import copy

import blind_workflow_simulator as BW
import s30_common as S

NLU_SUBTREES = ("nlu_original", "nlu_context")


def scan_v2(obj, classes) -> list:
    hits, cls = [], set(classes)

    def walk(o, path, in_nlu):
        if isinstance(o, dict):
            for k, v in o.items():
                if not in_nlu and str(k).lower() in BW.FORBIDDEN_KEYS:
                    hits.append(f"KEY:{path}/{k}")
                walk(v, f"{path}/{k}", in_nlu or k in NLU_SUBTREES)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]", in_nlu)
        elif isinstance(o, str) and o in cls:
            hits.append(f"VALUE:{path}")
    walk(obj, "", False)
    return hits


def self_test(packet, classes) -> dict:
    """주입 사례: 잡아야 할 것 3 · 잡지 말아야 할 것 1."""
    cases = []
    p = copy.deepcopy(packet)
    p["ranking"] = [["X", 0.5]]
    cases.append(("TOP_LEVEL_RANKING_KEY", bool(scan_v2(p, classes)), True))
    p = copy.deepcopy(packet)
    p["items"][0]["candidates"] = []
    cases.append(("ADAPTER_ITEM_CANDIDATES_KEY", bool(scan_v2(p, classes)), True))
    p = copy.deepcopy(packet)
    p["items"][0]["nlu_original"]["note_x"] = classes[0]
    cases.append(("DISEASE_CODE_VALUE_IN_NLU", bool(scan_v2(p, classes)), True))
    p = copy.deepcopy(packet)
    cases.append(("NLU_SYMPTOM_CANDIDATES_ONLY", bool(scan_v2(p, classes)), False))
    rows = [{"case": n, "flagged": f, "expected": e, "ok": f == e} for n, f, e in cases]
    return {"rows": rows, "misjudged": sum(1 for r in rows if not r["ok"])}


def main():
    classes = BW.reg().classes
    e2e = S.load_json(S.OUT / "end_to_end_cases.json")["cases"]
    r10 = next(c for c in e2e if c["case_id"] == "R10")["packet_before_confirmation"]
    st = self_test(r10, classes)
    if st["misjudged"]:
        raise SystemExit(f"v2 검사기 오판 {st['misjudged']} — 적용 중단")
    per = []
    for c in e2e:
        pkt = c["packet_before_confirmation"]
        bw = c["blind_workflow"]
        other = [x for x in bw["violations"] if x not in ("STAGE1_LEAK", "STAGE3_LEAK")]
        h1 = scan_v2(pkt, classes)
        per.append({"case_id": c["case_id"], "official_violations": bw["violations"], "v2_stage1_hits": h1, "other_official_violations": other})
    # STAGE3 packet(확인 뒤)은 공식 산출물에 sections·model_input 만 있다 — 확인 뒤 packet 의 추가 필드는 confirmation(어댑터) 뿐이라 v2 키 검사를 그 두 부분에 적용
    s3 = [{"case_id": c["case_id"], "hits": scan_v2({"sections": c["sections_after_policy_stage_a"], "model_input": c["model_input_after_policy_stage_a"]}, classes)} for c in e2e]
    v2_total = sum(len(p["v2_stage1_hits"]) + len(p["other_official_violations"]) for p in per) + sum(len(x["hits"]) for x in s3)
    v = S.load_json(S.OUT / "integration_verdict.json")
    g = dict(v["gates"])
    g["G10"] = "PASS" if v2_total == 0 else "FAIL"
    m = v["performance_integration_new"]
    fail = [k for k, x in g.items() if x != "PASS"]
    if "G11" in fail or "G12" in fail:
        res = "BLOCKED"
    elif fail:
        res = "REGRESSION"
    else:
        ntr = m["normal_transfer_rate"]["value"] or 0
        if m["stage_a_marking_errors"] == 0 and ntr >= 0.85 and (m["missing_rate"]["value"] or 0) <= 0.10 and (m["wrong_display_rate"]["value"] or 0) <= 0.10:
            res = "INTEGRATION_FEASIBLE"
        elif ntr < 0.50:
            res = "NO_GAIN"
        else:
            res = "PARTIAL_FEASIBILITY"
    out = {**S.RESEARCH_BANNER, "label": "EXPLORATORY — 공식 판정(integration_verdict.json) 변경 없음",
           "official_STEP30_RESULT": v["STEP30_RESULT"], "official_G10": v["gates"]["G10"],
           "cause": "공식 G10 검사기의 금지 키 'candidates' 가 NLU 원본 mention 의 증상 concept 후보 키(R10 '손이 떨려' → HP:0001337)와 겹침 — 질환 정보 노출 아님",
           "checker_self_test": st, "v2_G10": g["G10"], "v2_violations_total": v2_total,
           "exploratory_STEP30_RESULT": res,
           "exploratory_STEP31_READINESS": {"INTEGRATION_FEASIBLE": "GO_FOR_RESEARCH", "PARTIAL_FEASIBILITY": "CONDITIONAL_GO"}.get(res, "NO_GO"),
           "per_case": per, "stage3_rescan": s3,
           "lesson": "검사기 키 목록을 NLU 원본 스키마와 대조하지 않고 SHA 고정함 — 다음 단계는 검사기를 실제 NLU 출력 전체 키 목록과 먼저 대조"}
    S.dump_json(S.OUT / "exploratory_g10_v2.json", out)
    print(S.dumps({k: out[k] for k in ("official_STEP30_RESULT", "v2_G10", "v2_violations_total", "exploratory_STEP30_RESULT", "exploratory_STEP31_READINESS", "checker_self_test")}))


if __name__ == "__main__":
    main()
