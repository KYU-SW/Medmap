"""STEP28.5 개념 검증·구별 검사. 후보 검증은 STEP28 validate_concept_candidates.validate 를 그대로 쓴다(규칙 동일).

구별 검사(영어 이름으로 색인 조회 → HPO·SNOMED 관계): Epistaxis vs Hemoptysis · Epistaxis vs Hematemesis · Vomiting vs Nausea ·
 Headache vs Pain(MedMap 은 pain + E_55 부위) · Fever(기존 canonical 재사용) — 그리고 MedMap 77 안에서 vomiting·nausea·hemoptysis·hematemesis 의
 curated id 가 서로 다른지(같은 개념으로 합쳐지지 않는지).
'관계 DISTINCT' = 어느 쪽도 다른 쪽의 조상이 아님. 공통 조상은 기록만(같은 의미 근거 아님).
출력: outputs/distinction_checks.json
"""
import s285_common as S
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids, relation, validate


def first(oi, name, pre):
    return next((h["cid"] for h in oi.search_en(name, k=20) if h["cid"].startswith(pre) and h["lexical_score"] == 1.0), None)


def main():
    oi = OntologyIndex(S.ONT_DB)
    inv = S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")
    ex = existing_ids(inv)
    pairs = [("Epistaxis", "Hemoptysis"), ("Epistaxis", "Hematemesis"), ("Vomiting", "Nausea"), ("Headache", "Pain")]
    rel = []
    for a, b in pairs:
        for pre in ("HP:", "SCTID:"):
            ca, cb = first(oi, a, pre), first(oi, b, pre)
            if ca and cb:
                rel.append({"pair": f"{a} vs {b}", "source": pre[:-1], **relation(oi, ca, cb)})
    val = {}
    for n in ("Epistaxis", "Headache", "Fever", "Vomiting", "Nausea", "Hemoptysis", "Hematemesis"):
        val[n] = {pre[:-1]: (lambda c: validate(oi, {"cid": c, "lexical_score": 1.0}, "B", ex)["check"] if c else None)(first(oi, n, pre)) for pre in ("HP:", "SCTID:")}
    ids = {r["canonical_id"]: set(filter(None, r["hpo_ids"].split(";"))) for r in inv}
    sep = {f"{a} vs {b}": not (ids[a] & ids[b]) for a, b in (("vomiting", "nausea"), ("hemoptysis", "hematemesis"))}
    out = {"pairwise": rel, "validation_checks": val, "medmap_curated_ids_disjoint": sep,
           "note": "영어 이름 조회(한국어 연결 아님). DISTINCT = 조상 관계 없음. 공통 조상은 같은 의미의 근거가 아니다."}
    S.dump_json(S.OUT / "distinction_checks.json", out)
    for r in rel:
        print(r["pair"], r["source"], r["relation"])
    print(S.dumps(val), S.dumps(sep))


if __name__ == "__main__":
    main()
