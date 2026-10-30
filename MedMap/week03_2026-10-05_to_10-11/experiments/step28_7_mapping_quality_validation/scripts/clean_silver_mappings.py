"""STEP28.7 §7 — STEP28.6 SILVER 대응표 → 정제 대응표(입력 1,355 각 1행). 기존 silver_ko_en_table.csv·ontology_links.csv 는 읽기만.

[규칙 — 평가(evaluate_mapping_safety) 실행 전 고정, 2026-10-11]
근거 등급(evidence_level):
 LEVEL_0 A·B 모두 연결 근거 없음(BOTH_UNKNOWN) · LEVEL_1 한 작성자만(SINGLE) 또는 서로 다름(CONFLICT) · LEVEL_2 A·B 일치(범주+concept) ·
 LEVEL_3 A·B 일치 + 그 (입력, concept) 의 HPO 정의 대비 자동 감사 EXACT · LEVEL_4 독립 적격 인간 검토 — 이번 단계 0(부여 안 함).
 LEVEL_3 도 SILVER. 감사자 = opus(작성자 A 와 같은 모델) → 독립 검증 아님(audit_dependency 기록).
격리(isolation_status, 입력 단위): 두 작성자 행 중 하나라도 ISOLATION_FAIL → ISOLATION_FAIL. 세션 기록 없음 → ISOLATION_UNVERIFIED.
매핑 결정(mapping_decision):
 LEVEL_0                                   → NO_MAPPING(원문 보존)
 LEVEL_1                                   → HOLD_SINGLE_AUTHOR / HOLD_AUTHOR_CONFLICT
 일치 NON_SYMPTOM                           → ACCEPT_NON_SYMPTOM(격리 FAIL 이어도 허용: '연결 거부' 방향으로만 쓰는 근거, isolation 플래그 유지)
 일치 증상인데 ontology 완전일치 없음·질환형    → NO_MAPPING / HOLD_SEMANTIC_TYPE
 일치 EXISTING_CANONICAL·COMPOSITE          → ACCEPT_EXISTING(격리 PASS) · HOLD_ISOLATION(FAIL)
 일치 NEW(감사 반려)                         → REJECT_AUDIT
 일치 NEW → concept 분류(audited_concepts.csv):
   A/B(기존 동의어·속성) → ACCEPT_EXISTING_SYNONYM(canonical = 관련 기존, 확인 필요) · C(기존 하위) → ACCEPT_SUBTYPE(canonical = 부모, 모델 미지원) ·
   D(독립 신규) → ACCEPT_NEW_CANDIDATE · E → ACCEPT_NON_SYMPTOM · F → HOLD_CONCEPT_UNCERTAIN
   단 행 감사가 EXACT 가 아님(BROADER·NARROWER) → HOLD_AUDIT_NOT_EXACT · 감사 불가(SNOMED 전용)는 audit_status UNVERIFIED 로 수락 후보 유지(LEVEL_2)
   격리 FAIL → HOLD_ISOLATION(양성 연결 금지)
표시(safe_for_candidate_display): ACCEPT_EXISTING · ACCEPT_EXISTING_SYNONYM 만(77 concept, 확인 질문용). 신규·하위·보류는 표시 안 함.
모델 사용(usable_by_disease_model): 전부 False — SILVER 는 49질환 모델 입력으로 쓰지 않는다(STEP28.7 G8).
출력: data/cleaned_silver_mappings.csv · data/mapping_provenance.csv
"""
from __future__ import annotations

import collections
import json

import s287_common as S

MODEL = {"A": "opus", "B": "sonnet"}


