"""STEP28.5 평가 — 정답 없음(매핑 정확도 계산 안 함). Silver 442 는 STEP25–28 에서 여러 번 본 데이터(blind 아님).

비교군: A = STEP28 결과(파일) · B = KO_ONLY · C = EN_ONLY · D = PARALLEL.
단위: 구문(span). Silver 입력 1개가 구문 2개 이상이면 구문마다 센다(입력 수와 구문 수를 둘 다 기록). A 는 입력 단위.
지표(모드별): 기존 canonical · 기존 composite · 신규 ontology 후보 · 한→영 연결 성공(연결표 매칭) · 검증된 신규(EXACT/ACCEPTABLE) ·
 후보 중복(영어 쪽 후보가 기존 concept 으로 해소된 수) · UNKNOWN · UNCERTAIN · NON · 비증상 자동 매핑 위험(EXT_EVAL weak-non 903 → 기존/신규 연결) ·
 부적절 표시(STEP28 과 같은 proxy: 표시 후보에 한국어 어휘 근거 없음 — STEP28 ExistingSearch.lexical_support, 제품 매퍼·통증 규칙 예외 포함) ·
 구별 위반(코피 입력에 객혈·토혈 표시, 구토·토하 입력에 오심만 표시, 메스껍·오심·구역 입력에 구토 표시) · 원문 보존율.
실패 분석(D 의 UNKNOWN·UNCERTAIN 구문, 사전 고정 순서): SPAN_EXTRACTION_FAILURE → CONCEPT_AMBIGUITY → SEMANTIC_TYPE_MISMATCH(영어 후보가 질환형) →
 KOREAN_NORMALIZATION_FAILURE(정확·구문 일치 없고 n-gram 후보만) → ENGLISH_RETRIEVAL_FAILURE(연결은 있으나 ontology 미일치) →
 BILINGUAL_BRIDGE_MISSING(연결표 없음) → 기타 BODY_PART_ONLY·TYPE_UNCLEAR. LICENSE_RESTRICTION·ONTOLOGY_COVERAGE_MISSING 은 정답 영어 개념을 모르면 판정 불가
 (MDRKOR 미접근) → 개수 '측정 불가'.
'영어 ontology 에는 개념이 있으나 한국어 연결이 없어 실패' = 정답 영어 개념을 알아야 셀 수 있다 → Silver 전체는 측정 불가. smoke 중 지시문이 대응을 명시한
 코피(=Epistaxis)만 1건 확인.
출력: data/retrieval_results.csv · outputs/{retrieval_comparison.csv, new_concept_candidates.csv, failure_analysis.csv, smoke_cases.csv,
 weak_non_risk.csv, retrieval_summary.json}
"""
from __future__ import annotations

import collections
import json

import s285_common as S
from bilingual_retriever import Retriever

