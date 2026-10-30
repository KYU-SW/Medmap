"""STEP28.5 한국어 검색 색인 + 자원 목록(inspect_existing_resources 결과 포함).

행 = 한국어 용어 → 연결 대상 ID(근거 필수). role ∈ SYMPTOM(77 canonical) · ANTECEDENT/ATTRIBUTE(77 밖 DDXPlus 증거) · DISEASE(49질환) ·
 BODY_SITE(E_55 값) · VALUE(그 외 값) · TEST(LNC-KO-KR) · HERB(TKMT).
출처: STEP23 학습 표현 1,119 · STEP21 사전 294 · terminology_ko evidence_short(223, 라벨 통째 — STEP28 의 '·' 분리 조각 결함을 피함) ·
 terminology_ko diseases(49)·values(199) · STEP28 색인 kor_term(UMLS KOR SRL 0 만).
키 = 조사 제거 후 공백·구두점 제거(ko_key). nkey = 질의와 같은 kiwipiepy 구문 정규화(query_ko 원형) 키(용어가 구문 1개일 때).
char 2–3gram TF-IDF(sublinear) 를 함께 저장(후보 생성 전용, 확정 근거 아님).
[변경 기록] nkey 는 smoke(숨이 차요·토했어요·메스꺼워요가 색인 원문 키와 안 맞음)를 본 뒤 추가한 '색인·질의 정규화 일치' 수정.
출력: index/korean_index.csv(LOCAL — UMLS 유래 행 포함) · index/korean_ngram.joblib · outputs/resource_inventory.json
"""
import collections
import csv
import json

import s285_common as S
from search_new_ontology_concepts import OntologyIndex


