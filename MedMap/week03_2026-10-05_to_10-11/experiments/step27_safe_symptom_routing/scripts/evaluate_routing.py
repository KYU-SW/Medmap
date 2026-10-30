"""STEP27 평가 — 특징 구축 → DEV 에서만 파라미터·BEST_POLICY 선택 → 보고 집합 1회 적용.

[특징] STEP26 features.csv · model_cache.npz(L·P) · final_decisions.csv(B4 auto) 재사용. 추가: koe_top2 · 후보 pool 별 KoE 확률·cand_sim ·
       SYMPTOM_CUE · NON_TYPE_CUE. p_non: EXT_DEV = STEP26 재료(evaluate_ood_gate.make/fold, 같은 5-fold)로 다시 만든 out-of-fold 값
       (STEP26 full 분류기는 EXT_DEV 로 학습 → in-sample 이라 선택에 못 씀). 그 외 집합 = STEP26 full 분류기 값(predictions.csv, 고정).
[선택 집합] EXT_DEV(weak label) + INT_DEV_CORE 59(gold). 보고 전용: EXT_EVAL · INT_REGRESSION_CORE 109 · KMC_COMPLEX_STRESS.
[선택 규칙 — 사전 고정]
 B: grid t_strong ∈ {1.01(꺼짐),0.95,0.90,0.85,0.75,0.65} × t_type ∈ {0.80,0.70,0.65,0.60,0.50,0.40,0.30}(보수적 → 공격적 순서).
    feasible = DEV weak-symptom→NON ≤ 0.03 & INT_DEV_CORE NON 률 ≤ 0.05. 목적 = DEV weak-non→NON 최대, 동률(±0.005) → 낮은 weak-symptom→NON
    → grid 앞(보수적). feasible 없음 → weak-symptom→NON 최소.
 C: 새 파라미터 없음(B 값 사용).
 D: grid d_conf ∈ {0.0,0.05,0.1,0.2,0.3,0.5} × d_sim ∈ {0.0,0.1,0.15,0.2,0.25,0.3,0.35,0.4}(느슨 → 엄격).
    feasible = INT_DEV_CORE 비자동 행 중 gold 가 표시 후보에 있는 수 ≥ ceil(0.9 × C 의 수) & DEV weak-non→UNKNOWN 률 ≤ C + 0.05.
    목적 = DEV weak-non 행의 후보 표시율 최소, 동률(±0.002) → gold 표시 수 최대 → grid 앞(느슨).
 E(탐색): grid a ∈ {0,0.2,0.4} × b ∈ {0.98,0.95,0.90} × s ∈ {0.6,1.01} × c ∈ {1.01,0.6,0.5,0.4,0.3}. STEP26 과 같은 5-fold(policy_lib.fold_of, cluster)
    pooled CV. feasible = CV core precision ≥ 0.95 & CV weak-non auto ≤ B4 CV(0.0021) + 0.005. 목적 = CV core coverage 최대 → grid 앞.
    E 채택 = fold 별 선택 CV pooled core coverage ≥ B4(DEV) coverage + 2/59. 미채택이면 BEST 후보에서 제외(보고만).
 BEST_POLICY: 순서 E > D > C > B > A 중 DEV gate 를 모두 통과하는 첫 정책(E 는 채택된 경우만).
    DEV gate = weak-symptom→NON ≤ 0.03 · weak-non auto ≤ A + 0.005 · core precision ≥ 0.95 · core coverage ≥ A · DEV disagreement auto 0 ·
               weak-non→UNKNOWN ≤ A + 0.05(UNKNOWN 남발 방지). 아무것도 통과 못 하면 A.
출력: outputs/routing_features.csv · routing_decisions.csv · routing_selection.json · policy_comparison.csv · regression_metrics.json
"""
import collections
import math

import numpy as np

import s27_common as S
from safe_symptom_router import POLICIES, STATUSES, pool, route

S26 = S.S26
SETS = ("EXT_DEV", "INT_DEV_CORE", "EXT_EVAL", "INT_REGRESSION_CORE", "KMC_COMPLEX_STRESS")


