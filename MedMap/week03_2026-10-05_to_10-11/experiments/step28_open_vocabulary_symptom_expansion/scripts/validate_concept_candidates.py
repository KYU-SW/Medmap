"""STEP28 후보 concept 검증(사전 고정 규칙). 문자열 유사도만으로 EXACT 를 주지 않는다.

validate(cand, evidence_path, existing):
 1 존재·활성: 색인에 없음 → UNCERTAIN(NOT_IN_INDEX) · HPO obsolete / SNOMED 비활성 → WRONG(INACTIVE, replaced_by 기록)
 2 유형: HPO phenotype 하위 아님 · UMLS 의미유형에 질환류(DISEASE_STY, T046 제외)가 있고 Sign or Symptom(T184)이 없음 · SNOMED 'disorder' 이면서 증상류 의미유형(T184·T033)도
   HPO phenotype 연결도 없음 → WRONG(NOT_SYMPTOM_TYPE). (SNOMED 은 토혈 등 증상도 disorder 로 표기 → 태그 단독 판정 안 함)
 3 기존 77 과의 관계(중복 통제). 계층 = 후보 + 같은 CUI 의 다른 ontology code 들의 조상 합집합(HPO·SNOMED 교차):
   같은 id·같은 CUI → DUPLICATE_OF_EXISTING(신규 아님) ·
   기존 concept 하위 + 그 concept 이 속성 칸(ATTRIBUTE_SLOT_CONCEPTS, 예 pain→E_55 부위)을 가짐 → NARROWER_AS_ATTRIBUTE(기존+속성, 신규 아님) ·
   기존 concept 하위 + 속성 칸 없음 → 신규 후보(new_concept, 상위 기존 concept 연결 기록 NARROWER_THAN_EXISTING) ·
   기존 concept 상위 → BROADER(신규 아님).
 [변경 기록] 2·3 의 세부(T046 제외, 질환류+T184 없음, CUI 교차 계층, 속성 칸 구분)는 영어 이름 관계 검사(CLI: Epistaxis·Hemoptysis·Hematemesis·
   Headache·Pain·Fever·Hypertension·Tuberculosis) 결과를 본 뒤, 데이터 평가 실행 전에 고쳤다 → 이 8개 개념의 결과는 회귀 확인용이다.
 4 근거 경로: C(XLM-R 자동) → UNCERTAIN(AUTO_CANDIDATE) — 이번 단계에서 의미 검증 근거로 인정하지 않음.
   한국어 근거가 MedMap 검증 용어(경로 A/B)이고 curated 매핑이 EXACT → EXACT, ACCEPTABLE → ACCEPTABLE.
 5 정의 없음(HPO def·SNOMED 정의 모두 없음) → EXACT/ACCEPTABLE 불가, 최고 UNCERTAIN.
 mapping_decision ∈ EXACT · ACCEPTABLE · BROADER · NARROWER · RELATED_ONLY · WRONG · UNCERTAIN (+ new_concept 여부, 표시 허용 여부)

CLI: 대표 개념 관계 검사(Epistaxis·Hemoptysis·Hematemesis 등 — 영어 이름으로 색인 조회) → outputs/concept_relation_checks.json
"""
from __future__ import annotations

import s28_common as S
from search_new_ontology_concepts import OntologyIndex


def existing_ids(inv_rows) -> dict[str, str]:
    """기존 curated id(HP·SCTID·CUI) → canonical."""
    out = {}
    for r in inv_rows:
        for col, pre in (("hpo_ids", ""), ("snomed_ids", "SCTID:"), ("umls_cuis", "CUI:")):
            for x in r[col].split(";"):
                if x:
                    out[pre + x if not x.startswith(pre) else x] = r["canonical_id"]
    return out


