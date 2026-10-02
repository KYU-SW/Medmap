"""STEP 13 (0~7단계): 공통 입력 코호트 + A′ 내부 verifier 점수 + 외부지식 입력 고정. 평가(9단계 이후)는 B 점수식 사전등록 확인 후에만."""
import json, pickle, time, collections
import numpy as np, pandas as pd, scipy.sparse as sp
D = "data/ddxplus/en"; W = "exp/step2_3_workingdx"; S = "exp/step5_7_discrepancy"; S9 = "exp/step9_external_knowledge"; S11 = "exp/step11_external_expansion"; O = "exp/step13_aprime"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
vj = json.load(open(f"{W}/vocab.json")); vocab, classes = vj["vocab"], vj["classes"]; cidx = {c: i for i, c in enumerate(classes)}; V = len(vocab)
clf = pickle.load(open(f"{W}/model.pkl", "rb")); logP = np.load(f"{S}/cond_token_logp.npz", allow_pickle=True)["logP"]  # TRAIN 전용 통계 (discrepancy_internal.py에서 train만 사용)
el = pd.read_csv(f"{S9}/03_evidence_eligibility.csv", dtype=str).fillna(""); COMMON = sorted(el[el.finding_eligible == "True"].evidence_id); log("COMMON_FINDINGS", len(COMMON))
common_tok = {t: j for t, j in vocab.items() if t.startswith("E_") and t.split("_@_")[0] in set(COMMON)}; log("common tokens", len(common_tok), "of evidence tokens", sum(t.startswith("E_") for t in vocab))
cov = pd.read_csv(f"{S11}/08_coverage_by_source_final.csv").set_index("ddxplus_disease")
ext_strict = set(cov[cov["matched_strict|F:+UMLS_MRREL"] > 0].index); ext_len = set(cov[cov["matched|F:+UMLS_MRREL"] > 0].index)
KS = [3, 5, 10, "all"]; SEEDS = [42, 43, 44]
def partial_view(ev, init, k, rng):
    rest = [e for e in ev if e != init]
    if k == "all" or k >= len(rest): return ev
    idx = rng.choice(len(rest), size=k, replace=False); return [init] + [rest[i] for i in sorted(idx)]
def featurize(views, ages, sexes):
    rows, cols = [], []
    for i, v in enumerate(views):
        for t in set(v) | {f"AGE_{min(int(ages[i])//10, 9)}", f"SEX_{sexes[i]}"}:
            j = vocab.get(t)
            if j is not None: rows.append(i); cols.append(j)
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(views), V))
def aprime(views, d):
    rows, cols = [], []
    for i, v in enumerate(views):
        for t in v:
            j = common_tok.get(t)
            if j is not None: rows.append(i); cols.append(j)
    X = sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(views), V)); LL = X @ logP.T
    own = LL[np.arange(len(d)), d]; LLm = LL.copy(); LLm[np.arange(len(d)), d] = -np.inf; return LLm.max(1) - own, np.asarray(X.sum(1)).ravel()