def oof_p_non(fin, inv):
    import evaluate_ood_gate as G26
    train_expr = [S.norm(r["expression"]) for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv")]
    dev = [f for f in fin if f["set"] == "EXT_DEV" and f["weak_label"] in ("WEAK_SYMPTOM", "WEAK_NON_SYMPTOM")]
    other = [f for f in fin if f["set"] == "EXT_DEV" and f["weak_label"] not in ("WEAK_SYMPTOM", "WEAK_NON_SYMPTOM")]
    out = {}
    for k in range(5):
        tr = [f for f in dev if G26.fold(inv[f["row_id"]]["cluster"]) != k]
        ho = [f for f in dev if G26.fold(inv[f["row_id"]]["cluster"]) == k]
        ho_o = [f for f in other if G26.fold(inv[f["row_id"]]["cluster"]) == k]
        m = G26.make().fit([S.norm(f["text"]) for f in tr] + train_expr,
                           [int(f["weak_label"] == "WEAK_NON_SYMPTOM") for f in tr] + [0] * len(train_expr))
        for f, p in zip(ho + ho_o, m.predict_proba([S.norm(f["text"]) for f in ho + ho_o])[:, 1]):
            out[f["row_id"]] = float(p)
    return out


def build_features():
    o = S26.OUT
    fin = S.read_csv(o / "final_decisions.csv")
    feats = {r["row_id"]: r for r in S.P26.load_rows()}
    pred = {r["row_id"]: r for r in S.read_csv(o / "predictions.csv")}
    inv = {r["row_id"]: r for r in S.read_csv(S26.DATA / "weak_label_inventory.csv")}
    cache = np.load(o / "model_cache.npz")
    cls = [str(c) for c in cache["classes"]]
    ci = {c: i for i, c in enumerate(cls)}
    ri = {r: i for i, r in enumerate(cache["row_id"])}
    oof = oof_p_non(fin, inv)
    tr_by_c = S.load_train_by_concept()
    rows, lex_diff = [], 0.0
    for fd in fin:
        r = feats[fd["row_id"]]
        i = ri[fd["row_id"]]
        P = cache["P"][i]
        f = {"row_id": fd["row_id"], "set": fd["set"], "weak_label": fd["weak_label"], "gold_concept": fd["gold_concept"], "text": fd["text"],
             "cluster": inv.get(fd["row_id"], {}).get("cluster", ""), "complex_flags": [x for x in r["complex_flags"].split(";") if x] if isinstance(r["complex_flags"], str) else [],
             "lin_top1": r["lin_top1"], "lin_top2": r["lin_top2"], "lin_margin": r["lin_margin"], "koe_top1": r["koe_top1"],
             "koe_top2": cls[int(np.argsort(-P)[1])], "koe_conf": r["koe_conf"], "agree": r["agree"], "train_sim": r["train_sim"],
             "b4_auto": fd["new_auto"] == "True", "sym_cue": S.symptom_cue(fd["text"]), "non_type": S.non_type(fd["text"]),
             "p_non_frozen": float(pred[fd["row_id"]]["non_symptom_score"])}
        f["complex"] = bool(f["complex_flags"])
        f["p_non"] = oof[fd["row_id"]] if fd["set"] == "EXT_DEV" else f["p_non_frozen"]
        cs = set(pool(f)) | {f["lin_top1"]}
        f["csim"] = {c: S.cand_sim(fd["text"], c, tr_by_c) for c in cs}
        f["koe_p"] = {c: float(P[ci[c]]) for c in cs}
        lex_diff = max(lex_diff, abs(f["csim"][f["lin_top1"]] - r["lex_overlap"]))
        rows.append(f)
    assert lex_diff < 1e-5, f"cand_sim(lin_top1) ≠ STEP26 lex_overlap ({lex_diff})"
    S.write_csv(S.OUT / "routing_features.csv", [{**{k: v for k, v in f.items() if k not in ("csim", "koe_p", "complex_flags")},
                                                   "complex_flags": ";".join(f["complex_flags"]), "csim": S.dumps({k: round(v, 6) for k, v in f["csim"].items()}),
                                                   "koe_p": S.dumps({k: round(v, 6) for k, v in f["koe_p"].items()})} for f in rows])
    return rows, {"cand_sim_vs_lex_overlap_max_abs_diff": lex_diff, "n_oof_p_non": len(oof)}


def r4(x):
    return S.rnd(x) if x is not None else None


def metrics(rows, outs, ref=None):
    """outs: row_id → interface. ref: POLICY_A outs(후보 억제율 계산용)."""
    m = {}
    by = collections.defaultdict(list)
    for f in rows:
        by[f["set"]].append(f)
    for st, rs in by.items():
        if st.startswith("EXT"):
            for w in ("WEAK_SYMPTOM", "WEAK_NON_SYMPTOM", "WEAK_MIXED"):
                ws = [f for f in rs if f["weak_label"] == w]
                if not ws:
                    continue
                c = collections.Counter(outs[f["row_id"]]["status"] for f in ws)
                m[f"{st}|{w}|n"] = len(ws)
                for s in STATUSES:
                    m[f"{st}|{w}|{s}_rate"] = r4(c.get(s, 0) / len(ws))
                m[f"{st}|{w}|candidate_display_rate"] = r4(sum(bool(outs[f["row_id"]]["candidate_ids"]) and outs[f["row_id"]]["status"] == "UNCERTAIN" for f in ws) / len(ws))
            m[f"{st}|disagreement_auto_count"] = sum(outs[f["row_id"]]["status"] == "KNOWN_SYMPTOM" and not f["agree"] for f in rs)
            c = collections.Counter(outs[f["row_id"]]["status"] for f in rs)
            m[f"{st}|UNKNOWN_rate"] = r4(c.get("UNKNOWN_SYMPTOM", 0) / len(rs))
            m[f"{st}|UNCERTAIN_rate"] = r4(c.get("UNCERTAIN", 0) / len(rs))
        elif st.startswith("INT"):
            acc = [f for f in rs if outs[f["row_id"]]["status"] == "KNOWN_SYMPTOM"]
            ok = [f for f in acc if outs[f["row_id"]]["canonical_id"] == f["gold_concept"]]
            non_auto = [f for f in rs if outs[f["row_id"]]["status"] != "KNOWN_SYMPTOM"]
            shown = [f for f in non_auto if outs[f["row_id"]]["candidate_ids"]]
            m[f"{st}|n"] = len(rs)
            m[f"{st}|auto_precision"] = r4(len(ok) / len(acc)) if acc else None
            m[f"{st}|auto_coverage"] = r4(len(acc) / len(rs))
            m[f"{st}|auto_correct"] = len(ok)
            c = collections.Counter(outs[f["row_id"]]["status"] for f in rs)
            for s in STATUSES:
                m[f"{st}|{s}_rate"] = r4(c.get(s, 0) / len(rs))
            m[f"{st}|nonauto_gold_in_displayed"] = sum(f["gold_concept"] in outs[f["row_id"]]["candidate_ids"] for f in shown)
            m[f"{st}|nonauto_displayed_without_gold"] = sum(f["gold_concept"] not in outs[f["row_id"]]["candidate_ids"] for f in shown)
            m[f"{st}|nonauto_n"] = len(non_auto)
        else:
            c = collections.Counter(outs[f["row_id"]]["status"] for f in rs)
            m[f"{st}|n"] = len(rs)
            m[f"{st}|auto_rate"] = r4(c.get("KNOWN_SYMPTOM", 0) / len(rs))
            m[f"{st}|COMPLEX_INPUT_rate"] = r4(c.get("COMPLEX_INPUT", 0) / len(rs))
        if ref is not None:
            had = [f for f in rs if ref[f["row_id"]]["candidate_ids"] and ref[f["row_id"]]["status"] == "UNCERTAIN"]
            m[f"{st}|candidate_suppression_rate_vs_A"] = r4(sum(not outs[f["row_id"]]["candidate_ids"] for f in had) / len(had)) if had else None
            m[f"{st}|A_displayed_n"] = len(had)
    return m


def run(policy, rows, params):
    return {f["row_id"]: route(policy, f, params) for f in rows}


def g(m, k, d=0.0):
    v = m.get(k)
    return d if v is None else v


def select_B(dev, params):
    grid = [{"t_strong": ts, "t_type": tt} for ts in (1.01, 0.95, 0.90, 0.85, 0.75, 0.65) for tt in (0.80, 0.70, 0.65, 0.60, 0.50, 0.40, 0.30)]
    res = []
    for gi, p in enumerate(grid):
        m = metrics(dev, run("POLICY_B", dev, {**params, "B": p}))
        ws, cn, wn = g(m, "EXT_DEV|WEAK_SYMPTOM|NON_SYMPTOM_rate"), g(m, "INT_DEV_CORE|NON_SYMPTOM_rate"), g(m, "EXT_DEV|WEAK_NON_SYMPTOM|NON_SYMPTOM_rate")
        res.append({"grid_index": gi, **p, "dev_WS_to_NON": ws, "dev_core_NON": cn, "dev_WN_to_NON": wn, "feasible": ws <= 0.03 and cn <= 0.05})
    fe = [r for r in res if r["feasible"]]
    if fe:
        top = max(r["dev_WN_to_NON"] for r in fe)
        tied = [r for r in fe if r["dev_WN_to_NON"] >= top - 0.005]
        best = min(tied, key=lambda r: (r["dev_WS_to_NON"], r["grid_index"]))
    else:
        best = min(res, key=lambda r: (r["dev_WS_to_NON"], -r["dev_WN_to_NON"], r["grid_index"]))
    for r in res:
        r["selected"] = r is best
    return {"t_strong": best["t_strong"], "t_type": best["t_type"]}, res


def select_D(dev, params):
    mC = metrics(dev, run("POLICY_C", dev, params))
    need = math.ceil(0.9 * mC["INT_DEV_CORE|nonauto_gold_in_displayed"])
    grid = [{"d_conf": dc, "d_sim": ds} for dc in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5) for ds in (0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4)]
    res = []
    for gi, p in enumerate(grid):
        m = metrics(dev, run("POLICY_D", dev, {**params, "D": p}))
        hit, wnd = m["INT_DEV_CORE|nonauto_gold_in_displayed"], g(m, "EXT_DEV|WEAK_NON_SYMPTOM|candidate_display_rate")
        wnu = g(m, "EXT_DEV|WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate")
        res.append({"grid_index": gi, **p, "core_gold_displayed": hit, "need": need, "dev_WN_display_rate": wnd,
                    "dev_WS_display_rate": g(m, "EXT_DEV|WEAK_SYMPTOM|candidate_display_rate"), "dev_WN_to_UNKNOWN": wnu,
                    "feasible": hit >= need and wnu <= g(mC, "EXT_DEV|WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate") + 0.05})
    fe = [r for r in res if r["feasible"]] or res[:1]
    low = min(r["dev_WN_display_rate"] for r in fe)
    tied = [r for r in fe if r["dev_WN_display_rate"] <= low + 0.002]
    best = min(tied, key=lambda r: (-r["core_gold_displayed"], r["grid_index"]))
    for r in res:
        r["selected"] = r is best
    return {"d_conf": best["d_conf"], "d_sim": best["d_sim"]}, res, need


