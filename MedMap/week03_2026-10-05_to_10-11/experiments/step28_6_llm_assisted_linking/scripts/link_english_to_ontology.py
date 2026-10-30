"""STEP28.6 SILVER 대응표 → ontology 연결·검증·범주(규칙은 작성 결과를 보기 전에 고정, 2026-10-11).

1 파싱: out/author_{A,B}_cNN.tsv(있는 조각만). 형식 검사(열 8개·id 일치·expr_type 값). 형식 오류 행은 그 작성자 결과 없음(FORMAT_ERROR).
2 영어 → concept: english_preferred 를 STEP28 색인 search_en 에서 정규화 **완전일치(lexical_score 1.0)** 로만 찾고, 없으면 synonyms 를 같은 방식으로.
  부분·유사 일치는 연결로 인정하지 않는다(개수만 기록). 찾은 id 는 STEP28 validate(path 'L' = LLM SILVER, EXACT 부여 없음)로 검증.
3 작성자별 판정(expr_type 우선 — 증상·질환·부위·약물·치료·검사 엄격 구분):
  UNCLEAR 또는 영어 비어 있음 → UNKNOWN(NO_ENGLISH) · expr_type ≠ SYMPTOM_OR_SIGN → NON_SYMPTOM(<유형>) ·
  증상인데 완전일치 0 → UNKNOWN(ONTOLOGY_NO_EXACT_MATCH) ·
  검증 결과: DUPLICATE_OF_EXISTING → EXISTING_CANONICAL · NARROWER_AS_ATTRIBUTE 또는 (concept=pain 이고 body_site_en 있음) → EXISTING_COMPOSITE ·
  new_concept → NEW_ONTOLOGY_CANDIDATE(대표 id = HPO phenotype 우선, 없으면 SNOMED) · 전부 NOT_SYMPTOM_TYPE → UNCERTAIN(SEMANTIC_TYPE_MISMATCH) ·
  기존과 신규가 섞이면 기존 우선 + AMBIGUOUS_TERM 표시.
4 A·B 통합(같다고 정답 아님 — 일치는 필요조건일 뿐):
  같은 범주 + 같은 concept(같은 canonical, 또는 CUI 겹침) → AGREE · 범주나 concept 이 다름 → CONFLICT → UNCERTAIN(후보 표시 없음) ·
  한쪽만 결과 → SINGLE → UNCERTAIN(후보 보존·표시 없음) · 둘 다 NON(유형 달라도) → NON_SYMPTOM · 둘 다 UNKNOWN → UNKNOWN.
5 최종 상태: AGREE 인 EXISTING_* / NEW_ONTOLOGY_CANDIDATE 만 해당 범주. 신규는 감사 전 SILVER_AGREED, 감사(HPO 정의 대비) 후 등급 갱신은 evaluate_linking.
  신규 concept 은 MODEL_SUPPORTED=False, 49질환 모델 입력 금지.
출력: data/silver_ko_en_table.csv(작성자별 원 출력 + 파싱) · data/ontology_links.csv(입력별 통합 결과) · outputs/format_check.json
"""
from __future__ import annotations

import collections
import csv
import json

import s286_common as S
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids, validate

COLS = ["id", "korean", "expr_type", "english_preferred", "english_synonyms", "body_site_en", "confidence", "note"]


def read_author(who):
    rows, errs = {}, []
    for f in sorted((S.WS / "out").glob(f"author_{who}_c*.tsv")):
        with f.open(encoding="utf-8") as fh:
            rd = csv.reader(fh, delimiter="\t")
            head = next(rd, [])
            if [h.strip() for h in head[:8]] != COLS:
                errs.append(f"{f.name}:HEADER:{head[:8]}")
            for ln in rd:
                if not ln:
                    continue
                if len(ln) < 8:
                    ln = ln + [""] * (8 - len(ln))
                d = dict(zip(COLS, [x.strip() for x in ln[:8]]))
                if d["expr_type"] not in S.EXPR_TYPES:
                    errs.append(f"{f.name}:{d['id']}:TYPE:{d['expr_type']}")
                    d["format_error"] = True
                rows[d["id"]] = d
    return rows, errs


