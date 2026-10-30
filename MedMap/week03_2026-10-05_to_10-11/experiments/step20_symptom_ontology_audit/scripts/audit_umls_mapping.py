"""STEP20-5: DDXPlus 증상 110 → UMLS 2026AA mapping 감사.

입력(읽기만): step8 evidence_umls_candidates.csv(top3) · evidence_concept_map.csv · curation/curated_mappings.tsv
           · data/umls/mrconso_eng.parquet(SUPPRESS=N) · MRSTY.RRF
curated 의 umls 칸: 'C…' 직접 지정 / 'sct:<code>' · 'hpo:<id>' 는 MRCONSO 에서 그 코드의 CUI 로 유도('|' 는 대체 순서, ';' 는 composite).
semantic type: Sign or Symptom / Finding 이면 OK, Disease or Syndrome 등은 CHECK(UMLS 는 증상 개념에도 D/S 를 붙이는 경우가 많아
             타입만으로 WRONG 처리하지 않는다). 질환 자체를 증상 자리에 둔 후보는 DISEASE_CUIS 로 WRONG.
출력: outputs/ddxplus_umls_mapping_audit.csv, outputs/umls_lay_strings.csv(정규화 개념별 CHV/MEDLINEPLUS 표현 — 9절 표현층 분리용)
"""
import pandas as pd
import pyarrow.dataset as ds

import common as c
from audit_hpo_mapping import hpo_depth_rel

SYMPTOM_STY = {"Sign or Symptom", "Finding"}
# 증상 evidence 에 연결되면 안 되는 '질환 그 자체' 개념(Claude 판정)
DISEASE_CUIS = {
    "C0043167": "Pertussis (disease) for a cough symptom",
    "C0043168": "Whooping cough, unspecified organism (disease)",
    "C0947912": "Myasthenias (disease) for fatigable weakness",
    "C0003811": "Cardiac Arrhythmia (disease) for perceived irregular beat",
    "C0017168": "Gastroesophageal reflux disease for heartburn symptom",
    "C0037315": "Sleep Apnea Syndromes (syndrome) for witnessed apnea",
    "C0002965": "Unstable angina (disease)",
    "C0031350": "Pharyngitis (disease) for sore throat",
}
OVERRIDES = {   # (evidence, cui) → (class, reason)
    ("E_76", "C0042571"): ("PARTIAL", "Vertigo; lightheadedness is not vertigo"),
    ("E_82", "C0042571"): ("PARTIAL", "Vertigo; presyncope is not vertigo"),
    ("E_55", "C0234225"): ("WRONG", "Pain absent - negated concept"),
    ("E_159", "C0234421"): ("WRONG", "Conscious - opposite state"),
    ("E_51", "C0426642"): ("PARTIAL", "Frequency of bowel action - neutral observable for the frequency disjunct"),
    ("E_179", "C4047940"): ("PARTIAL", "Blood clots in stool covers the clots disjunct only"),
    ("E_220", "C5141269"): ("PARTIAL", "Increased pain without the breathing trigger"),
    ("E_216", "C5141269"): ("PARTIAL", "Increased pain without the movement trigger"),
    ("E_93", "C3472693"): ("ACCEPTABLE_BROADER", "Numbness and tingling of skin; foot site lost"),
    ("E_127", "C5229448"): ("ACCEPTABLE_NARROWER", "bilateral epiphora due to excess tear production"),
    ("E_144", "C0520963"): ("PARTIAL", "diffuse pain, not specifically muscle"),
    ("E_206", "C0221776"): ("PARTIAL", "Oral pain without the ulcer"),
    ("E_38", "C0240080"): ("PARTIAL", "covers the jaw-weakness disjunct only"),
    ("E_84", "C2219734"): ("PARTIAL", "covers the legs disjunct only"),
}


def sct_rel(sct, a, b, maxd=6):
    """a 가 b 의 조상이면 ('ANC', d), 자손이면 ('DESC', d)."""
    def dist(x, y):
        frontier, seen, d = {x}, {x}, 0
        while frontier and d <= maxd:
            if y in frontier:
                return d
            nxt = set()
            for z in frontier:
                nxt.update(sct["parents"].get(z, []))
            frontier = nxt - seen
            seen |= nxt
            d += 1
        return None
    d = dist(b, a)
    if d:
        return ("ANC", d)
    d = dist(a, b)
    if d:
        return ("DESC", d)
    return None


