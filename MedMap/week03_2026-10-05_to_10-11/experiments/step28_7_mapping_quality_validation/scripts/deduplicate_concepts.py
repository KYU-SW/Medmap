"""STEP28.7 §3·§4 — 신규 concept 후보 39(STEP28.6 보고 34 = G3 22 + G2 12) 최종 분류·중복 정리. LLM 없음.

입력: data/concept_facts.csv(audit_new_concepts — 로컬 색인 사실) · data/concept_review_decisions.csv(분류 결정) ·
     outputs/isolation_analysis.json · STEP28.6 audit_manifest(감사 상태).
분류 결정 출처(사전 명시): data/concept_review_decisions.csv 는 STEP28.7 Claude 세션이 사실 표(계층 관계·정의·감사·한국어 표현)를 보고 작성했다.
 → 인간 검토 아님(EVIDENCE LEVEL_4 아님) · STEP28.6 작성자 A·감사자(opus)와 같은 모델 계열이라 독립 검증도 아님.
분류: A EXISTING_SYNONYM · B EXISTING_COMPOSITE · C EXISTING_SUBTYPE · D NEW_INDEPENDENT_CONCEPT · E NON_SYMPTOM · F UNCERTAIN.
보존 규칙: concept 이 등급 REJECTED 이거나 G1 이면 신규 유지 안 함(보류·반려 파일). D 는 신규 후보 유지(SILVER, MODEL_SUPPORTED=False).
 C 는 '기존 하위' 로 기록하고 부모 feature 자동 통합 금지(parent_feature_candidate 는 연구용 표시일 뿐).
출력: data/audited_concepts.csv · outputs/{concept_audit.json, independent_new_concepts.csv, existing_synonyms.csv, existing_subtypes.csv,
     held_candidates.csv, rejected_candidates.csv}
"""
from __future__ import annotations

import collections
import json

import s287_common as S

CLASS_NAME = {"A": "EXISTING_SYNONYM", "B": "EXISTING_COMPOSITE", "C": "EXISTING_SUBTYPE", "D": "NEW_INDEPENDENT_CONCEPT", "E": "NON_SYMPTOM", "F": "UNCERTAIN"}