class AutoArr:
    """E 선택용 numpy 배열(DEV 행 순서 고정)."""

    def __init__(self, rows):
        import numpy as np
        self.agree = np.array([f["agree"] and not f["complex"] for f in rows])
        self.margin = np.array([f["lin_margin"] for f in rows])
        self.conf = np.array([f["koe_conf"] for f in rows])
        self.tsim = np.array([f["train_sim"] for f in rows])
        self.csim = np.array([f["csim"][f["lin_top1"]] for f in rows])
        self.wn = np.array([f["set"] == "EXT_DEV" and f["weak_label"] == "WEAK_NON_SYMPTOM" for f in rows])
        self.core = np.array([f["set"] == "INT_DEV_CORE" for f in rows])
        self.ok = np.array([f["set"] == "INT_DEV_CORE" and f["lin_top1"] == f["gold_concept"] for f in rows])
        self.b4 = np.array([f["b4_auto"] for f in rows])

    def dec(self, p):
        return self.agree & (self.margin >= p["a"]) & (self.conf >= p["b"]) & ((self.tsim >= p["s"]) | (self.csim >= p["c"]))

    def met(self, d, mask):
        wn, core = self.wn & mask, self.core & mask
        acc = d & core
        return {"WN_auto": S.rnd(float((d & wn).sum() / max(1, wn.sum()))),
                "core_precision": S.rnd(float((acc & self.ok).sum() / acc.sum())) if acc.sum() else 0.0,
                "core_coverage": S.rnd(float(acc.sum() / max(1, core.sum()))), "core_correct": int((acc & self.ok).sum())}


