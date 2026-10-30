"""STEP24 Linear · KoELECTRA · Hybrid 비교(같은 데이터·같은 dev·같은 FIXED_REGRESSION_TEST core 109).

정책(실행 전 고정, 모든 임계값·α 는 dev 에서만):
- LINEAR_CHAR      : STEP23 EXPANDED 모델 그대로(재학습 없음). auto = margin ≥ STEP23 dev 임계값
- KOELECTRA_SMALL  : auto = max softmax ≥ koelectra_selection dev 임계값
- HYBRID_A Agreement: auto 후보 = Linear top1 == KoELECTRA top1, 다르면 ASK_CONFIRMATION.
                      순위 = Linear·KoELECTRA 순위 교차(L1,K1,L2,K2,… 중복 제거) → Top-1 = Linear top1
- HYBRID_B Linear fast path: Linear margin ≥ T_lin(STEP23 dev 임계값) → Linear 결과·auto,
                      아니면 KoELECTRA 실행 → KoELECTRA 결과, auto 는 KoELECTRA confidence ≥ dev 임계값
- HYBRID_C Score fusion: 표본별 z-score(77 class) 후 α·z_T + (1−α)·z_L, α ∈ {0.5, 0.25, 0.75}(dev Top-1 > R@3 > 이 순서),
                      auto = fused margin(top1−top2) ≥ dev 임계값(P≥0.95 최소값, 수락 ≥5)
- PRIMARY_HYBRID = HYBRID_B, HYBRID_C 중 dev core Top-1 > R@3 높은 쪽(동률 → HYBRID_B, 더 빠름)
- LOW_SIMILARITY = STEP23 정의(같은 concept 생성 학습 표현과 최대 difflib ratio < 0.5)
출력: predictions_linear.csv · predictions_hybrid.csv · similarity_bucket_metrics.csv · hybrid_metrics.json · models/hybrid_config.json
"""
import numpy as np

import s24_common as S

ALPHAS = [0.5, 0.25, 0.75]


def z(a):
    return (a - a.mean(1, keepdims=True)) / (a.std(1, keepdims=True) + 1e-9)


def rank_of(row, classes):
    return [classes[i] for i in sorted(range(len(classes)), key=lambda i: (-row[i], classes[i]))]


def min_threshold(vals, ok):
    for t in sorted(set(vals)):
        acc = [o for v, o in zip(vals, ok) if v >= t]
        if len(acc) < 5:
            return None
        if sum(acc) / len(acc) >= 0.95:
            return float(t)
    return None


