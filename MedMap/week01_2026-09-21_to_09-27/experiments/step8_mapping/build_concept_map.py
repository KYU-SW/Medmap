"""Step 8c: evidence_semantics.tsv(의미 구조) × MRCONSO exact/normalized 검색 → evidence_concept_map.csv
매칭 순서: (1) exact normalized string == MRCONSO string  (2) 변형(복수/of/hyphen)  (3) char-TFIDF ≥0.90 → NORMALIZED
CUI 선택: SNOMEDCT_US 또는 HPO 원천이 있는 CUI 우선, 그다음 SAB 수 많은 CUI. 코드: 해당 CUI의 SNOMEDCT_US CODE, HPO CODE.
status: NOT_REQUIRED / EXACT(단일 concept, exact, context가 self·none) / COMPOSITE(2 concept 모두 발견) / PARTIAL(일부 발견·normalized·qualifier 손실·value-level) / FAIL
"""
import re, json, collections, time
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
t0 = time.time()
sem = pd.read_csv("exp/step8_mapping/evidence_semantics.tsv", sep="\t", dtype=str).fillna("")
ev = json.load(open("data/ddxplus/en/release_evidences.json"))
m = pd.read_parquet("data/umls/mrconso_eng.parquet")
m = m[m["SAB"].isin(["SNOMEDCT_US", "HPO", "MSH", "ICD10CM", "NCI", "RXNORM", "MTH", "MEDCIN"]) & (m["SUPPRESS"] == "N")].reset_index(drop=True)
def normstr(s):
    s = s.lower().strip(); s = re.sub(r"\s*\((finding|disorder|procedure|substance|product|body structure|qualifier value|observable entity|situation|event|environment|occupation|person|social concept|morphologic abnormality|physical object|attribute|navigational concept|record artifact|physical force|regime/therapy|organism|specimen|staging scale|assessment scale|tumor staging|cell|cell structure|geographic location|environment / location|medicinal product|clinical drug|medicinal product form|disposition|role|ethnic group|racial group|religion/philosophy|life style|context-dependent category|special concept|link assertion|core metadata concept|foundation metadata concept|metadata|namespace concept|OWL metadata concept|inactive concept|linkage concept|administrative concept|physical force|SNOMED RT\+CTV3)\)\s*$", "", s)
    s = s.replace("’", "'").replace("'s", "s").replace("'", ""); s = re.sub(r"[^a-z0-9 ]+", " ", s); return re.sub(r"\s+", " ", s).strip()
m["n"] = m["STR"].map(normstr)
by_str = collections.defaultdict(set)
for n, c in zip(m["n"].values, m["CUI"].values): by_str[n].add(c)
cui_sabs = m.groupby("CUI")["SAB"].agg(lambda s: set(s)).to_dict()
snomed = m[m["SAB"] == "SNOMEDCT_US"].groupby("CUI")["CODE"].agg(lambda s: ";".join(sorted(set(s))[:3])).to_dict()
hpo = m[m["SAB"] == "HPO"].groupby("CUI")["CODE"].agg(lambda s: ";".join(sorted(set(s))[:3])).to_dict()
pref = m[m["ISPREF"] == "Y"].drop_duplicates("CUI").set_index("CUI")["STR"].to_dict()
print("index", len(by_str), round(time.time() - t0), flush=True)
uniq = pd.Series(list(by_str.keys())); vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit(uniq.sample(400000, random_state=0))
inv = collections.defaultdict(list)
for i, s in enumerate(uniq.values):
    for w in set(s.split()):
        if len(w) > 2: inv[w].append(i)
def pick(cuis):
    return sorted(cuis, key=lambda c: (-(("SNOMEDCT_US" in cui_sabs.get(c, set())) or ("HPO" in cui_sabs.get(c, set()))), -len(cui_sabs.get(c, set())), c))
def variants(q):
    out = {q}
    out.add(re.sub(r"s$", "", q)); out.add(q + "s"); out.add(q.replace("disorder of ", "")); out.add(q.replace(" of the ", " of ")); out.add(q.replace("s ", " "))
    return [v for v in out if v]
def lookup(concept):
    if not concept: return None
    q = normstr(concept)
    for v in variants(q):
        if v in by_str: return {"cuis": pick(by_str[v]), "how": "EXACT", "matched": v, "score": 1.0}
    cnt = collections.Counter()
    for w in q.split():
        for i in inv.get(w, []): cnt[i] += 1
    cand = [i for i, _ in cnt.most_common(3000)]
    if not cand: return None
    S = (vec.transform([q]) @ vec.transform(uniq.values[cand]).T).toarray().ravel(); j = int(S.argmax())
    if S[j] >= 0.90: return {"cuis": pick(by_str[uniq.values[cand[j]]]), "how": "NORMALIZED", "matched": uniq.values[cand[j]], "score": round(float(S[j]), 3)}
    return {"cuis": [], "how": "NONE", "matched": uniq.values[cand[j]], "score": round(float(S[j]), 3)}
