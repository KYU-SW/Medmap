"""STEP28 확장 파이프라인 실행·평가(정답 없음 — 매핑 정확도라고 부르지 않는다).

파이프라인 Expansion(text): search_existing_concepts → (미해결이면) 비증상 근거 → ontology 신규 후보(경로 C, gate 통과 시) → validate → 범주.
 범주: EXISTING_CANONICAL · EXISTING_COMPOSITE · NEW_ONTOLOGY_CONCEPT(검증 통과 = EXACT/ACCEPTABLE) · NON_SYMPTOM · UNCERTAIN ·
       UNKNOWN_SYMPTOM(증상 근거 있음, 한국어 연결 없음 = KOREAN_LINK_MISSING 또는 자동 후보만 있음 = NEW_CANDIDATE_UNVERIFIED)
 비증상 근거 추가: UMLS KOR SRL0(LNC-KO-KR 검사명·TKMT 약재명) 원문/stem 완전일치 · STEP27 NON_TYPE_CUE(증상 어휘 없을 때).
 표시 후보: 기존 concept 결과만. 신규·자동 후보는 표시 안 함.
[부적절 표시 proxy — 사전 고정, STEP27·STEP28 같은 함수] 표시 후보 c 가 (a) 입력에 c 의 한국어 어휘 근거 없음 AND (b) 제품 매퍼 alias 가 c 를
 가리키지 않음 AND (c) 통증 부위 규칙 결과가 아님 → UNSUPPORTED_DISPLAY. INT(gold 있는 내부 문장)는 gold 미포함 표시도 따로 센다.
평가 입력: Silver 442(STEP27 data/external_silver_candidates.csv) · 대표 15 표현 + STEP27 smoke 7 문장(회귀 확인용) ·
 EXT_EVAL weak-non 903(질환·신체부위 등 → 증상/신규 concept 으로 잘못 연결되는지) · INT core dev 59 + regression 109(기존 증상 차단 여부).
출력: data/external_silver_expansion.csv · data/ontology_expansion_candidates.csv · outputs/{expansion_coverage.json, new_concept_candidates.csv,
 composite_concept_cases.csv, unsupported_symptom_cases.csv, non_symptom_cases.csv, candidate_error_analysis.csv, comparison_step27_step28.csv,
 representative_cases.csv, internal_regression_check.csv, weak_non_check.csv}
"""
from __future__ import annotations

import collections
import json

import s28_common as S
from search_existing_concepts import ExistingSearch, ns_stem
from search_new_ontology_concepts import OntologyIndex
from validate_concept_candidates import existing_ids, validate

CAND_FIELDS = ["source_text", "candidate_concept_id", "ontology_source", "concept_name", "definition", "semantic_type", "active_status", "parent_concepts",
               "evidence_source", "lexical_score", "mapping_confidence", "mapping_decision", "check", "new_concept", "auto_generated_candidate",
               "ontology_supported", "model_supported"]


def wcsv(path, rows, fields):
    """빈 표도 헤더를 남긴다(경로 C 미사용이면 후보 0)."""
    import csv
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


REP = ["코피", "객혈", "토혈", "두통", "발열", "호흡곤란", "구토", "오심", "목 통증", "흉통", "복통", "어지럼", "두근거림", "고혈압", "결핵"]
SMOKE27 = ["고혈압", "결핵", "코피가 나요", "숨이 차요", "기침이 나요", "토했어요", "열이 나요"]


