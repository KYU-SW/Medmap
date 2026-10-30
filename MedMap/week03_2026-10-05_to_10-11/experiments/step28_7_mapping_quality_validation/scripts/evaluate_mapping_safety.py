"""STEP28.7 §9–§12 평가(정답 없음 — 임상 정확도·민감도·특이도 계산 안 함). 규칙·지표·데이터는 실행 전 고정(2026-10-11).

[데이터 — 모두 STEP21–28.6 에서 반복 관찰된 개발·회귀 자료, blind 아님]
 SILVER442    STEP25 BERT-NER-KO 증상 span(약한 양성, 정답 아님) — STEP28 external_silver_expansion.csv raw_expression
 WEAKNON903   EXT_EVAL 약한 비증상 라벨 — STEP28 weak_non_check.csv text(진짜 false-positive rate 아님)
 REGRESSION168 STEP27 합성 INT_DEV_CORE 59 + INT_REGRESSION_CORE 109(gold concept 있음, 여러 번 사용된 합성)
 PROBES       지시문 §10·§4 표현 + STEP28.5 smoke 10(사용자 지정 — 이미 노출, 독립 성능 아님)
 C·D 는 SILVER442·WEAKNON903·smoke 를 키로 가진 대응표를 쓴다(표 = 그 입력으로 작성) → 그 세트 결과는 '표 안(in-table)' 수치다.
 D_LOO(입력과 같은 원문 행 제외)로 처음 보는 표면형 근사치를 따로 낸다.
[정책 — 결과 구분 §11]
 A STEP27 POLICY_D(B4) · B STEP28 Expansion → '기존 정책의 재현'(라이브 재실행 + 기존 산출 파일과 일치 수 기록)
 C STEP28.6 대응표 조회 → 재현 · D STEP28.7(사전 고정 신규 정책) · D_NO_TABLE(=STEP28.5 KO_ONLY) · D_LOO — 탐색 변형은 build_report 에서 따로 표기
[지표 — 단위·분모 명시]
 unit: A·B·C = 입력 1개당 결과 1개 · D 계열 = 구문(span) 단위(입력 수와 구문 수를 같이 기록)
 1 EXISTING_CANONICAL · 2 EXISTING_COMPOSITE · 3 신규 독립 ontology concept(고유 id, NEW_ONTOLOGY_CANDIDATE) · 4 신규 하위(EXISTING_SUBTYPE 고유 id) ·
 5 SILVER 동의어로 기존에 정리된 구문 수 · 6 UNCERTAIN 구문 수 — SILVER442 기준
 7 비증상 자동 연결 위험 = WEAKNON903 입력 중 어느 구문이라도 EXISTING_*·EXISTING_SUBTYPE·NEW 인 입력 수 / 903
 8 지원 증상 자동 처리 coverage = REGRESSION168 중 EXISTING_* 결과(77 canonical)가 있는 입력 / 168 · 9 auto-accept precision = 그 중 canonical == gold
 10 잘못된 확인 후보 표시 = (전 세트+probe) 표시 후보에 구별 위반 concept 이 있는 입력 수
 11 의미 구별 위반 = (전 세트+probe) 자동 concept 또는 표시 후보가 구별 규칙 위반인 입력 수
 12 UNKNOWN/UNCERTAIN 비율(SILVER442 unit) · 13 원문 보존율(전 출력) · 14·15 = benchmark_runtime
 구별 규칙(지시문 §4·§10 그대로): 코피→객혈·토혈 · 구토/토하→오심만 · 메스꺼/오심/구역→구토만 · 떨림/떨려(오한·춥 없이)→오한 ·
  고혈압→증상 concept · 기침 억제제/기침약/진해제→기침
 비증상 위험 원인 분류(§9, 사전 순서): NON_TYPE_CUE(질환·약물·치료·검사 접미) → BODY_PART_ONLY → SUBSTRING(PHRASE 부분 일치) →
  SPAN_EXTRACTION(구문 2개 이상) → SYMPTOM_TERM_WEAK_LABEL_CONFLICT(두 작성자 모두 증상형 & 한국어 EXACT/RULE 동의 — 약한 라벨 쪽 의심) → OTHER
출력: outputs/{policy_comparison.csv, regression_metrics.json, non_symptom_error_analysis.csv, candidate_safety_analysis.csv, reproduction_check.json,
     eval_summary.json} · data/eval_rows.csv
"""
from __future__ import annotations

