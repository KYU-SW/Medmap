"""STEP20 요약 단계(audit_symptom_mapping.py summary 에서 호출). 모든 숫자는 결과 CSV 에서 계산한다(손으로 적지 않음).

출력:
  mapping_coverage_summary.json     7.  ontology 별/union coverage (+기존 후보 baseline, core subset)
  symptom_expansion_opportunities.csv 8. 확장 수준·차원·SNOMED/HPO 하위 개념 수
  concept_normalization_layers.csv  9.  표면 표현 → 정규화 ID → canonical concept
  disease_overlap_summary.csv       11. HPO phenotype.hpoa 질환 공간 + phenotype-overlap disease count (진단 가능 수 아님)
  disease_annotation_distribution.json 11. 질환당 phenotype 수 · phenotype 당 질환 수 분포
  auxiliary_kb_sampling.csv         12. HSDN · MEDLINE · OptimusKG 보조 대조(통합 그래프 아님)
  representative_symptoms.csv       13. 대표 증상 상세표
  manifest.json                     21. 원본 버전·SHA256, 결과 row 수·SHA256, 결정성 메모
"""
import json
from collections import Counter, defaultdict

import pandas as pd

import common as c

ROLES_CORE = {"SYMPTOM", "SIGN", "COMPOSITE"}
ONT = ("HPO", "SNOMED", "UMLS")


def _best(classes):
    return min(classes, key=lambda k: c.RANK[k])


def evidence_classes(cur):
    """evidence × ontology curated 판정(UMLS '=SCT'/'=HPO' 해소)."""
    out = {}
    for r in cur.itertuples():
        u = {"=SCT": r.sct_class, "=HPO": r.hpo_class}.get(r.umls_class, r.umls_class)
        out[r.evidence_id] = {"HPO": r.hpo_class, "SNOMED": r.sct_class, "UMLS": u}
    return out


def coverage_block(cls_by_eid, eids):
    n = len(eids)
    cnt = Counter(cls_by_eid[e] for e in eids)
    exact = cnt["EXACT"]
    usable = sum(cnt[k] for k in c.USABLE)
    partial = usable + cnt["PARTIAL"]
    return {"n": n, "counts": {k: cnt.get(k, 0) for k in c.CLASSES},
            "strict_coverage": round(exact / n, 4), "usable_coverage": round(usable / n, 4),
            "partial_included_coverage": round(partial / n, 4),
            "exact_n": exact, "usable_n": usable, "partial_included_n": partial}


def coverage(cur):
    ec = evidence_classes(cur)
    roles = dict(zip(cur.evidence_id, cur.role))
    all_e = sorted(ec)
    core = [e for e in all_e if roles[e] in ROLES_CORE]
    combos = {"HPO": ["HPO"], "UMLS": ["UMLS"], "SNOMED": ["SNOMED"], "HPO∪SNOMED": ["HPO", "SNOMED"],
              "HPO∪UMLS": ["HPO", "UMLS"], "HPO∪UMLS∪SNOMED": list(ONT)}
    res = {"denominator_note": "all 110 DDXPlus symptoms; NOT_APPLICABLE (attribute/exposure) stays in the denominator",
           "definitions": {"strict": "EXACT/110", "usable": "(EXACT+ACCEPTABLE_BROADER+ACCEPTABLE_NARROWER)/110",
                           "partial_included": "(usable+PARTIAL)/110",
                           "union": "per evidence, best class across the ontologies in the set"},
           "all_110": {}, "core_symptom_subset": {}}
    for name, onts in combos.items():
        per = {e: _best([ec[e][o] for o in onts]) for e in all_e}
        res["all_110"][name] = coverage_block(per, all_e)
        res["core_symptom_subset"][name] = coverage_block(per, core)
    res["core_symptom_subset_note"] = f"roles {sorted(ROLES_CORE)}: n={len(core)} (ATTRIBUTE/MODIFIER/EXPOSURE removed)"
    res["roles"] = dict(Counter(roles.values()))
    res["composite_evidence_n"] = int((cur["role"] == "COMPOSITE").sum())
    res["composite_note"] = "COMPOSITE evidence counts as EXACT only when every component concept is mapped exactly"
    return res, ec