class Expansion:
    def __init__(self):
        self.es = ExistingSearch()
        self.oi = OntologyIndex()
        self.inv = {r["canonical_id"]: r for r in S.read_csv(S.DATA / "existing_concept_inventory.csv")}
        self.ex = existing_ids(self.inv.values())
        fz = S.OUT / "crosslingual_feasibility.json"
        self.path_c = S.load_json(fz)["PATH_C_ENABLED"] if fz.exists() else False
        self.cl = None
        if self.path_c:
            from search_new_ontology_concepts import CrossLingual
            self.cl = CrossLingual(self.oi)

    def ontology_ids(self, c):
        r = self.inv.get(c, {})
        return [x for x in (r.get("hpo_ids", "").split(";") + ["SCTID:" + y for y in r.get("snomed_ids", "").split(";") if y]
                            + ["CUI:" + y for y in r.get("umls_cuis", "").split(";") if y]) if x]

    def __call__(self, text: str) -> dict:
        r = self.es.search(text)
        out = {"source_text": text, "raw_preserved": True, "step27_status": r["router"]["status"], "step27_candidates": r["router"]["candidate_ids"],
               "features": r["features"], "mapper_hits": [(m["evidence_id"], m["status"]) for m in r["mapper"]], "ontology_candidates": [],
               "attributes": r.get("attributes", {}), "korean_link_path": "", "new_concept": False}
        if r["category"]:
            c = r["canonical_id"]
            out.update(category=r["category"], reason=r["reason"], canonical_id=c, display=r["display"],
                       korean_link_path="A(MedMap 한국어 용어/규칙/모델)", ontology_ids=self.ontology_ids(c) if c else [],
                       mapping_decision="EXISTING" if c else "UNCERTAIN",
                       confirmable=r["category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") and r["reason"] not in ("MODEL_AUTO(STEP27)",))
            return out
        non = list(r.get("non_evidence", []))
        t = S.norm(text)
        kor = self.oi.kor_lookup(t) or self.oi.kor_lookup(S.josa_strip(t))
        if kor:
            non.append("UMLS_KOR_SRL0:" + ";".join(sorted({f"{sab}:{cui}" for _, cui, sab in kor})))
        f = r["features"]
        if f["non_type"] and not f["sym_cue"]:
            non.append("NON_TYPE_CUE:" + f["non_type"])
        if non:
            out.update(category="NON_SYMPTOM", reason=";".join(non), canonical_id=None, display=[], ontology_ids=[], mapping_decision="DO_NOT_MAP",
                       korean_link_path="K/A(비증상 근거)", confirmable=False)
            return out
        sym_ev = bool(f["sym_cue"] or f["p_non"] < 0.5)
        if self.cl is not None:
            for cand in self.cl.search(text, k=5):
                v = validate(self.oi, cand, "C", self.ex)
                out["ontology_candidates"].append(v)
        verified = [v for v in out["ontology_candidates"] if v["new_concept"] and v["mapping_decision"] in ("EXACT", "ACCEPTABLE")]
        auto_new = [v for v in out["ontology_candidates"] if v["new_concept"]]
        if verified:
            out.update(category="NEW_ONTOLOGY_CONCEPT", reason="VERIFIED", canonical_id=None, display=[], ontology_ids=[v["candidate_concept_id"] for v in verified],
                       mapping_decision=verified[0]["mapping_decision"], korean_link_path="C", new_concept=True, confirmable=False)
        elif sym_ev:
            out.update(category="UNKNOWN_SYMPTOM", reason="NEW_CANDIDATE_UNVERIFIED" if auto_new else "KOREAN_LINK_MISSING", canonical_id=None, display=[],
                       ontology_ids=[v["candidate_concept_id"] for v in auto_new], mapping_decision="UNCERTAIN",
                       korean_link_path="C(자동 후보)" if auto_new else "D(연결 자원 없음)", new_concept=bool(auto_new), confirmable=False)
        else:
            out.update(category="UNCERTAIN", reason="TYPE_UNCLEAR", canonical_id=None, display=[], ontology_ids=[], mapping_decision="UNCERTAIN",
                       korean_link_path="D(증상 근거도 없음)", confirmable=False)
        return out

    def display_flags(self, text, cands, reason=""):
        mapc = {self.es.cw[e] for e, st in [(m["evidence_id"], m["status"]) for m in self.es.mapper.extract(text)] if st == "POSITIVE" and e in self.es.cw}
        rule = reason in ("PAIN_PLUS_SITE", "SORE_THROAT_SITE_RULE") or reason.startswith("NECK_SITE")
        return [c for c in cands if c and not self.es.lexical_support(text, c) and c not in mapc and not rule]