import collections
import re

import s287_common as S
from safe_offline_retriever import EXISTING, POSITIVE, PolicyA, PolicyB, PolicyC, SafeOfflineRetriever

PROBES_10 = ["코피", "토했어요", "떨림", "고혈압", "기침 억제제"]
PROBES_4 = ["무기력", "마른기침", "설사", "묽은변", "구토", "오심"]
SMOKE = ["코피가 나요", "머리가 아파요", "열이 없어요", "숨이 차요", "토했어요", "메스꺼워요", "목이 아파요", "고혈압", "결핵",
         "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]
PROBES = list(dict.fromkeys(PROBES_10 + PROBES_4 + SMOKE))
POLICIES = ("A_STEP27_B4", "B_STEP28", "C_STEP28_6", "D_STEP28_7", "D_NO_TABLE", "D_LOO")


def violations(text: str, concepts) -> list[str]:
    x = S.nospace(text)
    cs = set(c for c in concepts if c)
    v = []
    if "코피" in x and {"hemoptysis", "hematemesis"} & cs:
        v.append("EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS")
    if re.search(r"(구토|토하|토했|토해|토할)", x) and "nausea" in cs and "vomiting" not in cs:
        v.append("VOMITING_AS_NAUSEA")
    if re.search(r"(메스꺼|메스껍|오심|구역)", x) and "vomiting" in cs and "nausea" not in cs:
        v.append("NAUSEA_AS_VOMITING")
    if re.search(r"(떨림|떨려|떨리)", x) and not re.search(r"(오한|춥|추워|으슬)", x) and "chills" in cs:
        v.append("TREMOR_AS_CHILLS")
    if "고혈압" in x and cs:
        v.append("HYPERTENSION_AS_SYMPTOM")
    if re.search(r"(억제제|기침약|진해제)", x) and "cough" in cs:
        v.append("ANTITUSSIVE_AS_COUGH")
    return v


def main():
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    wn_rows = S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")
    wn = [r["text"] for r in wn_rows]
    feats = S.read_csv(S.S27_DIR / "outputs/routing_features.csv")
    reg = [(f["text"], f["gold_concept"], f["set"]) for f in feats if f["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")]
    D = SafeOfflineRetriever()
    A = PolicyA(D.R.router)
    B = PolicyB()
    C = PolicyC()
    sets = {"SILVER442": [(t, "", "") for t in sil], "WEAKNON903": [(t, "", "") for t in wn], "REGRESSION168": reg, "PROBES": [(t, "", "") for t in PROBES]}
    rows = []
    for sname, items in sets.items():
        for idx, (t, gold, sub) in enumerate(items):
            ko = D.R.run(t, "KO_ONLY")
            outs = {"A_STEP27_B4": A.run(t), "B_STEP28": B.run(t), "C_STEP28_6": C.run(t)}
            keysets = [D._keys(t, o, len(ko)) for o in ko]
            outs["D_STEP28_7"] = [D.combine(t, o, D.table.lookup(k)) for o, k in zip(ko, keysets)]
            outs["D_NO_TABLE"] = [D.combine(t, o, None) for o in ko]
            D.table.excluded_raw = S.ko_key(t)
            outs["D_LOO"] = [D.combine(t, o, D.table.lookup(k)) for o, k in zip(ko, keysets)]
            D.table.excluded_raw = None
            for p, os_ in outs.items():
                auto = [o["canonical_id"] for o in os_ if o["status"] in EXISTING and o["canonical_id"]]
                disp = sorted({c for o in os_ for c in (o.get("display") or [])})
                rows.append({"set": sname, "subset": sub, "idx": idx, "input": t, "gold": gold, "policy": p, "n_units": len(os_),
                             "statuses": ";".join(o["status"] for o in os_), "canonicals": ";".join(o["canonical_id"] or "" for o in os_),
                             "ontology_ids": ";".join(o.get("ontology_id") or "" for o in os_), "display": ";".join(disp),
                             "reasons": " | ".join(str(o.get("reason", ""))[:80] for o in os_),
                             "evidence": ";".join(str(o.get("evidence_sources", o.get("reason", "")))[:40] for o in os_),
                             "ko_tiers": ";".join(o.get("ko_tier", "") for o in os_), "polarity": ";".join(str(o.get("polarity") or "") for o in os_),
                             "positive": any(o["status"] in POSITIVE for o in os_), "auto_canonical": auto[0] if auto else "",
                             "usable_any": any(o.get("usable_by_disease_model") for o in os_),
                             "violations_auto": ";".join(violations(t, auto)), "violations_display": ";".join(violations(t, disp)),
                             "raw_ok": all(o.get("raw_preserved") and o.get("source_text") == t for o in os_),
                             "silver_only_existing": any(o["status"] in EXISTING and o.get("evidence_sources") == "SILVER" for o in os_),
                             "new_or_subtype_usable": any(o["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") and o.get("usable_by_disease_model") for o in os_),
                             "silver_isolation_fail_positive": any(o["status"] in POSITIVE and o.get("isolation_status") == "ISOLATION_FAIL" and "SILVER" in str(o.get("evidence_sources")) for o in os_),
                             "units_status": [o["status"] for o in os_], "units_onto": [o.get("ontology_id") for o in os_]})
        print(sname, "done", flush=True)
    S.wcsv(S.DATA / "eval_rows.csv", [{k: v for k, v in r.items() if not k.startswith("units_")} for r in rows])

    # ---- 지표 ----
    met = {}
    ex_ids = set()
    from validate_concept_candidates import existing_ids
    ex = existing_ids(S.read_csv(S.S28.DATA / "existing_concept_inventory.csv"))
    ex_ids = set(ex)
    canon77 = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    for p in POLICIES:
        R = [r for r in rows if r["policy"] == p]
        sr = [r for r in R if r["set"] == "SILVER442"]
        units = [s for r in sr for s in r["units_status"]]
        uc = collections.Counter(units)
        new_ids = {o for r in sr for s, o in zip(r["units_status"], r["units_onto"]) if s == "NEW_ONTOLOGY_CANDIDATE" and o}
        sub_ids = {o for r in sr for s, o in zip(r["units_status"], r["units_onto"]) if s == "EXISTING_SUBTYPE" and o}
        wr = [r for r in R if r["set"] == "WEAKNON903"]
        rg = [r for r in R if r["set"] == "REGRESSION168"]
        auto_rg = [r for r in rg if r["auto_canonical"]]
        allr = R
        all_onto = {o for r in R for o in r["units_onto"] if o}
        met[p] = {"silver_inputs": len(sr), "silver_units": len(units),
                  "1_EXISTING_CANONICAL": uc["EXISTING_CANONICAL"], "2_EXISTING_COMPOSITE": uc["EXISTING_COMPOSITE"],
                  "3_NEW_INDEPENDENT_ontology_ids": len(new_ids), "3b_NEW_units": uc["NEW_ONTOLOGY_CANDIDATE"],
                  "4_NEW_SUBTYPE_ontology_ids": len(sub_ids), "4b_SUBTYPE_units": uc["EXISTING_SUBTYPE"],
                  "5_SILVER_SYNONYM_units": sum(1 for r in sr for x in r["reasons"].split(" | ") if "ACCEPT_EXISTING_SYNONYM" in x),
                  "6_UNCERTAIN_units": uc["UNCERTAIN"], "UNKNOWN_units": uc["UNKNOWN_SYMPTOM"], "NON_units": uc["NON_SYMPTOM"],
                  "7_weaknon_auto_link_risk": sum(r["positive"] for r in wr), "7_n": len(wr),
                  "8_supported_auto_coverage": S.rnd(len(auto_rg) / len(rg)), "8_n_auto": len(auto_rg), "8_n": len(rg),
                  "9_regression_auto_precision": S.rnd(sum(r["auto_canonical"] == r["gold"] for r in auto_rg) / len(auto_rg)) if auto_rg else None,
                  "9_n_correct": sum(r["auto_canonical"] == r["gold"] for r in auto_rg),
                  "regression_usable_coverage": S.rnd(sum(r["usable_any"] and r["auto_canonical"] == r["gold"] for r in rg) / len(rg)),
                  "10_wrong_candidate_display_inputs": sum(bool(r["violations_display"]) for r in allr),
                  "11_semantic_violation_inputs": sum(bool(r["violations_auto"] or r["violations_display"]) for r in allr),
                  "12_unknown_uncertain_rate(silver units)": S.rnd((uc["UNKNOWN_SYMPTOM"] + uc["UNCERTAIN"]) / len(units)),
                  "silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)": S.rnd(sum(uc[k] for k in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE",
                                                                                                    "NEW_ONTOLOGY_CANDIDATE", "NON_SYMPTOM")) / len(units)),
                  "13_raw_preservation": S.rnd(sum(r["raw_ok"] for r in allr) / len(allr)),
                  "G2_new_id_collision_with_77": sum(1 for o in all_onto if o in ex_ids),
                  "G2_canonical_outside_77": sum(1 for r in R for c in r["canonicals"].split(";") if c and c not in canon77),
                  "G8_new_or_subtype_usable_by_model": sum(r["new_or_subtype_usable"] for r in R),
                  "G9_isolation_fail_positive": sum(r["silver_isolation_fail_positive"] for r in R),
                  "silver_only_existing_units(silver)": sum(r["silver_only_existing"] for r in sr)}
    comp = [{"metric": k, **{p: met[p][k] for p in POLICIES}} for k in met["D_STEP28_7"]]
    S.wcsv(S.OUT / "policy_comparison.csv", comp)

    regm = {}
    for p in POLICIES:
        for sub in ("INT_DEV_CORE", "INT_REGRESSION_CORE", "ALL"):
            rg = [r for r in rows if r["policy"] == p and r["set"] == "REGRESSION168" and (sub == "ALL" or r["subset"] == sub)]
            au = [r for r in rg if r["auto_canonical"]]
            regm.setdefault(p, {})[sub] = {"n": len(rg), "auto": len(au), "coverage": S.rnd(len(au) / len(rg)), "correct": sum(r["auto_canonical"] == r["gold"] for r in au),
                                          "precision": S.rnd(sum(r["auto_canonical"] == r["gold"] for r in au) / len(au)) if au else None,
                                          "wrong": [(r["input"], r["gold"], r["auto_canonical"]) for r in au if r["auto_canonical"] != r["gold"]][:20]}
    S.dump_json(S.OUT / "regression_metrics.json", {"data": "STEP27 합성 regression(INT_DEV_CORE 59 + INT_REGRESSION_CORE 109, gold) — 반복 사용, 독립 테스트 아님",
                                                    "metrics": regm})

    # ---- §9 비증상 위험 원인 ----
    links = {S.ko_key(r["korean"]): r for r in S.read_csv(S.S286_DIR / "data/ontology_links.csv") if "WEAKNON903" in r["sources"]}
    bp = set(S.S28.body_parts())
    na = []
    risk_inputs = {r["input"] for r in rows if r["set"] == "WEAKNON903" and r["positive"] and r["policy"] in ("C_STEP28_6", "D_STEP28_7")}
    for r in rows:
        if r["set"] != "WEAKNON903" or r["input"] not in risk_inputs or r["policy"] not in ("C_STEP28_6", "D_STEP28_7"):
            continue
        t = r["input"]
        l = links.get(S.ko_key(t), {})
        nt = S.S28.non_type(t)
        head = S.stem_key(t)
        tiers = r["ko_tiers"].split(";")
        if nt:
            cause = f"NON_TYPE_CUE:{nt}"
        elif head in bp:
            cause = "BODY_PART_ONLY"
        elif "PHRASE" in tiers and r["policy"] == "D_STEP28_7":
            cause = "SUBSTRING(PHRASE)"
        elif r["n_units"] > 1:
            cause = "SPAN_EXTRACTION"
        elif l.get("A_type") == l.get("B_type") == "SYMPTOM_OR_SIGN":
            cause = "SYMPTOM_TERM_WEAK_LABEL_CONFLICT"
        else:
            cause = "OTHER"
        na.append({"policy": r["policy"], "input": t, "statuses": r["statuses"], "canonicals": r["canonicals"], "ontology_ids": r["ontology_ids"],
                   "evidence": r["evidence"], "ko_tiers": r["ko_tiers"], "A_type": l.get("A_type", ""), "B_type": l.get("B_type", ""),
                   "A_english": l.get("A_english", ""), "B_english": l.get("B_english", ""), "step28_6_final": f"{l.get('final_cat', '')}:{l.get('final_concept', '')}",
                   "non_type_cue": nt, "body_part_only": head in bp, "symptom_cue": S.S28.symptom_cue(t), "cause": cause,
                   "is_disease_name": nt == "disease", "is_drug": nt == "drug", "is_test_or_treatment": nt in ("test", "treatment"),
                   "symptom_context_present": "확인 불가(단어 조각 — 원문 문맥 없음)"})
    S.wcsv(S.OUT / "non_symptom_error_analysis.csv", na)

    # ---- §10 후보 표시 안전성 ----
    cs = []
    for r in rows:
        if r["set"] == "PROBES":
            cs.append({k: r[k] for k in ("input", "policy", "statuses", "canonicals", "ontology_ids", "display", "reasons", "violations_auto", "violations_display")})
    mapper = []
    for t in PROBES:
        hits = B.e.es.mapper.extract(t)
        mapper.append({"input": t, "policy": "PRODUCT_MAPPER(read-only, 연구용 탐지)", "statuses": ";".join(f"{m['evidence_id']}:{m['status']}" for m in hits),
                       "canonicals": ";".join(B.e.es.cw.get(m["evidence_id"], "") for m in hits if m["status"] == "POSITIVE"), "ontology_ids": "", "display": "",
                       "reasons": "", "violations_auto": ";".join(violations(t, [B.e.es.cw.get(m["evidence_id"], "") for m in hits if m["status"] == "POSITIVE"])),
                       "violations_display": ""})
    S.wcsv(S.OUT / "candidate_safety_analysis.csv", cs + mapper)

    # ---- 재현 확인(A·B 라이브 ↔ 기존 파일) ----
    f_sil = {r["raw_expression"]: r for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")}
    f_wn = {r["text"]: r for r in wn_rows}
    f_rg = {r["text"]: r for r in S.read_csv(S.S28_DIR / "outputs/internal_regression_check.csv")}
    s27map = {"KNOWN_SYMPTOM": "EXISTING_CANONICAL", "COMPLEX_INPUT": "UNCERTAIN"}
    rep = {}
    for p, col, conv in (("A_STEP27_B4", "step27_status", lambda x: s27map.get(x, x)), ("B_STEP28", "step28_category", lambda x: {"NEW_ONTOLOGY_CONCEPT": "NEW_ONTOLOGY_CANDIDATE"}.get(x, x))):
        for sname, f in (("SILVER442", f_sil), ("WEAKNON903", f_wn), ("REGRESSION168", f_rg)):
            rs = [r for r in rows if r["policy"] == p and r["set"] == sname]
            mism = [(r["input"], conv(f[r["input"]][col]), r["statuses"]) for r in rs if r["input"] in f and conv(f[r["input"]][col]) != r["statuses"]]
            rep[f"{p}:{sname}"] = {"n": len(rs), "mismatch": len(mism), "examples": mism[:5]}
    c_wn = [r for r in rows if r["policy"] == "C_STEP28_6" and r["set"] == "WEAKNON903"]
    rep["C_STEP28_6:WEAKNON903_risk_vs_reported_8"] = {"recomputed": sum(r["positive"] for r in c_wn), "reported": 8}
    S.dump_json(S.OUT / "reproduction_check.json", rep)
    S.dump_json(S.OUT / "eval_summary.json", {"metrics": met, "probes": PROBES, "units_note": "A·B·C 입력 단위 · D 계열 구문 단위(SILVER442 구문 수 = silver_units)"})
    print(S.dumps({p: {k: met[p][k] for k in ("7_weaknon_auto_link_risk", "8_supported_auto_coverage", "9_regression_auto_precision", "11_semantic_violation_inputs",
                                              "10_wrong_candidate_display_inputs", "12_unknown_uncertain_rate(silver units)")} for p in POLICIES}))
    print(S.dumps(rep))


if __name__ == "__main__":
    main()