class Linker:
    def __init__(self):
        self.oi = OntologyIndex(S.ONT_DB)
        _anc, _memo = self.oi.ancestors, {}           # STEP28 코드 수정 없이 조상 계산 결과만 메모(판정 동일, 속도용)

        def ancestors(cid, limit=5000):
            if cid not in _memo:
                _memo[cid] = _anc(cid, limit)
            return set(_memo[cid])
        self.oi.ancestors = ancestors
        self.inv = S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")
        self.ex = existing_ids(self.inv)
        self.cache = {}

    fast = False   # True = 런타임 경로(완전일치만, 유사 일치 개수 세기 생략) — 지연시간 측정용. 판정 결과는 같다(유사 일치는 연결에 안 씀).

    def lookup(self, term):
        if term not in self.cache:
            if self.fast:
                from search_new_ontology_concepts import tnorm
                rows = self.oi.q("SELECT term,cid,ttype FROM term WHERE term_norm=?", tnorm(term)) if term else []
                hits = list({cid: {"cid": cid, "matched_term": t, "ttype": tt, "lexical_score": 1.0} for t, cid, tt in rows}.values())[:20]
                self.cache[term] = (hits, 0)
            else:
                hits = self.oi.search_en(term, k=20) if term else []
                self.cache[term] = ([h for h in hits if h["lexical_score"] == 1.0], len([h for h in hits if 0.6 <= h["lexical_score"] < 1.0]))
        return self.cache[term]

    def judge(self, d):
        if not d or d.get("format_error"):
            return {"cat": "UNKNOWN", "reason": "FORMAT_ERROR"}
        terms = [d["english_preferred"]] + [x.strip() for x in d["english_synonyms"].split(";") if x.strip()]
        terms = [t for t in terms if t]
        if d["expr_type"] == "UNCLEAR" or not terms:
            return {"cat": "UNKNOWN", "reason": "NO_ENGLISH"}
        if d["expr_type"] != "SYMPTOM_OR_SIGN":
            hits, _ = self.lookup(terms[0])
            return {"cat": "NON_SYMPTOM", "reason": d["expr_type"], "ids": [h["cid"] for h in hits][:5]}
        hits, used, fuzzy = [], "", 0
        for t in terms:
            h, fz = self.lookup(t)
            fuzzy += fz
            if h:
                hits, used = h, t
                break
        if not hits:
            return {"cat": "UNKNOWN", "reason": "ONTOLOGY_NO_EXACT_MATCH", "fuzzy_hits": fuzzy}
        vals = [validate(self.oi, {"cid": h["cid"], "lexical_score": 1.0, "matched_term": h["matched_term"]}, "L", self.ex) for h in hits]
        cuis = sorted({u for h in hits for u in self.oi.cuis(h["cid"])} | {h["cid"][4:] for h in hits if h["cid"].startswith("CUI:")})
        ex_c = sorted({v.get("existing_canonical") for v in vals if str(v["check"]).startswith("DUPLICATE_OF_EXISTING")})
        attr = sorted({v.get("existing_canonical") for v in vals if str(v["check"]).startswith("NARROWER_AS_ATTRIBUTE")})
        new = [v for v in vals if v["new_concept"]]
        base = {"term_used": used, "cuis": cuis, "validations": [{k: v.get(k) for k in ("candidate_concept_id", "concept_name", "check", "semantic_type", "active_status",
                                                                                        "definition")} for v in vals]}
        amb = bool((ex_c or attr) and new)
        if ex_c:
            c = ex_c[0]
            if c == "pain" and d["body_site_en"]:
                return {**base, "cat": "EXISTING_COMPOSITE", "concept": "pain", "site": d["body_site_en"], "reason": "PAIN+SITE" + (";AMBIGUOUS_TERM" if amb else "")}
            return {**base, "cat": "EXISTING_CANONICAL", "concept": c, "reason": "DUPLICATE" + (";AMBIGUOUS_TERM" if amb or len(ex_c) > 1 else "")}
        if attr:
            return {**base, "cat": "EXISTING_COMPOSITE", "concept": attr[0], "site": d["body_site_en"], "reason": "NARROWER_AS_ATTRIBUTE" + (";AMBIGUOUS_TERM" if amb else "")}
        if new:
            rep = next((v for v in new if v["candidate_concept_id"].startswith("HP:")), new[0])
            return {**base, "cat": "NEW_ONTOLOGY_CANDIDATE", "concept": rep["candidate_concept_id"], "concept_name": rep["concept_name"],
                    "broader_existing": rep.get("broader_existing", ""), "reason": rep["check"]}
        return {**base, "cat": "UNCERTAIN", "reason": "SEMANTIC_TYPE_MISMATCH"}