NEUTRAL_CTX = {"", "self", "static"}
rows = []
for _, r in sem.iterrows():
    e = r["evidence_id"]; q = ev[e]["question_en"]
    L1, L2 = lookup(r["concept_1"]), lookup(r["concept_2"])
    def cols(L, k):
        if L is None or not L["cuis"]: return {f"concept_{k}_cui": "", f"concept_{k}_snomed": "", f"concept_{k}_hpo": "", f"concept_{k}_umls_pref": "", f"concept_{k}_match": (L["how"] if L else ""), f"concept_{k}_alt_cuis": ""}
        c = L["cuis"][0]
        return {f"concept_{k}_cui": c, f"concept_{k}_snomed": snomed.get(c, ""), f"concept_{k}_hpo": hpo.get(c, ""), f"concept_{k}_umls_pref": pref.get(c, ""), f"concept_{k}_match": L["how"], f"concept_{k}_alt_cuis": ";".join(L["cuis"][1:4])}
    c1, c2 = cols(L1, 1), cols(L2, 2)
    f1, f2 = bool(c1["concept_1_cui"]), bool(c2["concept_2_cui"]); has2 = bool(r["concept_2"])
    qual_lost = r["context"] not in NEUTRAL_CTX or r["temporality"] not in {"current", "static", "ever", ""}
    reasons = []
    if r["mapping_required"] == "VALUE_LEVEL":
        status = "PARTIAL" if f1 else "FAIL"; reasons.append("value-level question: values(body site/scale/color) need separate value table")
    elif not f1 and not (has2 and f2):
        status = "FAIL"; reasons.append("no MRCONSO string match for concept(s)")
    elif has2:
        if f1 and f2: status = "COMPOSITE"; reasons.append(f"two atomic concepts joined by {r['operator']}")
        else: status = "PARTIAL"; reasons.append("only one of two concepts matched")
    else:
        status = "EXACT" if (c1["concept_1_match"] == "EXACT" and not qual_lost) else "PARTIAL"
        if c1["concept_1_match"] != "EXACT": reasons.append("normalized (fuzzy) match, verify concept")
    if qual_lost and status != "FAIL": reasons.append(f"qualifier not encoded in CUI: temporality={r['temporality']}, context={r['context']}")
    if status == "EXACT" and c1["concept_1_alt_cuis"]: reasons.append("multiple CUIs share the string; top chosen by SNOMED/HPO presence")
    review = status != "EXACT" or bool(c1["concept_1_alt_cuis"])
    rows.append({"evidence_id": e, "original_question": q, "evidence_type": r["evidence_type"], "concept_1": r["concept_1"], **{k: c1[k] for k in ["concept_1_cui", "concept_1_snomed", "concept_1_hpo"]},
                 "concept_2": r["concept_2"], **{k: c2[k] for k in ["concept_2_cui", "concept_2_snomed", "concept_2_hpo"]}, "operator": r["operator"], "temporality": r["temporality"], "context": r["context"],
                 "mapping_status": status, "mapping_reason": " | ".join(reasons), "review_needed": review,
                 "concept_1_umls_pref": c1["concept_1_umls_pref"], "concept_1_match": c1["concept_1_match"], "concept_1_alt_cuis": c1["concept_1_alt_cuis"],
                 "concept_2_umls_pref": c2["concept_2_umls_pref"], "concept_2_match": c2["concept_2_match"], "concept_2_alt_cuis": c2["concept_2_alt_cuis"],
                 "matched_string_1": (L1 or {}).get("matched", ""), "matched_score_1": (L1 or {}).get("score", ""), "matched_string_2": (L2 or {}).get("matched", ""), "matched_score_2": (L2 or {}).get("score", "")})
df = pd.DataFrame(rows); df.to_csv("exp/step8_mapping/evidence_concept_map.csv", index=False)
summ = {"n": len(df), "mapping_status": dict(collections.Counter(df["mapping_status"])), "review_needed": int(df["review_needed"].sum()),
        "concept_1_match": dict(collections.Counter(df["concept_1_match"])), "concept_1_has_snomed": int((df["concept_1_snomed"] != "").sum()), "concept_1_has_hpo": int((df["concept_1_hpo"] != "").sum()),
        "by_type": {f"{a}|{b}": int(c) for (a, b), c in df.groupby("evidence_type")["mapping_status"].value_counts().items()}}
json.dump(summ, open("exp/step8_mapping/concept_map_summary.json", "w"), indent=1); print(json.dumps(summ, indent=1)); print("DONE", round(time.time() - t0))
