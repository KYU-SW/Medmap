"""STEP20-6: DDXPlus 증상 110 → SNOMED CT International 2026-09-01 mapping 감사.

입력(읽기만): RF2 Snapshot(Concept·Description·Relationship·Language refset·Association refset)
           · curation/curated_mappings.tsv · step8 evidence_concept_map.csv(concept_1/2_snomed)
           · step8 evidence_umls_candidates.csv(cui1 의 SNOMEDCT_US 코드 — 기존 자동 후보가 가리키던 SNOMED 개념)
판정: curated(Claude) / auto_rule(curated 와 is-a 계층 비교) / manual_override.
분할 권고(split_recommendation): SNOMED 의 더 세밀한 하위 개념을 MedMap 의 별도 binary feature 로 쪼갤지 여부.
  원칙 — 하위 개념이 부위·양상·시간·악화요인 같은 속성 조합이면 상위 개념 + 속성 slot 값으로 표현하고 쪼개지 않는다.
출력: outputs/ddxplus_snomed_mapping_audit.csv
"""
from collections import defaultdict

import pandas as pd

import common as c
from audit_umls_mapping import sct_rel

TOP = {"404684003": "Clinical finding", "71388002": "Procedure", "363787002": "Observable entity",
       "362981000": "Qualifier value", "272379006": "Event", "243796009": "Situation with explicit context",
       "123037004": "Body structure", "105590001": "Substance", "410607006": "Organism", "48176007": "Social context",
       "106237007": "Linkage concept", "900000000000441003": "SNOMED CT Model Component", "260787004": "Physical object",
       "78621006": "Physical force", "308916002": "Environment or geographical location", "370115009": "Special concept",
       "373873005": "Pharmaceutical / biologic product", "419891008": "Record artifact", "254291000": "Staging and scales",
       "123038009": "Specimen"}
OVERRIDES = {
    ("E_159", "106167005"): ("WRONG", "Finding of consciousness grouping, not loss"),
    ("E_159", "418107008"): ("PARTIAL", "Unconscious is a state; evidence is an episode of loss"),
    ("E_129", "247441003"): ("PARTIAL", "Erythema covers the redness disjunct only"),
    ("E_51", "15510009"): ("PARTIAL", "covers the increased-frequency disjunct only"),
    ("E_89", "248274002"): ("PARTIAL", "Lack of energy ~ related to fatigue, not equivalent"),
    ("E_88", "248274002"): ("PARTIAL", "Lack of energy; severity lost"),
    ("E_175", "248274002"): ("PARTIAL", "Lack of energy; one disjunct"),
    ("E_175", "213257006"): ("PARTIAL", "Generally unwell (malaise synonym) covers one disjunct"),
    ("E_220", "2237002"): ("ACCEPTABLE_NARROWER", "Pleuritic pain is chest-specific"),
    ("E_220", "1144586002"): ("PARTIAL", "Increased pain without breathing trigger"),
    ("E_216", "1144586002"): ("PARTIAL", "Increased pain without movement trigger"),
    ("E_33", "22253000"): ("PARTIAL", "Pain without the relieving modifier"),
    ("E_33", "230021003"): ("PARTIAL", "Forward lean position without pain relief"),
    ("E_93", "397974008"): ("ACCEPTABLE_BROADER", "Hypesthesia; foot site lost"),
    ("E_93", "59073000"): ("PARTIAL", "Tactile hypesthesia; site lost, tingling missing"),
    ("E_93", "101000119102"): ("ACCEPTABLE_BROADER", "Numbness and tingling of skin; foot site lost"),
    ("E_127", "193982009"): ("ACCEPTABLE_BROADER", "Epiphora (watery eye of any cause)"),
    ("E_127", "346181000119106"): ("ACCEPTABLE_NARROWER", "bilateral epiphora due to excess tear production"),
    ("E_181", "267101005"): ("PARTIAL", "situation concept (present), not the finding"),
    ("E_182", "267101005"): ("PARTIAL", "situation concept (present), colour lost"),
    ("E_182", "8442000"): ("PARTIAL", "Purulent rhinitis is an inflammatory label"),
    ("E_144", "2134003"): ("PARTIAL", "diffuse pain, not specifically muscle"),
    ("E_215", "225758001"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_215", "24863003"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_215", "309603005"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_219", "2546009"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_221", "261039008"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_13", "252157006"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_13", "255314001"): ("PARTIAL", "qualifier value; usable only in post-coordination"),
    ("E_96", "816159004"): ("PARTIAL", "observable (measured amount), not the finding"),
    ("E_50", "312230002"): ("EXACT", "Hyperhidrosis (disorder tag) - synonymous clinical label"),
    ("E_65", "288939007"): ("EXACT", "Difficulty swallowing - synonymous finding"),
    ("E_63", "8011004"): ("EXACT", "Dysarthria - clinical label of the same finding"),
    ("E_128", "406444002"): ("PARTIAL", "Laryngeal spasm is a mechanism-level label"),
    ("E_128", "53787002"): ("PARTIAL", "Laryngismus is a mechanism-level label"),
    ("E_212", "50219008"): ("PARTIAL", "Hoarse covers one disjunct"),
    ("E_212", "16617009"): ("EXACT", "Dysphonia ~ change in voice"),
    ("E_206", "102616008"): ("PARTIAL", "Painful mouth without ulcer"),
    ("E_211", "249497008"): ("ACCEPTABLE_BROADER", "Vomiting symptom; frequency and retching lost"),
    ("E_211", "84480002"): ("PARTIAL", "Retching covers one disjunct"),
    ("E_112", "272040008"): ("ACCEPTABLE_BROADER", "Wheezing symptom; inspiratory lost"),
    ("E_112", "248573009"): ("PARTIAL", "Noisy respiration; whoop component unspecific"),
    ("E_178", "125667009"): ("PARTIAL", "Contusion (traumatic bruise) for spontaneous bruising"),
    ("E_45", "6686005"): ("ACCEPTABLE_NARROWER", "Blood streaked sputum is a mild form of hemoptysis"),
    ("E_150", "14760008"): ("PARTIAL", "Constipation; polarity inverted and flatus part missing"),
    ("E_169", "418290006"): ("ACCEPTABLE_BROADER", "Itching (generic); nose/throat site lost"),
    ("E_177", "397974008"): ("PARTIAL", "Hypesthesia covers the loss-of-sensation disjunct"),
    ("E_177", "59073000"): ("PARTIAL", "Tactile hypesthesia covers part of one disjunct"),
    ("E_168", "285503005"): ("PARTIAL", "Does protrude tongue - voluntary ability finding"),
    ("E_67", "249489001"): ("PARTIAL", "Choking without the nocturnal paroxysmal dyspnea context"),
}
SLOT_HINTS = ("left", "right", "bilateral", "acute", "chronic", "nocturnal", "night", "severe", "mild", "moderate",
              "recurrent", "intermittent", "persistent", "upper", "lower", "on exertion", "at rest", "of ")