def select_E(dev):
    """E 그리드·선택(numpy). 선택의 일반화 = fold 별 선택 → hold-out pooled CV."""
    import numpy as np
    grid = [{"a": a, "b": b, "s": s, "c": c} for a in (0.0, 0.2, 0.4) for b in (0.98, 0.95, 0.90) for s in (0.6, 1.01) for c in (1.01, 0.6, 0.5, 0.4, 0.3)]
    A = AutoArr(dev)
    folds = np.array([S.P26.fold_of({"cluster": f["cluster"] or None, "row_id": f["row_id"]}) for f in dev])
    decs = [A.dec(p) for p in grid]
    allm = np.ones(len(dev), bool)

    def fit27(mask):
        best = None
        for gi, d in enumerate(decs):
            m = A.met(d, mask)
            feas = m["core_precision"] >= 0.95 and m["WN_auto"] <= 0.0021 + 0.005
            k = (feas, m["core_coverage"], -gi)
            if best is None or k > best[0]:
                best = (k, gi)
        return best[1]
    res = [{"grid_index": gi, **p, **A.met(decs[gi], allm), "feasible": None} for gi, p in enumerate(grid)]
    for r in res:
        r["feasible"] = r["core_precision"] >= 0.95 and r["WN_auto"] <= 0.0021 + 0.005
    pooled = np.zeros(len(dev), bool)
    fold_params = []
    for k in range(5):
        gi = fit27(folds != k)
        fold_params.append(grid[gi])
        pooled[folds == k] = decs[gi][folds == k]
    cv27 = A.met(pooled, allm)
    b4cv = A.met(A.b4, allm)
    fgi = fit27(allm)
    adopted = cv27["core_precision"] >= 0.95 and cv27["WN_auto"] <= 0.0021 + 0.005 and cv27["core_coverage"] >= b4cv["core_coverage"] + 2 / 59
    for r in res:
        r["selected"] = r["grid_index"] == fgi
    return grid[fgi], res, {"cv_step27_objective": cv27, "fold_params": fold_params, "b4_on_dev(in-sample params)": b4cv, "adopted": adopted,
                            "rule": "adopted = CV core precision ≥ 0.95 & CV WN auto ≤ 0.0071 & CV core coverage ≥ B4(DEV) + 2/59"}


