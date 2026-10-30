"""STEP20-3/4: DDXPlus 증상 110 → HPO mapping 감사.

입력(읽기만): step8 evidence_hpo_candidates.csv(문자열 TF-IDF top3) · evidence_concept_map.csv(이전 의미 구조 기반 map)
           · curation/curated_mappings.tsv(Claude 판정) · data/hpo/hp.obo(2026-09-01)
판정 출처 구분:
  curated            — Claude 가 label·definition·parent 를 보고 내린 판정(임상의 검증 아님)
  auto_rule          — 기존 후보를 curated 판정과 HPO 계층으로 비교한 결정적 규칙
  manual_override    — 규칙이 부당한 기존 후보에 대해 Claude 가 사유와 함께 고친 판정(OVERRIDES)
출력: outputs/ddxplus_hpo_mapping_audit.csv (long: evidence × 후보 출처)
"""
import pandas as pd

import common as c

# 규칙 판정을 사람이(Claude) 고친 기존 후보. (evidence, hpo_id) → (class, reason)
OVERRIDES = {
    ("E_76", "HP:0002321"): ("PARTIAL", "Vertigo carries 'Dizziness' synonym; lightheadedness is not vertigo (same as curated)"),
    ("E_67", "HP:0033710"): ("PARTIAL", "Rest dyspnea is a sibling of PND, not the nocturnal paroxysmal concept"),
    ("E_14", "HP:0100749"): ("ACCEPTABLE_BROADER", "Chest pain; 'at rest' lost (same as curated)"),
    ("E_203", "HP:0012735"): ("ACCEPTABLE_BROADER", "Cough; paroxysmal subtype lost (same as curated)"),
    ("E_166", "HP:0012735"): ("WRONG", "Cough is the trigger, not the vomiting finding"),
    ("E_169", "HP:0033050"): ("WRONG", "Pharyngalgia (throat pain) is not itch"),
    ("E_170", "HP:0000989"): ("PARTIAL", "Pruritus is a skin phenotype; ocular pruritus is a separate HPO term"),
    ("E_179", "HP:0025085"): ("PARTIAL", "Bloody diarrhea requires diarrhea; evidence is blood in stool"),
    ("E_210", "HP:0032144"): ("ACCEPTABLE_NARROWER", "Coffee ground vomitus covers one disjunct of the question"),
    ("E_96", "HP:0004325"): ("WRONG", "Decreased body weight - opposite direction"),
    ("E_51", "HP:0040279"): ("WRONG", "'Frequency' is a frequency modifier term, not diarrhea"),
    ("E_32", "HP:0004396"): ("EXACT", "Poor appetite (same as curated)"),
    ("E_103", "HP:0004408"): ("ACCEPTABLE_BROADER", "Abnormality of the sense of smell is the parent of Anosmia"),
    ("E_218", "HP:0025377"): ("PARTIAL", "Triggered by exertion; relief by rest lost (same as curated)"),
    ("E_217", "HP:6000014"): ("ACCEPTABLE_NARROWER", "Pain worse when lying flat is pain-specific; evidence says 'symptoms'"),
    ("E_131", "HP:0040189"): ("ACCEPTABLE_BROADER", "Scaling skin ~ peeling (same as curated)"),
    ("E_88", "HP:0012378"): ("ACCEPTABLE_BROADER", "Fatigue; severity lost (same as curated)"),
    ("E_43", "HP:0007185"): ("PARTIAL", "Loss of consciousness without the convulsive/absence component"),
    ("E_157", "HP:0002936"): ("PARTIAL", "Distal sensory impairment: distal limbs only, perioral missing"),
    ("E_84", "HP:0430025"): ("WRONG", "Bilateral facial palsy - face, not limbs"),
    ("E_156", "HP:0004374"): ("PARTIAL", "Hemiplegia/hemiparesis is limb+face; evidence is facial only"),
    ("E_176", "HP:0012799"): ("PARTIAL", "Unilateral facial palsy covers the face disjunct only"),
    ("E_83", "HP:0030319"): ("PARTIAL", "covers facial disjunct only; ocular part missing"),
    ("E_9", "HP:0002716"): ("PARTIAL", "covers swollen disjunct only; painful part = HP:0025804"),
    ("E_172", "HP:0001488"): ("ACCEPTABLE_NARROWER", "Bilateral ptosis; evidence allows one or both"),
    ("E_202", "HP:0031247"): ("EXACT", "Whooping cough (same as curated)"),
    ("E_112", "HP:0010307"): ("PARTIAL", "Stridor is not inspiratory wheeze; overlaps only as abnormal breath sound"),
    ("E_194", "HP:0001620"): ("WRONG", "Abnormally high-pitched voice is voice, not breath sound"),
    ("E_130", "HP:0000988"): ("NOT_APPLICABLE", "evidence asks color; Skin rash is the parent finding"),
    ("E_134", "HP:0000988"): ("NOT_APPLICABLE", "evidence asks pain intensity; Skin rash is the parent finding"),
    ("E_132", "HP:0031244"): ("NOT_APPLICABLE", "evidence asks swelling grade of rash; Swollen lip is wrong site anyway"),
    ("E_136", "HP:0000989"): ("ACCEPTABLE_BROADER", "Pruritus (same as curated)"),
    ("E_57", "HP:6000684"): ("ACCEPTABLE_BROADER", "Radiating pain (same as curated)"),
    ("E_55", "HP:0012531"): ("NOT_APPLICABLE", "site attribute; Pain is the parent symptom E_53"),
    ("E_54", "HP:0012531"): ("NOT_APPLICABLE", "quality attribute; Pain is the parent symptom E_53"),
    ("E_56", "HP:0012531"): ("NOT_APPLICABLE", "severity attribute; Pain is the parent symptom E_53"),
    ("E_58", "HP:0012531"): ("NOT_APPLICABLE", "localization attribute; Pain is the parent symptom E_53"),
    ("E_59", "HP:0012531"): ("NOT_APPLICABLE", "onset attribute; Pain is the parent symptom E_53"),
    ("E_33", "HP:0012531"): ("PARTIAL", "Pain without the relieving modifier"),
    ("E_216", "HP:0012531"): ("PARTIAL", "Pain without the aggravating modifier"),
    ("E_221", "HP:0012531"): ("PARTIAL", "Pain without the Valsalva modifier"),
    ("E_220", "HP:0033771"): ("ACCEPTABLE_NARROWER", "Pleuritic chest pain (same as curated)"),
    ("E_161", "HP:0004396"): ("PARTIAL", "covers appetite disjunct only; early satiety = HP:0033842"),
    ("E_174", "HP:0004396"): ("PARTIAL", "covers appetite disjunct only"),
    ("E_89", "HP:0012378"): ("PARTIAL", "covers fatigue disjunct only"),
    ("E_89", "HP:5200292"): ("PARTIAL", "covers non-restful sleep disjunct only"),
    ("E_175", "HP:0033834"): ("PARTIAL", "covers malaise disjunct only"),
    ("E_177", "HP:0003401"): ("PARTIAL", "covers tingling disjunct only"),
    ("E_93", "HP:0003401"): ("ACCEPTABLE_BROADER", "Paresthesia (same as curated)"),
    ("E_181", "HP:0031417"): ("PARTIAL", "covers rhinorrhea disjunct only"),
    ("E_181", "HP:0001742"): ("PARTIAL", "covers congestion disjunct only"),
    ("E_205", "HP:0040264"): ("PARTIAL", "covers jaw pain disjunct only"),
    ("E_205", "HP:0000211"): ("PARTIAL", "covers trismus disjunct only"),
    ("E_114", "HP:0000737"): ("PARTIAL", "covers irritability disjunct only"),
    ("E_178", "HP:0000978"): ("PARTIAL", "covers bruising disjunct only"),
    ("E_178", "HP:0001892"): ("PARTIAL", "covers bleeding disjunct only"),
    ("E_188", "HP:0040319"): ("PARTIAL", "covers dark urine conjunct only"),
    ("E_188", "HP:0011985"): ("PARTIAL", "covers pale stool conjunct only"),
    ("E_171", "HP:5200217"): ("PARTIAL", "covers depersonalization disjunct only"),
    ("E_171", "HP:5200218"): ("PARTIAL", "covers derealization disjunct only"),
    ("E_30", "HP:0003270"): ("ACCEPTABLE_BROADER", "Abdominal distention covers the main sense of the question"),
    ("E_82", "HP:0002321"): ("PARTIAL", "Vertigo (has 'Dizziness' synonym); presyncope is not vertigo"),
    ("E_212", "HP:0001609"): ("PARTIAL", "Hoarse voice covers the 'hoarse' disjunct only"),
    ("E_90", "HP:0003750"): ("PARTIAL", "Increased muscle fatiguability ~ related but not fatigable weakness"),
    ("E_192", "HP:0003394"): ("PARTIAL", "Muscle spasm without the neck/head-turning component"),
}


