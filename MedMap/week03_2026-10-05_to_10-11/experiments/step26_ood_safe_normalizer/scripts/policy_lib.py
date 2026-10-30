"""STEP26 정책 정의·지표·선택 규칙(실행 전 고정).

공통: 새 정책(B1–B4, GATE)은 COMPLEX_INPUT(부정·과거·타인·복수 연결어·40자 초과)을 자동 수락하지 않는다. 기존 baseline 은 원래 규칙 그대로.
출력 concept: LINEAR_ONLY·B1–B4 = Linear top1(B2–B4 는 두 모델 동의 시 같은 값) · HYBRID_B·GATE = Hybrid B 출력.
선택 규칙(DEV 만): feasible = INT_DEV_CORE auto precision ≥ 0.95 & coverage ≥ 0.40 →
  WEAK_NON_SYMPTOM auto-accept rate(EXT_DEV) 최소 → INT_DEV_CORE coverage 최대 → grid 순서.
BEST_POLICY: 5-fold CV(EXT_DEV cluster·INT_DEV_CORE index 기준) pooled 지표로 같은 규칙, 동률(±0.005) → B1<B2<B3<B4<GATE.
GATE 승격: CV WN auto-rate 가 최선 규칙 정책보다 0.02 이상 낮을 때만.
"""
from __future__ import annotations

import hashlib
import numpy as np

import s26_common as S

ORDER = ["B1", "B2", "B3", "B4", "LIGHTWEIGHT_GATE"]
GRIDS = {
    "B1": [{"t": round(t, 3)} for t in np.arange(0.0, 2.01, 0.05)],
    "B2": [{}],
    "B3": [{"a": a, "b": b} for a in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0] for b in [0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99]],
    "B4": [{"a": a, "b": b, "s": s} for a in [0.0, 0.2, 0.4, 0.6] for b in [0.0, 0.7, 0.9, 0.95, 0.98] for s in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]],
    "LIGHTWEIGHT_GATE": [{"th": round(t, 2)} for t in np.arange(0.05, 0.96, 0.05)],
}
GATE_FEATS = ["lin_margin", "koe_conf", "koe_gap", "agree", "train_sim", "length", "lex_overlap"]


def load_rows():
    rows = S.read_csv(S.OUT / "features.csv")
    for r in rows:
        for k in ("lin_margin", "koe_conf", "koe_gap", "train_sim", "lex_overlap"):
            r[k] = float(r[k])
        r["length"] = int(r["length"])
        r["agree"] = r["agree"] == "True"
        r["complex"] = bool(r["complex_flags"])
    return rows


def hyb_b(r):
    fast = r["lin_margin"] >= S.T_LIN
    return (r["lin_top1"], True) if fast else (r["koe_top1"], r["koe_conf"] >= S.T_KOE)


def baseline(name, r):
    if name == "LINEAR_ONLY":
        return r["lin_top1"], r["lin_margin"] >= S.T_LIN
    return hyb_b(r)


def decide(policy, p, r, gp=None):
    if r["complex"]:
        return (r["lin_top1"], False)
    if policy == "B1":
        return r["lin_top1"], r["lin_margin"] >= p["t"]
    if policy == "B2":
        return r["lin_top1"], r["agree"]
    if policy == "B3":
        return r["lin_top1"], r["agree"] and r["lin_margin"] >= p["a"] and r["koe_conf"] >= p["b"]
    if policy == "B4":
        return r["lin_top1"], r["agree"] and r["lin_margin"] >= p["a"] and r["koe_conf"] >= p["b"] and r["train_sim"] >= p["s"]
    if policy == "LIGHTWEIGHT_GATE":
        return hyb_b(r)[0], gp[r["row_id"]] >= p["th"]
    raise ValueError(policy)


def gate_x(rows):
    return np.array([[float(r[f]) for f in GATE_FEATS] for r in rows])


def fit_gate(rows):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    tr = [r for r in rows if r["set"] == "INT_DEV_CORE" or (r["set"] == "EXT_DEV" and r["weak_label"] == "WEAK_NON_SYMPTOM")]
    y = [int(r["set"] == "INT_DEV_CORE" and hyb_b(r)[0] == r["gold_concept"]) for r in tr]
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=S.SEED))
    m.fit(gate_x(tr), y)
    return m


