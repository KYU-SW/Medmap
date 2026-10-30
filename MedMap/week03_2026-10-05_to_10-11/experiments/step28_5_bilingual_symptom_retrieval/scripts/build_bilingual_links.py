"""STEP28.5 한국어 → 영어 연결표(근거 있는 쌍만). 번역 생성 없음.

연결 종류(link_type):
 EN_TERM_EXACT  : 한국어 용어의 영어 쌍(같은 MedMap/DDXPlus 레코드의 영어 이름)이 STEP28 색인 영어 term 과 정규화 완전일치 → concept id
 ID_ANCHORED    : 한국어 용어가 STEP20 curated HPO/SNOMED/CUI id 를 직접 가진다(영어 문자열 검색 없이 id 연결)
 UMLS_CUI       : UMLS KOR SRL0 행의 CUI 직접 연결
 ATTRIBUTE_EN   : 부위·값 영어 의미(값 차원, concept 검색 대상 아님)
 QUESTION_ONLY  : 영어 쪽이 질문 문장뿐(용어 아님) → 영어 검색에 쓰지 않음
 NONE           : 영어 쌍 없음
각 한국어 키별로 77 안/밖(신규 가능) 여부를 표시: 연결된 concept 이 기존 77 curated id·같은 CUI 이면 INSIDE_77.
출력: index/bilingual_links.csv(LOCAL) · outputs/bilingual_link_coverage.csv
"""
import collections

import s285_common as S
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids


def main():
    oi = OntologyIndex(S.ONT_DB)
    ex = existing_ids(S.read_csv(S.S28.DATA / "existing_concept_inventory.csv"))
    rows = S.read_csv(S.INDEX / "korean_index.csv")
    out = []
    for r in rows:
        ids, lt, en_hits = [], "NONE", []
        if r["target_type"] == "UMLS_CUI":
            ids, lt = [r["target_id"]], "UMLS_CUI"
        elif r["role"] in ("BODY_SITE", "VALUE"):
            lt = "ATTRIBUTE_EN" if r["en_term"] else "NONE"
        elif r["role"] in ("ANTECEDENT", "ATTRIBUTE") and not r["ontology_ids"]:
            lt = "QUESTION_ONLY" if r["en_term"] else "NONE"
        else:
            if r["ontology_ids"]:
                ids += [x for x in r["ontology_ids"].split(";") if x]
                lt = "ID_ANCHORED"
            if r["en_term"] and r["role"] in ("SYMPTOM", "DISEASE"):
                en_hits = [h["cid"] for h in oi.search_en(r["en_term"].split(" (")[0], k=5) if h["lexical_score"] == 1.0]
                if en_hits:
                    ids += en_hits
                    lt = "EN_TERM_EXACT" if lt == "NONE" else lt + "+EN_TERM_EXACT"
        cuis = {u for i in ids for u in oi.cuis(i)} | {i[4:] for i in ids if i.startswith("CUI:")}
        inside = any(i in ex for i in ids) or any(f"CUI:{u}" in ex for u in cuis) or r["target_type"] == "CANONICAL"
        out.append({**r, "link_type": lt, "linked_concept_ids": ";".join(dict.fromkeys(ids)), "linked_cuis": ";".join(sorted(cuis)),
                    "scope": ("INSIDE_77" if inside else "OUTSIDE_77") if ids else "NO_CONCEPT"})
    S.wcsv(S.INDEX / "bilingual_links.csv", out)
    cov = []
    for (src, role), g in sorted(collections.Counter((r["provenance"].split(":")[0], r["role"]) for r in out).items()):
        rs = [r for r in out if r["provenance"].split(":")[0] == src and r["role"] == role]
        lt = collections.Counter(r["link_type"] for r in rs)
        cov.append({"source": src, "role": role, "korean_terms": len(rs), "with_english_pair": sum(bool(r["en_term"]) for r in rs),
                    "linked_to_concept_id": sum(bool(r["linked_concept_ids"]) for r in rs),
                    "en_term_exact_ontology_hit": sum("EN_TERM_EXACT" in r["link_type"] for r in rs),
                    "inside_77": sum(r["scope"] == "INSIDE_77" for r in rs), "outside_77": sum(r["scope"] == "OUTSIDE_77" for r in rs),
                    "outside_77_symptom_type": sum(1 for r in rs if r["scope"] == "OUTSIDE_77" and r["role"] == "SYMPTOM"),
                    "link_types": S.dumps(dict(lt))})
    S.wcsv(S.OUT / "bilingual_link_coverage.csv", cov)
    for c in cov:
        print(c)


if __name__ == "__main__":
    main()