def hpo_depth_rel(hpo, cand: str, target: str):
    """cand 가 target 의 조상이면 ('ANC', 거리), 자손이면 ('DESC', 거리), 아니면 None."""
    def dist(a, b):   # a 에서 위로 올라가 b 까지 hop 수
        frontier, seen, d = {a}, {a}, 0
        while frontier and d < 12:
            if b in frontier:
                return d
            nxt = set()
            for x in frontier:
                nxt.update(hpo["terms"].get(x, {}).get("is_a", []))
            frontier = nxt - seen
            seen |= nxt
            d += 1
        return None
    d = dist(target, cand)
    if d:
        return ("ANC", d)
    d = dist(cand, target)
    if d:
        return ("DESC", d)
    return None


def rule_class(hpo, eid, cand, cur):
    """기존 후보 1개를 curated 판정과 비교(결정적 규칙)."""
    if (eid, cand) in OVERRIDES:
        cls, why = OVERRIDES[(eid, cand)]
        return cls, why, "manual_override"
    ids = c.split_ids(cur["hpo_ids"])
    ccls = cur["hpo_class"]
    if ccls == "NOT_APPLICABLE":
        return "NOT_APPLICABLE", f"evidence role {cur['role']}: HPO phenotype not appropriate", "auto_rule"
    if cand in ids:
        if len(ids) > 1 and ccls in c.USABLE:
            return "PARTIAL", "covers one component of a composite evidence", "auto_rule"
        return ccls, "same concept as curated", "auto_rule"
    if ccls == "NO_MATCH":
        return "WRONG", "curated: no appropriate HPO concept exists", "auto_rule"
    for t in ids:
        rel = hpo_depth_rel(hpo, cand, t)
        if rel and rel[0] == "ANC":
            return (("ACCEPTABLE_BROADER" if rel[1] <= 2 and ccls in c.USABLE else "PARTIAL"),
                    f"ancestor of curated {t} ({rel[1]} hop)", "auto_rule")
        if rel and rel[0] == "DESC":
            return (("ACCEPTABLE_NARROWER" if rel[1] <= 2 and ccls in c.USABLE else "PARTIAL"),
                    f"descendant of curated {t} ({rel[1]} hop)", "auto_rule")
    return "WRONG", "not curated concept, not its ancestor/descendant", "auto_rule"