def main():
    facts = {r["concept_id"]: r for r in S.read_csv(S.DATA / "concept_facts.csv")}
    dec = {r["concept_id"]: r for r in S.read_csv(S.DATA / "concept_review_decisions.csv")}
    assert set(facts) == set(dec), (set(facts) ^ set(dec))
    am = S.read_csv(S.S286_DIR / "data/audit_manifest.csv")
    astat = collections.defaultdict(set)
    for r in am:
        astat[r["concept_id"]].add(r["audit_status"])
    rows = []
    for cid, f in facts.items():
        d = dec[cid]
        aud = json.loads(f["audit"] or "{}")
        labels = sorted({v[0] for v in aud.values()})
        iso = f["isolation_flags"]
        grades = f["grades"].split(";")
        if "REJECTED" in grades and not ({"G3_SILVER_AUDITED", "G2_SILVER_AGREED"} & set(grades)):
            keep, why = "REJECTED", "STEP28.6 감사 RELATED_ONLY/WRONG"
        elif not ({"G3_SILVER_AUDITED", "G2_SILVER_AGREED"} & set(grades)):
            keep, why = "HELD", "G1 단일 작성자"
        elif d["final_class"] == "D":
            keep, why = "KEEP_NEW_CANDIDATE", ""
        elif d["final_class"] in ("A", "B", "C"):
            keep, why = "MERGE_AS_EXISTING_RELATION", f"기존 {d['related_canonical']} 의 {CLASS_NAME[d['final_class']]}"
        elif d["final_class"] == "E":
            keep, why = "REJECTED", "비증상"
        else:
            keep, why = "HELD", "분류 불확실"
        if "ISOLATION_FAIL" in iso and "ISOLATION_PASS" not in iso:
            why = (why + " · " if why else "") + "지지 행 전부 격리 FAIL 조각"
        snomed_only = cid.startswith("SCTID:") and not f["hpo_crossref"]
        rows.append({"concept_id": cid, "korean_expressions": f["korean_expressions"], "english_A": f["english_A"], "english_B": f["english_B"],
                     "ontology_source": f["ontology_source"], "preferred_label": f["preferred_label"], "definition": f["definition"][:200],
                     "semantic_type": f["semantic_type"], "active_status": f["active_status"], "existing_ancestors(77)": f["existing_ancestors(77)"],
                     "related_canonical": d["related_canonical"], "final_class": d["final_class"], "relation_to_existing": d["relation_to_existing"],
                     "parent_feature_candidate": d["parent_feature_candidate"], "new_concept_family": d["new_concept_family"],
                     "step28_6_grades": f["grades"], "in_reported_34": f["in_reported_34"],
                     "hpo_audit": ";".join(labels) or ("NOT_AUDITED_LICENSE(SNOMED 전용)" if snomed_only else
                                                       "NOT_AUDITED_NO_HPO_DEFINITION" if "NOT_AUDITED_NO_HPO_DEFINITION" in astat[cid] else "NONE"),
                     "audit_dependency": "감사자 opus = 작성자 A 와 같은 모델 · 입력 = 한국어 + HPO 이름·정의(작성자 출력 미전송)" if labels else "",
                     "snomed_only": snomed_only, "isolation_flags": iso, "keep_decision": keep, "hold_or_reject_reason": why or "",
                     "classification_reason": d["reason"], "classified_by": "STEP28.7 Claude 세션(비인간·비독립)", "human_verified": False,
                     "model_supported": False, "usable_by_disease_model": False})
    S.wcsv(S.DATA / "audited_concepts.csv", rows)
    sel = lambda pred: [r for r in rows if pred(r)]  # noqa: E731
    S.wcsv(S.OUT / "independent_new_concepts.csv", sel(lambda r: r["final_class"] == "D" and r["keep_decision"] == "KEEP_NEW_CANDIDATE"))
    S.wcsv(S.OUT / "existing_synonyms.csv", sel(lambda r: r["final_class"] in ("A", "B")))
    S.wcsv(S.OUT / "existing_subtypes.csv", sel(lambda r: r["final_class"] == "C"))
    S.wcsv(S.OUT / "held_candidates.csv", sel(lambda r: r["keep_decision"] == "HELD"))
    S.wcsv(S.OUT / "rejected_candidates.csv", sel(lambda r: r["keep_decision"] == "REJECTED"))

    def counts(rs):
        c = collections.Counter(r["final_class"] for r in rs)
        return {CLASS_NAME[k]: c.get(k, 0) for k in "ABCDEF"}
    in34 = [r for r in rows if r["in_reported_34"] in (True, "True")]
    ind = sel(lambda r: r["final_class"] == "D" and r["keep_decision"] == "KEEP_NEW_CANDIDATE")
    fams = {r["new_concept_family"] or r["concept_id"] for r in ind}
    summ = {"ORIGINAL_NEW_CANDIDATES(reported)": 34, "distinct_in_reported_34": len(in34), "distinct_all_grades": len(rows),
            "by_class(all 39)": counts(rows), "by_class(34-set distinct 33)": counts(in34),
            "INDEPENDENT_NEW_CONCEPTS": len(ind), "independent_new_concept_families(tremor 하위 묶음)": len(fams),
            "independent_new_HPO_audited_EXACT": sum(1 for r in ind if r["hpo_audit"] == "EXACT"),
            "independent_new_SNOMED_only_UNVERIFIED": sum(1 for r in ind if r["snomed_only"] in (True, "True")),
            "EXISTING_SYNONYMS": len(sel(lambda r: r["final_class"] == "A")), "EXISTING_COMPOSITES": len(sel(lambda r: r["final_class"] == "B")),
            "EXISTING_SUBTYPES": len(sel(lambda r: r["final_class"] == "C")),
            "overlap_with_77(A+B+C)": len(sel(lambda r: r["final_class"] in ("A", "B", "C"))),
            "HELD_CANDIDATES": len(sel(lambda r: r["keep_decision"] == "HELD")), "REJECTED_CANDIDATES": len(sel(lambda r: r["keep_decision"] == "REJECTED")),
            "ISOLATION_FAIL_ONLY_CANDIDATES": len(sel(lambda r: "ISOLATION_FAIL" in r["isolation_flags"] and "ISOLATION_PASS" not in r["isolation_flags"])),
            "ISOLATION_MIXED_CANDIDATES": len(sel(lambda r: "ISOLATION_FAIL" in r["isolation_flags"] and "ISOLATION_PASS" in r["isolation_flags"])),
            "SNOMED_only(all)": len(sel(lambda r: r["snomed_only"] in (True, "True"))), "SNOMED_only(34-set)": sum(1 for r in in34 if r["snomed_only"] in (True, "True")),
            "HUMAN_VERIFIED_GOLD": 0, "classified_by": "STEP28.7 Claude 세션(비인간·비독립) — 분류는 SILVER",
            "priority_cases": {k: next(({x: r[x] for x in ("final_class", "relation_to_existing", "related_canonical", "keep_decision")} for r in rows
                                        if r["concept_id"] == k), None)
                               for k in ("HP:0001254", "HP:0031246", "SCTID:398032003", "HP:0001337", "HP:0000421")}}
    S.dump_json(S.OUT / "concept_audit.json", summ)
    print(S.dumps(summ))


if __name__ == "__main__":
    main()
