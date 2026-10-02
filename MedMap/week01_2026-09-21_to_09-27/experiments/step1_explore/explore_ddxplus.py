"""Step 1: DDXPlus 구조 탐색 (read-only). 출력: 콘솔 + exp/step1_explore/summary.json"""
import json, ast, collections, sys
import pandas as pd
D = "data/ddxplus/en"
ev = json.load(open(f"{D}/release_evidences.json")); cond = json.load(open(f"{D}/release_conditions.json"))
out = {}
# evidence 타입
dt = collections.Counter(v["data_type"] for v in ev.values())
out["evidence_data_type"] = dict(dt)
out["evidence_antecedent"] = int(sum(v["is_antecedent"] for v in ev.values()))
ex = next(v for v in ev.values() if v["data_type"] == "C"); out["example_C"] = {k: ex[k] for k in ["name","question_en","possible-values","default_value"]}
ex = next(v for v in ev.values() if v["data_type"] == "M"); out["example_M"] = {k: ex[k] for k in ["name","question_en","possible-values"]}
# condition
out["n_conditions"] = len(cond)
out["cond_symptom_count"] = pd.Series({k: len(v["symptoms"]) for k, v in cond.items()}).describe().round(1).to_dict()
out["cond_antecedent_count"] = pd.Series({k: len(v["antecedents"]) for k, v in cond.items()}).describe().round(1).to_dict()
out["cond_icd10"] = {k: v["icd10-id"] for k, v in cond.items()}
# 환자 (validate 셋으로 통계, train은 행수만)
for split in ["validate", "test"]:
    df = pd.read_csv(f"{D}/release_{split}_patients")
    s = {"n": len(df)}
    s["age"] = df["AGE"].describe().round(1).to_dict(); s["sex"] = df["SEX"].value_counts().to_dict()
    s["pathology_top10"] = df["PATHOLOGY"].value_counts().head(10).to_dict()
    s["pathology_min"] = df["PATHOLOGY"].value_counts().tail(3).to_dict()
    evl = df["EVIDENCES"].map(ast.literal_eval)
    n_ev = evl.map(len); s["evidences_per_patient"] = n_ev.describe().round(1).to_dict()
    # 값 있는 evidence(E_xx_@_val) 비율
    s["frac_valued_tokens"] = round(float(evl.map(lambda l: sum("_@_" in t for t in l)).sum() / n_ev.sum()), 3)
    ddx = df["DIFFERENTIAL_DIAGNOSIS"].map(ast.literal_eval)
    s["ddx_len"] = ddx.map(len).describe().round(1).to_dict()
    rank = [next((i for i, (n, p) in enumerate(d) if n == g), -1) for d, g in zip(ddx, df["PATHOLOGY"])]
    rc = collections.Counter(rank); s["truth_rank_in_ddx"] = {str(k): rc[k] for k in sorted(rc)[:6]}
    s["truth_rank_in_ddx_frac_top1"] = round(rc[0] / len(df), 3)
    s["truth_missing_in_ddx"] = rc[-1]
    s["initial_evidence_top5"] = df["INITIAL_EVIDENCE"].value_counts().head(5).to_dict()
    out[split] = s
n_train = sum(1 for _ in open(f"{D}/release_train_patients")) - 1; out["train_n"] = n_train
json.dump(out, open("exp/step1_explore/summary.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