def top_hierarchy(sct, cid):
    anc = c.sct_ancestors(sct, cid)
    hits = [TOP[t] for t in TOP if t in anc or t == cid]
    return ";".join(sorted(set(hits)))


def main():
    sct = c.load_snomed()
    cur = c.load_curation().set_index("evidence_id")
    _, s8u, cmap = c.load_step8()
    s8u, cmap = s8u.set_index("evidence"), cmap.set_index("evidence_id")
    umls = c.load_umls()
    labels = c.inventory_labels()
    children = defaultdict(list)
    for k, ps in sct["parents"].items():
        if sct["active"].get(k):
            for p in ps:
                children[p].append(k)

    def info(cid):
        act = sct["active"].get(cid)
        kids = sorted(children.get(cid, []), key=lambda x: sct["pt"].get(x, sct["fsn"].get(x, "")))
        assoc = sct["assoc"].get(cid, [])
        return {
            "snomed_fsn": sct["fsn"].get(cid, ""), "preferred_term": sct["pt"].get(cid, ""),
            "semantic_tag": c.sct_semantic_tag(sct, cid), "synonyms": "; ".join(sct["syn"].get(cid, [])[:6]),
            "in_release": act is not None, "active": bool(act),
            "inactive_associations": "; ".join(f"{a}:{t} {sct['fsn'].get(t, '')}" for a, t in assoc) if act is False else "",
            "top_hierarchy": top_hierarchy(sct, cid) if act else "",
            "is_clinical_finding": bool(act) and c.SCT_CLINICAL_FINDING in c.sct_ancestors(sct, cid),
            "parent_concepts": "; ".join(f"{p} {sct['pt'].get(p, '')}" for p in sct["parents"].get(cid, [])),
            "n_children": len(kids), "child_examples": "; ".join(sct["pt"].get(k, "") for k in kids[:6]),
            "n_children_slotlike": sum(1 for k in kids if any(h in sct["pt"].get(k, "").lower() for h in SLOT_HINTS)),
        }

    def judge(eid, cid, r):
        if (eid, cid) in OVERRIDES:
            return (*OVERRIDES[(eid, cid)], "manual_override")
        ids, ccls = c.split_ids(r["sct_ids"]), r["sct_class"]
        if ccls == "NOT_APPLICABLE":
            return "NOT_APPLICABLE", f"evidence role {r['role']}", "auto_rule"
        if cid not in sct["active"]:
            return "WRONG", "not in INT 2026-09-01 release (namespace 1000124/1000119 = US extension)", "auto_rule"
        if not sct["active"][cid]:
            return "WRONG", "inactive concept in 2026-09-01 release", "auto_rule"
        if cid in ids:
            return (("PARTIAL", "covers one component of composite", "auto_rule") if len(ids) > 1 and ccls in c.USABLE
                    else (ccls, "same concept as curated", "auto_rule"))
        if ccls == "NO_MATCH":
            return "WRONG", "curated: no appropriate concept", "auto_rule"
        for t in ids:
            rel = sct_rel(sct, cid, t)
            if rel:
                ok = rel[1] <= 2 and ccls in c.USABLE
                return ((("ACCEPTABLE_BROADER" if rel[0] == "ANC" else "ACCEPTABLE_NARROWER") if ok else "PARTIAL"),
                        f"{rel[0].lower()} of curated {t} ({rel[1]} hop)", "auto_rule")
        return "WRONG", "different concept (no is-a link to curated)", "auto_rule"

    def split_rec(r, inf):
        if r["role"] in ("ATTRIBUTE", "MODIFIER", "EXPOSURE"):
            return "N/A - evidence is itself a slot/context"
        if inf["n_children"] == 0:
            return "NO_FINER_CONCEPTS"
        return ("USE_AS_SLOT_VALUES - keep one canonical concept; children are attribute combinations "
                f"({inf['n_children_slotlike']}/{inf['n_children']} children carry site/time/severity words)")

    rows = []
    for eid in cur.index:
        r = cur.loc[eid]
        base = {"evidence_id": eid, "label_en": labels[eid][0], "label_ko": labels[eid][1], "evidence_role": r["role"],
                "canonical_concept": r["canonical_concept"]}
        ids = c.split_ids(r["sct_ids"])
        for cid in ids or [""]:
            inf = info(cid) if cid else {}
            rows.append({**base, "candidate_source": "curated", "snomed_id": cid, **inf, "is_composite": len(ids) > 1,
                         "mapping_class": r["sct_class"], "confidence": r["sct_conf"], "reason": r["sct_reason"],
                         "judgement_source": "curated", "review_status": c.CURATED_REVIEW,
                         "split_recommendation": split_rec(r, inf) if cid else ("N/A - evidence is itself a slot/context"
                                                                                if r["role"] in ("ATTRIBUTE", "MODIFIER", "EXPOSURE") else "")})
        cands = []
        m = cmap.loc[eid]
        for comp in ("concept_1_snomed", "concept_2_snomed"):
            cands += [(f"step8_concept_map:{comp}", x) for x in c.split_ids(m[comp])]
        cui1 = s8u.loc[eid]["cui1"]
        if cui1:
            cands += [("step8_tfidf_cui1_linked", code) for sab, code in umls["codes"].get(cui1, []) if sab == "SNOMEDCT_US"]
        for src, cid in cands:
            cls, why, jsrc = judge(eid, cid, r)
            rows.append({**base, "candidate_source": src, "snomed_id": cid, **info(cid), "is_composite": False,
                         "mapping_class": cls, "confidence": "rule" if jsrc == "auto_rule" else "medium", "reason": why,
                         "judgement_source": jsrc, "review_status": c.AUTO_REVIEW if jsrc == "auto_rule" else c.CURATED_REVIEW,
                         "split_recommendation": ""})
    df = pd.DataFrame(rows)
    df["snomed_release"] = "INT 2026-09-01 Snapshot"
    assert df["mapping_class"].isin(c.CLASSES).all() and set(df["evidence_id"]) == set(cur.index)
    cu = df[(df.candidate_source == "curated") & (df.snomed_id != "")]
    assert cu["active"].all(), cu[~cu["active"]][["evidence_id", "snomed_id"]]
    c.write_csv(df, "ddxplus_snomed_mapping_audit.csv")
    print("curated concepts", len(cu), "clinical finding", int(cu["is_clinical_finding"].sum()),
          "tags", cu["semantic_tag"].value_counts().to_dict())
    pr = df[df.candidate_source != "curated"]
    print("prior candidates", pr["mapping_class"].value_counts().to_dict(),
          "not_in_release", int((~pr["in_release"].astype(bool)).sum()),
          "inactive_in_release", int((pr["in_release"].astype(bool) & ~pr["active"].astype(bool)).sum()))


if __name__ == "__main__":
    main()