def baselines():
    """기존 step8 자동 후보·이전 concept map 이 그대로 쓰였을 때의 coverage(rule/override 판정 결과 사용)."""
    h = pd.read_csv(c.OUT / "ddxplus_hpo_mapping_audit.csv", dtype=str, keep_default_na=False)
    u = pd.read_csv(c.OUT / "ddxplus_umls_mapping_audit.csv", dtype=str, keep_default_na=False)
    s = pd.read_csv(c.OUT / "ddxplus_snomed_mapping_audit.csv", dtype=str, keep_default_na=False)
    eids = sorted(h["evidence_id"].unique())
    out = {}

    def block(df, src_mask, label):
        sub = df[src_mask]
        per = {e: _best(sub[sub.evidence_id == e]["mapping_class"].tolist() or ["NO_MATCH"]) for e in eids}
        b = coverage_block(per, eids)
        b["evidences_without_candidate"] = int(sum(1 for e in eids if sub[sub.evidence_id == e].empty))
        out[label] = b
    block(h, (h.candidate_source == "step8_tfidf") & (h.candidate_rank == "1"), "HPO step8 TF-IDF top1")
    block(h, h.candidate_source == "step8_tfidf", "HPO step8 TF-IDF best of top3 (oracle pick)")
    block(h, h.candidate_source.str.startswith("step8_concept_map"), "HPO step8 concept_map (best component)")
    block(u, (u.candidate_source == "step8_tfidf") & (u.candidate_rank == "1"), "UMLS step8 TF-IDF cui1")
    block(u, u.candidate_source.str.startswith("step8_concept_map"), "UMLS step8 concept_map (best component)")
    block(s, s.candidate_source.str.startswith("step8_concept_map"), "SNOMED step8 concept_map (best component)")
    out["_note"] = ("existing candidates judged by deterministic rule against the curated mapping plus listed manual "
                    "overrides; 'best' = most favourable candidate per evidence, i.e. an upper bound for that source")
    return out


def expansion(cur):
    hpo, sct = c.load_hpo(), c.load_snomed()
    s_audit = pd.read_csv(c.OUT / "ddxplus_snomed_mapping_audit.csv", dtype=str, keep_default_na=False)
    s_cur = s_audit[s_audit.candidate_source == "curated"]
    kids = defaultdict(set)
    for t in hpo["terms"].values():
        if not t["obsolete"]:
            for p in t["is_a"]:
                kids[p].add(t["id"])

    def hpo_desc(h):
        out, st = set(), [h]
        while st:
            for k in kids.get(st.pop(), ()):
                if k not in out:
                    out.add(k)
                    st.append(k)
        return out
    inv = pd.read_csv(c.OUT / "symptom_inventory.csv", dtype=str, keep_default_na=False).set_index("evidence_id")
    rows = []
    for r in cur.itertuples():
        dims = c.split_ids(r.expansion_dims)
        hd = set().union(*[hpo_desc(h) for h in c.split_ids(r.hpo_ids)]) if r.hpo_ids else set()
        sc = s_cur[s_cur.evidence_id == r.evidence_id]
        rows.append({
            "evidence_id": r.evidence_id, "label_ko": inv.loc[r.evidence_id, "label_ko"], "evidence_role": r.role,
            "canonical_concept": r.canonical_concept, "expansion_level": r.expansion_level,
            "expansion_dimensions": ";".join(dims), "n_dimensions": len(dims),
            "dims_already_in_ddxplus": ("E_54 quality;E_55 site;E_56 severity;E_57 radiation;E_58 localization;E_59 onset" if r.evidence_id == "E_53"
                                        else "E_130 color;E_132 swelling;E_133 site;E_134 pain;E_135 size;E_136 itch" if r.evidence_id == "E_129"
                                        else "E_152 site" if r.evidence_id == "E_151" else ""),
            "hpo_descendant_terms_n": len(hd),
            "hpo_descendant_examples": "; ".join(sorted(hpo["terms"][x]["name"] for x in hd)[:6]),
            "snomed_children_n": int(pd.to_numeric(sc["n_children"], errors="coerce").fillna(0).sum()),
            "snomed_child_examples": " | ".join(x for x in sc["child_examples"] if x)[:300],
            "snomed_split_recommendation": " | ".join(sorted({x for x in sc["split_recommendation"] if x})),
            "judgement_source": "curated (Claude) for level/dims; counts computed from HPO/SNOMED",
            "note": r.note,
        })
    df = pd.DataFrame(rows)
    c.write_csv(df, "symptom_expansion_opportunities.csv")
    return dict(Counter(df["expansion_level"]))


