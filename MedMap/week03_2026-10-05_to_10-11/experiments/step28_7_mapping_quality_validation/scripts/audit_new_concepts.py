"""STEP28.7 §1·§3·§4·§5 — STEP28.6 신규 후보 원본 집계 재검증 + concept 별 사실 수집(판단 없음, LLM 없음).

1 집계 재계산(outputs/new_concept_candidates.csv 원본 행 기준):
  - STEP28.6 보고 '34' = G3 고유 22 + G2 고유 12 의 **등급별 고유 수 합**인지, concept 고유 합집합인지 확인.
  - concept 이 두 등급에 동시에 나오면(다른 한국어 입력) 등급별 합은 중복을 센다 → 고유 합집합·최고 등급 기준 수를 따로 낸다.
  - G1(단일 작성자)·REJECTED 포함 여부를 명시.
2 concept 별 사실(로컬 색인만): source · preferred label · definition · semantic type · active · 부모(이름) · 기존 77 상위 연결 ·
  같은 CUI 의 HPO id · 한국어 표현 · 작성자 A/B 영어 · 등급 · 감사 · 지지 행의 조각·격리 상태 · 출처(SILVER442/WEAKNON903/SMOKE).
3 §4 우선 쌍 관계(HPO·SNOMED 계층): lethargy↔fatigue · dry cough↔cough · loose stool↔diarrhea · tremor↔chills ·
  epistaxis↔hemoptysis/hematemesis · vomiting↔nausea. 기존 쪽 id 는 existing_concept_inventory(STEP20 curated).
4 §5 SNOMED 전용 후보 로컬 감사: id 유효·active·clinical finding 계층 소속·부모·자식 수·HPO 교차·기존 77 관계.
  SNOMED 문자열은 외부로 보내지 않는다. 한국어 대응 정확성은 이 단계에서 확인 불가 → UNVERIFIED.
출력: outputs/count_reconciliation.json · data/concept_facts.csv(LOCAL_ONLY) · outputs/priority_pair_relations.json(LOCAL_ONLY) ·
     data/snomed_local_audit.csv(LOCAL_ONLY)
"""
from __future__ import annotations

import collections
import json

import s287_common as S
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids, relation

PRIORITY = [("lethargy", "HP:0001254", "fatigue"), ("dry cough", "HP:0031246", "cough"), ("loose stool", "SCTID:398032003", "diarrhea"),
            ("tremor", "HP:0001337", "chills"), ("hand tremor", "HP:0002378", "chills"), ("fine tremor", "SCTID:42800007", "chills"),
            ("epistaxis", "HP:0000421", "hemoptysis"), ("epistaxis", "HP:0000421", "hematemesis"), ("epistaxis", "HP:0000421", "EV:E_178"),
            ("chronic cough", "HP:0034315", "cough"), ("tachycardia", "HP:0001649", "palpitations"), ("drowsiness", "HP:0002329", "fatigue"),
            ("high fever", "HP:0033031", "fever"), ("muscle fatigue", "HP:0003750", "fatigue"), ("stiffness", "SCTID:271587009", "EV:E_193"),
            ("tingling", "SCTID:62507009", "EV:E_177"), ("muscle cramp", "SCTID:55300003", "EV:E_193"), ("spasticity", "HP:0001257", "EV:E_193"),
            ("epigastric discomfort", "SCTID:119416008", "pain"), ("cold sweat", "SCTID:83547004", "EV:E_50"), ("collapse", "SCTID:271787007", "loc"),
            ("collapse", "SCTID:271787007", "EV:E_82")]
VOM_NAU = ("vomiting", "nausea")


