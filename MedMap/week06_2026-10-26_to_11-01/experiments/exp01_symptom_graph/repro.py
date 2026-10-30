"""Baseline A 재현 대조(manifest baseline): SELECT_SMOKE 행에서 STEP16B MODEL_k 초기 예측이
02_holdout_initial_predictions.csv(config k{k}_s42) 와 같은지. 정답 열(truth·truth_rank·wrong)은 읽지 않는다.
불일치 = INVALID(중단).
"""
from __future__ import annotations

import csv

import numpy as np

from core import Exp01Invalid

PRED_CSV = "/home/<user>/medmap/exp/step16b_next_information_validation/02_holdout_initial_predictions.csv"
READ_COLS = ("config", "row_index", "top1", "p_top1")


def load_reference(rows: set, ks=(3, 5, 10), path=PRED_CSV) -> dict:
    """(k, row_index) -> (top1, p_top1). 지정 행·열만 보관(정답 열은 버림)."""
    want = {f"k{k}_s42": k for k in ks}
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        idx = {c: header.index(c) for c in READ_COLS}
        for line in r:
            cfg = line[idx["config"]]
            if cfg not in want:
                continue
            ri = int(line[idx["row_index"]])
            if ri in rows:
                out[(want[cfg], ri)] = (line[idx["top1"]], float(line[idx["p_top1"]]))
    return out


def check(predict, cases, ref: dict, ks=(3, 5, 10), tol=1e-5) -> dict:
    """predict(k, case) -> (top1 이름, p_top1). STEP16B 와 같은 뷰(make_view, split 'step16b_holdout', seed 42)로 만든다."""
    n, bad = 0, []
    for case in cases:
        for k in ks:
            key = (k, case["row_index"])
            if key not in ref:
                raise Exp01Invalid(f"EXP01_REPRO_REFERENCE_MISSING:{key}")
            top1, p = predict(k, case)
            rt, rp = ref[key]
            n += 1
            if top1 != rt or not np.isclose(p, rp, atol=tol, rtol=0):
                bad.append(key)
    if bad:
        raise Exp01Invalid(f"EXP01_BASELINE_A_NOT_REPRODUCED:{len(bad)}/{n}:{bad[:3]}")
    return {"compared": n, "mismatch": 0}


def make_predict(c, sem, models: dict, classes):
    """STEP16B 경로 그대로: make_view → Encoder.transform → model.predict_proba."""
    enc = c.Encoder(sem)
    def predict(k, case):
        v = c.make_view(sem, list(case["tokens"]), case["initial"], k, "step16b_holdout", 42, case["row_index"])
        P = models[k].predict_proba(enc.transform([v], [case["age"]], [case["sex"]]))[0]
        j = int(np.argmax(P))
        return classes[j], float(np.float32(P[j]))
    return predict