def layers(cur):
    hpo, sct = c.load_hpo(), c.load_snomed()
    inv = pd.read_csv(c.OUT / "symptom_inventory.csv", dtype=str, keep_default_na=False).set_index("evidence_id")
    lay = pd.read_csv(c.OUT / "umls_lay_strings.csv", dtype=str, keep_default_na=False)
    u = pd.read_csv(c.OUT / "ddxplus_umls_mapping_audit.csv", dtype=str, keep_default_na=False)
    ucur = u[u.candidate_source == "curated"]
    rows = []
    for r in cur.itertuples():
        hids, sids = c.split_ids(r.hpo_ids), c.split_ids(r.sct_ids)
        cuis = [x for x in ucur[ucur.evidence_id == r.evidence_id]["cui"] if x]
        rows.append({
            "evidence_id": r.evidence_id, "evidence_role": r.role,
            "layer3_canonical_symptom": r.canonical_concept,
            "layer2_normalized_ids": " | ".join(filter(None, [";".join(hids), ";".join(f"SCTID:{x}" for x in sids), ";".join(cuis)])),
            "layer1_surface_ddxplus_en": inv.loc[r.evidence_id, "question_en"],
            "layer1_surface_ko_label": inv.loc[r.evidence_id, "label_ko"],
            "layer1_surface_ko_question": inv.loc[r.evidence_id, "question_ko"],
            "layer1_surface_hpo_exact_synonyms": "; ".join(sorted({s for h in hids for s, k in hpo["terms"][h]["syn"] if k == "EXACT"}))[:400],
            "layer1_surface_snomed_synonyms": "; ".join(sorted({x for s in sids for x in sct["syn"].get(s, [])}))[:400],
            "layer1_surface_umls_consumer_chv_medlineplus": " | ".join(x for x in lay[lay.evidence_id == r.evidence_id]["consumer_strings_chv_medlineplus"] if x)[:500],
            "n_umls_english_strings": int(pd.to_numeric(lay[lay.evidence_id == r.evidence_id]["n_english_strings"]).sum()),
        })
    df = pd.DataFrame(rows)
    c.write_csv(df, "concept_normalization_layers.csv")
    return {"evidence_with_consumer_strings": int((df["layer1_surface_umls_consumer_chv_medlineplus"] != "").sum()),
            "median_umls_english_strings": float(df["n_umls_english_strings"].median())}