def main():
    oi = OntologyIndex(S.ONT_DB)
    inv = S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")
    ex = existing_ids(inv)
    inv_by = {r["canonical_id"]: r for r in inv}
    man = S.read_csv(S.S286_DIR / "data/expression_manifest.csv")
    chunk = S.chunk_of([m["id"] for m in man])
    sess = S.isolation_by_session()
    rows = S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv")
    links = {r["id"]: r for r in S.read_csv(S.S286_DIR / "data/ontology_links.csv")}

    # ---- 1 집계 ----
    by_c = collections.defaultdict(set)
    for r in rows:
        by_c[r["concept_id"]].add(r["grade"])
    per_grade = {g: sorted(c for c, gs in by_c.items() if g in gs) for g in S.GRADES}
    best = {c: min(gs, key=S.GRADES.index) for c, gs in by_c.items()}
    multi = {c: sorted(gs, key=S.GRADES.index) for c, gs in by_c.items() if len(gs) > 1}
    g2p = sorted(c for c, gs in by_c.items() if gs & {"G3_SILVER_AUDITED", "G2_SILVER_AGREED"})
    rep = S.load_json(S.S286_DIR / "outputs/linking_metrics.json")["new_distinct_concepts_by_grade"]
    rec = {"source_file": "exp/step28_6_llm_assisted_linking/outputs/new_concept_candidates.csv", "n_rows": len(rows),
           "rows_by_source": dict(collections.Counter(r["sources"] for r in rows)),
           "step28_6_reported_by_grade": rep, "step28_6_reported_34_definition": "G3 고유 22 + G2 고유 12 (등급별 고유 수의 단순 합)",
           "recomputed_per_grade_distinct": {g: len(v) for g, v in per_grade.items()},
           "concepts_in_multiple_grades": multi,
           "distinct_G2plus_union": len(g2p), "distinct_all_grades_union": len(by_c),
           "distinct_by_best_grade": dict(collections.Counter(best.values())),
           "G1_or_REJECTED_in_34": "아니오 — 34 는 G3·G2 만. 단 G1 6 중 SCTID:55300003 은 G2 에도 있어 34 안에 concept 으로 포함, REJECTED HP:0003750 은 G3/G2 에 없음",
           "discrepancy": None}
    if sum(rep[g] for g in ("G3_SILVER_AUDITED", "G2_SILVER_AGREED")) != len(g2p):
        rec["discrepancy"] = {"reported_sum_G3_G2": rep["G3_SILVER_AUDITED"] + rep["G2_SILVER_AGREED"], "distinct_union_G2plus": len(g2p),
                              "cause": "같은 concept 이 서로 다른 한국어 입력에서 다른 등급을 받으면 등급별 고유 수 합이 중복을 센다",
                              "double_counted": sorted(c for c in g2p if {"G3_SILVER_AUDITED", "G2_SILVER_AGREED"} <= by_c[c]),
                              "correction": "STEP28.6 산출물은 수정하지 않는다. STEP28.7 은 'ORIGINAL_NEW_CANDIDATES=34(보고 기준)'를 유지하고 고유 기준 33·전 등급 39 를 함께 보고"}
    S.dump_json(S.OUT / "count_reconciliation.json", rec)

    # ---- 2 concept 사실 ----
    facts = []
    for cid in sorted(by_c, key=lambda c: (S.GRADES.index(best[c]), c)):
        rs = [r for r in rows if r["concept_id"] == cid]
        c = oi.concept(cid) or {}
        cuis = oi.cuis(cid)
        sib = sorted({x for u in cuis for x in oi.codes(u)} - {cid})
        hpo_x = [x for x in sib if x.startswith("HP:")]
        anc = set(oi.ancestors(cid))
        for x in sib:
            anc |= oi.ancestors(x)
        under = sorted({ex[a] for a in anc if a in ex})
        ids = sorted({r["id"] for r in rs})
        supp = []
        for i in ids:
            l = links[i]
            for w in ("A", "B"):
                if l[f"{w}_cat"] == "NEW_ONTOLOGY_CANDIDATE" and l[f"{w}_concept"] == cid:
                    supp.append(f"{i}:{w}:{chunk[i]}:{S.row_isolation(w, chunk[i], sess)}")
        aud = {}
        for r in rs:
            a = json.loads(r["audit"] or "{}").get(cid)
            if a:
                aud[r["korean"]] = a
        facts.append({"concept_id": cid, "ontology_source": c.get("source", cid.split(":")[0]), "preferred_label": c.get("name", ""),
                      "definition": (c.get("definition") or "")[:400], "semantic_type": ";".join(f"{t}:{n}" for t, n in oi.sty(cid)),
                      "active_status": c.get("active"), "kind": c.get("kind", ""),
                      "parents": ";".join(f"{p}|{(oi.concept(p) or {}).get('name', '')}" for p in c.get("parents", [])[:6]),
                      "hpo_crossref": ";".join(hpo_x), "cuis": ";".join(cuis), "existing_ancestors(77)": ";".join(under),
                      "korean_expressions": " | ".join(sorted({r["korean"] for r in rs})), "input_ids": ";".join(ids),
                      "sources": ";".join(sorted({r["sources"] for r in rs})),
                      "english_A": ";".join(sorted({r["english"] for r in rs if r["author"] == "A"})),
                      "english_B": ";".join(sorted({r["english"] for r in rs if r["author"] == "B"})),
                      "grades": ";".join(sorted(by_c[cid], key=S.GRADES.index)), "best_grade": best[cid],
                      "in_reported_34": cid in g2p, "audit": S.dumps(aud), "supporting_rows": " ".join(supp),
                      "isolation_flags": ";".join(sorted({s.split(":")[-1] for s in supp})), "check": ";".join(sorted({r["check"] for r in rs}))})
    S.wcsv(S.DATA / "concept_facts.csv", facts)

    # ---- 3 우선 쌍 관계 ----
    def ex_ids(canon):
        r = inv_by[canon]
        return ([x for x in r["hpo_ids"].split(";") if x] + ["SCTID:" + x for x in r["snomed_ids"].split(";") if x and not x.startswith("sct")])
    pairs = []
    for name, cid, canon in PRIORITY:
        for eid in ex_ids(canon):
            if oi.concept(eid):
                pairs.append({"new": name, "canonical": canon, **relation(oi, cid, eid)})
    vn = [relation(oi, a, b) for a in ex_ids(VOM_NAU[0]) for b in ex_ids(VOM_NAU[1]) if oi.concept(a) and oi.concept(b) and a.split(":")[0] == b.split(":")[0]]
    S.dump_json(S.OUT / "priority_pair_relations.json", {"LOCAL_ONLY": "SNOMED 이름 포함 — 공개 금지", "pairs": pairs, "vomiting_vs_nausea": vn,
                                                         "note": "relation = ontology 계층(is-a)만. SAME/A_IS_A_B/B_IS_A_A/DISTINCT. 계층 관계는 동의어 근거가 아니다(§10)"})

    # ---- 4 SNOMED 전용 ----
    sn = []
    for f in facts:
        cid = f["concept_id"]
        if not cid.startswith("SCTID:") or f["hpo_crossref"]:
            continue
        c = oi.concept(cid) or {}
        kids = oi.q("SELECT cid FROM concept WHERE parents LIKE ?", f"%{cid[6:]}%")
        kids = [k[0] for k in kids if cid[6:] in (oi.concept(k[0]) or {}).get("parents", []) or cid in (oi.concept(k[0]) or {}).get("parents", [])]
        anc = oi.ancestors(cid)
        sn.append({"concept_id": cid, "id_valid": bool(c), "active_status": c.get("active"),
                   "in_clinical_finding_hierarchy": S.S28.SCT_FINDING_ROOT in {a.removeprefix("SCTID:") for a in anc},
                   "kind": c.get("kind", ""), "preferred_description(LOCAL_ONLY)": c.get("name", ""), "definition_present": bool(c.get("definition")),
                   "parents(LOCAL_ONLY)": f["parents"], "n_children": len(kids), "existing_ancestors(77)": f["existing_ancestors(77)"],
                   "semantic_type": f["semantic_type"], "korean_expressions": f["korean_expressions"], "best_grade": f["best_grade"],
                   "hpo_audit_possible": False, "korean_mapping_verification": "UNVERIFIED(HPO 대응 없음·SNOMED 문자열 외부 전송 금지·인간 검토 없음)"})
    S.wcsv(S.DATA / "snomed_local_audit.csv", sn)
    print(S.dumps({k: rec[k] for k in ("step28_6_reported_by_grade", "recomputed_per_grade_distinct", "concepts_in_multiple_grades", "distinct_G2plus_union",
                                       "distinct_all_grades_union", "distinct_by_best_grade")}))
    print("facts", len(facts), "pairs", len(pairs), "snomed_only", len(sn))


if __name__ == "__main__":
    main()