def term_info(hpo, hid):
    raw = hpo["terms"].get(hid)
    resolved = hpo["alt"].get(hid, hid)
    t = hpo["terms"].get(resolved, {})
    obsolete = bool(raw and raw.get("obsolete"))
    repl = ";".join((raw or {}).get("replaced_by", []) + (raw or {}).get("consider", []))
    return {
        "hpo_name": t.get("name", ""),
        "hpo_definition": t.get("def", "")[:300],
        "hpo_synonyms": "; ".join(f"{s}[{k}]" for s, k in t.get("syn", [])[:8]),
        "hpo_parents": "; ".join(f"{p} {hpo['terms'].get(p, {}).get('name', '')}" for p in t.get("is_a", [])),
        "in_hp_obo": hid in hpo["terms"] or hid in hpo["alt"],
        "is_alt_id": hid in hpo["alt"],
        "is_obsolete": obsolete,
        "replacement_id": repl,
    }


def string_match(hpo, hid, texts):
    """canonical / 질문 문자열이 HPO name 또는 synonym(scope) 과 정규화 일치하는가 — 자동 신호(판정 아님)."""
    t = hpo["terms"].get(hid, {})
    norms = {c.norm(x) for x in texts if x}
    if c.norm(t.get("name", "")) in norms:
        return "NAME"
    for s, scope in t.get("syn", []):
        if c.norm(s) in norms:
            return f"SYNONYM_{scope}"
    return ""


