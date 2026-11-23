"""관계 파일 relations_v3_schema.json 생성(PROTOCOL_TIME_v2.md §9-3) — 합성 자료 전용, 실제 MIMIC 미사용.

입력 관계 = disclosure_schema.build_schema()(스키마·프로토콜 선언). 합성 자료는 규칙을 만들지 않고 대조에만 쓴다.
1) 선언 대조: 선언 등식·부등식·상수가 합성 자료 전부에서 성립해야 함. 하나라도 거짓이면 이 스크립트가 실패(선언을 고쳐야 함).
2) 상수 칸 분류: 합성에서 늘 같은 값인 칸 = constant(정의상, 선언분) / generator_constant(생성기 미도달 — 공격자 지식 아님, 값이 다르면 그 칸 비공개).
3) 빈틈 대조: 합성 자료 정수 영공간의 관계 중 선언 등식의 span 에 없는 것 = 선언 누락 후보. 그 관계에 든 칸 = untrusted_cells(비공개).
   쌍별 부등식 중 선언(등식·부등식 폐포)으로 설명되지 않는 것은 규칙으로 쓰지 않고 건수·목록만 coverage_report 에 남긴다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import disclosure_schema as DSC  # noqa: E402


def _rref_rows(rows: list[dict]) -> dict:
    """희소 정확 소거: {pivot 칸: {칸: 분수}}."""
    basis: dict = {}
    for r in rows:
        v = _reduce({c: Fraction(w) for c, w in r.items() if w}, basis)
        if v:
            p = min(v)
            inv = 1 / v[p]
            basis[p] = {c: w * inv for c, w in v.items()}
    return basis


def _reduce(v: dict, basis: dict) -> dict:
    changed = True
    while changed:
        changed = False
        for c in sorted(v):
            b = basis.get(c)
            if b is not None:
                f = v[c]
                for k, w in b.items():
                    nv = v.get(k, Fraction(0)) - f * w
                    if nv:
                        v[k] = nv
                    else:
                        v.pop(k, None)
                changed = True
                break
    return v


def check_declared(schema: dict, U: list, M: np.ndarray) -> list:
    """합성 자료 전부에서 선언이 성립하는지. 거짓 목록 반환."""
    ix = {c: i for i, c in enumerate(U)}
    bad = []

    def col(c):
        return M[:, ix[c]] if c in ix else None
    for e in schema["equalities"]:
        cs = [col(c) for c in e["cells"]]
        if any(x is None for x in cs):
            bad.append(("MISSING", e["why"], [c for c in e["cells"] if c not in ix][:3]))
            continue
        if np.any(np.abs(sum(w * x for w, x in zip(e["coef"], cs))) > 1e-9):
            bad.append(("EQ", e["why"], e["cells"][:6]))
    for (a, b_), why in zip(schema["inequalities"], schema["inequality_reasons"]):
        if col(a) is None or col(b_) is None:
            bad.append(("MISSING", why, [a, b_]))
        elif np.any(col(a) > col(b_)):
            bad.append(("LE", why, [a, b_]))
    for e in schema["inequalities_general"]:
        cs = [col(c) for c in e["cells"]]
        if any(x is None for x in cs):
            bad.append(("MISSING", e["why"], e["cells"][:3]))
        elif np.any(sum(w * x for w, x in zip(e["coef"], cs)) > 1e-9):
            bad.append(("GEN", e["why"], e["cells"][:6]))
    for c, v in schema["constant"].items():
        if col(c) is None:
            bad.append(("MISSING", "constant", [c]))
        elif np.any(col(c) != v):
            bad.append(("CONST", schema["constant_reasons"][c], [c]))
    return bad


def coverage(schema: dict, U: list, M: np.ndarray, empirical_eq: list, empirical_le: list) -> dict:
    """empirical_eq: 합성 정수 영공간 기저 [{칸: 계수}]. 상수 칸(늘 0)은 관계에서 사라져 있으므로 제외하고 비교."""
    var = {U[i] for i in range(len(U)) if M[:, i].max() != M[:, i].min()}
    basis = _rref_rows([{c: w for c, w in zip(e["cells"], e["coef"]) if c in var} for e in schema["equalities"]])
    gap_rel = []
    gap_cells = set()
    for e in empirical_eq:
        v = _reduce({c: Fraction(w) for c, w in e.items()}, basis)
        if v:
            gap_rel.append(sorted(v))                                  # 선언 span 으로 줄지 않는 잔여
            gap_cells.update(v)
    # 부등식: 선언 부등식 + 같음 + 합의 부분 ≤ 합(음수 없음) 폐포로 설명되는지
    idx = {c: i for i, c in enumerate(U)}
    n = len(U)
    R = np.zeros((n, n), dtype=bool)
    for a, b_ in schema["inequalities"]:
        if a in idx and b_ in idx:
            R[idx[a], idx[b_]] = True
    for e in schema["equalities"]:
        pos = [c for c, w in zip(e["cells"], e["coef"]) if w > 0]
        neg = [c for c, w in zip(e["cells"], e["coef"]) if w < 0]
        if len(pos) == 1:
            for c in neg:
                if c in idx and pos[0] in idx:
                    R[idx[c], idx[pos[0]]] = True                      # 부분 ≤ 합
                    if len(neg) == 1:
                        R[idx[pos[0]], idx[c]] = True                  # 같음
    for _ in range(12):
        Rf = R.astype(np.float32)
        R2 = R | ((Rf @ Rf) > 0)
        if (R2 == R).all():
            break
        R = R2
    unexplained = [(a, b_) for a, b_ in empirical_le if a in idx and b_ in idx and not R[idx[a], idx[b_]]]
    return {"gap_relations": gap_rel, "gap_cells": sorted(gap_cells), "unexplained_le": unexplained, "n_empirical_le": len(empirical_le)}


def assemble(U: list, M: np.ndarray, skipped: int, n: int, seed0: int, seconds: float) -> dict:
    import relation_discovery_v2 as RD
    schema = DSC.build_schema()
    bad = check_declared(schema, U, M)
    if bad:
        raise RuntimeError("DECLARED_RELATION_FALSE_ON_SYNTH " + json.dumps(bad[:40], ensure_ascii=False))
    # 환자 칸은 집합 관계라 선형 선언 대상이 아니고 공개 안 함(허용 칸은 선언함) — 빈틈 대조는 비환자 칸만
    keep = [i for i, c in enumerate(U) if not c.endswith("/patients") and "patients" not in c.split("/")[1]]
    UK, MK = [U[i] for i in keep], M[:, keep]
    emp = RD.discover(UK, MK)
    empirical_eq = [dict(zip(e["cells"], e["coef"])) for e in emp["equalities"]]
    # 경험적 쌍별 부등식 전체(이행 폐포 전) — 축약 없이 다시 계산
    Uv = emp["varying"]
    Vi = MK[:, [UK.index(c) for c in Uv]]
    le_pairs = []
    for i in range(len(Uv)):
        le = (Vi[:, [i]] <= Vi).all(axis=0) & ~(Vi[:, [i]] == Vi).all(axis=0)
        le[i] = False
        le_pairs += [(Uv[i], Uv[j]) for j in np.nonzero(le)[0]]
    cov = coverage(schema, UK, MK, empirical_eq, le_pairs)
    gen_const = {c: v for c, v in emp["constant"].items() if c not in schema["constant"]}
    universe = sorted(set(U) | set(schema["schema_cells"]))
    return {"universe": universe, "equalities": schema["equalities"], "inequalities": schema["inequalities"],
            "inequality_reasons": schema["inequality_reasons"], "inequalities_general": schema["inequalities_general"],
            "constant": schema["constant"], "constant_reasons": schema["constant_reasons"], "generator_constant": gen_const,
            "external_cells": schema["external_cells"], "untrusted_cells": cov["gap_cells"],
            "coverage_report": {"n_runs": int(M.shape[0]), "n_cells": len(U), "n_declared_constant": len(schema["constant"]),
                                "n_generator_constant": len(gen_const), "n_empirical_equalities": len(empirical_eq),
                                "n_declared_equalities": len(schema["equalities"]), "n_gap_relations": len(cov["gap_relations"]),
                                "gap_relations": cov["gap_relations"], "n_empirical_pairwise_le": cov["n_empirical_le"],
                                "n_empirical_le_not_explained_by_schema": len(cov["unexplained_le"]),
                                "empirical_le_not_explained_sample(규칙으로 쓰지 않음, 앞 300쌍)": sorted(cov["unexplained_le"])[:300]},
            "created": datetime.now().isoformat(timespec="seconds"), "generator": "synth_random_v2", "seed0": seed0, "n_requested": n,
            "skipped_zero_match_guard_seeds": skipped, "seconds": round(seconds, 1),
            "note": "관계 = 스키마·프로토콜 선언. 합성 자료는 대조만(실제 MIMIC 미사용). 보호 코드·묶음 G 미사용"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--out", required=True, help="관계 JSON(이미 있으면 거부)")
    ap.add_argument("--cache", default=None, help="합성 집계 행렬 npz(있으면 재사용, 없으면 저장) — 선언 수정 중 재계산 절약")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit("이미 있음 — 덮어쓰지 않음")
    t = time.time()
    skipped = 0
    if a.cache and Path(a.cache).exists():
        z = np.load(a.cache, allow_pickle=False)
        U, M, skipped = [str(x) for x in z["U"]], z["M"], int(z["skipped"])
    else:
        import relation_discovery_v2 as RD
        U, M = RD.collect(a.n, a.seed0, log=lambda m: print(m, flush=True))
        skipped = len(RD.SKIPPED)
        if a.cache:
            np.savez_compressed(a.cache, U=np.array(U), M=M, skipped=skipped)
    rel = assemble(U, M, skipped, a.n, a.seed0, time.time() - t)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rel, ensure_ascii=False), encoding="utf-8")
    c = rel["coverage_report"]
    print("RELATIONS_V3_DONE", json.dumps({k: v for k, v in c.items() if k.startswith("n_")}, ensure_ascii=False), "untrusted", len(rel["untrusted_cells"]), flush=True)


if __name__ == "__main__":
    main()