def main():
    gold, core_dev, core_test = S.eval_sets()
    ids = [g["utterance_id"] for g in gold]
    lin, sel23 = S.linear_model()
    T_lin = sel23["conditions"]["EXPANDED"]["families"]["LINEAR_CHAR"]["auto_accept_dev"]["margin_threshold"]
    cls = list(lin.classes_)
    L = np.atleast_2d(lin.decision_function([S.norm(g["text_ko"]) for g in gold]))
    tz = np.load(S.OUT / "transformer_logits.npz")
    assert list(tz["ids"]) == ids and list(tz["classes"]) == cls
    T = tz["logits"]
    P = np.exp(T - T.max(1, keepdims=True))
    P /= P.sum(1, keepdims=True)
    ksel = S.load_json(S.OUT / "koelectra_selection.json")
    T_koe = (ksel["auto_accept_dev"] or {}).get("conf_threshold", 2.0)
    ix = {u: i for i, u in enumerate(ids)}

    R = {"LINEAR_CHAR": {}, "KOELECTRA_SMALL": {}, "HYBRID_A": {}, "HYBRID_B": {}}
    AUTO = {k: {} for k in R}
    tcall = {}
    lin_m = {}
    for u, i in ix.items():
        lr, kr = rank_of(L[i], cls), rank_of(P[i], cls)
        lm_ = float(np.sort(L[i])[-1] - np.sort(L[i])[-2])
        lin_m[u] = lm_
        R["LINEAR_CHAR"][u], R["KOELECTRA_SMALL"][u] = lr, kr
        AUTO["LINEAR_CHAR"][u] = lm_ >= T_lin
        AUTO["KOELECTRA_SMALL"][u] = float(P[i].max()) >= T_koe
        inter = []
        for a, b in zip(lr, kr):
            for c in (a, b):
                if c not in inter:
                    inter.append(c)
        R["HYBRID_A"][u], AUTO["HYBRID_A"][u] = inter, lr[0] == kr[0]
        fast = lm_ >= T_lin
        tcall[u] = not fast
        R["HYBRID_B"][u] = lr if fast else kr
        AUTO["HYBRID_B"][u] = True if fast else float(P[i].max()) >= T_koe

    # HYBRID_C: dev 로 α 선택 후 dev 로 auto 임계값
    ZL, ZT = z(L), z(T)
    best = None
    alpha_rows = []
    for a in ALPHAS:
        F = a * ZT + (1 - a) * ZL
        rk = {u: rank_of(F[ix[u]], cls) for u in ix}
        s = S.score(core_dev, rk)
        alpha_rows.append({"alpha": a, "dev_top1": s["top1"], "dev_recall_at_3": s["recall_at_3"]})
        key = (s["top1"], s["recall_at_3"], -ALPHAS.index(a))
        if best is None or key > best[0]:
            best = (key, a, F, rk)
    _, alpha, F, rkC = best
    fm = {u: float(np.sort(F[ix[u]])[-1] - np.sort(F[ix[u]])[-2]) for u in ix}
    T_fus = min_threshold([fm[g["utterance_id"]] for g in core_dev], [rkC[g["utterance_id"]][0] == g["primary_concept"] for g in core_dev])
    R["HYBRID_C"] = rkC
    AUTO["HYBRID_C"] = {u: (T_fus is not None and fm[u] >= T_fus) for u in ix}

    # 실험 A 동일성: STEP23 LINEAR_CHAR EXPANDED test top1 과 일치해야 한다
    s23 = {r["utterance_id"]: r["top1"] for r in S.read_csv(S.S23 / "outputs/predictions_regression.csv")
           if r["model"] == "LINEAR_CHAR" and r["condition"] == "EXPANDED"}
    assert all(R["LINEAR_CHAR"][u][0] == s23[u] for u in s23), "LINEAR_CHAR ≠ STEP23"
    sim = S.test_similarity(core_test)
    low = [g for g in core_test if sim[g["utterance_id"]] < 0.5]
    assert len(low) == 23, len(low)
    buckets = ["<0.3", "0.3-0.5", "0.5-0.7", ">=0.7"]

    def evals(name, rows):
        rk = R[name]
        acc = [g for g in rows if AUTO[name][g["utterance_id"]]]
        return {**S.score(rows, rk), "macro_top1": S.macro_top1(rows, rk), "auto_n": len(acc),
                "auto_coverage": S.rnd(len(acc) / len(rows)) if rows else None,
                "auto_precision": S.rnd(sum(rk[g["utterance_id"]][0] == g["primary_concept"] for g in acc) / len(acc)) if acc else None,
                "confirmation_rate": S.rnd(1 - len(acc) / len(rows)) if rows else None}

    res, brow = {}, []
    for name in R:
        res[name] = {"core_test": evals(name, core_test), "core_dev": evals(name, core_dev), "low_similarity_lt_0.5": evals(name, low),
                     "unseen_step21_def": S.score([g for g in core_test if g["lexical_exposure"] == "novel"], R[name])}
        for b in buckets:
            rows = [g for g in core_test if S.sim_bucket(sim[g["utterance_id"]]) == b]
            s = S.score(rows, R[name])
            brow.append({"model": name, "bucket": b, "n": s["n"], "top1": s["top1"], "recall_at_3": s["recall_at_3"]})
    res["HYBRID_B"]["transformer_call_rate"] = {"core_test": S.rnd(sum(tcall[g["utterance_id"]] for g in core_test) / len(core_test)),
                                                "core_dev": S.rnd(sum(tcall[g["utterance_id"]] for g in core_dev) / len(core_dev))}
    db, dc = res["HYBRID_B"]["core_dev"], res["HYBRID_C"]["core_dev"]
    primary = "HYBRID_C" if (dc["top1"], dc["recall_at_3"]) > (db["top1"], db["recall_at_3"]) else "HYBRID_B"
    cfg = {"T_lin_margin(STEP23 dev)": T_lin, "T_koe_conf(dev)": T_koe if ksel["auto_accept_dev"] else None, "alpha(dev)": alpha,
           "alpha_dev_grid": alpha_rows, "T_fusion_margin(dev)": T_fus, "PRIMARY_HYBRID": primary,
           "primary_rule": "dev core Top-1 > R@3 between HYBRID_B and HYBRID_C, tie → HYBRID_B", "policies": __doc__}
    S.dump_json(S.MODELS / "hybrid_config.json", cfg)
    S.write_csv(S.OUT / "similarity_bucket_metrics.csv", brow)
    S.dump_json(S.OUT / "hybrid_metrics.json", {"PRIMARY_HYBRID": primary, "config": cfg, "results": res,
                                                 "n_low_similarity": len(low), "bucket_counts": {b: sum(S.sim_bucket(v) == b for v in sim.values()) for b in buckets}})
    G = {g["utterance_id"]: g for g in gold}
    S.write_csv(S.OUT / "predictions_linear.csv", [
        {"model": "LINEAR_CHAR", "utterance_id": u, "split": G[u]["split"], "is_core": str(S.is_core(G[u])), "gold_primary": G[u]["primary_concept"],
         "top1": R["LINEAR_CHAR"][u][0], "margin": round(lin_m[u], 6), "auto": str(AUTO["LINEAR_CHAR"][u]),
         "ranked_top5": ";".join(R["LINEAR_CHAR"][u][:5]), "top1_correct": str(R["LINEAR_CHAR"][u][0] in S.c21.patient_concepts(G[u]))} for u in ids])
    S.write_csv(S.OUT / "predictions_hybrid.csv", [
        {"model": n, "utterance_id": u, "split": G[u]["split"], "is_core": str(S.is_core(G[u])), "gold_primary": G[u]["primary_concept"],
         "top1": R[n][u][0], "auto": str(AUTO[n][u]), "transformer_called": str(tcall[u]) if n == "HYBRID_B" else "True",
         "sim_max_generated": round(sim[u], 4) if u in sim else "", "ranked_top5": ";".join(R[n][u][:5]),
         "top1_correct": str(R[n][u][0] in S.c21.patient_concepts(G[u]))} for n in ("HYBRID_A", "HYBRID_B", "HYBRID_C") for u in ids])
    for n in R:
        t = res[n]["core_test"]
        print(n, {k: t[k] for k in ("top1", "recall_at_3", "recall_at_5", "macro_top1", "auto_precision", "auto_coverage")},
              "low", res[n]["low_similarity_lt_0.5"]["top1"])
    print("PRIMARY", primary, cfg["alpha(dev)"], res["HYBRID_B"]["transformer_call_rate"])


if __name__ == "__main__":
    main()