def validate(oi: OntologyIndex, cand: dict, path: str, existing: dict[str, str], curated_class: str = "") -> dict:
    cid = cand["cid"]
    c = oi.concept(cid)
    rec = {"candidate_concept_id": cid, "ontology_source": (c or {}).get("source", cid.split(":")[0]), "concept_name": (c or {}).get("name", ""),
           "definition": ((c or {}).get("definition") or "")[:300], "semantic_type": ";".join(f"{t}:{n}" for t, n in oi.sty(cid)),
           "active_status": (c or {}).get("active"), "kind": (c or {}).get("kind", ""), "parent_concepts": ";".join((c or {}).get("parents", [])[:5]),
           "evidence_source": path, "lexical_score": cand.get("lexical_score"), "matched_term": cand.get("matched_term", "")}
    if c is None:
        return {**rec, "mapping_decision": "UNCERTAIN", "mapping_confidence": "none", "check": "NOT_IN_INDEX", "new_concept": False, "display_allowed": False}
    if not c["active"]:
        return {**rec, "mapping_decision": "WRONG", "mapping_confidence": "none", "check": f"INACTIVE(replaced_by={c['replaced_by']})", "new_concept": False,
                "display_allowed": False}
    tuis = {t for t, _ in oi.sty(cid)}
    sib = sorted({code for u in oi.cuis(cid) for code in oi.codes(u)} - {cid})
    hpo_pheno = any((oi.concept(x) or {}).get("kind") == "phenotype" for x in [cid] + sib if x.startswith("HP:"))
    if ((c["source"] == "HPO" and c["kind"] != "phenotype") or (tuis & S.DISEASE_STY and "T184" not in tuis)
            or (c["kind"] == "disorder" and not (tuis & S.SYMPTOM_STY) and not hpo_pheno)):
        return {**rec, "mapping_decision": "WRONG", "mapping_confidence": "none", "check": "NOT_SYMPTOM_TYPE", "new_concept": False, "display_allowed": False}
    same = [existing[x] for x in [cid] + sib + [f"CUI:{u}" for u in oi.cuis(cid)] if x in existing]
    if same:
        return {**rec, "mapping_decision": "EXACT" if path in ("A", "B") else "UNCERTAIN", "mapping_confidence": "existing",
                "check": f"DUPLICATE_OF_EXISTING:{same[0]}", "new_concept": False, "display_allowed": False, "existing_canonical": same[0]}
    anc = set(oi.ancestors(cid))
    for x in sib:
        anc |= oi.ancestors(x)
    under = sorted({existing[a] for a in anc if a in existing})
    slot = [u for u in under if u in S.ATTRIBUTE_SLOT_CONCEPTS]
    if slot:
        return {**rec, "mapping_decision": "NARROWER", "mapping_confidence": "hierarchy", "check": f"NARROWER_AS_ATTRIBUTE:{slot[0]}+{S.ATTRIBUTE_SLOT_CONCEPTS[slot[0]]}",
                "new_concept": False, "display_allowed": False, "existing_canonical": slot[0]}
    rec["broader_existing"] = ";".join(under)
    above = sorted({canon for e, canon in existing.items() if e.split(":")[0] in ("HP", "SCTID") and any(y in oi.ancestors(e) for y in [cid] + sib)})
    if above:
        return {**rec, "mapping_decision": "BROADER", "mapping_confidence": "hierarchy", "check": f"BROADER_THAN_EXISTING:{';'.join(above)}",
                "new_concept": False, "display_allowed": False}
    tag = f";NARROWER_THAN_EXISTING:{rec['broader_existing']}" if rec["broader_existing"] else ""
    if path == "C":
        return {**rec, "mapping_decision": "UNCERTAIN", "mapping_confidence": "auto_candidate", "check": "AUTO_CANDIDATE(XLMR)" + tag, "new_concept": True,
                "display_allowed": False}
    if not rec["definition"]:
        return {**rec, "mapping_decision": "UNCERTAIN", "mapping_confidence": "no_definition", "check": "NO_DEFINITION" + tag, "new_concept": True,
                "display_allowed": False}
    dec = curated_class if curated_class in ("EXACT", "ACCEPTABLE") else "UNCERTAIN"
    return {**rec, "mapping_decision": dec, "mapping_confidence": "korean_verified_term" if dec != "UNCERTAIN" else "weak", "check": "NEW_CONCEPT" + tag,
            "new_concept": True, "display_allowed": dec in ("EXACT", "ACCEPTABLE")}


def relation(oi: OntologyIndex, a: str, b: str) -> dict:
    aa, bb = oi.ancestors(a), oi.ancestors(b)
    common = aa & bb
    rel = "SAME" if a == b else "A_IS_A_B" if b in aa else "B_IS_A_A" if a in bb else "DISTINCT"
    near = sorted(common, key=lambda x: -len(oi.ancestors(x)))[:3]
    return {"a": a, "a_name": (oi.concept(a) or {}).get("name"), "b": b, "b_name": (oi.concept(b) or {}).get("name"), "relation": rel,
            "nearest_common_ancestors": [(x, (oi.concept(x) or {}).get("name")) for x in near]}


def main():
    oi = OntologyIndex()
    names = {"Epistaxis": None, "Hemoptysis": None, "Hematemesis": None, "Headache": None, "Fever": None, "Pain": None, "Hypertension": None,
             "Tuberculosis": None}
    found = {}
    for n in names:
        hits = oi.search_en(n, k=20)
        found[n] = {"hpo": next((h for h in hits if h["cid"].startswith("HP:")), None), "snomed": next((h for h in hits if h["cid"].startswith("SCTID:")), None)}
    pairs = []
    for src in ("hpo", "snomed"):
        e = (found["Epistaxis"][src] or {}).get("cid")
        for other in ("Hemoptysis", "Hematemesis"):
            o = (found[other][src] or {}).get("cid")
            if e and o:
                pairs.append({"source": src, **relation(oi, e, o)})
        h, p = (found["Headache"][src] or {}).get("cid"), (found["Pain"][src] or {}).get("cid")
        if h and p:
            pairs.append({"source": src, **relation(oi, h, p)})
    inv = S.read_csv(S.DATA / "existing_concept_inventory.csv")
    ex = existing_ids(inv)
    vals = {n: {src: validate(oi, found[n][src], "B", ex) if found[n][src] else None for src in ("hpo", "snomed")} for n in names}
    S.dump_json(S.OUT / "concept_relation_checks.json", {"english_lookup": found, "pairwise_relations": pairs, "validation_as_if_linked": vals,
                                                         "note": "영어 이름 조회 결과(한국어 연결 아님). validation_as_if_linked 는 한국어 근거가 있다고 가정했을 때의 검증 결과"})
    for p in pairs:
        print(p)
    for n, v in vals.items():
        print(n, {k: (x or {}).get("check") for k, x in v.items()})


if __name__ == "__main__":
    main()
