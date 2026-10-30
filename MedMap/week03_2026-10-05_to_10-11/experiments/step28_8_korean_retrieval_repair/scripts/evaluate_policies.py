"""STEP28.8 §6·§8·§10 평가(임상 정확도 아님). 규칙·데이터·지표는 실행 전 고정(2026-10-11). 검사기 = evaluator v3(SHA 는 evaluator_validation.json 과 일치해야 실행).

[데이터 — 출처·라벨 종류]
 SILVER442      STEP25 BERT-NER 증상 span(WEAK +) — STEP28 external_silver_expansion.csv
 WEAKNON903     EXT_EVAL 약한 비증상(WEAK −) — STEP28 weak_non_check.csv
 REGRESSION168  STEP27 INT_DEV_CORE 59 + INT_REGRESSION_CORE 109(SYNTHETIC GOLD, gold_concept) — STEP21–28.7 에서 반복 노출, 오류 사례를 보고 규칙 일부 작성
 PILOT_EXTRA106 STEP21 pilot_gold 274 중 REGRESSION168 밖 106(SYNTHETIC GOLD, Claude 작성 — 부정·시점·타인·복합·연결 불가 should_link False 포함).
                STEP26–28.7 정책 선택 코드에 쓰인 기록 없음(grep). 이번 규칙 작성 전 결과를 보지 않음 → '덜 노출 보조 평가'. 독립 임상 Gold 아님.
 SUPPORTED12    지시문 §6 짧은 지원 증상 12(기대 canonical = MedMap 77 구조) — 지시문 지정 사례
 PROBES         STEP28.7 probe 19 + 지시문 §2·§4 예시 6(노출 사례 — 회귀 확인용)
[정책] P0–P5(policies.py) + REF_A(STEP27 POLICY_D B4, 참고 — REGRESSION168·PILOT_EXTRA106 만)
[지표 — 분모 명시]
 auto = 구문 상태 EXISTING_CANONICAL/COMPOSITE(77 canonical).
 R1 coverage = REGRESSION168 중 auto 가 있는 입력 / 168 · R2 precision = 첫 auto canonical == gold / auto 입력(STEP28.7 과 같은 정의 — G5·G6)
 R3 span precision = REGRESSION168 auto 구문 중 canonical ∈ pilot_gold mention concept 집합 / auto 구문
 X1 span precision(PILOT_EXTRA106 같은 정의) · X2 primary coverage = should_link True & primary ∈ 77 인 입력 중 primary ∈ auto canonical
 X3 연결 불가 입력(should_link False) 중 auto 가 있는 입력
 W1 비증상 자동 연결 = WEAKNON903 입력 중 구문 상태 ∈ {EXISTING_*, EXISTING_SUBTYPE, NEW} / 903
 V1 의미 구별 위반 = 전 세트 입력 중 v3 위반(자동 concept 또는 표시 후보) · V2 잘못된 확인 후보 = 표시 후보만 위반
 SFM 부분 문자열 오매칭 = 전 세트 auto 구문 중 KO 어휘 근거(EXACT/PHRASE/BOUNDARY)가 질의와 경계 정렬되지 않은 것
   (정렬 = 용어 조사 제거 키가 질의 키 중 하나와 같음, 또는 용어 핵심 형태소열이 질의 형태소열 안에 연속 — 1글자·신체 부위 단독 제외)
 SUP = SUPPORTED12 중 기대 canonical 이 auto · NEWU = SILVER442 신규 후보 구문·고유 id · U = SILVER442 UNKNOWN+UNCERTAIN 구문 비율
 HELD = 정제표 보류 행(HOLD_CONCEPT_UNCERTAIN·HOLD_AUDIT_NOT_EXACT)의 원문 입력 중 해당 구문이 auto 인 입력 수(0 이어야)
 G2 77 id 충돌 · G9 신규·하위 usable · ISO 격리 FAIL 양성 · RAW 원문 보존율
출력: data/eval_rows.csv · outputs/{policy_comparison.csv, coverage_precision_tradeoff.csv, eval_summary.json}
"""
from __future__ import annotations

import collections
import json
import re

import s288_common as S
from evaluator import evaluator_sha, violations
from policies import HELD_DECISIONS, POLICIES, PolicyEngine
from repair_korean_matching import contains, core_tokens
from safe_offline_retriever import EXISTING, POSITIVE, PolicyA, nk

