"""공개 집계 칸 사이 관계 경험적 발견(합성 자료 전용, PROTOCOL_TIME_v2.md §9-2) — 독립 검증기용 관계 파일 생성.

방법: synth_random_v2 무작위 소규모 자료 N 개를 파이프라인(run_time_policy_audit_v2.run, publish=False)으로 돌려 정확 집계 X 행렬을 만든다.
- 상수 칸: 모든 자료에서 같은 값(구조적 0 등) → constant
- 선형 등식: 변하는 칸 행렬의 영공간(SVD) → RREF 로 희소화, 모든 자료에서 성립 확인 후 저장
- 쌍별 부등식: 모든 자료에서 x_i ≤ x_j(항상 같지는 않음) → 이행적 축약(Hasse) 만 저장
보호 코드(public_v2·disclosure_v2·묶음 G)를 쓰지 않는다. 실제 MIMIC 미사용. 자료 수가 칸 수보다 충분히 많아야 함(부족하면 거짓 관계 → 검증이 더 보수적).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_time_policy_audit_v2 as R  # noqa: E402
import synth_random_v2 as SR  # noqa: E402


SKIPPED: list = []


def collect(n: int, seed0: int, log=print) -> tuple[list, np.ndarray]:
    rows, keys = [], set()
    t = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            d = Path(tmp) / f"s{i}"
            SR.make(seed0 + i, d / "src")
            r = R.run(d / "src", d / "o", d / "src" / "radiology_detail.parquet", publish=False)
            if r["status"] != "INTERNAL_ONLY":
                if set(r.get("violations", {})) <= {"B_zero_match_guard_ecg", "B_zero_match_guard_lab", "B_zero_match_guard_radiology"}:
                    SKIPPED.append(seed0 + i)                           # 의도된 0 매칭 가드 중단(실제 실행도 공개 없이 중단) — 관계 표본에서 제외
                    shutil.rmtree(d, ignore_errors=True)
                    continue
                raise RuntimeError(f"SYNTH_RUN_ABORT seed={seed0 + i}")
            rows.append(r["flat"])
            keys |= set(r["flat"])
            shutil.rmtree(d, ignore_errors=True)
            if (i + 1) % 200 == 0:
                log(f"PROGRESS {i + 1}/{n} {time.time() - t:.0f}s")
    U = sorted(keys)
    M = np.array([[r.get(k, 0) for k in U] for r in rows], dtype=float)
    return U, M


def rref_rows(B: np.ndarray, tol=1e-9) -> np.ndarray:
    A = B.copy()
    r = 0
    for c in range(A.shape[1]):
        if r >= A.shape[0]:
            break
        p = r + int(np.argmax(np.abs(A[r:, c])))
        if abs(A[p, c]) < tol:
            continue
        A[[r, p]] = A[[p, r]]
        A[r] /= A[r, c]
        others = np.abs(A[:, c]) > tol
        others[r] = False
        A[others] -= np.outer(A[others, c], A[r])
        r += 1
    A = A[:r]
    A[np.abs(A) < 1e-9] = 0.0
    return A


def exact_null(V: np.ndarray, rank: int) -> list:
    """정수 행렬 V(자료 × 칸)의 영공간을 분수로 정확히 계산(RREF) → 정수 계수 관계 목록. 전 자료에서 정수 연산으로 성립 확인."""
    from fractions import Fraction
    from math import gcd
    from scipy.linalg import qr
    _, _, piv = qr(V.T, pivoting=True, mode="economic")              # 독립 자료 행 고르기
    rows = sorted(piv[: min(len(piv), rank + 40)])
    A = [[Fraction(int(x)) for x in V[i]] for i in rows]
    n = V.shape[1]
    pivcols, r = [], 0
    for c in range(n):
        p = next((i for i in range(r, len(A)) if A[i][c] != 0), None)
        if p is None:
            continue
        A[r], A[p] = A[p], A[r]
        inv = 1 / A[r][c]
        A[r] = [x * inv for x in A[r]]
        for i in range(len(A)):
            if i != r and A[i][c] != 0:
                f = A[i][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[r])]
        pivcols.append(c)
        r += 1
        if r == len(A):
            break
    if r != rank:
        raise RuntimeError(f"RANK_MISMATCH exact={r} svd={rank}")
    free = [c for c in range(n) if c not in set(pivcols)]
    rels = []
    Vi = V.astype(np.int64)
    for fcol in free:
        vec = {fcol: Fraction(1)}
        for i, pc in enumerate(pivcols):
            if A[i][fcol] != 0:
                vec[pc] = -A[i][fcol]
        den = 1
        for v in vec.values():
            den = den * v.denominator // gcd(den, v.denominator)
        ints = {c: int(v * den) for c, v in vec.items()}
        g = 0
        for v in ints.values():
            g = gcd(g, abs(v))
        ints = {c: v // g for c, v in ints.items()}
        cols = sorted(ints)
        if np.any(Vi[:, cols] @ np.array([ints[c] for c in cols], dtype=np.int64) != 0):   # 전 자료 정수 검증
            raise RuntimeError("EXACT_RELATION_FAILS_ON_FULL_DATA")
        rels.append(ints)
    return rels


def discover(U: list, M: np.ndarray) -> dict:
    var = M.max(axis=0) != M.min(axis=0)
    constant = {U[i]: int(M[0, i]) for i in range(len(U)) if not var[i]}
    Uv = [U[i] for i in range(len(U)) if var[i]]
    V = M[:, var]
    s, vt = np.linalg.svd(V, full_matrices=True)[1:]
    tol = s.max() * max(V.shape) * 1e-12
    rank = int((s > tol).sum())
    exact = exact_null(V, rank)                                       # 정수 계수·전 자료 검증(누락·근사 없음)
    if len(exact) != V.shape[1] - rank:
        raise RuntimeError("NULL_DIM_MISMATCH")
    equalities = [{"cells": [Uv[j] for j in sorted(e)], "coef": [float(e[j]) for j in sorted(e)]} for e in exact]
    keep = np.ones(len(equalities), dtype=bool)
    # 쌍별 부등식 x_i ≤ x_j (항상 같지는 않음) → Hasse
    n = len(Uv)
    LE = np.zeros((n, n), dtype=bool)
    for i in range(n):
        le = (V[:, [i]] <= V).all(axis=0)
        eqall = (V[:, [i]] == V).all(axis=0)
        LE[i] = le & ~eqall
    np.fill_diagonal(LE, False)
    Lf = LE.astype(np.float32)
    TR = LE & ~((Lf @ Lf) > 0)
    ineq = [[Uv[i], Uv[j]] for i, j in zip(*np.nonzero(TR))]
    return {"universe": U, "varying": Uv, "constant": constant, "equalities": equalities, "inequalities": ineq,
            "n_runs": int(M.shape[0]), "n_cells": len(U), "n_varying": n, "rank": rank, "n_dropped_unverified_relations": int((~keep).sum()), "equality_method": "정확 분수 RREF + 전 자료 정수 검증",
            "n_pairwise_le_before_reduction": int(LE.sum())}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--out", required=True, help="관계 JSON(이미 있으면 거부)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit("이미 있음 — 덮어쓰지 않음")
    t = time.time()
    U, M = collect(a.n, a.seed0, log=lambda m: print(m, flush=True))
    rel = discover(U, M)
    rel.update({"created": datetime.now().isoformat(timespec="seconds"), "generator": "synth_random_v2", "seed0": a.seed0,
                "code_sha256": R.code_sha(), "seconds": round(time.time() - t, 1), "skipped_zero_match_guard_seeds": len(SKIPPED),
                "note": "합성 자료에서 경험적으로 찾은 관계 — 실제 MIMIC 미사용. 보호 코드·묶음 G 미사용"})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rel, ensure_ascii=False), encoding="utf-8")
    print("RELATIONS_DONE", rel["n_runs"], rel["n_cells"], rel["n_varying"], rel["rank"], len(rel["equalities"]), len(rel["inequalities"]),
          flush=True)


if __name__ == "__main__":
    main()