def main():
    links = S.read_csv(S.S286_DIR / "data/ontology_links.csv")
    tab = collections.defaultdict(dict)
    for t in S.read_csv(S.S286_DIR / "data/silver_ko_en_table.csv"):
        tab[t["id"]][t["author"]] = t
    newc = collections.defaultdict(dict)
    for r in S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv"):
        newc[r["id"]][r["author"]] = r
    grade = {}
    for r in S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv"):
        grade[r["id"]] = r["grade"]
    audit = {}
    for r in S.read_csv(S.S286_DIR / "outputs/new_concept_candidates.csv"):
        for c, v in json.loads(r["audit"] or "{}").items():
            if v:
                audit[(r["id"], c)] = v[0]
    con = {r["concept_id"]: r for r in S.read_csv(S.DATA / "audited_concepts.csv")}
    iso = collections.defaultdict(dict)
    for r in S.read_csv(S.DATA / "row_isolation.csv"):
        iso[r["id"]][r["author"]] = r
    sess = S.load_json(S.S286_DIR / "outputs/authoring_isolation_check.json")["sessions"]
    out, prov = [], []
    for l in links:
        i = l["id"]
        ag = l["agreement"]
        ist = {iso[i][w]["isolation_status"] for w in ("A", "B")}
        istat = "ISOLATION_FAIL" if "ISOLATION_FAIL" in ist else "ISOLATION_UNVERIFIED" if "ISOLATION_UNVERIFIED" in ist else "ISOLATION_PASS"
        fc, cid = l["final_cat"], l["final_concept"]
        g = grade.get(i, "")
        ctype = l["A_type"] if l["A_type"] == l["B_type"] else f"{l['A_type']}|{l['B_type']}"
        rel, canon, ont_id, src, astat, dec, why = "", "", "", "", "NOT_APPLICABLE", "", ""
        lvl = {"BOTH_UNKNOWN": "LEVEL_0", "SINGLE": "LEVEL_1", "CONFLICT": "LEVEL_1"}.get(ag, "LEVEL_2")
        if ag == "BOTH_UNKNOWN":
            dec, why = "NO_MAPPING", l["final_reason"]
        elif ag in ("SINGLE", "CONFLICT"):
            dec, why = ("HOLD_SINGLE_AUTHOR", "SINGLE_AUTHOR_ONLY") if ag == "SINGLE" else ("HOLD_AUTHOR_CONFLICT", l["final_reason"][:120])
            ont_id = ";".join(sorted({x for x in (l["A_concept"], l["B_concept"]) if x}))
        elif fc == "NON_SYMPTOM":
            dec, rel = "ACCEPT_NON_SYMPTOM", "NON_SYMPTOM"
        elif fc == "UNKNOWN":
            dec, why = "NO_MAPPING", l["final_reason"]
        elif fc == "UNCERTAIN":
            dec, why = "HOLD_SEMANTIC_TYPE", l["final_reason"]
        elif fc in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE"):
            canon, rel = cid, fc
            dec = "ACCEPT_EXISTING" if istat == "ISOLATION_PASS" else "HOLD_ISOLATION"
            why = "" if dec == "ACCEPT_EXISTING" else "작성 조각 격리 FAIL"
        elif fc == "NEW_ONTOLOGY_CANDIDATE":
            ont_id = cid
            c = con.get(cid, {})
            a = audit.get((i, cid))
            astat = ("AUDITED_" + a) if a else ("UNVERIFIED_SNOMED_ONLY" if c.get("snomed_only") in ("True", True) else "NOT_AUDITED")
            if a == "EXACT":
                lvl = "LEVEL_3"
            rel = c.get("relation_to_existing", "UNCERTAIN")
            if g == "REJECTED" or (a in ("RELATED_ONLY", "WRONG")):
                dec, why = "REJECT_AUDIT", f"감사 {a}"
            elif istat != "ISOLATION_PASS":
                dec, why = "HOLD_ISOLATION", "작성 조각 격리 FAIL"
            elif a in ("BROADER", "NARROWER", "UNCLEAR"):
                dec, why = "HOLD_AUDIT_NOT_EXACT", f"감사 {a}"
            else:
                k = c.get("final_class", "F")
                canon = c.get("related_canonical", "") if k in ("A", "B", "C") else ""
                canon = canon.split(";")[0] if canon else ""
                dec = {"A": "ACCEPT_EXISTING_SYNONYM", "B": "ACCEPT_EXISTING_SYNONYM", "C": "ACCEPT_SUBTYPE", "D": "ACCEPT_NEW_CANDIDATE",
                       "E": "ACCEPT_NON_SYMPTOM"}.get(k, "HOLD_CONCEPT_UNCERTAIN")
                if dec == "HOLD_CONCEPT_UNCERTAIN":
                    why = c.get("classification_reason", "")[:160]
            src = c.get("ontology_source", "")
        else:
            dec, why = "NO_MAPPING", f"UNEXPECTED:{fc}"
        out.append({"id": i, "sources": l["sources"], "korean_expression": l["korean"], "normalized_korean": S.ko_key(S.stem_key(l["korean"])),
                    "english_candidate": f"A={l['A_english']} | B={l['B_english']}", "ontology_id": ont_id, "ontology_source": src,
                    "concept_type": ctype, "relation_to_existing": rel, "canonical_id": canon, "author_agreement": ag, "step28_6_final_cat": fc,
                    "step28_6_grade": g, "audit_status": astat, "isolation_status": istat, "evidence_level": lvl,
                    "safe_for_candidate_display": dec in ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM"),
                    "usable_by_disease_model": False, "mapping_decision": dec, "rejection_reason": why, "silver": True, "human_verified": False})
        for w in ("A", "B"):
            t = tab[i].get(w, {})
            ch = iso[i][w]["chunk"]
            s = sess.get(f"author_{w}_{ch}", {})
            prov.append({"id": i, "korean": l["korean"], "author": w, "model": MODEL[w], "chunk": ch, "session_id": s.get("session_id", ""),
                         "isolation_status": iso[i][w]["isolation_status"], "changed_by_self_revision": iso[i][w]["changed_by_self_revision"],
                         "expr_type": t.get("expr_type", ""), "english_preferred": t.get("english_preferred", ""), "confidence": t.get("confidence", ""),
                         "judged_category": l[f"{w}_cat"], "judged_concept": l[f"{w}_concept"],
                         "audit": audit.get((i, l[f"{w}_concept"]), "") if l[f"{w}_concept"] else "",
                         "audit_model_inputs": "opus · 한국어 + HPO id·이름·정의(작성자 출력·77·SNOMED 미전송)" if audit.get((i, l[f"{w}_concept"])) else "",
                         "linker": "STEP28.6 link_english_to_ontology(완전일치) + STEP28 validate(path L)"})
    S.wcsv(S.DATA / "cleaned_silver_mappings.csv", out)
    S.wcsv(S.DATA / "mapping_provenance.csv", prov)
    c = collections.Counter(o["mapping_decision"] for o in out)
    print(S.dumps(dict(c)))
    print(S.dumps(dict(collections.Counter(o["evidence_level"] for o in out))))
    print(S.dumps({s: dict(collections.Counter(o["mapping_decision"] for o in out if s in o["sources"])) for s in ("SILVER442", "WEAKNON903", "SMOKE")}))


if __name__ == "__main__":
    main()