def same(a, b):
    if a["cat"] != b["cat"]:
        return False
    if a["cat"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE"):
        return a.get("concept") == b.get("concept")
    if a["cat"] == "NEW_ONTOLOGY_CANDIDATE":
        return a.get("concept") == b.get("concept") or bool(set(a.get("cuis", [])) & set(b.get("cuis", [])))
    return True


def main():
    man = S.read_csv(S.DATA / "expression_manifest.csv")
    A, ea = read_author("A")
    B, eb = read_author("B")
    L = Linker()
    tab, links = [], []
    for m in man:
        i = m["id"]
        if i not in A and i not in B:
            continue
        for who, R in (("A", A), ("B", B)):
            d = R.get(i)
            if d:
                tab.append({"tier": "SILVER(LLM, 검증 전)", "author": who, "sources": m["sources"], **{k: d.get(k, "") for k in COLS},
                            "korean_matches_manifest": d.get("korean", "") == m["korean"]})
        ja, jb = L.judge(A.get(i)), L.judge(B.get(i))
        if ja["cat"] == "UNKNOWN" and jb["cat"] == "UNKNOWN":
            fin, agree = {"cat": "UNKNOWN", "reason": ja["reason"] + "|" + jb["reason"]}, "BOTH_UNKNOWN"
        elif ja["cat"] == "NON_SYMPTOM" and jb["cat"] == "NON_SYMPTOM":
            fin, agree = {"cat": "NON_SYMPTOM", "reason": ja["reason"] + "|" + jb["reason"]}, "AGREE"
        elif same(ja, jb):
            fin, agree = ja, "AGREE"
        elif "UNKNOWN" in (ja["cat"], jb["cat"]):
            fin, agree = {"cat": "UNCERTAIN", "reason": "SINGLE_AUTHOR_ONLY"}, "SINGLE"
        else:
            fin, agree = {"cat": "UNCERTAIN", "reason": f"AUTHOR_CONFLICT:{ja['cat']}({ja.get('concept', '')})|{jb['cat']}({jb.get('concept', '')})"}, "CONFLICT"
        links.append({"id": i, "korean": m["korean"], "sources": m["sources"], "A_cat": ja["cat"], "A_concept": ja.get("concept", ""), "A_reason": ja["reason"],
                      "A_english": (A.get(i) or {}).get("english_preferred", ""), "A_type": (A.get(i) or {}).get("expr_type", ""),
                      "B_cat": jb["cat"], "B_concept": jb.get("concept", ""), "B_reason": jb["reason"], "B_english": (B.get(i) or {}).get("english_preferred", ""),
                      "B_type": (B.get(i) or {}).get("expr_type", ""), "agreement": agree, "final_cat": fin["cat"], "final_concept": fin.get("concept", ""),
                      "final_concept_name": fin.get("concept_name", ""), "final_reason": fin["reason"], "site_en": fin.get("site", ""),
                      "broader_existing": fin.get("broader_existing", ""), "cuis": ";".join(fin.get("cuis", [])),
                      "A_validations": S.dumps(ja.get("validations", [])[:4]), "B_validations": S.dumps(jb.get("validations", [])[:4]),
                      "model_supported": False, "raw_preserved": True})
    S.wcsv(S.DATA / "silver_ko_en_table.csv", tab)
    S.wcsv(S.DATA / "ontology_links.csv", links)
    fc = {"A_rows": len(A), "B_rows": len(B), "A_errors": ea[:20], "B_errors": eb[:20], "n_linked_inputs": len(links),
          "korean_mismatch": sum(1 for t in tab if not t["korean_matches_manifest"])}
    S.dump_json(S.OUT / "format_check.json", fc)
    print(S.dumps(fc))
    print(S.dumps(dict(collections.Counter(l["final_cat"] for l in links))), S.dumps(dict(collections.Counter(l["agreement"] for l in links))))


if __name__ == "__main__":
    main()