def disease_overlap(cur):
    hpo = c.load_hpo()
    ann = pd.read_csv(c.HPO_HPOA, sep="\t", comment="#", dtype=str, keep_default_na=False)
    # '#' 로 시작하는 header 행 처리: pandas comment 로 header 도 지워지므로 직접 지정
    if "database_id" not in ann.columns:
        cols = ["database_id", "disease_name", "qualifier", "hpo_id", "reference", "evidence", "onset", "frequency",
                "sex", "modifier", "aspect", "biocuration"]
        ann = pd.read_csv(c.HPO_HPOA, sep="\t", comment="#", header=None, names=cols, dtype=str, keep_default_na=False)
        ann = ann[ann.database_id != "database_id"]
    ann["source"] = ann["database_id"].str.split(":").str[0]
    allsrc = ann.groupby("source")["database_id"].nunique().to_dict()
    p = ann[(ann.aspect == "P") & (ann.qualifier != "NOT")]
    dis = p.groupby("database_id")["hpo_id"].agg(lambda s: set(s))
    src = p.groupby("database_id")["source"].first()
    per_dis = dis.map(len)
    per_phe = p.groupby("hpo_id")["database_id"].nunique()
    q = lambda s: {k: float(v) for k, v in s.describe(percentiles=[.1, .5, .9]).round(2).items()}
    dist = {"hpoa_version_line": open(c.HPO_HPOA).readline().strip(), "diseases_all_aspects_by_source": allsrc,
            "phenotypic_abnormality_aspect_P_excluding_NOT": {"diseases": int(len(dis)), "by_source": src.value_counts().to_dict(),
                                                                "annotations": int(len(p)), "distinct_hpo_terms": int(per_phe.size)},
            "phenotypes_per_disease": q(per_dis), "diseases_per_phenotype": q(per_phe)}
    # 매칭 집합: curated usable / +partial
    sets = {}
    for label, ok in (("usable", c.USABLE), ("usable+partial", c.USABLE | {"PARTIAL"})):
        ev = {r.evidence_id: c.split_ids(r.hpo_ids) for r in cur.itertuples() if r.hpo_class in ok and r.hpo_ids}
        sets[label] = ev
    anc_cache = {}

    def anc(h):
        if h not in anc_cache:
            anc_cache[h] = c.hpo_ancestors(hpo, hpo["alt"].get(h, h)) | {hpo["alt"].get(h, h)}
        return anc_cache[h]
    rows = []
    for label, ev in sets.items():
        target = {h for hs in ev.values() for h in hs}
        for mode in ("exact_id", "true_path"):
            n_ev, n_id = {}, {}
            for d, terms in dis.items():
                if mode == "exact_id":
                    hit_ids = target & terms
                else:
                    up = set().union(*[anc(t) for t in terms])
                    hit_ids = target & up
                n_id[d] = len(hit_ids)
                n_ev[d] = sum(1 for hs in ev.values() if set(hs) & hit_ids)
            for unit, cnt in (("distinct_ddx_evidence", n_ev), ("distinct_hpo_terms", n_id)):
                ser = pd.Series(cnt)
                for k in (1, 2, 3, 5):
                    sel = ser[ser >= k]
                    rows.append({"hpo_set": label, "n_ddx_evidence_in_set": len(ev), "n_hpo_terms_in_set": len(target),
                                 "match_mode": mode, "count_unit": unit, "min_overlap": k,
                                 "phenotype_overlap_disease_count": int(len(sel)),
                                 **{f"n_{s}": int(src[sel.index].eq(s).sum()) for s in ("OMIM", "ORPHA", "DECIPHER")},
                                 "metric_name": "phenotype-overlap disease count (candidate-retrievable space; NOT diagnosable count)"})
    df = pd.DataFrame(rows)
    c.write_csv(df, "disease_overlap_summary.csv")
    # DDXPlus 49 질환 이름이 hpoa 질환명에 그대로 있는가(대략적 확인)
    conds = json.load(open(c.DDX_CONDITIONS, encoding="utf-8"))
    names = {n.lower() for n in ann["disease_name"]}
    hits = sorted(v["cond-name-eng"] for v in conds.values() if v["cond-name-eng"].lower() in names)
    dist["ddxplus_49_name_exact_in_hpoa"] = {"n": len(hits), "names": hits,
                                             "note": "exact lower-case name match only; synonyms not resolved"}
    json.dump(dist, open(c.OUT / "disease_annotation_distribution.json", "w"), ensure_ascii=False, indent=1)
    return df, dist