MODES = ("KO_ONLY", "EN_ONLY", "PARALLEL")
SMOKE = ["코피가 나요", "머리가 아파요", "열이 없어요", "숨이 차요", "토했어요", "메스꺼워요", "목이 아파요", "고혈압", "결핵",
         "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]


def violations(text, disp):
    x = S.nospace(text)
    v = []
    if "코피" in x and {"hemoptysis", "hematemesis"} & set(disp):
        v.append("EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS")
    if ("구토" in x or "토하" in x or "토했" in x) and "nausea" in disp and "vomiting" not in disp:
        v.append("VOMITING_AS_NAUSEA")
    if any(t in x for t in ("메스꺼", "메스껍", "오심", "구역")) and "vomiting" in disp and "nausea" not in disp:
        v.append("NAUSEA_AS_VOMITING")
    return v


def main():
    R = Retriever()
    from search_existing_concepts import ExistingSearch
    es = ExistingSearch(router=R.router)

    def unsupported(text, disp):
        mapc = {es.cw[m["evidence_id"]] for m in es.mapper.extract(text) if m["status"] == "POSITIVE" and m["evidence_id"] in es.cw}
        return [c for c in disp if c and not es.lexical_support(text, c) and c not in mapc]

    sil = S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")
    rows = []
    for r in sil:
        t = r["raw_expression"]
        rec = {m: R.run(t, m) for m in MODES}
        for m in MODES:
            for i, o in enumerate(rec[m]):
                disp = o["display"] if o["category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "UNCERTAIN") else []
                rows.append({"input": t, "mode": m, "span_idx": i, "n_spans": len(rec[m]), "span_text": o["span_text"], "query_ko": o["query_ko"],
                             "pred_class": o["pred_class"], "polarity": o["polarity"], "category": o["category"], "concept": o["concept"] or "",
                             "attributes": S.dumps(o.get("attributes") or {}), "display": ";".join(disp), "reason": o.get("reason", ""),
                             "ko_category": o.get("ko_category") or "", "ko_reason": o.get("ko_reason", ""), "en_category": o.get("en_category") or "",
                             "en_reason": o.get("en_reason", ""), "en_terms": ";".join(o.get("en_terms", [])), "en_validations": S.dumps(o.get("en_validations", [])),
                             "evidence_ko": " | ".join(o.get("evidence_ko", [])[:3]), "evidence_en": " | ".join(o.get("evidence_en", [])[:3]),
                             "ngram_targets": ";".join(o.get("ngram_targets", [])), "n_sources": o.get("n_sources", ""),
                             "unsupported_display": ";".join(unsupported(t, disp)), "violations": ";".join(violations(t, disp)),
                             "raw_preserved": o.get("raw_preserved", True), "step28_category": r["step28_category"]})
    S.wcsv(S.DATA / "retrieval_results.csv", rows)

    # 비증상(EXT_EVAL weak-non 903)
    dec = S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")
    wn = []
    for d in dec:
        for m in MODES:
            os_ = R.run(d["text"], m)
            cats = [o["category"] for o in os_]
            ev = " | ".join(e for o in os_ for e in (o.get("evidence_ko") or [])[:2])
            tier = ("MODEL_AUTO(B4)" if "MODEL_AUTO" in ev else "PAIN+SITE_RULE" if "PAIN+SITE" in ev else "EXACT" if "EXACT:" in ev
                    else "PHRASE" if "PHRASE:" in ev else "EN_LINK" if any(o.get("evidence_en") for o in os_) else "OTHER")
            wn.append({"text": d["text"], "mode": m, "categories": ";".join(cats), "concepts": ";".join(str(o["concept"] or "") for o in os_),
                       "step28_category": d["step28_category"], "evidence_ko": ev[:200], "evidence_tier": tier,
                       "risk": any(c in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE") for c in cats)})
    S.wcsv(S.OUT / "weak_non_risk.csv", wn)

    # smoke
    sm = []
    for t in SMOKE:
        for o in R.run(t, "PARALLEL"):
            ev = o.get("en_validations", [])
            sm.append({"input": t, "span_text": o["span_text"], "query_ko": o["query_ko"], "polarity": o["polarity"], "temporal": o["temporal"],
                       "subject": o["subject"], "category": o["category"], "concept": o["concept"] or "", "display": ";".join(o["display"]),
                       "reason": o.get("reason", ""), "ko_category": o.get("ko_category"), "en_category": o.get("en_category"),
                       "Q1_english_term_linked": ";".join(o.get("en_terms", [])) or "NO",
                       "Q2_ontology_concept_with_evidence": ";".join(f"{v['candidate_concept_id']}({v['check']})" for v in ev[:3]) or "NO",
                       "violations": ";".join(violations(t, o["display"]))})
    S.wcsv(S.OUT / "smoke_cases.csv", sm)

    # 지표
    comp, summ = [], {}
    A = collections.Counter(s["step28_category"] for s in sil)
    a_unsup = sum(bool(s["step28_unsupported_display"]) for s in sil)
    a_viol = sum(bool(violations(s["raw_expression"], s["display"].split(";") if s["display"] else [])) for s in sil)
    wnA = collections.Counter(d["step28_category"] for d in dec)
    met = {"A_STEP28": {"units": len(sil), "EXISTING_CANONICAL": A["EXISTING_CANONICAL"], "EXISTING_COMPOSITE": A["EXISTING_COMPOSITE"],
                        "NEW_ONTOLOGY_CANDIDATE": A["NEW_ONTOLOGY_CONCEPT"], "UNKNOWN_SYMPTOM": A["UNKNOWN_SYMPTOM"], "UNCERTAIN": A["UNCERTAIN"],
                        "NON_SYMPTOM": A["NON_SYMPTOM"], "ko_en_link_success": None, "verified_new": 0, "candidate_resolved_to_existing": None,
                        "nonsymptom_auto_mapping_risk(weak-non 903)": wnA["EXISTING_CANONICAL"] + wnA["EXISTING_COMPOSITE"] + wnA["NEW_ONTOLOGY_CONCEPT"],
                        "unsupported_display": a_unsup, "distinction_violations": a_viol, "raw_preservation_rate": 1.0}}
    for m in MODES:
        rs = [r for r in rows if r["mode"] == m]
        c = collections.Counter(r["category"] for r in rs)
        vals = [v for r in rs for v in json.loads(r["en_validations"])]
        met[m] = {"units": len(rs), "inputs": len({r["input"] for r in rs}), "EXISTING_CANONICAL": c["EXISTING_CANONICAL"], "EXISTING_COMPOSITE": c["EXISTING_COMPOSITE"],
                  "NEW_ONTOLOGY_CANDIDATE": c["NEW_ONTOLOGY_CANDIDATE"], "UNKNOWN_SYMPTOM": c["UNKNOWN_SYMPTOM"], "UNCERTAIN": c["UNCERTAIN"], "NON_SYMPTOM": c["NON_SYMPTOM"],
                  "ko_en_link_success": sum(1 for r in rs if r["en_category"] and r["en_reason"] not in ("BILINGUAL_BRIDGE_MISSING", "MODEL_CANDIDATE_ONLY")) if m != "KO_ONLY" else None,
                  "verified_new": sum(1 for v in vals if v.get("new_concept") and v.get("mapping_decision") in ("EXACT", "ACCEPTABLE")),
                  "candidate_resolved_to_existing": sum(1 for v in vals if str(v.get("check", "")).startswith(("DUPLICATE_OF_EXISTING", "NARROWER_AS_ATTRIBUTE", "BROADER"))),
                  "nonsymptom_auto_mapping_risk(weak-non 903)": sum(1 for w in wn if w["mode"] == m and w["risk"]),
                  "unsupported_display": sum(bool(r["unsupported_display"]) for r in rs), "distinction_violations": sum(bool(r["violations"]) for r in rs),
                  "raw_preservation_rate": S.rnd(sum(r["raw_preserved"] in (True, "True") for r in rs) / len(rs)),
                  "two_source_agreement": sum(1 for r in rs if str(r["n_sources"]) == "2") if m == "PARALLEL" else None}
    for k in met["PARALLEL"]:
        comp.append({"metric": k, **{m: met[m].get(k) for m in ("A_STEP28",) + MODES}})
    S.wcsv(S.OUT / "retrieval_comparison.csv", comp)

    # 신규 후보
    newc = []
    for r in rows:
        for v in json.loads(r["en_validations"]):
            if v.get("new_concept"):
                newc.append({"input": r["input"], "mode": r["mode"], **v, "model_supported": False, "relation_to_77": v.get("check")})
    S.wcsv(S.OUT / "new_concept_candidates.csv", newc,
           ["input", "mode", "candidate_concept_id", "concept_name", "check", "mapping_decision", "new_concept", "model_supported", "relation_to_77"])

    # 실패 분석(PARALLEL)
    fa = []
    for r in rows:
        if r["mode"] != "PARALLEL" or r["category"] not in ("UNKNOWN_SYMPTOM", "UNCERTAIN"):
            continue
        vs = json.loads(r["en_validations"])
        if r["reason"] == "SPAN_EXTRACTION_FAILURE":
            code = "SPAN_EXTRACTION_FAILURE"
        elif "CONCEPT_AMBIGUITY" in r["reason"] or r["ko_reason"] == "CONCEPT_AMBIGUITY":
            code = "CONCEPT_AMBIGUITY"
        elif any(v.get("check") == "NOT_SYMPTOM_TYPE" for v in vs):
            code = "SEMANTIC_TYPE_MISMATCH"
        elif r["ko_reason"] == "NGRAM_ONLY":
            code = "KOREAN_NORMALIZATION_FAILURE"
        elif r["en_reason"] == "ENGLISH_RETRIEVAL_FAILURE":
            code = "ENGLISH_RETRIEVAL_FAILURE"
        elif r["en_reason"] in ("BILINGUAL_BRIDGE_MISSING", "MODEL_CANDIDATE_ONLY"):
            code = "BILINGUAL_BRIDGE_MISSING"
        else:
            code = r["ko_reason"] or "TYPE_UNCLEAR"
        fa.append({"input": r["input"], "span_text": r["span_text"], "query_ko": r["query_ko"], "category": r["category"], "failure_code": code,
                   "ko_reason": r["ko_reason"], "en_reason": r["en_reason"], "ngram_targets": r["ngram_targets"],
                   "english_concept_exists_but_korean_link_missing": "UNMEASURABLE(정답 영어 개념 없음)"})
    S.wcsv(S.OUT / "failure_analysis.csv", fa)
    summ = {"metrics": met, "failure_codes(PARALLEL)": dict(collections.Counter(f["failure_code"] for f in fa)),
            "nonsymptom_risk_evidence_tier(PARALLEL)": dict(collections.Counter(w["evidence_tier"] for w in wn if w["mode"] == "PARALLEL" and w["risk"])),
            "english_concept_exists_but_korean_link_missing": {"silver": "측정 불가 — 정답 영어 개념이 없고 한·영 대응 자원이 없다",
                                                               "smoke_user_stated": "코피 → Epistaxis(HP:0000421, SNOMED 249366005) 1건: 영어 색인에 있음 · 한국어 연결 없음"},
            "LICENSE_RESTRICTION": "측정 불가 — MDRKOR 를 열지 않았다(사용자 지시)", "ONTOLOGY_COVERAGE_MISSING": "측정 불가 — 영어 질의가 없는 구문은 판정할 수 없다",
            "model_path_enabled": R.model_path}
    S.dump_json(S.OUT / "retrieval_summary.json", summ)
    print(S.dumps(summ["metrics"]))
    print(S.dumps(summ["failure_codes(PARALLEL)"]))


if __name__ == "__main__":
    main()