def dev_gate(m, mA):
    c = {"WS_to_NON<=0.03": g(m, "EXT_DEV|WEAK_SYMPTOM|NON_SYMPTOM_rate") <= 0.03,
         "WN_auto<=A+0.005": g(m, "EXT_DEV|WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate") <= g(mA, "EXT_DEV|WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate") + 0.005,
         "core_precision>=0.95": g(m, "INT_DEV_CORE|auto_precision") >= 0.95,
         "core_coverage>=A": g(m, "INT_DEV_CORE|auto_coverage") >= g(mA, "INT_DEV_CORE|auto_coverage") - 1e-9,
         "disagree_auto==0": m.get("EXT_DEV|disagreement_auto_count", 0) == 0,
         "WN_to_UNKNOWN<=A+0.05": g(m, "EXT_DEV|WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate") <= g(mA, "EXT_DEV|WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate") + 0.05}
    return c, all(c.values())


def main():
    rows, chk = build_features()
    dev = [f for f in rows if f["set"] in ("EXT_DEV", "INT_DEV_CORE")]
    params = {}
    params["B"], grid_B = select_B(dev, params)
    params["D"], grid_D, need = select_D(dev, params)
    pE, grid_E, infoE = select_E(dev)
    params["E"] = pE
    S.write_csv(S.OUT / "selection_grid_B.csv", grid_B)
    S.write_csv(S.OUT / "selection_grid_D.csv", grid_D)
    S.write_csv(S.OUT / "selection_grid_E.csv", grid_E)

    outs = {p: run(p, rows, params) for p in POLICIES}
    # POLICY_A(보고 집합) == STEP26 predictions 상태 확인
    pred = {r["row_id"]: r for r in S.read_csv(S26.OUT / "predictions.csv")}
    a_mis = sum(outs["POLICY_A"][f["row_id"]]["status"] != pred[f["row_id"]]["status"] for f in rows if f["set"] != "EXT_DEV")
    a_cand = sum(";".join(outs["POLICY_A"][f["row_id"]]["candidate_ids"]) != pred[f["row_id"]]["candidate_ids"]
                 for f in rows if f["set"] != "EXT_DEV" and pred[f["row_id"]]["status"] == "UNCERTAIN" and not f["complex"])
    assert a_mis == 0 and a_cand == 0, f"POLICY_A ≠ STEP26 (status {a_mis}, cand {a_cand})"

    mets = {p: metrics(rows, outs[p], outs["POLICY_A"]) for p in POLICIES}
    gates = {p: dev_gate(mets[p], mets["POLICY_A"]) for p in POLICIES}
    order = (["POLICY_E"] if infoE["adopted"] else []) + ["POLICY_D", "POLICY_C", "POLICY_B", "POLICY_A"]
    best = next((p for p in order if gates[p][1]), "POLICY_A")

    sel = {"BEST_POLICY": best, "params": params, "dev_gate": {p: {"checks": gates[p][0], "pass": gates[p][1]} for p in POLICIES},
           "E_info": infoE, "D_need_core_gold_displayed": need, "feature_checks": chk, "rules": __doc__, "order": order}
    S.dump_json(S.OUT / "routing_selection.json", sel)

    comp = []
    for p in POLICIES:
        for k, v in sorted(mets[p].items()):
            st, _, name = k.partition("|")
            comp.append({"policy": p, "set": st, "metric": name, "value": v,
                         "role": "SELECTION" if st in ("EXT_DEV", "INT_DEV_CORE") else "REPORT_ONLY"})
    S.write_csv(S.OUT / "policy_comparison.csv", comp)
    dec = []
    for f in rows:
        d = {k: f[k] for k in ("row_id", "set", "weak_label", "gold_concept", "text", "lin_top1", "koe_top1", "agree", "sym_cue", "non_type")}
        d["p_non"] = round(f["p_non"], 6)
        for p in POLICIES:
            o = outs[p][f["row_id"]]
            d[f"{p}_status"], d[f"{p}_decision"], d[f"{p}_candidates"] = o["status"], o["decision"], ";".join(o["candidate_ids"])
            d[f"{p}_reasons"] = ";".join(o["reason_codes"])
        d["best_interface_json"] = S.dumps(outs[best][f["row_id"]])
        dec.append(d)
    S.write_csv(S.OUT / "routing_decisions.csv", dec)
    S.dump_json(S.OUT / "regression_metrics.json", {p: {k: v for k, v in mets[p].items() if k.startswith(("INT_REGRESSION_CORE", "INT_DEV_CORE"))} for p in POLICIES}
                | {"note": "INT_REGRESSION_CORE = STEP21–24 FIXED_REGRESSION_TEST(합성·blind 아님, 보고 전용). INT_DEV_CORE = 선택용."})
    print("params", S.dumps(params), "BEST", best, "E adopted", infoE["adopted"])
    for p in POLICIES:
        m = mets[p]
        print(p, "gate", gates[p][1], {k: m.get(k) for k in ("EXT_DEV|WEAK_SYMPTOM|NON_SYMPTOM_rate", "EXT_DEV|WEAK_NON_SYMPTOM|KNOWN_SYMPTOM_rate",
                                                         "EXT_DEV|WEAK_NON_SYMPTOM|UNKNOWN_SYMPTOM_rate", "INT_DEV_CORE|auto_coverage",
                                                         "INT_DEV_CORE|auto_precision", "EXT_DEV|WEAK_NON_SYMPTOM|candidate_display_rate")})


if __name__ == "__main__":
    main()