def aux_kb(cur):
    """HSDN · MEDLINE · OptimusKG 보조 대조. DisMech(4.9 GB YAML)는 이번에 재측정하지 않는다."""
    hpo, umls = c.load_hpo(), c.load_umls()
    u = pd.read_csv(c.OUT / "ddxplus_umls_mapping_audit.csv", dtype=str, keep_default_na=False)
    ucur = u[(u.candidate_source == "curated") & (u.cui != "")]
    hsdn_sym = pd.read_csv(c.DATA / "hsdn/processed/hsdn_symptom_terms_mesh.csv", dtype=str, keep_default_na=False)
    hsdn_cuis, hsdn_mesh = set(hsdn_sym["umls_cui"]), set(hsdn_sym["mesh_id"])
    med = pd.read_csv(c.DATA / "medline_disease_symptom/raw/disease-symptom-cooccurrence.tsv", sep="\t", dtype=str)
    med_mesh = set(med["mesh_id"])
    okg = pd.read_parquet(c.DATA / "optimuskg/gold/edges/disease_phenotype.parquet", columns=["from", "to"])
    okg["hp"] = okg["to"].str.replace("HP_", "HP:", regex=False)
    okg_terms = set(okg["hp"])
    rows = []
    for r in cur.itertuples():
        cuis = ucur[ucur.evidence_id == r.evidence_id]["cui"].tolist()
        mesh = {code for cu in cuis for sab, code in umls["codes"].get(cu, []) if sab == "MSH"}
        hids = c.split_ids(r.hpo_ids)
        rows.append({"evidence_id": r.evidence_id, "canonical_concept": r.canonical_concept, "hpo_class": r.hpo_class,
                     "in_hsdn_symptom_vocab": bool(set(cuis) & hsdn_cuis or mesh & hsdn_mesh),
                     "in_medline_symptom_vocab": bool(mesh & med_mesh), "curated_mesh_codes": ";".join(sorted(mesh)),
                     "optimuskg_disease_edges_for_curated_hpo": int(okg["hp"].isin(hids).sum()) if hids else 0,
                     "hpo_terms_used_in_optimuskg": ";".join(h for h in hids if h in okg_terms)})
    df = pd.DataFrame(rows)
    c.write_csv(df, "auxiliary_kb_sampling.csv")
    # OptimusKG 질환 공간(같은 usable HPO 집합, true-path)
    usable = {h for r in cur.itertuples() if r.hpo_class in c.USABLE for h in c.split_ids(r.hpo_ids)}
    anc = {}
    def up(h):
        if h not in anc:
            anc[h] = c.hpo_ancestors(hpo, h) | {h}
        return anc[h]
    g = okg.groupby("from")["hp"].agg(set)
    hit = g.map(lambda ts: len(usable & set().union(*[up(t) for t in ts])))
    nodes = pd.read_parquet(c.DATA / "optimuskg/gold/nodes.parquet")
    nodes = nodes[nodes.label == "DIS"]
    name = {i: (json.loads(p).get("name") or "") for i, p in zip(nodes["id"], nodes["properties"])}
    conds = json.load(open(c.DDX_CONDITIONS, encoding="utf-8"))
    alias = {"GERD": "gastroesophageal reflux disease", "SLE": "systemic lupus erythematosus", "URTI": "upper respiratory tract infection",
             "PSVT": "paroxysmal supraventricular tachycardia", "Whooping cough": "pertussis", "Possible NSTEMI / STEMI": "myocardial infarction",
             "Bronchospasm / acute asthma exacerbation": "asthma", "Acute COPD exacerbation / infection": "chronic obstructive pulmonary disease",
             "Pulmonary neoplasm": "lung cancer", "Pancreatic neoplasm": "pancreatic cancer", "Chagas": "chagas disease",
             "Larygospasm": "laryngospasm", "Boerhaave": "boerhaave syndrome", "HIV (initial infection)": "hiv infection"}
    by_name = defaultdict(list)
    for i, n in name.items():
        if n:
            by_name[n.lower()].append(i)
    ddx_rows = []
    for v in conds.values():
        n = v["cond-name-eng"]
        ids = by_name.get(n.lower(), []) or (by_name.get(alias[n].lower(), []) if n in alias else [])
        hp_n = int(sum(len(g.get(i, set())) for i in ids))
        ddx_rows.append({"ddx_condition": n, "optimuskg_ids": ";".join(ids), "optimuskg_hpo_annotations": hp_n,
                         "overlap_with_usable_ddx_hpo": int(max([hit.get(i, 0) for i in ids] or [0]))})
    ddx = pd.DataFrame(ddx_rows)
    c.write_csv(ddx, "auxiliary_kb_ddx49_in_optimuskg.csv")
    return {
        "hsdn_symptom_vocab_hits": int(df["in_hsdn_symptom_vocab"].sum()),
        "medline_symptom_vocab_hits": int(df["in_medline_symptom_vocab"].sum()),
        "hpo_no_match_or_partial_but_in_hsdn_or_medline": df[df.hpo_class.isin(["NO_MATCH", "PARTIAL"]) &
                                                             (df.in_hsdn_symptom_vocab | df.in_medline_symptom_vocab)]["evidence_id"].tolist(),
        "optimuskg_diseases_with_phenotype_edges": int(g.size),
        "optimuskg_phenotype_overlap_disease_count_true_path": {k: int((hit >= k).sum()) for k in (1, 2, 3, 5)},
        "ddx49_found_in_optimuskg_by_name": int((ddx["optimuskg_ids"] != "").sum()),
        "ddx49_with_any_optimuskg_hpo_annotation": int((ddx["optimuskg_hpo_annotations"] > 0).sum()),
        "dismech": "not re-measured in STEP20 (4.9 GB YAML); README states 17/49 DDXPlus conditions linked",
    }