def gate_probs(gate, rows):
    """row_id → gate 확률(분류 점수, 확률·임상 확률 아님)."""
    if gate is None or not rows:
        return {}
    pr = gate.predict_proba(gate_x(rows))[:, 1]
    return {r["row_id"]: float(v) for r, v in zip(rows, pr)}


def metrics(rows, dec):
    """dec: row_id → (label, auto). EXT/INT 지표를 분리 계산."""
    out = {}
    ext = [r for r in rows if r["set"].startswith("EXT")]
    for w in ("WEAK_NON_SYMPTOM", "WEAK_SYMPTOM", "WEAK_MIXED"):
        rs = [r for r in ext if r["weak_label"] == w]
        out[f"{w}_n"] = len(rs)
        out[f"{w}_auto_rate"] = S.rnd(sum(dec[r["row_id"]][1] for r in rs) / len(rs)) if rs else None
    out["ext_disagreement_auto_count"] = sum(1 for r in ext if dec[r["row_id"]][1] and not r["agree"])
    out["ext_unknown_rate"] = S.rnd(1 - sum(dec[r["row_id"]][1] for r in ext) / len(ext)) if ext else None
    for st in ("INT_DEV_CORE", "INT_REGRESSION_CORE"):
        rs = [r for r in rows if r["set"] == st]
        if not rs:
            continue
        acc = [r for r in rs if dec[r["row_id"]][1]]
        ok = [r for r in acc if dec[r["row_id"]][0] == r["gold_concept"]]
        out[f"{st}_n"] = len(rs)
        out[f"{st}_auto_precision"] = S.rnd(len(ok) / len(acc)) if acc else None
        out[f"{st}_auto_coverage"] = S.rnd(len(acc) / len(rs))
        out[f"{st}_known_recall"] = S.rnd(len(ok) / len(rs))
    kmc = [r for r in rows if r["set"] == "KMC_COMPLEX_STRESS"]
    if kmc:
        out["KMC_auto_rate"] = S.rnd(sum(dec[r["row_id"]][1] for r in kmc) / len(kmc))
    return out


def feasible(m):
    return (m.get("INT_DEV_CORE_auto_precision") or 0) >= 0.95 and (m.get("INT_DEV_CORE_auto_coverage") or 0) >= 0.40


def objective_key(m, gi):
    return (feasible(m), -(m["WEAK_NON_SYMPTOM_auto_rate"] if m["WEAK_NON_SYMPTOM_auto_rate"] is not None else 1.0),
            m.get("INT_DEV_CORE_auto_coverage") or 0, -gi)


def fit_policy(policy, rows):
    """rows = 적합용(EXT_DEV ∪ INT_DEV_CORE 일부). 반환: (params, gate, metrics)."""
    gate = fit_gate(rows) if policy == "LIGHTWEIGHT_GATE" else None
    gp = gate_probs(gate, rows)
    best = None
    for gi, p in enumerate(GRIDS[policy]):
        m = metrics(rows, {r["row_id"]: decide(policy, p, r, gp) for r in rows})
        k = objective_key(m, gi)
        if best is None or k > best[0]:
            best = (k, p, m)
    return best[1], gate, best[2]


def fold_of(r):
    key = r.get("cluster") or r["row_id"]
    return int(hashlib.sha256(f"cv|{key}".encode()).hexdigest(), 16) % 5


def cross_validate(policy, dev_rows, cluster_of):
    pooled = {}
    for f in range(5):
        fit = [r for r in dev_rows if fold_of({"cluster": cluster_of.get(r["row_id"]), "row_id": r["row_id"]}) != f]
        hold = [r for r in dev_rows if fold_of({"cluster": cluster_of.get(r["row_id"]), "row_id": r["row_id"]}) == f]
        p, gate, _ = fit_policy(policy, fit)
        gp = gate_probs(gate, hold)
        for r in hold:
            pooled[r["row_id"]] = decide(policy, p, r, gp)
    return metrics(dev_rows, pooled)


def policy_index(name):
    return ORDER.index(name)