def main():
    term = S.S28.load_terminology()
    ev = S.evidences()
    cw = S.S28.evidence_crosswalk()
    inv = {r["canonical_id"]: r for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    with (S.S28.S20 / "curation/curated_mappings.tsv").open(encoding="utf-8") as fh:
        cur = {r["evidence_id"]: r for r in csv.DictReader(fh, delimiter="\t")}
    rows = []

    def add(ko, tid, ttype, role, prov, en="", ont=""):
        k = S.ko_key(S.S28.josa_strip(S.norm(ko)))
        if k:
            rows.append({"ko_term": ko, "key": k, "target_id": tid, "target_type": ttype, "role": role, "provenance": prov, "en_term": en, "ontology_ids": ont})
    for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv"):
        c = r["canonical_id"]
        add(r["expression"], c, "CANONICAL", "SYMPTOM", "STEP23_TRAIN", r["canonical_name"], inv[c]["hpo_ids"])
    for r in S.read_csv(S.S28.S21 / "data/dictionary_expressions.csv"):
        c = r["concept_id"]
        add(r["expression"], c, "CANONICAL", "SYMPTOM", "STEP21_DICT", inv[c]["canonical_name"], inv[c]["hpo_ids"])
    for e, v in term["evidence_short"].items():
        lab = v.get("label_ko", "")
        if not lab:
            continue
        if e in cw:
            c = cw[e]
            add(lab, c, "CANONICAL", "SYMPTOM", f"TERMINOLOGY_LABEL:{e}", cur.get(e, {}).get("canonical_concept", inv[c]["canonical_name"]), inv[c]["hpo_ids"])
        else:
            role = "ANTECEDENT" if ev.get(e, {}).get("is_antecedent") else "ATTRIBUTE"
            add(lab, e, "DDXPLUS_EVIDENCE", role, "TERMINOLOGY_LABEL", ev.get(e, {}).get("question_en", ""), cur.get(e, {}).get("hpo_ids", ""))
    for d, v in term["diseases"].items():
        if v.get("label_ko"):
            add(v["label_ko"], d, "DDXPLUS_CONDITION", "DISEASE", "TERMINOLOGY_DISEASE", d)
    e55 = set(ev["E_55"]["possible-values"])
    vm = {}
    for e, x in ev.items():
        for vk, m in (x.get("value_meaning") or {}).items():
            vm.setdefault(vk, m.get("en", ""))
    for vk, v in term["values"].items():
        if v.get("label_ko"):
            add(v["label_ko"], vk, "DDXPLUS_VALUE", "BODY_SITE" if vk in e55 else "VALUE", "TERMINOLOGY_VALUE", vm.get(vk, ""))
    oi = OntologyIndex(S.ONT_DB)
    for ko, cui, sab in oi.q("SELECT term, cui, sab FROM kor_term"):
        add(ko, f"CUI:{cui}", "UMLS_CUI", "TEST" if sab == "LNC-KO-KR" else "HERB", f"UMLS_KOR:{sab}")
    from extract_symptom_spans import extract_kiwi
    cache = {}
    for r in rows:
        t = r["ko_term"]
        if t not in cache:
            sp = extract_kiwi(t)[0]
            cache[t] = S.ko_key(sp["query_ko"].removesuffix("다")) if not sp.get("failure") and sp["polarity"] != "NEGATIVE" else ""   # 부정 포함 용어(후각 상실 등)는 nkey 없음
        r["nkey"] = cache[t] if len(extract_kiwi(t)) == 1 or r["role"] != "SYMPTOM" else ""
    S.wcsv(S.INDEX / "korean_index.csv", rows)
    from sklearn.feature_extraction.text import TfidfVectorizer
    keys = sorted({r["key"] for r in rows})
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), sublinear_tf=True)
    X = vec.fit_transform(keys)
    import joblib
    joblib.dump({"vec": vec, "X": X, "keys": keys}, S.INDEX / "korean_ngram.joblib")
    cnt = collections.Counter((r["provenance"].split(":")[0], r["role"]) for r in rows)
    mt = S.load_json(S.S28.OUT / "index_build.json")
    res = {"korean_index_rows": len(rows), "distinct_keys": len(keys), "by_source_role": {f"{a}|{b}": n for (a, b), n in sorted(cnt.items())},
           "outside_77_symptom_rows": sum(1 for r in rows if r["role"] == "SYMPTOM" and r["target_type"] != "CANONICAL"),
           "resources": {
               "MedMap_STEP23_train": {"use": "YES", "license": "MedMap 내부(격리 Claude 작성, SILVER)", "scope": "77 canonical"},
               "MedMap_STEP21_dict": {"use": "YES", "license": "MedMap 내부", "scope": "77 canonical"},
               "terminology_ko.json": {"use": "YES", "license": "MedMap 내부(정본 v1.1.2)", "scope": "증거 223·질환 49·값 199"},
               "STEP20_curated_mappings": {"use": "YES", "license": "MedMap 내부(LLM_REVIEWED, 임상 검증 아님)", "scope": "증거 110 → HPO/SNOMED/CUI"},
               "UMLS_KOR_LNC-KO-KR": {"use": "YES(비증상 근거)", "license": "UMLS SRL 0", "rows": mt["umls"]["kor_rows_loaded(SRL0)"]},
               "UMLS_KOR_TKMT": {"use": "YES(비증상 근거)", "license": "UMLS SRL 0"},
               "UMLS_KOR_MDRKOR": {"use": "NO", "license": "SRL 3 — 이용 조건 미확인(사용자 지시로 제외)", "rows": mt["umls"]["kor_rows_not_loaded(SRL>0)"].get("MDRKOR")},
               "UMLS_KOR_KCD5": {"use": "NO", "license": "SRL 3", "rows": mt["umls"]["kor_rows_not_loaded(SRL>0)"].get("KCD5")},
               "HPO/SNOMED_INT/UMLS_ENG": {"use": "YES(STEP28 색인 재사용)", "korean": "없음"},
               "kiwipiepy_0.23.2": {"use": "YES(구문 추출)", "note": "로컬 설치·오프라인"},
               "xlm-roberta-base": {"use": "NO", "note": "STEP28 gate hit@5 1.2%"},
               "siglip2-base-patch16-224": {"use": "GATE", "note": "outputs/multilingual_model_gate.json"},
               "environment_inventory_doc": "outputs/mip-postprocess-research-v1/docs/environment_ai_env_inventory.md 이 기기에 없음(확인 필요) → import 1회 확인"}}
    S.dump_json(S.OUT / "resource_inventory.json", res)
    print(S.dumps({k: v for k, v in res.items() if k != "resources"}))


if __name__ == "__main__":
    main()