REP = [  # 대표 증상 → DDXPlus 표현 (실제 evidence 만). 부위 값 기반 항목은 value-level 매핑(Claude 판정)
    ("chest pain", "E_53 + E_55∈{V_101 upper chest, V_29 lower chest, V_55/V_56 side of chest, V_170/V_171 posterior chest wall, V_159/V_160 breast}; E_14 at rest; E_220 pleuritic",
     "HP:0100749 Chest pain", "29857009 Chest pain", "C0008031 Chest Pain"),
    ("dyspnea", "E_66 (+E_64 exertional, E_67 PND, E_217 orthopnea-type)", None, None, None),
    ("fever", "E_91", None, None, None),
    ("cough", "E_201 (+E_77 sputum, E_203 paroxysmal, E_45 hemoptysis, E_166 post-tussive vomiting)", None, None, None),
    ("headache", "E_53 + E_55∈{V_89 forehead, V_62 top of head, V_25 back of head, V_124 occiput, V_166/V_167 temple}",
     "HP:0002315 Headache", "25064002 Headache", "C0018681 Headache"),
    ("abdominal pain", "E_53 + E_55∈{V_197 epigastric, V_103/V_104 hypochondrium, V_87/V_88 iliac fossa, V_84/V_85 flank, V_187 belly, V_153 pubis}",
     "HP:0002027 Abdominal pain", "21522001 Abdominal pain", "C0000737 Abdominal Pain"),
    ("nausea", "E_148", None, None, None),
    ("vomiting", "E_211 (+E_210 hematemesis)", None, None, None),
    ("dizziness", "E_76 (mild dizziness/lightheaded), E_82 (presyncope)", None, None, None),
    ("palpitations", "E_155 (+E_164 irregular)", None, None, None),
    ("fatigue", "E_89 (+E_88 severe, E_175 malaise)", None, None, None),
    ("syncope", "no syncope evidence; E_159 loss of consciousness, E_82 presyncope", None, None, None),
    ("edema", "E_151 swelling + E_152 site", None, None, None),
    ("diarrhea", "E_51", None, None, None),
    ("weakness", "E_84 bilateral limbs (+E_176 limb/face, E_90 fatigable, E_83 face/eye)", None, None, None),
]
REP_KEY = {"dyspnea": "E_66", "fever": "E_91", "cough": "E_201", "nausea": "E_148", "vomiting": "E_211", "dizziness": "E_76",
           "palpitations": "E_155", "fatigue": "E_89", "syncope": "E_159", "edema": "E_151", "diarrhea": "E_51", "weakness": "E_84"}


def representative(cur):
    c_idx = cur.set_index("evidence_id")
    rows = []
    for name, ddx, h, s, u in REP:
        e = REP_KEY.get(name)
        r = c_idx.loc[e] if e else None
        rows.append({
            "representative_symptom": name, "ddxplus_representation": ddx,
            "hpo_mapping": h or f"{r['hpo_ids']} [{r['hpo_class']}]",
            "snomed_mapping": s or f"{r['sct_ids']} [{r['sct_class']}]",
            "umls_mapping": u or f"{r['umls']} [{r['umls_class']}]",
            "mapping_level": "value-level (E_55 site value) - not a standalone DDXPlus evidence" if h else "evidence-level",
            "expansion_level": "HIGH (E_53 pain dims already factorized)" if h else r["expansion_level"],
            "expansion_dimensions": "anatomical_site;quality;severity;onset;radiation;aggravating_factor;relieving_factor;duration" if h else r["expansion_dims"],
            "recommended_canonical_representation": (
                f'{{"concept_id":"pain","canonical_name":"Pain","site":["{name.split()[0]}"],"hpo_id":"{h.split()[0]}","snomed_id":"{s.split()[0]}",'
                '"quality":[],"severity":null,"onset":null,"aggravating_factors":[],"relieving_factors":[]}' if h else
                f'{{"concept_id":"{r["canonical_concept"]}","hpo_id":"{r["hpo_ids"]}","snomed_id":"{r["sct_ids"]}","slots":"{r["expansion_dims"]}"}}'),
        })
    df = pd.DataFrame(rows)
    c.write_csv(df, "representative_symptoms.csv")