def main():
    hpo = c.load_hpo()
    cur = c.load_curation().set_index("evidence_id")
    s8, _, cmap = c.load_step8()
    s8 = s8.set_index("evidence")
    cmap = cmap.set_index("evidence_id")
    labels = c.inventory_labels()
    rows = []
    for eid in cur.index:
        r = cur.loc[eid]
        label_en, label_ko = labels[eid]
        base = {"evidence_id": eid, "label_en": label_en, "label_ko": label_ko, "evidence_role": r["role"],
                "canonical_concept": r["canonical_concept"]}
        # (1) curated
        ids = c.split_ids(r["hpo_ids"]) or [""]
        for hid in ids:
            info = term_info(hpo, hid) if hid else {}
            rows.append({**base, "candidate_source": "curated", "candidate_rank": "", "hpo_id": hid,
                         **info, "candidate_score": "", "string_match": string_match(hpo, hid, [r["canonical_concept"]]) if hid else "",
                         "is_composite": len(ids) > 1, "mapping_class": r["hpo_class"], "confidence": r["hpo_conf"],
                         "reason": r["hpo_reason"], "judgement_source": "curated", "review_status": c.CURATED_REVIEW})
        # (2) 기존 자동 후보 top3
        x = s8.loc[eid]
        for k, (col, scol) in enumerate([("hpo1_id", "hpo1_score"), ("hpo2_id", "hpo2_score"), ("hpo3_id", None)], 1):
            hid = x[col]
            if not hid:
                continue
            cls, why, src = rule_class(hpo, eid, hid, r)
            rows.append({**base, "candidate_source": "step8_tfidf", "candidate_rank": k, "hpo_id": hid,
                         **term_info(hpo, hid), "candidate_score": x[scol] if scol else "",
                         "string_match": string_match(hpo, hid, [r["canonical_concept"]]), "is_composite": False,
                         "mapping_class": cls, "confidence": "rule" if src == "auto_rule" else "medium", "reason": why,
                         "judgement_source": src, "review_status": c.AUTO_REVIEW if src == "auto_rule" else c.CURATED_REVIEW,
                         "step8_auto_grade": x["auto_grade"], "step8_review_status": x["review_status"] or "EMPTY",
                         "step8_final_hpo_id": x["final_hpo_id"] or "EMPTY"})
        # (3) 이전 concept map (concept_1/2_hpo, 세미콜론 여러 개 가능)
        m = cmap.loc[eid]
        for comp in ("concept_1_hpo", "concept_2_hpo"):
            for hid in c.split_ids(m[comp]):
                cls, why, src = rule_class(hpo, eid, hid, r)
                rows.append({**base, "candidate_source": f"step8_concept_map:{comp}", "candidate_rank": "", "hpo_id": hid,
                             **term_info(hpo, hid), "candidate_score": "", "string_match": "", "is_composite": False,
                             "mapping_class": cls, "confidence": "rule" if src == "auto_rule" else "medium", "reason": why,
                             "judgement_source": src, "review_status": c.AUTO_REVIEW if src == "auto_rule" else c.CURATED_REVIEW,
                             "step8_auto_grade": m["mapping_status"]})
    df = pd.DataFrame(rows)
    df["hpo_version"] = hpo["version"]
    assert set(df["evidence_id"]) == set(cur.index) and df["mapping_class"].isin(c.CLASSES).all()
    c.write_csv(df, "ddxplus_hpo_mapping_audit.csv")
    cu = df[df.candidate_source == "curated"].drop_duplicates("evidence_id")
    print("curated", cu["mapping_class"].value_counts().to_dict())
    t1 = df[(df.candidate_source == "step8_tfidf") & (df.candidate_rank == 1)]
    print("step8 top1", t1["mapping_class"].value_counts().to_dict(), "by", t1["judgement_source"].value_counts().to_dict())
    print("obsolete candidates", int(df["is_obsolete"].sum()), "alt ids", int(df["is_alt_id"].sum()),
          "not in obo", int((~df["in_hp_obo"].fillna(True).astype(bool)).sum()))


if __name__ == "__main__":
    main()