coh, sc = [], []
for split in ["validate", "test"]:
    df = pd.read_csv(f"{D}/release_{split}_patients"); df["ev"] = df["EVIDENCES"].map(lambda s: json.loads(s.replace("'", '"'))); truth = df["PATHOLOGY"].map(cidx).values
    for k in KS:
        for seed in (SEEDS if k != "all" else [42]):
            rng = np.random.default_rng(seed); views = [partial_view(ev, init, k, rng) for ev, init in zip(df["ev"], df["INITIAL_EVIDENCE"])]
            P = clf.predict_proba(featurize(views, df["AGE"].values, df["SEX"].values)); srt = np.sort(P, 1); wd = P.argmax(1)
            if split == "validate":  # 기존 저장본과 동일성 검증
                old = pd.read_parquet(f"{W}/val_working_dx.parquet"); o = old[(old.k == str(k)) & (old.seed == seed)].sort_values("idx"); assert (o["working_dx"].map(cidx).values == wd).mean() > 0.999
            a, ncommon = aprime(views, wd)
            # 배제 테스트: COMMON 외 토큰을 뷰에 추가해도 A′ 불변
            if split == "validate" and k == 3 and seed == 42:
                extra = [v + ["E_79", "E_104", "E_44"] for v in views[:2000]]; a2, _ = aprime(extra, wd[:2000]); assert np.allclose(a[:2000], a2), "non-COMMON token leaked into A′"; log("leak test passed")
            cfg = f"k{k}_s{seed}"
            coh.append(pd.DataFrame({"sample_id": np.arange(len(df)), "split": split, "config": cfg, "k": str(k), "seed": seed, "pathology": df["PATHOLOGY"].values, "working_diagnosis": [classes[i] for i in wd], "wrong_label": (wd != truth).astype(int), "model_confidence": srt[:, -1], "margin": srt[:, -1] - srt[:, -2], "entropy": -(P * np.log(P + 1e-12)).sum(1),
                                     "exposed_evidence": [json.dumps(v) for v in views], "exposed_common_findings": [json.dumps([t for t in v if t.split("_@_")[0] in set(COMMON)]) for v in views], "n_exposed_total": [len(v) for v in views], "n_positive_common_findings": ncommon.astype(int), "n_negative_findings": 0,
                                     "external_coverage_wd_strict": [classes[i] in ext_strict for i in wd], "external_coverage_wd_lenient": [classes[i] in ext_len for i in wd], "external_coverage_truth_strict": [t in ext_strict for t in df["PATHOLOGY"].values]}))
            sc.append(pd.DataFrame({"sample_id": np.arange(len(df)), "split": split, "config": cfg, "pathology": df["PATHOLOGY"].values, "working_diagnosis": [classes[i] for i in wd], "confidence": srt[:, -1], "A_prime_score": a, "wrong_label": (wd != truth).astype(int), "n_common_findings_used": ncommon.astype(int)}))
            log(split, cfg, "n", len(df), "wrong", int((wd != truth).sum()), "mean common findings", round(float(ncommon.mean()), 2))
C = pd.concat(coh); C.to_csv(f"{O}/01_common_input_cohort.csv", index=False); A = pd.concat(sc); A.to_csv(f"{O}/02_aprime_internal_scores.csv", index=False)
# 외부지식 입력 고정 (STEP11 FINAL 08b): (disease, evidence) × source × strict
det = pd.read_csv(f"{S11}/08b_coverage_detail_final.csv", dtype=str).fillna("")
ext = det[det.raw_source_support_count.astype(int) > 0][["ddxplus_disease", "evidence_id", "finding", "sources_lenient", "sources_strict", "families_lenient", "families_strict", "generic_or_self"]]
ext.to_csv(f"{O}/02b_external_input_fixed.csv", index=False)
summ = {"COMMON_FINDINGS_n": len(COMMON), "COMMON_FINDINGS": COMMON, "common_tokens": len(common_tok), "cohort_rows": len(C), "configs": sorted(C.config.unique()), "splits": {s: int((C.split == s).sum()) for s in ["validate", "test"]}, "nan_inf": int(np.isinf(A.A_prime_score).sum() + A.A_prime_score.isna().sum()),
        "external_input_pairs_lenient": len(ext), "external_input_pairs_strict": int((ext.sources_strict != "").sum()), "diseases_with_external_strict": len(ext_strict), "diseases_with_external_lenient": len(ext_len), "mean_common_findings_exposed": C.groupby("config").n_positive_common_findings.mean().round(2).to_dict(), "leak_test": "passed"}
json.dump(summ, open(f"{O}/10_summary.json", "w"), indent=1, default=str); print(json.dumps({k: v for k, v in summ.items() if k != "COMMON_FINDINGS"}, indent=1)); log("DONE")