def manifest(extra):
    hpo = c.load_hpo()
    sources = {"ddxplus_evidences": c.DDX_EVIDENCES, "ddxplus_conditions": c.DDX_CONDITIONS, "hp_obo": c.HPO_OBO,
               "phenotype_hpoa": c.HPO_HPOA, "umls_mrconso_eng_parquet": c.UMLS_CONSO, "umls_mrsty": c.UMLS_STY,
               "snomed_concept": c.SCT_CONCEPT, "snomed_description": c.SCT_DESC, "snomed_relationship": c.SCT_REL,
               "step8_hpo_candidates": c.STEP8 / "evidence_hpo_candidates.csv",
               "step8_umls_candidates": c.STEP8 / "evidence_umls_candidates.csv",
               "step8_concept_map": c.STEP8 / "evidence_concept_map.csv", "terminology_ko": c.TERMINOLOGY_KO,
               "curation": c.CURATION / "curated_mappings.tsv"}
    out = {"versions": {"hpo": hpo["version"], "hpoa": open(c.HPO_HPOA).readline().strip(), "umls": "2026AA",
                        "snomed": "International RF2 PRODUCTION 2026-09-01 Snapshot", "ddxplus": "release_evidences.json (en)"},
           "inputs": {k: {"path": str(p), "sha256": c.sha256(p)} for k, p in sources.items()},
           "outputs": [c.file_record(p) for p in sorted(c.OUT.glob("*")) if p.name != "manifest.json"],
           "determinism": "no randomness; sorted iteration; re-running scripts reproduces identical CSVs (checked by rerun SHA)",
           "judgement_provenance": "curated = Claude (LLM) review of labels/definitions/parents, NOT clinician-validated; "
                                   "auto_rule = deterministic comparison of legacy candidates to curated; manual_override listed in scripts",
           **extra}
    json.dump(out, open(c.OUT / "manifest.json", "w"), ensure_ascii=False, indent=1)


def run():
    cur = c.load_curation()
    cov, _ = coverage(cur)
    cov["baselines_existing_candidates"] = baselines()
    cov["expansion_levels"] = expansion(cur)
    cov["normalization_layers"] = layers(cur)
    ov, dist = disease_overlap(cur)
    cov["hpoa_disease_space"] = {k: dist[k] for k in ("diseases_all_aspects_by_source", "phenotypic_abnormality_aspect_P_excluding_NOT")}
    pick = ov[(ov.hpo_set == "usable") & (ov.match_mode == "true_path") & (ov.count_unit == "distinct_ddx_evidence")]
    cov["phenotype_overlap_disease_count_usable_true_path"] = dict(zip(pick.min_overlap.astype(str), pick.phenotype_overlap_disease_count))
    cov["auxiliary_kb"] = aux_kb(cur)
    representative(cur)
    cov["versions"] = {"hpo": c.load_hpo()["version"], "umls": "2026AA", "snomed": "INT 2026-09-01"}
    json.dump(cov, open(c.OUT / "mapping_coverage_summary.json", "w"), ensure_ascii=False, indent=1)
    manifest({})
    a = cov["all_110"]
    print({k: (v["exact_n"], v["usable_n"], v["partial_included_n"]) for k, v in a.items()})
    print("expansion", cov["expansion_levels"], "overlap", cov["phenotype_overlap_disease_count_usable_true_path"])
    print("aux", cov["auxiliary_kb"])
