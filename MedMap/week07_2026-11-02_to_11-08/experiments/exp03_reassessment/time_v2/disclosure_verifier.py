"""EXP-03-TIME v2 공개 집계 역산 위험 독립 검증기(PROTOCOL_TIME_v2.md §9-2).

독립성: public_v2·disclosure_v2·run 의 묶음(G)을 import·사용하지 않는다. 입력은 (1) 실제 공개 JSON(파일을 다시 읽음),
(2) 관계 파일(스키마·프로토콜에서 선언한 관계, disclosure_schema + build_relations_v3). 최종 재검사는 보호기와 독립이지만 이 검증기를 다시 적용하는 것이다.
개정(2026-11-03): 합성 자료에서 우연히 성립한 관계를 규칙으로 쓰지 않는다. 이번 자료에서 거짓인 선언 관계·상수는 버리고 통과시키지 않고
그 관계의 칸 전부를 NOT_VERIFIABLE 로 처리한다(표 비공개).

검사(공격자 모형 — 공개 JSON + 관계 + 코드 공개 가정):
- 미지수 = 공개 숫자가 아닌 모든 관계 범위 칸('<10' → [1,9], MASKED_COMPLEMENT → [10,∞), PUBLIC_WITHHELD·누락 → [0,∞)).
- 제약 = 선언 선형 등식 + 쌍별 부등식 + 다항 부등식(Σ c·x ≤ 0) + 정의상 상수 칸(constant) + 이미 공개된 외부 값(external_known: EXP-02 집계).
- 공개 정수가 1–9 → FAILED(직접 노출).
- 각 미지수의 선형계획 최소·최대 → 정수 범위 [lo, hi]. hi ≥ 1, lo ≤ 9 이고 1 이상 후보 수(hi − max(lo,1) + 1) < MIN_CANDIDATES 면 FAILED
  (0 을 포함한 범위 [0,2], 9 를 걸친 범위 [8,11] 도 해당). MIN_CANDIDATES=5 는 정책 선택: '<10' 의 후보 9개 중 절반 미만으로 좁혀지면 실패로 봄.
- 비율: 공개 비율은 ratio_sources 의 분자·분모가 모두 공개 정수여야 함(아니면 FAILED). 차이도 두 비율이 공개여야 함.
- 환자 수: 집합(중복) 관계는 선형 검사 범위 밖 → 허용 목록 외 공개 환자 칸은 NOT_VERIFIABLE.
- 관계 범위 밖 숫자·토큰 칸, 상수 칸 불일치(토큰 포함), 생성기 미도달 칸(generator_constant)의 불일치, 이번 자료에서 거짓인 관계의 칸,
  검사 범위 공백 칸(untrusted_cells), 선형계획 불가능(관계와 공개값 모순) → NOT_VERIFIABLE.
한계: 선언되지 않은 부등식·비선형 관계, 정수 간극(LP 완화), 외부 공개 값 중 선형 관계로 정의되지 않은 값(관련 칸은 공개 범위에서 제외).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import csr_matrix

VERIFIED, FAILED, NOT_VERIFIABLE = "VERIFIED", "FAILED", "NOT_VERIFIABLE"
MIN_CANDIDATES = 5
INTEGER_RECHECK_HI = 40                                                # LP 상한이 이보다 크면 정수 간극으로 후보가 5 미만이 될 수 없다고 보지 않음(한계 명시) — 재확인 대상 경계
DATA_ROOTS = ("stays", "records", "denominator", "flags_by_policy", "grades_by_policy", "C_candidates_vs_used", "flags_merged",
              "usage", "states", "categories", "paired_crosstab_vs_STRICT", "rate_diff_vs_STRICT")
PATIENT_WHITELIST = {"stays/evaluated_patients"}
SMALL_TOKEN, COMPLEMENT_TOKEN, WITHHELD_TOKEN = "<10", "MASKED_COMPLEMENT", "PUBLIC_WITHHELD"
NA_TOKEN = "계산 불가"
EPS = 1e-6
LIMITS = ["관계는 스키마·프로토콜 선언분만 사용 — 선언되지 않은 구조적 관계는 합성 대조(coverage_report)로 찾은 범위까지만 차단, 완전성 보장 아님",
          "실제 자료에서 거짓인 선언 관계·상수가 걸린 칸은 NOT_VERIFIABLE → 표 비공개(버리고 통과시키지 않음)",
          "합성 생성기가 도달 못 한 칸(generator_constant)은 값이 다르면 비공개, 값이 같으면 공개 가능 — 그 칸에 대한 관계 검사는 약함",
          "정수 간극: LP 상한 40 이하 칸은 최종 판정에서 정수 계획으로 재확인, 그보다 큰 범위는 미재확인. 비선형 관계 미검사",
          "칸 단위 검사 — 전체 집계에 없는 작은 칸들의 합 자체는 칸이 아니면 미검사",
          "환자 수의 집합(중복) 관계는 미검사 → 평가·코호트 환자 칸 외 공개하지 않음",
          "외부 결합은 external_known 으로 선언한 EXP-02 값만 검사. 시간 감사·Ext-PE 등 다른 공개 집계는 정의가 달라 선형 관계로 넣지 않고, 겹칠 수 있는 칸은 공개 범위에서 제외",
          "최종 재검사는 보호기와 독립이지만 같은 검증기의 재적용임. 재검증에는 내부 정확 집계가 필요(외부 제3자 단독 재현 불가)"]
TOP_LEVEL_NON_DATA = {"ratio_sources", "unit_notes", "masking", "disclosure_check", "created", "protocol_version", "source_dir_name", "limit",
                      "input_key_dtypes", "code_sha256", "input_sha256", "graph_kb_sources", "software", "simulated_wd", "safety_checks",
                      "ext_pe_overlap_note", "interpretation", "status"}


def load_relations(path: Path) -> dict:
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    r["_index"] = {c: i for i, c in enumerate(r["universe"])}
    return r


def restrict_to_truth(rel: dict, truth: dict) -> tuple[dict, dict]:
    """선언 관계를 이번 자료 정확값(truth: 경로 문자열 → 정수)과 대조한다. 거짓인 관계는 '모형이 불완전하다'는 신호이므로 그 칸 전부를
    untrusted(NOT_VERIFIABLE → 표 비공개)로 표시한다 — 조용히 지우고 통과시키지 않는다. 자료에 없는 칸이 낀 관계도 대조 불가 → untrusted.
    거짓 관계 자체는 LP 제약에서 뺀다(그 칸들은 어차피 비공개). external_cells 값은 truth 에서 채운다(실제 실행은 run 이 EXP-02 공개값과 대조).
    반환 (대조된 관계, 건수 — 내부 기록용)."""
    untrusted = set(rel.get("untrusted_cells", ())) | set(rel.get("_untrusted", ()))

    def holds(cells, coef, le=False):
        if any(c not in truth for c in cells):
            return False
        total = sum(w * truth[c] for c, w in zip(cells, coef))
        return total <= 1e-6 if le else abs(total) < 1e-6
    eqs, ineq, gen, const = [], [], [], {}
    for e in rel["equalities"]:
        if holds(e["cells"], e["coef"]):
            eqs.append(e)
        else:
            untrusted.update(e["cells"])
    for x in rel.get("inequalities", []):
        if holds(x, (1.0, -1.0), le=True):
            ineq.append(x)
        else:
            untrusted.update(x)
    for e in rel.get("inequalities_general", []):
        if holds(e["cells"], e["coef"], le=True):
            gen.append(e)
        else:
            untrusted.update(e["cells"])
    for c, v in rel.get("constant", {}).items():
        if truth.get(c, 0) == v:
            const[c] = v
        else:
            untrusted.add(c)
    n_gen_false = 0
    for c, v in rel.get("generator_constant", {}).items():
        if truth.get(c, 0) != v:
            untrusted.add(c)
            n_gen_false += 1
    out = dict(rel, equalities=eqs, inequalities=ineq, inequalities_general=gen, constant=const)
    out["_index"] = {c: i for i, c in enumerate(out["universe"])}
    out["_untrusted"] = sorted(untrusted)
    out["_declared"] = rel.get("_declared") or {"n_equalities": len(rel["equalities"]), "n_pairwise_inequalities": len(rel.get("inequalities", [])),
                                                "n_general_inequalities": len(rel.get("inequalities_general", []))}
    ext = dict(rel.get("external_known", {}))
    for c in rel.get("external_cells", ()):
        if c not in ext and c in truth and truth[c] >= 10:            # 작은 합성 자료 전용 분기(실제 외부 값은 run 이 EXP-02 공개 파일에서 넣음, 전부 ≥ 10)
            ext[c] = truth[c]
    out["external_known"] = ext
    return out, {"equalities_false_on_data": len(rel["equalities"]) - len(eqs),
                 "inequalities_false_on_data": len(rel.get("inequalities", [])) - len(ineq) + len(rel.get("inequalities_general", [])) - len(gen),
                 "constants_false_on_data": len(rel.get("constant", {})) - len(const), "generator_constants_false_on_data": n_gen_false,
                 "n_untrusted_cells": len(untrusted)}


def flatten(d, prefix=()) -> dict:
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, prefix + (str(k),)))
    else:
        out["/".join(prefix)] = d
    return out


def _is_count(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _integer_range(obj_i: int, n: int, Aeq, beq, Aub, bub, bounds) -> tuple | None:
    """정수 제약 최소·최대. 반환 (lo, hi) · 풀 수 없으면 None(→ 검증 불가)."""
    lb = np.array([b[0] for b in bounds], dtype=float)
    ub = np.array([np.inf if b[1] is None else b[1] for b in bounds], dtype=float)
    cons = []
    if Aeq is not None:
        cons.append(LinearConstraint(Aeq, beq, beq))
    if Aub is not None:
        cons.append(LinearConstraint(Aub, -np.inf, bub))
    out = []
    for sgn in (1.0, -1.0):
        c = np.zeros(n)
        c[obj_i] = sgn
        res = milp(c, constraints=cons, integrality=np.ones(n), bounds=Bounds(lb, ub), options={"time_limit": 20})
        if res.status != 0 or res.x is None:
            return None
        out.append(round(float(res.x[obj_i])))
    return out[0], out[1]


def verify_flat(flat: dict, ratio_sources: dict, rel: dict, integer_check: bool = False) -> dict:
    """flat: 공개 JSON 을 펼친 {경로: 값}. 반환 {status, failed:[경로], not_verifiable:[경로], components…}.
    integer_check=True: LP 로 통과한 칸 중 범위가 INTEGER_RECHECK_HI 이하인 칸을 정수 계획으로 재확인(정수 간극). 풀지 못하면 NOT_VERIFIABLE."""
    idx, U = rel["_index"], rel["universe"]
    const = rel.get("constant", {})
    gen_const = rel.get("generator_constant", {})
    external = rel.get("external_known", {})
    untrusted = set(rel.get("_untrusted", ())) | set(rel.get("untrusted_cells", ()))
    failed, nv = [], []
    data = {k: v for k, v in flat.items() if k.split("/")[0] in DATA_ROOTS}
    # 1) 비율·차이
    for rp, srcs in ratio_sources.items():
        v = data.get(rp)
        if v is None or isinstance(v, str):
            continue
        for sp in srcs:
            sv = flat.get(sp)
            ok = isinstance(sv, (int, float)) and not isinstance(sv, bool) if sp in ratio_sources else _is_count(sv)
            if not ok:
                failed.append(rp)                                      # 분자·분모(또는 출처 비율)가 공개 아님 → 비율이 숨긴 값을 드러냄
    for k, v in data.items():
        if isinstance(v, float) and k not in ratio_sources:
            nv.append(k)                                               # 출처 선언 없는 소수 = 검증 불가
    # 2) 공개 숫자 칸 분류
    known, unknown = {}, {}
    for k, v in data.items():
        if k in ratio_sources:
            continue
        is_token = v in (SMALL_TOKEN, COMPLEMENT_TOKEN)
        if k in untrusted and (_is_count(v) or is_token):              # 관계 모형이 이번 자료를 설명 못 함·검사 범위 공백 → 공개 금지
            nv.append(k)
            continue
        if is_token and (k in const or k in gen_const or k not in idx):   # 상수 칸에 작은 값 토큰 = 불일치 / 관계 범위 밖 토큰 = 검증 불가
            nv.append(k)
            continue
        if k in gen_const and _is_count(v) and gen_const[k] != v:
            nv.append(k)
            continue
        if k in external and _is_count(v) and external[k] != v:
            nv.append(k)
            continue
        if k.endswith("/patients") and k not in PATIENT_WHITELIST and _is_count(v):
            nv.append(k)
            continue
        if _is_count(v):
            if k not in idx:
                nv.append(k)
                continue
            if k in const and const[k] != v:
                nv.append(k)
                continue
            if 1 <= v <= 9 and k not in external:                      # 공개 정수 1–9 직접 노출(보호 단계와 무관하게 검증기가 직접 차단)
                failed.append(k)
            known[k] = v
        elif v == SMALL_TOKEN:
            unknown[k] = (1, 9)
        elif v == COMPLEMENT_TOKEN:
            unknown[k] = (10, None)
        elif v == WITHHELD_TOKEN:
            unknown[k] = (0, None)
    for c, v in external.items():                                     # 이미 공개된 외부 값(EXP-02 등)은 공격자가 앎 — 이번 공개본에 있든 없든
        unknown.pop(c, None)
        known[c] = v
    for c in U:                                                       # 공개 JSON 에 없는 관계 칸도 미지수(공격자는 존재를 앎)
        if c not in known and c not in unknown:
            unknown[c] = (const[c], const[c]) if c in const else (0, None)
    for c, v in const.items():                                        # 상수 칸은 공격자가 앎
        if c in unknown and unknown[c][0] != unknown[c][1]:
            if unknown[c][0] <= v and (unknown[c][1] is None or v <= unknown[c][1]):
                unknown[c] = (v, v)
    # 3) 성분별 선형계획
    eqs = rel["equalities"]
    ineq = rel.get("inequalities", [])
    adj = defaultdict(set)
    for e in eqs:
        cs = e["cells"]
        for a in cs:
            adj[a].update(cs)
    for a, b in ineq:
        adj[a].add(b)
        adj[b].add(a)
    gen_ineq = rel.get("inequalities_general", [])
    for e in gen_ineq:
        cs = e["cells"]
        for a in cs:
            adj[a].update(cs)
    seen, comps = set(), []
    for c in unknown:
        if c in seen:
            continue
        stack, comp = [c], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack.extend(adj.get(x, ()))
        seen |= comp
        comps.append(comp)
    eq_by_cell = defaultdict(list)
    for i, e in enumerate(eqs):
        for c in e["cells"]:
            eq_by_cell[c].append(i)
    ineq_by_cell = defaultdict(list)
    for i, (a, b) in enumerate(ineq):
        ineq_by_cell[a].append(i)
        ineq_by_cell[b].append(i)
    gen_by_cell = defaultdict(list)
    for i, e in enumerate(gen_ineq):
        for c in e["cells"]:
            gen_by_cell[c].append(i)
    n_lp = 0
    n_milp = 0
    linked = {}
    for comp in comps:
        unk = sorted(c for c in comp if c in unknown)
        # 생성기 미도달 칸은 값이 선언과 같을 때만 여기 도달(다르면 untrusted) — 그 값이 0 이면 지킬 작은 건수가 없어 범위 검사 생략
        cand = [c for c in unk if unknown[c][0] != unknown[c][1] and unknown[c][0] <= 9 and gen_const.get(c) != 0]
        has_info = any(c in known for c in comp) or any(unknown[c][0] > 0 or unknown[c][1] is not None for c in unk)
        if not cand or not has_info:
            continue                                                   # 공개 정보가 없는 성분 = 범위 [0,∞) 그대로
        pos = {c: i for i, c in enumerate(unk)}
        A_eq, b_eq, A_ub, b_ub = [], [], [], []
        for i in sorted({j for c in comp for j in eq_by_cell.get(c, ())}):
            e = eqs[i]
            row, rhs = np.zeros(len(unk)), 0.0
            for c, w in zip(e["cells"], e["coef"]):
                if c in pos:
                    row[pos[c]] += w
                else:
                    rhs -= w * known[c]
            if not np.any(np.abs(row) > EPS):
                if abs(rhs) > 1e-4 * max(1.0, sum(abs(w) for w in e["coef"])):
                    nv.extend(cand)                                    # 공개값끼리 관계와 모순 → 검증 불가
                continue
            A_eq.append(row)
            b_eq.append(rhs)
        for i in sorted({j for c in comp for j in ineq_by_cell.get(c, ())}):
            a, b = ineq[i]                                             # x_a ≤ x_b
            row, rhs = np.zeros(len(unk)), 0.0
            for c, w in ((a, 1.0), (b, -1.0)):
                if c in pos:
                    row[pos[c]] += w
                elif c in known:
                    rhs -= w * known[c]
            if np.any(np.abs(row) > EPS):
                A_ub.append(row)
                b_ub.append(rhs)
        for i in sorted({j for c in comp for j in gen_by_cell.get(c, ())}):
            e = gen_ineq[i]                                            # Σ c·x ≤ 0
            row, rhs = np.zeros(len(unk)), 0.0
            for c, w in zip(e["cells"], e["coef"]):
                if c in pos:
                    row[pos[c]] += w
                elif c in known:
                    rhs -= w * known[c]
            if np.any(np.abs(row) > EPS):
                A_ub.append(row)
                b_ub.append(rhs)
        bounds = [unknown[c] for c in unk]
        Aub = csr_matrix(np.array(A_ub)) if A_ub else None                # 성분당 1회 구성 후 재사용(목적함수만 바뀜)
        bub = np.array(b_ub) if b_ub else None
        Aeq = csr_matrix(np.array(A_eq)) if A_eq else None
        beq = np.array(b_eq) if b_eq else None
        for c in cand:
            lo_hi = []
            for sgn in (-1.0, 1.0):                                    # 최대 먼저 — 무한대·충분히 크면 최소 불필요
                obj = np.zeros(len(unk))
                obj[pos[c]] = sgn
                res = linprog(obj, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
                n_lp += 1
                if res.status == 2:                                    # 불가능 → 관계·공개값 모순
                    lo_hi = None
                    break
                if res.status not in (0, 3):                           # 수치 실패 → 검증 불가
                    lo_hi = None
                    break
                val = None if res.status == 3 else sgn * res.fun
                lo_hi.append(val)
                if sgn < 0 and (val is None or val >= (INTEGER_RECHECK_HI if integer_check else 9 + MIN_CANDIDATES) + 1 - EPS):
                    break                                              # 충분히 크거나 위로 열림(정수 재확인 시 경계까지는 최소도 계산)
            if lo_hi is None:
                nv.append(c)
                continue
            if len(lo_hi) == 1:
                continue
            hi = math.floor(lo_hi[0] + EPS)
            lo = math.ceil(lo_hi[1] - EPS)
            if hi < lo:                                                # 정수 해 없음 → 관계·공개값 모순
                nv.append(c)
                continue
            if hi >= 1 and lo <= 9 and hi - max(lo, 1) + 1 < MIN_CANDIDATES:
                failed.append(c)
                linked[c] = sorted(x for x in comp if x in known)      # 역산에 쓰인 공개 칸 후보(같은 관계 성분)
            elif integer_check and hi >= 1 and lo <= 9 and hi <= INTEGER_RECHECK_HI:
                n_milp += 1
                ir = _integer_range(pos[c], len(unk), Aeq, beq, Aub, bub, bounds)
                if ir is None:
                    nv.append(c)
                elif ir[1] >= 1 and ir[0] <= 9 and ir[1] - max(ir[0], 1) + 1 < MIN_CANDIDATES:
                    failed.append(c)
                    linked[c] = sorted(x for x in comp if x in known)
    status = FAILED if failed else NOT_VERIFIABLE if nv else VERIFIED
    return {"status": status, "failed": sorted(set(failed)), "not_verifiable": sorted(set(nv)), "n_lp": n_lp, "n_milp": n_milp, "integer_check": integer_check, "linked_public": linked,
            "scope": {"min_candidates": MIN_CANDIDATES, **(rel.get("_declared") or {"n_equalities": len(eqs), "n_pairwise_inequalities": len(ineq),
                                                                                    "n_general_inequalities": len(gen_ineq)}),
                      "n_universe": len(U), "n_external_known": len(external)}, "limits": LIMITS}


def verify_file(path: Path, rel: dict, integer_check: bool = True) -> dict:
    pub = json.loads(Path(path).read_text(encoding="utf-8"))
    extra = sorted(set(pub) - set(DATA_ROOTS) - TOP_LEVEL_NON_DATA)
    if extra:                                                          # 선언 안 된 최상위 항목 = 검증 범위 밖
        return {"status": NOT_VERIFIABLE, "failed": [], "not_verifiable": extra, "n_lp": 0, "linked_public": {}, "scope": {}, "limits": LIMITS}
    return verify_flat(flatten({k: v for k, v in pub.items() if k in DATA_ROOTS}), pub.get("ratio_sources", {}), rel, integer_check=integer_check)
