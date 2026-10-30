"""STEP28.6 감사 입력 준비(LLM 호출 없음). 대상 = 작성자 중 하나라도 NEW_ONTOLOGY_CANDIDATE 로 연결한 (입력, HPO concept) 쌍.
감사자에게는 한국어 표현 + HPO id·이름·정의만 보낸다(HPO 공개 라이선스). SNOMED 만 있는 후보는 SNOMED 문자열을 외부 LLM 에 보내지 않으므로
감사 없음(NOT_AUDITED_LICENSE). 작성자 영어 출력·MedMap 77 목록·모델 예측은 보내지 않는다.
출력: ~/medmap_step28_6_ws/in/audit_items_cNN.tsv(≤230 행) · data/audit_manifest.csv
"""
import csv

import s286_common as S
from search_new_ontology_concepts import OntologyIndex


def main():
    oi = OntologyIndex(S.ONT_DB)
    links = S.read_csv(S.DATA / "ontology_links.csv")
    items, seen = [], set()
    for l in links:
        for who in ("A", "B"):
            if l[f"{who}_cat"] != "NEW_ONTOLOGY_CANDIDATE":
                continue
            cid = l[f"{who}_concept"]
            key = (l["id"], cid)
            if key in seen:
                continue
            seen.add(key)
            c = oi.concept(cid) or {}
            hp = cid if cid.startswith("HP:") else next((x for u in oi.cuis(cid) for x in oi.codes(u) if x.startswith("HP:")), "")
            hc = oi.concept(hp) if hp else None
            items.append({"row": f"R{len(items) + 1:04d}", "id": l["id"], "korean": l["korean"], "concept_id": cid, "hpo_id": hp,
                          "hpo_name": (hc or {}).get("name", ""), "hpo_definition": ((hc or {}).get("definition", "") or "").replace("\t", " ").replace("\n", " "),
                          "audit_status": "TO_AUDIT" if hc and hc.get("definition") else "NOT_AUDITED_LICENSE" if not hp else "NOT_AUDITED_NO_HPO_DEFINITION",
                          "concept_source": c.get("source", "")})
    S.wcsv(S.DATA / "audit_manifest.csv", items)
    for f in (S.WS / "in").glob("audit_items_c*.tsv"):
        f.unlink()
    todo = [i for i in items if i["audit_status"] == "TO_AUDIT"]
    for c in range(0, len(todo), S.CHUNK):
        part = todo[c:c + S.CHUNK]
        p = S.WS / "in" / f"audit_items_c{c // S.CHUNK + 1:02d}.tsv"
        with p.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["row", "korean", "hpo_id", "hpo_name", "hpo_definition"])
            for i in part:
                w.writerow([i["row"], i["korean"], i["hpo_id"], i["hpo_name"], i["hpo_definition"]])
    print({"pairs": len(items), "to_audit": len(todo), "not_audited": len(items) - len(todo)})


if __name__ == "__main__":
    main()