SUPPORTED12 = [("기침", "cough"), ("숨참", "dyspnea"), ("발열", "fever"), ("흉통", "pain"), ("두통", "pain"), ("복통", "pain"), ("메스꺼움", "nausea"),
               ("구토", "vomiting"), ("객혈", "hemoptysis"), ("설사", "diarrhea"), ("피로", "fatigue"), ("어지럼", "dizziness")]
PROBES28_7 = ["코피", "토했어요", "떨림", "고혈압", "기침 억제제", "무기력", "마른기침", "설사", "묽은변", "구토", "오심", "코피가 나요", "머리가 아파요", "열이 없어요",
              "숨이 차요", "토했어요", "메스꺼워요", "목이 아파요", "결핵", "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]
PROBES_NEW = ["혈관성 편두통", "몸이 덜덜 떨려요", "토할 것 같아요", "무기력하지 않아요", "발열", "두통"]
EV_RE = re.compile(r"^(EXACT|PHRASE|BOUNDARY):(UMLS_KOR:[^:]+|TERMINOLOGY_LABEL:E_\d+|[A-Za-z0-9_]+):(.*)$")


def main():
    val = S.load_json(S.OUT / "evaluator_validation.json")
    assert val["EVALUATOR_FIXED"] == "PASS" and val["evaluator_sha256"] == evaluator_sha(), "검사기 SHA 불일치 — 고정본이 아님"
    E = PolicyEngine()
    A = PolicyA(E.R.router)
    feats = {r["text"]: r for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    gset = {r["text_ko"]: {m["concept"] for m in json.loads(r["gold_mentions"] or "[]")} for r in pilot}
    reg = [(t, f["gold_concept"], f["set"]) for t, f in feats.items()]
    extra = [r for r in pilot if r["text_ko"] not in feats]
    models = E.models
    sets = {"SILVER442": [(r["raw_expression"], "", "") for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")],
            "WEAKNON903": [(r["text"], "", "") for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")],
            "REGRESSION168": reg,
            "PILOT_EXTRA106": [(r["text_ko"], r["primary_concept"], r["should_link"]) for r in extra],
            "SUPPORTED12": [(t, g, "") for t, g in SUPPORTED12],
            "PROBES": [(t, "", "") for t in dict.fromkeys(PROBES28_7 + PROBES_NEW)]}
    prefix = collections.defaultdict(list)
    for r in S.read_csv(S.S285_DIR / "index/korean_index.csv"):
        if len(r["ko_term"]) > 30:
            prefix[r["ko_term"][:30]].append(r["ko_term"])
    body = E.R.body

    def aligned(term, o):
        cands = prefix.get(term, [term]) if len(term) == 30 else [term]
        qkeys = {nk(o["span_text"]), S.ko_key(S.stem_key(o["span_text"]))}
        Q = core_tokens(o["span_text"])
        for t in cands:
            if S.ko_key(S.stem_key(t)) in qkeys or S.ko_key(t) in qkeys:
                return True
            C = core_tokens(t)
            if C and not (len(C) == 1 and (len(C[0]) < 2 or C[0] in body)) and contains(Q, C):
                return True
        return False

    held_inputs = {r["korean_expression"] for r in E.clean.rows if r["mapping_decision"] in HELD_DECISIONS}
    rows = []
    for sname, items in sets.items():
        for idx, (t, gold, sub) in enumerate(items):
            outs = E.run_all(t)
            if sname in ("REGRESSION168", "PILOT_EXTRA106"):
                a = A.run(t)
                outs["REF_A"] = [{**x, "ko_evidence": [], "ko_tier": "MODEL_B4", "span_text": t} for x in a]
            for p, os_ in outs.items():
                auto = [o for o in os_ if o["status"] in EXISTING and o["canonical_id"] in models]
                disp = sorted({c for o in os_ for c in (o.get("display") or [])})
                sfm = 0
                for o in auto:
                    if o.get("ko_tier") in ("EXACT", "PHRASE", "BOUNDARY") and o.get("evidence_sources", "").startswith("KO"):
                        terms = [m.group(3) for e in o.get("ko_evidence", []) for m in [EV_RE.match(e)] if m]
                        if terms and not any(aligned(x, o) for x in terms):
                            sfm += 1
                rows.append({"set": sname, "subset": sub, "idx": idx, "input": t, "gold": gold, "gold_set": ";".join(sorted(gset.get(t, set()))), "policy": p,
                             "n_units": len(os_), "statuses": ";".join(o["status"] for o in os_), "canonicals": ";".join(o["canonical_id"] or "" for o in os_),
                             "ontology_ids": ";".join(o.get("ontology_id") or "" for o in os_), "display": ";".join(disp),
                             "reasons": " | ".join(str(o.get("reason", ""))[:90] for o in os_), "ko_tiers": ";".join(o.get("ko_tier", "") for o in os_),
                             "evidence": " | ".join(";".join(o.get("ko_evidence", [])[:2])[:120] for o in os_), "polarity": ";".join(str(o.get("polarity") or "") for o in os_),
                             "auto_canonicals": ";".join(o["canonical_id"] for o in auto), "first_auto": auto[0]["canonical_id"] if auto else "",
                             "positive": any(o["status"] in POSITIVE for o in os_), "violations_auto": ";".join(violations(t, [o["canonical_id"] for o in auto])),
                             "violations_display": ";".join(violations(t, disp)), "substring_false_match": sfm,
                             "raw_ok": all(o.get("raw_preserved") and o.get("source_text", t) == t for o in os_),
                             "new_or_subtype_usable": any(o["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") and o.get("usable_by_disease_model") for o in os_),
                             "silver_only_usable": any(o.get("evidence_sources") == "SILVER" and o.get("usable_by_disease_model") for o in os_),
                             "iso_fail_positive": any(o["status"] in POSITIVE and o.get("isolation_status") == "ISOLATION_FAIL" and "SILVER" in str(o.get("evidence_sources")) for o in os_),
                             "held_input": t in held_inputs, "held_auto": t in held_inputs and bool(auto),
                             "u_status": [o["status"] for o in os_], "u_onto": [o.get("ontology_id") for o in os_], "u_auto": [o["canonical_id"] for o in auto]})
        print(sname, "done", flush=True)
    S.wcsv(S.DATA / "eval_rows.csv", [{k: v for k, v in r.items() if not k.startswith("u_")} for r in rows])

    from validate_concept_candidates import existing_ids
    ex = set(existing_ids(S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")))
    met = {}
    for p in POLICIES + ("REF_A",):
        R = [r for r in rows if r["policy"] == p]
        get = lambda s: [r for r in R if r["set"] == s]  # noqa: E731
        sr, wr, rg, xr, sp = get("SILVER442"), get("WEAKNON903"), get("REGRESSION168"), get("PILOT_EXTRA106"), get("SUPPORTED12")
        m = {}
        if rg:
            au = [r for r in rg if r["first_auto"]]
            spans = [(r, c) for r in rg for c in r["u_auto"]]
            m.update({"R1_regression_coverage": S.rnd(len(au) / len(rg)), "R1_n_auto": len(au), "R1_n": len(rg),
                      "R2_regression_precision(first_auto)": S.rnd(sum(r["first_auto"] == r["gold"] for r in au) / len(au)) if au else None,
                      "R2_n_correct": sum(r["first_auto"] == r["gold"] for r in au),
                      "R3_regression_span_precision": S.rnd(sum(c in set(r["gold_set"].split(";")) for r, c in spans) / len(spans)) if spans else None, "R3_n_spans": len(spans)})
        if xr:
            spans = [(r, c) for r in xr for c in r["u_auto"]]
            link = [r for r in xr if r["subset"] == "True" and r["gold"] in models]
            m.update({"X1_extra_span_precision": S.rnd(sum(c in set(r["gold_set"].split(";")) for r, c in spans) / len(spans)) if spans else None,
                      "X1_n_spans": len(spans), "X2_extra_primary_coverage": S.rnd(sum(r["gold"] in r["u_auto"] for r in link) / len(link)) if link else None,
                      "X2_n": len(link), "X3_should_not_link_auto": sum(bool(r["u_auto"]) for r in xr if r["subset"] == "False"),
                      "X3_n": sum(1 for r in xr if r["subset"] == "False")})
        if sr:
            uc = collections.Counter(s for r in sr for s in r["u_status"])
            n_u = sum(uc.values())
            m.update({"silver_units": n_u, "EXISTING_CANONICAL": uc["EXISTING_CANONICAL"], "EXISTING_COMPOSITE": uc["EXISTING_COMPOSITE"],
                      "EXISTING_SUBTYPE": uc["EXISTING_SUBTYPE"], "NEWU_units": uc["NEW_ONTOLOGY_CANDIDATE"],
                      "NEWU_distinct_ids": len({o for r in sr for s, o in zip(r["u_status"], r["u_onto"]) if s == "NEW_ONTOLOGY_CANDIDATE" and o}),
                      "UNKNOWN": uc["UNKNOWN_SYMPTOM"], "UNCERTAIN": uc["UNCERTAIN"], "NON": uc["NON_SYMPTOM"],
                      "U_unknown_uncertain_rate": S.rnd((uc["UNKNOWN_SYMPTOM"] + uc["UNCERTAIN"]) / n_u),
                      "W1_weaknon_auto_link": sum(r["positive"] for r in wr), "W1_n": len(wr),
                      "SUP_supported12": sum(g in r["u_auto"] for r in sp for g in [r["gold"]]), "SUP_n": len(sp),
                      "HELD_auto_inputs": sum(r["held_auto"] for r in R), "HELD_inputs": sum(r["held_input"] for r in R),
                      "G9_new_or_subtype_usable": sum(r["new_or_subtype_usable"] for r in R), "G9_silver_only_usable": sum(r["silver_only_usable"] for r in R),
                      "ISO_fail_positive": sum(r["iso_fail_positive"] for r in R),
                      "G2_id_collision": sum(1 for r in R for o in r["u_onto"] if o and o in ex),
                      "G2_canonical_outside_77": sum(1 for r in R for c in r["canonicals"].split(";") if c and c not in models)})
        m.update({"V1_semantic_violation_inputs": sum(bool(r["violations_auto"] or r["violations_display"]) for r in R),
                  "V2_wrong_candidate_display_inputs": sum(bool(r["violations_display"]) for r in R),
                  "SFM_substring_false_match_spans": sum(r["substring_false_match"] for r in R),
                  "RAW_preservation": S.rnd(sum(r["raw_ok"] for r in R) / len(R)), "n_rows": len(R)})
        met[p] = m
    keys = list(dict.fromkeys(k for p in met for k in met[p]))
    S.wcsv(S.OUT / "policy_comparison.csv", [{"metric": k, **{p: met[p].get(k, "") for p in POLICIES + ("REF_A",)}} for k in keys])
    S.wcsv(S.OUT / "coverage_precision_tradeoff.csv", [{"policy": p, "R1_coverage": met[p].get("R1_regression_coverage"), "R2_precision": met[p].get("R2_regression_precision(first_auto)"),
                                                         "R3_span_precision": met[p].get("R3_regression_span_precision"), "X1_extra_span_precision": met[p].get("X1_extra_span_precision"),
                                                         "X2_extra_coverage": met[p].get("X2_extra_primary_coverage"), "W1_weaknon": met[p].get("W1_weaknon_auto_link", "")}
                                                        for p in POLICIES + ("REF_A",)])
    S.dump_json(S.OUT / "eval_summary.json", {"metrics": met, "evaluator_sha256": evaluator_sha(), "sets": {k: len(v) for k, v in sets.items()},
                                              "labels": {"SILVER442": "WEAK+", "WEAKNON903": "WEAK-", "REGRESSION168": "SYNTHETIC_GOLD(노출)",
                                                         "PILOT_EXTRA106": "SYNTHETIC_GOLD(덜 노출)", "SUPPORTED12": "지시문 지정", "PROBES": "노출 사례"}})
    print(S.dumps({p: {k: met[p].get(k) for k in ("R1_regression_coverage", "R2_regression_precision(first_auto)", "W1_weaknon_auto_link", "V1_semantic_violation_inputs",
                                                   "SFM_substring_false_match_spans", "SUP_supported12", "HELD_auto_inputs", "X1_extra_span_precision", "X2_extra_primary_coverage")}
                   for p in POLICIES + ("REF_A",)}))


if __name__ == "__main__":
    main()
