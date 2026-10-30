"""EXP-01 실데이터 적재(RG RUN + 사용자 승인 후에만 호출). 공식 validate/test 는 s16b_core.guarded_path 가 막는다.

반환물: 분할 배정, 프로필, TRAIN16 질환 빈도(prior), 평가 사례 목록, Baseline B 학습 행렬.
이 모듈은 질환 지식표를 읽지 않는다(중증 집합은 severity_eval 만).
"""
from __future__ import annotations

import ast
import hashlib
import json

import numpy as np

import split_rules as sr

TRAIN_SHA256 = "93933e9a9a7a00d618a931deda7767485af299fe4635bf189a7c63b510e8b172"
EVIDENCES_SHA256 = "281c78b044ae60514e28ecc9052d08a8225dd3e2db3f00f8788b99c47b05e0c0"
IG_NPZ = "/home/<user>/medmap/exp/step16b_next_information_validation/ig_table_step16b_train.npz"


def verify_inputs(c) -> None:
    for path, exp in ((c.TRAIN_PATH, TRAIN_SHA256), (f"{c.D}/release_evidences.json", EVIDENCES_SHA256)):
        if c.sha(c.guarded_path(path)) != exp:
            raise RuntimeError(f"EXP01_INPUT_SHA_MISMATCH:{path}")


def load_all(nrows=None):
    c = sr.s16b_core()
    verify_inputs(c)
    df = c.load_train(nrows=nrows)                     # row_index·split_key·holdout·tokens (STEP16B 그대로)
    asg = {int(r): (sr.exp01_half(int(r)) if h else "TRAIN16") for r, h in zip(df.row_index, df.holdout)}
    prof = {int(r): (a, s, i, e) for r, a, s, i, e in zip(df.row_index, df.AGE, df.SEX, df.INITIAL_EVIDENCE, df.EVIDENCES)}
    rep = sr.verify(asg, prof, expected=None if nrows else sr.EXPECTED_S16B)
    select = [r for r, v in asg.items() if v == "SELECT"]
    rep["select_smoke_index_sha256"] = sr.index_sha(sr.smoke_subset(select))
    tr = df[df.row_index.map(lambda r: asg[int(r)] == "TRAIN16")]
    classes = list(json.load(open(f"{sr.S16B_DIR}/01_split_manifest.json"))["classes"])
    counts = tr.PATHOLOGY.value_counts()
    prior = np.array([counts.get(k, 0) for k in classes], dtype=np.float64)
    if (prior <= 0).any():
        raise RuntimeError("EXP01_EMPTY_CLASS_IN_TRAIN16")
    prior /= prior.sum()
    return c, df, asg, rep, classes, prior


def train_profiles(df, asg) -> set:
    tr = df[df.row_index.map(lambda r: asg[int(r)] == "TRAIN16")]
    return set(zip(tr.AGE, tr.SEX, tr.INITIAL_EVIDENCE, tr.EVIDENCES))


def cases(df, asg, which: str, train_prof: set | None = None):
    """which ∈ {SELECT_SMOKE, SELECT, FINAL}. 탐색기에는 initial·age·sex 만 전달된다(tokens 는 시뮬레이터 전용).
    differential·novel 은 평가 전용 필드(run_exp01.evaluate 가 탐색기에 넘기지 않는다)."""
    if which == "SELECT_SMOKE":
        keep = set(sr.smoke_subset([r for r, v in asg.items() if v == "SELECT"]))
    else:
        keep = {r for r, v in asg.items() if v == which}
    sub = df[df.row_index.isin(keep)]
    for r, a, s, i, t, y, ev, dd in zip(sub.row_index, sub.AGE, sub.SEX, sub.INITIAL_EVIDENCE, sub.tokens, sub.PATHOLOGY,
                                        sub.EVIDENCES, sub.DIFFERENTIAL_DIAGNOSIS):
        yield {"row_index": int(r), "age": int(a), "sex": s, "initial": i, "tokens": tuple(t), "truth": y,
               "differential": [(str(n), float(p)) for n, p in ast.literal_eval(dd)],
               "novel": None if train_prof is None else (a, s, i, ev) not in train_prof}


def profile_hash(rows) -> str:
    return hashlib.sha256(",".join(map(str, sorted(rows))).encode()).hexdigest()
