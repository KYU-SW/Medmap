"""Step 8: DDXPlus 223 소견 → HPO 자동 후보 매핑 (문자열 기반, 검수용).
question_en 정규화(질문 접두어 제거) → HPO name+synonym 대상 TF-IDF(char 3-5gram) 코사인 + 토큰 자카드 → top3 후보.
자동 등급: exact(≥0.80) / partial(0.45~0.80) / fail(<0.45). M/C형 값은 별도 표기. 최종 등급은 사람이 검수(review_status 컬럼).
출력: exp/step8_mapping/evidence_hpo_candidates.csv, mapping_summary.json
"""
import json, re, collections
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
ev = json.load(open("data/ddxplus/en/release_evidences.json"))
# HPO 파싱 (phenotypic abnormality 하위만: HP:0000118 후손) — 간단히 전체 term 사용, obsolete 제외
terms, cur = [], None
for line in open("data/hpo/hp.obo", encoding="utf-8"):
    line = line.rstrip("\n")
    if line == "[Term]": cur = {"syn": []}; terms.append(cur)
    elif cur is None: continue
    elif line.startswith("id: "): cur["id"] = line[4:]
    elif line.startswith("name: "): cur["name"] = line[6:]
    elif line.startswith("synonym: "): cur["syn"].append(re.match(r'synonym: "(.*?)"', line).group(1))
    elif line.startswith("is_obsolete: true"): cur["obs"] = True
terms = [t for t in terms if "id" in t and not t.get("obs")]
hpo_strings, hpo_ids, hpo_names = [], [], []
for t in terms:
    for s in [t["name"]] + t["syn"]:
        hpo_strings.append(s.lower()); hpo_ids.append(t["id"]); hpo_names.append(t["name"])
PREF = [r"^do you (have|feel|suffer from|experience|notice|currently take|regularly take|drink|smoke|live|work|travel)\b", r"^are you (experiencing|currently|suffering)\b", r"^have you (had|been|ever|recently|noticed|lost|gained)\b",
        r"^did you\b", r"^is your\b", r"^are you\b", r"^do you\b", r"^have you\b", r"^has\b", r"^is\b", r"^does\b", r"^were you\b", r"^what\b", r"^how\b", r"^where\b", r"^characterize\b"]
def norm(q):
    q = q.lower().strip().rstrip("?")
    for p in PREF: q = re.sub(p, "", q).strip()
    q = re.sub(r"\b(a|an|the|any|some|of|in|on|your|you|that|which|this|to|or|and|with|either|significant way|significantly|related to your reason for consulting|,|\(.*?\))\b", " ", q)
    return re.sub(r"\s+", " ", q).strip()
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1).fit(hpo_strings + [norm(v["question_en"]) for v in ev.values()])
H = vec.transform(hpo_strings)
def jacc(a, b):
    A, B = set(a.split()), set(b.split()); return len(A & B) / max(1, len(A | B))
rows = []
for e, v in ev.items():
    q = norm(v["question_en"]); sims = (vec.transform([q]) @ H.T).toarray().ravel()
    best = {}
    for i in np.argsort(-sims)[:60]:
        hid = hpo_ids[i]; sc = 0.7 * sims[i] + 0.3 * jacc(q, hpo_strings[i])
        if hid not in best or sc > best[hid][0]: best[hid] = (sc, hpo_names[i], hpo_strings[i])
    top = sorted(best.items(), key=lambda x: -x[1][0])[:3]
    s1 = top[0][1][0] if top else 0
    grade = "exact_candidate" if s1 >= 0.80 else "partial_candidate" if s1 >= 0.45 else "fail"
    kind = {"B": "binary", "C": f"numeric_scale({len(v['possible-values'])})", "M": f"multichoice({len(v['possible-values'])})"}[v["data_type"]]
    rows.append({"evidence": e, "is_antecedent": v["is_antecedent"], "data_type": kind, "code_question": v["code_question"], "question_en": v["question_en"], "normalized": q,
                 "hpo1_id": top[0][0], "hpo1_name": top[0][1][1], "hpo1_matched_str": top[0][1][2], "hpo1_score": round(s1, 3),
                 "hpo2_id": top[1][0] if len(top) > 1 else "", "hpo2_name": top[1][1][1] if len(top) > 1 else "", "hpo2_score": round(top[1][1][0], 3) if len(top) > 1 else "",
                 "hpo3_id": top[2][0] if len(top) > 2 else "", "hpo3_name": top[2][1][1] if len(top) > 2 else "",
                 "auto_grade": grade, "review_status": "", "final_hpo_id": "", "note": "값(부위/정도)은 HPO 대상 아님 → SNOMED/UBERON" if v["data_type"] != "B" else ""})
df = pd.DataFrame(rows); df.to_csv("exp/step8_mapping/evidence_hpo_candidates.csv", index=False)
# M형 값 라벨(부위 등) 별도 표
vals = [{"evidence": e, "value": k, "en": m["en"]} for e, v in ev.items() for k, m in v.get("value_meaning", {}).items()]
pd.DataFrame(vals).to_csv("exp/step8_mapping/multichoice_values.csv", index=False)
summ = {"n_evidence": len(df), "auto_grade": dict(collections.Counter(df["auto_grade"])), "by_type": {f"{a}|{b}": int(c) for (a, b), c in df.groupby("data_type")["auto_grade"].value_counts().items()},
        "antecedent_grade": {f"{a}|{b}": int(c) for (a, b), c in df.groupby("is_antecedent")["auto_grade"].value_counts().items()}, "n_multichoice_values": len(vals), "hpo_terms": len(terms)}
json.dump(summ, open("exp/step8_mapping/mapping_summary.json", "w"), indent=1, default=str); print(json.dumps(summ, indent=1, default=str))
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(df[["evidence", "question_en", "hpo1_name", "hpo1_score", "auto_grade"]].sort_values("hpo1_score", ascending=False).to_string())
