"""Step 8b: DDXPlus 223 소견 → UMLS CUI 자동 후보 (MRCONSO ENG, SAB∈{SNOMEDCT_US,HPO,MSH,ICD10CM}).
정규화 질문의 내용어로 역색인 후보(내용어 ≥ half 포함) → char TF-IDF 코사인+자카드 → CUI별 최고점 top3.
CUI에 연결된 SNOMED/HPO/ICD10 코드 동반 출력. 등급: exact_candidate ≥0.80 / partial ≥0.45 / fail.
출력: exp/step8_mapping/evidence_umls_candidates.csv, mapping_summary_umls.json
"""
import json, re, collections, time
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from map_evidence_hpo import norm  # 동일 정규화
t0 = time.time()
ev = json.load(open("data/ddxplus/en/release_evidences.json"))
m = pd.read_parquet("data/umls/mrconso_eng.parquet")
m = m[m["SAB"].isin(["SNOMEDCT_US", "HPO", "MSH", "ICD10CM"]) & (m["SUPPRESS"] == "N")]
m["s"] = m["STR"].str.lower().str.replace(r"\s*\(.*?\)\s*$", "", regex=True).str.strip()
m = m.drop_duplicates(["CUI", "s"]).reset_index(drop=True); print("strings", len(m), "CUI", m["CUI"].nunique(), round(time.time() - t0))
STOP = set("is are be been have has had do does did you your my me it its this that of in on at to for with and or a an the any some no not from by as if than then there their they what how when where who which".split())
def words(s): return [w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP and len(w) > 2]
inv = collections.defaultdict(list)
for i, s in enumerate(m["s"].values):
    for w in set(words(s)): inv[w].append(i)
print("index built", len(inv), round(time.time() - t0))
codes = m.groupby("CUI").apply(lambda g: {sab: sorted(set(g.loc[g["SAB"] == sab, "CODE"]))[:3] for sab in g["SAB"].unique()}).to_dict()
pref = m[m["ISPREF"] == "Y"].drop_duplicates("CUI").set_index("CUI")["STR"].to_dict()
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit(m["s"].sample(300000, random_state=0).tolist() + [norm(v["question_en"]) for v in ev.values()])
def jacc(a, b): A, B = set(words(a)), set(words(b)); return len(A & B) / max(1, len(A | B))
rows = []
for e, v in ev.items():
    q = norm(v["question_en"]); ws = words(q)
    cnt = collections.Counter()
    for w in ws:
        for i in inv.get(w, []): cnt[i] += 1
    need = max(1, (len(ws) + 1) // 2)
    cand = [i for i, c in cnt.most_common(5000) if c >= need]
    best = {}
    if cand:
        S = (vec.transform([q]) @ vec.transform(m["s"].values[cand]).T).toarray().ravel()
        for j, i in enumerate(cand):
            cui = m["CUI"].values[i]; sc = 0.7 * S[j] + 0.3 * jacc(q, m["s"].values[i])
            if cui not in best or sc > best[cui][0]: best[cui] = (sc, m["s"].values[i])
    top = sorted(best.items(), key=lambda x: -x[1][0])[:3]
    s1 = top[0][1][0] if top else 0
    r = {"evidence": e, "is_antecedent": v["is_antecedent"], "data_type": v["data_type"], "question_en": v["question_en"], "normalized": q,
         "auto_grade": "exact_candidate" if s1 >= 0.80 else "partial_candidate" if s1 >= 0.45 else "fail"}
    for n, (cui, (sc, s)) in enumerate(top, 1):
        c = codes.get(cui, {})
        r.update({f"cui{n}": cui, f"cui{n}_pref": pref.get(cui, ""), f"cui{n}_matched": s, f"cui{n}_score": round(sc, 3),
                  f"cui{n}_snomed": ";".join(c.get("SNOMEDCT_US", [])), f"cui{n}_hpo": ";".join(c.get("HPO", [])), f"cui{n}_icd10": ";".join(c.get("ICD10CM", []))})
    r.update({"review_status": "", "final_cui": "", "note": ""}); rows.append(r)
df = pd.DataFrame(rows); df.to_csv("exp/step8_mapping/evidence_umls_candidates.csv", index=False)
summ = {"n": len(df), "auto_grade": dict(collections.Counter(df["auto_grade"])), "has_hpo_code_top1": int((df["cui1_hpo"].fillna("") != "").sum()), "has_snomed_top1": int((df["cui1_snomed"].fillna("") != "").sum())}
json.dump(summ, open("exp/step8_mapping/mapping_summary_umls.json", "w"), indent=1); print(json.dumps(summ, indent=1), round(time.time() - t0))
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 55)
print(df[["evidence", "question_en", "cui1_pref", "cui1_score", "cui1_snomed", "cui1_hpo", "auto_grade"]].sort_values("cui1_score", ascending=False).to_string())