def main():
    hpo, sct, umls = c.load_hpo(), c.load_snomed(), c.load_umls()
    cur = c.load_curation().set_index("evidence_id")
    _, s8, cmap = c.load_step8()
    s8, cmap = s8.set_index("evidence"), cmap.set_index("evidence_id")
    labels = c.inventory_labels()
    code2cui = {}
    for cui, codes in umls["codes"].items():
        for sab, code in codes:
            if sab in ("SNOMEDCT_US", "HPO"):
                code2cui.setdefault((sab, code), []).append(cui)

    def resolve(token):
        token = token.strip()
        for alt in token.split("|"):
            if alt.startswith("sct:"):
                hit = sorted(code2cui.get(("SNOMEDCT_US", alt[4:]), []))
            elif alt.startswith("hpo:"):
                hit = sorted(code2cui.get(("HPO", alt[4:]), []))
            else:
                hit = [alt] if alt in umls["sty"] else []
            if hit:
                return hit[0], alt
        return "", token

    # 모든 대상 CUI 수집
    plan = []
    for eid in cur.index:
        r = cur.loc[eid]
        ucls = {"=SCT": r["sct_class"], "=HPO": r["hpo_class"]}.get(r["umls_class"], r["umls_class"])
        ucon = {"=SCT": r["sct_conf"], "=HPO": r["hpo_conf"]}.get(r["umls_class"], r["umls_conf"])
        toks = c.split_ids(r["umls"])
        for tok in toks or [""]:
            cui, how = resolve(tok) if tok else ("", "")
            plan.append((eid, "curated", "", cui, how, ucls, ucon, r["umls_reason"] + (f" [{how}]" if how and not how.startswith("C") else ""), "curated", len(toks) > 1))
        x = s8.loc[eid]
        for k in (1, 2, 3):
            if x[f"cui{k}"]:
                plan.append((eid, "step8_tfidf", k, x[f"cui{k}"], x[f"cui{k}_score"], None, None, None, None, False))
        m = cmap.loc[eid]
        for comp in ("concept_1_cui", "concept_2_cui"):
            for cui in c.split_ids(m[comp]):
                plan.append((eid, f"step8_concept_map:{comp}", "", cui, "", None, None, None, None, False))
    cuis = sorted({p[3] for p in plan if p[3]})
    tab = ds.dataset(c.UMLS_CONSO).to_table(filter=ds.field("CUI").isin(cuis),
                                             columns=["CUI", "SAB", "TTY", "CODE", "STR", "SUPPRESS"]).to_pandas()
    tab = tab[tab["SUPPRESS"] == "N"].sort_values(["CUI", "SAB", "TTY", "CODE", "STR"], kind="mergesort")
    sabs = tab.groupby("CUI")["SAB"].agg(lambda s: ";".join(sorted(set(s)))).to_dict()

    def codes_of(cui, sab):
        return sorted({cd for s, cd in umls["codes"].get(cui, []) if s == sab})

    def judge(eid, cui, r):
        if (eid, cui) in OVERRIDES:
            return (*OVERRIDES[(eid, cui)], "manual_override")
        if cui in DISEASE_CUIS:
            return "WRONG", "disease concept in symptom slot: " + DISEASE_CUIS[cui], "manual_override"
        cur_cuis = [resolve(t)[0] for t in c.split_ids(r["umls"])]
        ucls = {"=SCT": r["sct_class"], "=HPO": r["hpo_class"]}.get(r["umls_class"], r["umls_class"])
        if ucls == "NOT_APPLICABLE":
            return "NOT_APPLICABLE", f"evidence role {r['role']}", "auto_rule"
        cur_sct, cur_hpo = c.split_ids(r["sct_ids"]), c.split_ids(r["hpo_ids"])
        composite = len(cur_cuis) > 1
        same = cui in cur_cuis or set(codes_of(cui, "SNOMEDCT_US")) & set(cur_sct) and r["sct_class"] == ucls
        if same:
            return ("PARTIAL", "covers one component of composite", "auto_rule") if composite and ucls in c.USABLE \
                else (ucls, "same concept as curated (CUI or linked SNOMED code)", "auto_rule")
        if ucls == "NO_MATCH":
            return "WRONG", "curated: no appropriate concept", "auto_rule"
        for code in codes_of(cui, "SNOMEDCT_US"):
            for t in cur_sct:
                rel = sct_rel(sct, code, t)
                if rel:
                    ok = rel[1] <= 2 and ucls in c.USABLE
                    return ((("ACCEPTABLE_BROADER" if rel[0] == "ANC" else "ACCEPTABLE_NARROWER") if ok else "PARTIAL"),
                            f"SNOMED {code} is {rel[0].lower()} of curated {t} ({rel[1]} hop)", "auto_rule")
        for code in codes_of(cui, "HPO"):
            if code in cur_hpo:
                return ("PARTIAL" if composite else r["hpo_class"]), "linked HPO code equals curated HPO", "auto_rule"
            for t in cur_hpo:
                rel = hpo_depth_rel(hpo, code, t)
                if rel:
                    ok = rel[1] <= 2 and ucls in c.USABLE
                    return ((("ACCEPTABLE_BROADER" if rel[0] == "ANC" else "ACCEPTABLE_NARROWER") if ok else "PARTIAL"),
                            f"HPO {code} is {rel[0].lower()} of curated {t}", "auto_rule")
        return "WRONG", "different concept (no shared code / hierarchy link)", "auto_rule"

    rows = []
    for eid, src, rank, cui, extra, cls, conf, why, jsrc, comp in plan:
        r = cur.loc[eid]
        if src != "curated" and cui:
            cls, why, jsrc = judge(eid, cui, r)
            conf = "rule" if jsrc == "auto_rule" else "medium"
        sty = umls["sty"].get(cui, [])
        sty_names = sorted({s for _, s in sty})
        rows.append({
            "evidence_id": eid, "label_en": labels[eid][0], "label_ko": labels[eid][1], "evidence_role": r["role"],
            "canonical_concept": r["canonical_concept"], "candidate_source": src, "candidate_rank": rank, "cui": cui,
            "derived_from": extra if src == "curated" else "", "candidate_score": extra if src == "step8_tfidf" else "",
            "preferred_name": umls["pref"].get(cui, ""), "source_vocabularies": sabs.get(cui, ""),
            "snomed_codes": ";".join(codes_of(cui, "SNOMEDCT_US")), "hpo_codes": ";".join(codes_of(cui, "HPO")),
            "icd10cm_codes": ";".join(codes_of(cui, "ICD10CM")), "mesh_codes": ";".join(codes_of(cui, "MSH")),
            "has_snomed": bool(codes_of(cui, "SNOMEDCT_US")), "has_hpo": bool(codes_of(cui, "HPO")),
            "has_icd": bool(codes_of(cui, "ICD10CM") or codes_of(cui, "ICD10")),
            "semantic_types": ";".join(sty_names), "semantic_type_check": ("" if not cui else "OK" if set(sty_names) & SYMPTOM_STY else "CHECK"),
            "is_composite": comp, "mapping_class": cls, "confidence": conf, "reason": why, "judgement_source": jsrc,
            "review_status": c.CURATED_REVIEW if jsrc in ("curated", "manual_override") else c.AUTO_REVIEW,
            "in_umls_2026AA": (cui in umls["sty"]) if cui else False,
        })
    df = pd.DataFrame(rows)
    df["umls_release"] = "2026AA"
    assert df["mapping_class"].isin(c.CLASSES).all() and set(df["evidence_id"]) == set(cur.index)
    c.write_csv(df, "ddxplus_umls_mapping_audit.csv")
    # 표현층: curated CUI 의 소비자 표현(CHV, MEDLINEPLUS) + 전체 영어 문자열 수
    cur_cuis = df[(df.candidate_source == "curated") & (df.cui != "")][["evidence_id", "cui"]]
    lay = tab[tab["SAB"].isin(["CHV", "MEDLINEPLUS"])].groupby("CUI")["STR"].agg(lambda s: sorted({x.lower() for x in s}))
    nstr = tab.groupby("CUI")["STR"].agg(lambda s: len({x.lower() for x in s}))
    lay_rows = [{"evidence_id": e, "cui": u, "n_english_strings": int(nstr.get(u, 0)),
                 "consumer_strings_chv_medlineplus": " | ".join(lay.get(u, [])[:15])} for e, u in cur_cuis.itertuples(index=False)]
    c.write_csv(pd.DataFrame(lay_rows), "umls_lay_strings.csv")
    cu = df[df.candidate_source == "curated"]
    print("curated rows", len(cu), "unresolved", int((cu.cui == "").sum() - (cu.mapping_class.isin(['NOT_APPLICABLE', 'NO_MATCH'])).sum()))
    print("curated sty check", cu[cu.cui != ""]["semantic_type_check"].value_counts().to_dict())
    t1 = df[(df.candidate_source == "step8_tfidf") & (df.candidate_rank == 1)]
    print("step8 cui1 classes", t1["mapping_class"].value_counts().to_dict())


if __name__ == "__main__":
    main()