def main():
    ex = Expansion()
    silver = S.read_csv(S.S27_DIR / "data/external_silver_candidates.csv")
    res, sil_rows = {}, []
    for r in silver:
        o = ex(r["raw_expression"])
        res[r["raw_expression"]] = o
        s27_disp = r["candidate_concept_ids"].split(";") if r["step27_status"] == "UNCERTAIN" and r["candidate_concept_ids"] else []
        un27 = ex.display_flags(r["raw_expression"], s27_disp)
        un28 = ex.display_flags(r["raw_expression"], o["display"], o["reason"])
        group = {"EXISTING_CANONICAL": "1_EXISTING_CANONICAL", "EXISTING_COMPOSITE": "2_EXISTING_COMPOSITE", "NEW_ONTOLOGY_CONCEPT": "3_NEW_ONTOLOGY_CONCEPT",
                 "NON_SYMPTOM": "4_NON_SYMPTOM", "UNCERTAIN": "5_UNCLEAR"}.get(o["category"], "6_KOREAN_LINK_MISSING" if o["reason"] == "KOREAN_LINK_MISSING" else "3b_NEW_CANDIDATE_UNVERIFIED")
        sil_rows.append({"tier": "SILVER_AUTO(사람 검증 아님)", "unit_id": r["unit_id"], "raw_expression": r["raw_expression"], "step26_split": r["step26_split"],
                         "step27_status": r["step27_status"], "step27_display": ";".join(s27_disp), "step27_unsupported_display": ";".join(un27),
                         "step28_category": o["category"], "step28_group": group, "step28_reason": o["reason"], "canonical_id": o["canonical_id"] or "",
                         "attributes": S.dumps(o["attributes"]) if o["attributes"] else "", "display": ";".join(o["display"]),
                         "step28_unsupported_display": ";".join(un28), "korean_link_path": o["korean_link_path"], "ontology_ids": ";".join(o["ontology_ids"][:6]),
                         "ontology_candidates": S.dumps([{k: v[k] for k in ("candidate_concept_id", "concept_name", "mapping_decision", "check")} for v in o["ontology_candidates"]]),
                         "mapping_decision": o["mapping_decision"], "new_concept": o["new_concept"], "raw_preserved": o["raw_preserved"],
                         "confirmable": o["confirmable"], "mapper_hits": S.dumps(o["mapper_hits"])})
    S.write_csv(S.DATA / "external_silver_expansion.csv", sil_rows)

    # 신규 후보 표(ontology_expansion_candidates) — §8 필드
    cand_rows = []
    for text, o in res.items():
        for v in o["ontology_candidates"]:
            cand_rows.append({"source_text": text, **{k: v.get(k, "") for k in ("candidate_concept_id", "ontology_source", "concept_name", "definition", "semantic_type",
                                                                                 "active_status", "parent_concepts", "evidence_source", "lexical_score",
                                                                                 "mapping_confidence", "mapping_decision", "check", "new_concept")},
                              "auto_generated_candidate": True, "ontology_supported": v["new_concept"] and v["mapping_decision"] in ("EXACT", "ACCEPTABLE"),
                              "model_supported": False})
    wcsv(S.DATA / "ontology_expansion_candidates.csv", cand_rows, CAND_FIELDS)
    newc = [c for c in cand_rows if c["new_concept"]]
    wcsv(S.OUT / "new_concept_candidates.csv", newc, CAND_FIELDS)
    wcsv(S.OUT / "composite_concept_cases.csv", [s for s in sil_rows if s["step28_category"] == "EXISTING_COMPOSITE"], list(sil_rows[0]))
    wcsv(S.OUT / "unsupported_symptom_cases.csv", [s for s in sil_rows if s["step28_category"] == "UNKNOWN_SYMPTOM"], list(sil_rows[0]))
    wcsv(S.OUT / "non_symptom_cases.csv", [s for s in sil_rows if s["step28_category"] == "NON_SYMPTOM"], list(sil_rows[0]))
    wcsv(S.OUT / "candidate_error_analysis.csv", [s for s in sil_rows if s["step27_unsupported_display"] or s["step28_unsupported_display"]
                                                         or (s["step27_status"] == "KNOWN_SYMPTOM" and s["step28_category"] not in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE"))], list(sil_rows[0]))
    # 대표 사례(회귀 확인용)
    rep = []
    for i, t in enumerate(REP + SMOKE27):
        o = ex(t)
        rep.append({"input": t, "set": "REP15" if i < len(REP) else "STEP27_SMOKE", "step27_status": o["step27_status"], "step27_candidates": ";".join(o["step27_candidates"]),
                    "step28_category": o["category"], "reason": o["reason"], "canonical_id": o["canonical_id"] or "", "attributes": S.dumps(o["attributes"]) if o["attributes"] else "",
                    "display": ";".join(o["display"]), "ontology_ids": ";".join(o["ontology_ids"][:4]), "korean_link_path": o["korean_link_path"],
                    "mapper_hits": S.dumps(o["mapper_hits"]), "unsupported_display": ";".join(ex.display_flags(t, o["display"], o["reason"]))})
    S.write_csv(S.OUT / "representative_cases.csv", rep)
    # weak-non(EXT_EVAL)
    dec = S.read_csv(S.S27_DIR / "outputs/routing_decisions.csv")
    wn = [d for d in dec if d["set"] == "EXT_EVAL" and d["weak_label"] == "WEAK_NON_SYMPTOM"]
    wn_rows = []
    for d in wn:
        o = ex(d["text"])
        wn_rows.append({"row_id": d["row_id"], "text": d["text"], "step27_status": d["POLICY_D_status"], "step28_category": o["category"], "reason": o["reason"],
                        "canonical_id": o["canonical_id"] or "", "display": ";".join(o["display"]), "new_concept": o["new_concept"]})
    S.write_csv(S.OUT / "weak_non_check.csv", wn_rows)
    # 내부 regression(기존 증상 차단 여부)
    feats = S.read_csv(S.S27_DIR / "outputs/routing_features.csv")
    ints = [f for f in feats if f["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")]
    int_rows = []
    d27 = {d["row_id"]: d for d in dec}
    for f in ints:
        o = ex(f["text"])
        int_rows.append({"row_id": f["row_id"], "set": f["set"], "text": f["text"], "gold": f["gold_concept"], "step27_status": d27[f["row_id"]]["POLICY_D_status"],
                         "step28_category": o["category"], "reason": o["reason"], "canonical_id": o["canonical_id"] or "", "display": ";".join(o["display"]),
                         "existing_correct": o["canonical_id"] == f["gold_concept"], "gold_in_display": f["gold_concept"] in o["display"]})
    S.write_csv(S.OUT / "internal_regression_check.csv", int_rows)

    # ---- 지표 ----
    n = len(sil_rows)
    cat = collections.Counter(s["step28_category"] for s in sil_rows)
    grp = collections.Counter(s["step28_group"] for s in sil_rows)
    s27 = collections.Counter(s["step27_status"] for s in sil_rows)
    unk27 = [s for s in sil_rows if s["step27_status"] in ("UNKNOWN_SYMPTOM", "UNCERTAIN")]
    new_ids = [c["candidate_concept_id"] for c in newc]
    dup_new = sum(1 for c in cand_rows if str(c["check"]).startswith(("DUPLICATE_OF_EXISTING", "NARROWER_AS_ATTRIBUTE", "BROADER")))
    cov = {"n_inputs(silver)": n, "step28_category_counts": dict(cat), "silver_groups(§11)": dict(grp), "step27_status_counts": dict(s27),
           "existing_canonical_coverage": S.rnd(cat["EXISTING_CANONICAL"] / n), "existing_composite_coverage": S.rnd(cat["EXISTING_COMPOSITE"] / n),
           "new_ontology_concept_candidate_count(auto, unverified 포함)": len(set((c["source_text"], c["candidate_concept_id"]) for c in newc)),
           "new_concept_inputs(auto 후보가 있는 입력 수)": len({c["source_text"] for c in newc}),
           "verified_mapping_candidate_count(EXACT/ACCEPTABLE new)": sum(1 for c in newc if c["mapping_decision"] in ("EXACT", "ACCEPTABLE")),
           "needs_semantic_verification_count": sum(1 for c in newc if c["mapping_decision"] not in ("EXACT", "ACCEPTABLE")),
           "unknown_rate": S.rnd(cat["UNKNOWN_SYMPTOM"] / n), "non_symptom_rate": S.rnd(cat["NON_SYMPTOM"] / n), "uncertain_rate": S.rnd(cat["UNCERTAIN"] / n),
           "unsupported_display_inputs": {"STEP27": sum(bool(s["step27_unsupported_display"]) for s in sil_rows),
                                          "STEP28": sum(bool(s["step28_unsupported_display"]) for s in sil_rows)},
           "display_inputs": {"STEP27": sum(bool(s["step27_display"]) for s in sil_rows), "STEP28": sum(bool(s["display"]) for s in sil_rows)},
           "raw_text_preservation_rate": S.rnd(sum(s["raw_preserved"] for s in sil_rows) / n),
           "concept_duplication": {"candidates_resolved_to_existing(dup/narrower-attr/broader)": dup_new,
                                   "new_ids_unique": len(set(new_ids)), "new_id_collision_with_77": sum(1 for x in new_ids if x in ex.ex)},
           "unsupported_concept_handling": {"UNKNOWN_with_display": sum(1 for s in sil_rows if s["step28_category"] == "UNKNOWN_SYMPTOM" and s["display"]),
                                            "UNKNOWN_with_canonical": sum(1 for s in sil_rows if s["step28_category"] == "UNKNOWN_SYMPTOM" and s["canonical_id"])},
           "Q1_step27_unknown_or_uncertain(n)": len(unk27),
           "Q1_of_those_now_existing": sum(1 for s in unk27 if s["step28_category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")),
           "Q1_of_those_new_ontology_candidate": sum(1 for s in unk27 if s["new_concept"] in (True, "True")),
           "Q2_of_those_verified": sum(1 for s in unk27 if s["step28_category"] == "NEW_ONTOLOGY_CONCEPT"),
           "Q4_step27_known_now_not_existing": sum(1 for s in sil_rows if s["step27_status"] == "KNOWN_SYMPTOM" and s["step28_category"] not in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")),
           "Q4_step27_known_now_different_canonical": sum(1 for s in sil_rows if s["step27_status"] == "KNOWN_SYMPTOM" and s["canonical_id"]
                                                          and s["canonical_id"] != next((r for r in silver if r["unit_id"] == s["unit_id"]), {}).get("step27_canonical_id")),
           "korean_link_path_counts": dict(collections.Counter(s["korean_link_path"] for s in sil_rows)),
           "path_c_enabled": ex.path_c,
           "weak_non_eval": {"n": len(wn_rows), "categories": dict(collections.Counter(w["step28_category"] for w in wn_rows)),
                             "linked_to_symptom(existing)": sum(w["step28_category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") for w in wn_rows),
                             "new_concept": sum(bool(w["new_concept"]) for w in wn_rows),
                             "step27_categories": dict(collections.Counter(w["step27_status"] for w in wn_rows))},
           "internal": {}}
    for st in ("INT_DEV_CORE", "INT_REGRESSION_CORE"):
        rs = [r for r in int_rows if r["set"] == st]
        ex_r = [r for r in rs if r["step28_category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")]
        cov["internal"][st] = {"n": len(rs), "categories": dict(collections.Counter(r["step28_category"] for r in rs)),
                               "existing_rate": S.rnd(len(ex_r) / len(rs)), "existing_precision_vs_gold": S.rnd(sum(r["existing_correct"] for r in ex_r) / len(ex_r)) if ex_r else None,
                               "existing_wrong": [(r["text"], r["gold"], r["canonical_id"]) for r in ex_r if not r["existing_correct"]][:15],
                               "blocked(gold supported → NON/NEW/UNKNOWN)": sum(r["step28_category"] in ("NON_SYMPTOM", "NEW_ONTOLOGY_CONCEPT", "UNKNOWN_SYMPTOM") for r in rs),
                               "step27_known": sum(r["step27_status"] == "KNOWN_SYMPTOM" for r in rs),
                               "step27_known_now_not_existing": sum(r["step27_status"] == "KNOWN_SYMPTOM" and r not in ex_r for r in rs)}
    S.dump_json(S.OUT / "expansion_coverage.json", cov)
    comp = []
    for k27 in sorted(s27):
        for k28 in sorted(cat):
            m = sum(1 for s in sil_rows if s["step27_status"] == k27 and s["step28_category"] == k28)
            if m:
                comp.append({"step27_status": k27, "step28_category": k28, "n": m})
    S.write_csv(S.OUT / "comparison_step27_step28.csv", comp)
    print(S.dumps({k: v for k, v in cov.items() if k != "internal"}))
    print(S.dumps(cov["internal"]))


if __name__ == "__main__":
    main()
