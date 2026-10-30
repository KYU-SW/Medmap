#!/usr/bin/env python3
"""EXP-SN-NBI-004 NBI-B1S — B1 Troponin 51003 신호의 최소 민감도 진단(LOCAL ONLY). B1 결과·코드는 수정하지 않는다.

코호트·라벨·lab 적격 규칙·baseline·모형·split·bootstrap 은 고정 B1 모듈(b1_feasibility, pinned)을 import 해 그대로 쓴다.
바뀌는 것은 분석 대상 행(subset) 제한과 결과 집계뿐이다.
  A0 재현 점검: 전체 ACS~PE 51003 측정 subset 의 점추정(M0·M1·Δ, 소수 2자리)이 B1 공개값과 같아야 함(아니면 INVALID).
  TEST A(참조 표준 민감도): ACS 를 B0a 고정 ACS_SUB 코드로만 나눔 — MI형 = MI 하위코드 ≥1개, UA형 = UA 하위코드만.
        A1 = MI형 ACS vs PE, A2 = UA형 ACS vs PE, 각각 B1 과 같은 B.cell(TROPONIN, 51003).
  TEST B(측정 선택 진단): B1 전체 코호트에서 결과변수 M = 51003 측정 subset 소속(B1 셀 분모와 동일 정의),
        입력 = B1 baseline 8개만, 같은 oof·fold 평균 AUROC·재적합 bootstrap. pooled(주) + class 내(ACS·PE, 보조).
  음성 대조 1회: 51003 측정 subset 안에서 lab 값을 고정 seed 로 한 번 섞은 뒤 점추정 Δ(구현 sanity, bias 교정 아님).
공개 = 사전 고정 키·어휘·소수 2자리 지표. exact count·계수·환자 단위 예측은 봉인(예측은 저장하지 않음).
"""
import argparse
import json
import os
import random
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "b1"))
import b1_feasibility as B  # noqa: E402  (고정 B1 모듈, 수정 금지)

A = B.A
C = B.C
CONCEPT, ITEM = "TROPONIN", "51003"
MI_SUB = ("STEMI", "NSTEMI", "MI_UNSPEC", "SUBSEQUENT")
PERM_SEED = 20261007  # 음성 대조 1회 섞기 seed(결과 전 고정)
NC_TOL = 0.02  # 음성 대조 |Δ| ≤ 이 값이면 NC_PASS
SEL_MIN_AUROC = 0.60  # 선택 신호: fold 평균 AUROC ≥ 0.60 ∧ 95 % CI 하한 > 0.50
ATTEN_RATIO = 0.5  # 감쇠: Δ(UA) ≤ 0.5 × Δ(MI)
CELL_KEYS = ("status", "n_bucket_acs", "n_bucket_pe", "auroc_m0", "auroc_m1", "delta", "delta_ci_lo", "delta_ci_hi",
             "auroc_value_only")
SEL_KEYS = ("status", "auroc", "ci_lo", "ci_hi")
FINAL = {"SIGNAL_MOSTLY_REFERENCE_DEPENDENT", "SIGNAL_PERSISTS_BEYOND_MI_SUBTYPE", "REFERENCE_SENSITIVITY_NOT_EVALUABLE"}
REASON = {"UA_CI_ABOVE_ZERO", "UA_ATTENUATED", "UA_NOT_ATTENUATED", "UA_ATTENUATION_UNRESOLVED", "UA_IMPRECISE",
          "UA_DIRECTION_REVERSED", "MI_CI_NOT_ABOVE_ZERO", "MI_NOT_EVALUABLE", "UA_INSUFFICIENT_DATA",
          "UA_NOT_EVALUABLE_UNIT", "UA_NOT_EVALUABLE_MODEL"}
SEL_STATUS = {"SELECTION_SIGNAL_PRESENT", "SELECTION_SIGNAL_WEAK_OR_UNRESOLVED", "INSUFFICIENT_DATA",
              "NOT_EVALUABLE_MODEL"}
EVAL = ("FEASIBLE", "EVALUABLE_IMPRECISE")


def keyspec():
    """공개 키 → 허용 형식('AUROC'·'DELTA' = WITHHELD 또는 소수 2자리 + 범위, set = 어휘)."""
    cellv = {"status": B.CELL_STATUS, "n_bucket_acs": B.LEAF_VOCAB["n_bucket_acs"],
             "n_bucket_pe": B.LEAF_VOCAB["n_bucket_pe"], "auroc_m0": "AUROC", "auroc_m1": "AUROC", "delta": "DELTA",
             "delta_ci_lo": "DELTA", "delta_ci_hi": "DELTA", "auroc_value_only": "AUROC"}
    selv = {"status": SEL_STATUS, "auroc": "AUROC", "ci_lo": "AUROC", "ci_hi": "AUROC"}
    bins = set(A.SHARE_BINS) | {"WITHHELD"}
    ks = {"pair.status": {"EVALUABLE", "NOT_EVALUABLE"}, "pair.cohort_pooled_bucket": {b[2] for b in A.POOL_BUCKETS},
          "reproduction.status": {"REPRODUCED"},
          "test_a.interpretation": FINAL, "test_a.reason": REASON,
          "test_b.acs_measured_bin": bins, "test_b.pe_measured_bin": bins,
          "negative_control.delta": "DELTA", "negative_control.status": {"NC_PASS", "NC_FLAG", "NOT_EVALUABLE"}}
    for c in ("mi_vs_pe", "ua_vs_pe"):
        ks.update({f"test_a.{c}.{k}": v for k, v in cellv.items()})
    for c in ("pooled", "within_acs", "within_pe"):
        ks.update({f"test_b.{c}.{k}": v for k, v in selv.items()})
    return ks


def guard(pub):
    ks = keyspec()
    bad = []
    for k, v in A.flatten(pub):
        spec = ks.get(k)
        if spec is None or not isinstance(v, str):
            bad.append(k)
        elif isinstance(spec, set):
            if v not in spec:
                bad.append(k)
        elif v != "WITHHELD":
            lo = 0.0 if spec == "AUROC" else -1.0
            if not (B.METRIC_RX.match(v) and lo <= float(v) <= 1.0):
                bad.append(k)
    return bad


def subtype(r):
    """B0a ACS_SUB 코드만 사용: PE / MI(MI 하위코드 ≥1, UA 동반 포함) / UA(UA 하위코드만) / UNASSIGNED."""
    if r["cls"] == "PE":
        return "PE"
    s = set(r["acs_sub"])
    if s & set(MI_SUB):
        return "MI"
    if s == {"UA"}:
        return "UA"
    return "UNASSIGNED"


def measured(r):
    """B1 셀 분모와 같은 정의: 첫 적격 Troponin 결과가 51003 이고 사용 가능(수치 또는 중도절단)."""
    lab = r["labs"][CONCEPT]
    return lab["status"] in B.USABLE and lab["item"] == ITEM


def point(rows, perm_seed=None):
    """B.cell 과 같은 subset·정렬·fold 로 점추정만(bootstrap 없음). perm_seed 가 있으면 lab 값을 한 번 섞음."""
    sub = sorted((r for r in rows if measured(r)), key=lambda r: int(r["subject"]))
    y = [r["y"] for r in sub]
    x = [r["labs"][CONCEPT]["x"] for r in sub]
    if perm_seed is not None:
        random.Random(perm_seed).shuffle(x)
    base = [r["base"] for r in sub]
    folds = B.strat_folds([r["subject"] for r in sub], y)
    a0 = B.fold_auroc(B.oof(base, y, folds), y, folds)
    a1 = B.fold_auroc(B.oof(base, y, folds, lab=x), y, folds)
    return a0, a1, a1 - a0


def interpret(p1, s1, p2, s2):
    """사전 고정 판정(반올림 전 봉인 값 사용). 반환 (interpretation, reason)."""
    nev = "REFERENCE_SENSITIVITY_NOT_EVALUABLE"
    if p2["status"] not in EVAL:
        return nev, {"INSUFFICIENT_DATA": "UA_INSUFFICIENT_DATA", "NOT_EVALUABLE_UNIT": "UA_NOT_EVALUABLE_UNIT"}.get(
            p2["status"], "UA_NOT_EVALUABLE_MODEL")
    if p1["status"] not in EVAL:
        return nev, "MI_NOT_EVALUABLE"
    if (s1["auroc_value_only"] - 0.5) * (s2["auroc_value_only"] - 0.5) <= 0:  # lab 단독 방향이 A1 과 반대(또는 0.5)
        return nev, "UA_DIRECTION_REVERSED"
    if s2["delta_ci"][0] > 0:
        return "SIGNAL_PERSISTS_BEYOND_MI_SUBTYPE", "UA_CI_ABOVE_ZERO"
    if s1["delta_ci"][0] <= 0:
        return nev, "MI_CI_NOT_ABOVE_ZERO"
    if p2["status"] != "FEASIBLE":
        return nev, "UA_IMPRECISE"
    if s2["delta"] > ATTEN_RATIO * s1["delta"]:
        return nev, "UA_NOT_ATTENUATED"
    if s2["delta_ci"][1] >= s1["delta"]:  # A2 CI 가 A1 점추정을 포함 → 감쇠 미확정
        return nev, "UA_ATTENUATION_UNRESOLVED"
    return "SIGNAL_MOSTLY_REFERENCE_DEPENDENT", "UA_ATTENUATED"


def selection(rows):
    """측정 선택 진단: y = measured(r), 입력 = baseline 8개만. 반환 (공개, 봉인)."""
    m = [1 if measured(r) else 0 for r in rows]
    n1, n0 = sum(m), len(m) - sum(m)
    S = {"n_measured": n1, "n_unmeasured": n0}
    P = {"status": "INSUFFICIENT_DATA", "auroc": "WITHHELD", "ci_lo": "WITHHELD", "ci_hi": "WITHHELD"}
    if min(n1, n0) < B.N_MIN_B1:
        return P, S
    base = [r["base"] for r in rows]
    folds = B.strat_folds([r["subject"] for r in rows], m)
    try:
        a = B.fold_auroc(B.oof(base, m, folds), m, folds)
        lo, hi, fail = B.boot_ci(base, m, folds)
        if lo is None or fail > B.BOOT_FAIL_MAX * B.B_BOOT:
            raise ArithmeticError(f"bootstrap_failures={fail}")
    except ArithmeticError as e:
        P["status"] = "NOT_EVALUABLE_MODEL"
        S["model_error"] = str(e)
        return P, S
    S.update({"auroc": a, "ci": [lo, hi], "boot_failures": fail})
    st = "SELECTION_SIGNAL_PRESENT" if lo > 0.5 and a >= SEL_MIN_AUROC else "SELECTION_SIGNAL_WEAK_OR_UNRESOLVED"
    P.update({"status": st, "auroc": B.fmt(a), "ci_lo": B.fmt(lo), "ci_hi": B.fmt(hi)})
    return P, S


def build_b1s(d, b1_pub):
    """반환 (public, sealed) 또는 ('INVALID', 이유)."""
    rows = sorted(d["b1_rows"].values(), key=lambda r: int(r["subject"]))
    na = sum(1 for r in rows if r["cls"] == "ACS")
    npe = len(rows) - na
    pub = {"pair": {"status": "EVALUABLE" if na and npe else "NOT_EVALUABLE",
                    "cohort_pooled_bucket": A.pool_bucket(na + npe)}}
    ref = b1_pub["TROPONIN"]["assays"][ITEM]
    if pub["pair"] != b1_pub["pair"] or ref["status"] not in EVAL:
        return "INVALID", "b1_cohort_mismatch"
    a0, a1, dl = point(rows)
    if (B.fmt(a0), B.fmt(a1), B.fmt(dl)) != (ref["auroc_m0"], ref["auroc_m1"], ref["delta"]):
        return "INVALID", "b1_reproduction_mismatch"
    pub["reproduction"] = {"status": "REPRODUCED"}
    st = {r["subject"]: subtype(r) for r in rows}
    sealed = {"reproduction": {"auroc_m0": a0, "auroc_m1": a1, "delta": dl},
              "subtype_counts": {t: {"all": sum(1 for v in st.values() if v == t),
                                     "measured_51003": sum(1 for r in rows if st[r["subject"]] == t and measured(r))}
                                 for t in ("MI", "UA", "UNASSIGNED", "PE")},
              "mi_with_ua_code": sum(1 for r in rows if st[r["subject"]] == "MI" and "UA" in r["acs_sub"])}
    p1, s1 = B.cell([r for r in rows if st[r["subject"]] in ("MI", "PE")], CONCEPT, ITEM)
    p2, s2 = B.cell([r for r in rows if st[r["subject"]] in ("UA", "PE")], CONCEPT, ITEM)
    interp, reason = interpret(p1, s1, p2, s2)
    pub["test_a"] = {"mi_vs_pe": p1, "ua_vs_pe": p2, "interpretation": interp, "reason": reason}
    sealed["test_a"] = {"mi_vs_pe": s1, "ua_vs_pe": s2}
    tb, sb = {}, {}
    for k, sel in (("pooled", rows), ("within_acs", [r for r in rows if r["cls"] == "ACS"]),
                   ("within_pe", [r for r in rows if r["cls"] == "PE"])):
        tb[k], sb[k] = selection(sel)
    ma = sum(1 for r in rows if r["cls"] == "ACS" and measured(r))
    mp = sum(1 for r in rows if r["cls"] == "PE" and measured(r))
    tb["acs_measured_bin"] = A.share_bin(ma, na) if na >= A.SHARE_MIN_POOL else "WITHHELD"
    tb["pe_measured_bin"] = A.share_bin(mp, npe) if npe >= A.SHARE_MIN_POOL else "WITHHELD"
    pub["test_b"] = tb
    sealed["test_b"] = sb
    try:
        _, _, dn = point(rows, perm_seed=PERM_SEED)
        pub["negative_control"] = {"delta": B.fmt(dn), "status": "NC_PASS" if abs(dn) <= NC_TOL else "NC_FLAG"}
        sealed["negative_control"] = {"delta": dn}
    except ArithmeticError as e:
        pub["negative_control"] = {"delta": "WITHHELD", "status": "NOT_EVALUABLE"}
        sealed["negative_control"] = {"model_error": str(e)}
    return pub, sealed


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("ed-zip", "ed-zip-sha", "ecg-zip", "ecg-zip-sha", "labevents", "labevents-sha", "d-labitems",
              "d-labitems-sha", "patients", "patients-sha", "schema", "schema-sha", "b1-public", "b1-public-sha",
              "out", "sealed", "private-log"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    for p in (a.out, a.sealed):
        if os.path.exists(p):
            print("B1S_VERDICT INVALID reason=output_exists stage=preflight")
            return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.private_log)), exist_ok=True)
    plog = open(a.private_log, "a", encoding="utf-8")
    old_err, sys.stderr = sys.stderr, plog
    stage = "preflight"
    try:
        for p, h in ((a.ed_zip, a.ed_zip_sha), (a.ecg_zip, a.ecg_zip_sha), (a.labevents, a.labevents_sha),
                     (a.d_labitems, a.d_labitems_sha), (a.patients, a.patients_sha), (a.schema, a.schema_sha),
                     (a.b1_public, a.b1_public_sha)):
            if A.sha256(p) != h:
                print("B1S_VERDICT INVALID reason=sha_mismatch stage=preflight")
                return 2
        im = C.item_map(a.d_labitems)
        if im != C.ITEMS or frozenset(B.CONCEPTS[CONCEPT]) != C.ITEMS[B.CONCEPT_B0C[CONCEPT]]:
            print("B1S_VERDICT INVALID reason=item_map_mismatch stage=preflight")
            return 2
        stage = "data"
        d = B.compute_b1(a.ed_zip, a.ecg_zip, a.labevents, a.patients)
        if d["verdict"] == "STOP_TITLE":
            print("B1S_VERDICT STOP_TITLE classes=" + ",".join(d["stop_classes"]))
            return 3
        b1_pub = json.load(open(a.b1_public, encoding="utf-8"))
        pub, sealed = build_b1s(d, b1_pub)
        if pub == "INVALID":
            print(f"B1S_VERDICT INVALID reason={sealed} stage=data")
            return 2
        schema = json.load(open(a.schema, encoding="utf-8"))
        if sorted(k for k, _ in A.flatten(pub)) != sorted(schema["keys"]) or sorted(schema["keys"]) != sorted(keyspec()):
            print("B1S_VERDICT INVALID reason=schema_mismatch stage=data")
            return 2
        if guard(pub):
            print("B1S_VERDICT INVALID reason=output_guard stage=data")
            return 2
        os.makedirs(a.sealed)
        os.chmod(a.sealed, 0o700)
        sp = os.path.join(a.sealed, "b1s_sealed.json")
        json.dump(sealed, open(sp, "w", encoding="utf-8"), sort_keys=True, indent=1, default=str)
        pub["meta"] = {"experiment": "EXP-SN-NBI-004", "phase": "B1S", "source_experiment": "EXP-SN-NBI-003",
                       "assay": f"{CONCEPT} {ITEM}", "subtype_source": "B0a ACS_SUB ICD code sets (unchanged)",
                       "mi_subcodes": list(MI_SUB), "ua_rule": "UA subcode only (no MI subcode)",
                       "n_min": B.N_MIN_B1, "k_folds": B.K_FOLDS, "ridge": B.RIDGE, "n_boot": B.B_BOOT,
                       "boot_seed": B.BOOT_SEED, "perm_seed": PERM_SEED, "nc_tol": NC_TOL,
                       "sel_min_auroc": SEL_MIN_AUROC, "atten_ratio": ATTEN_RATIO,
                       "ci_note": "95 % percentile refit bootstrap, no multiplicity adjustment; A1/A2 share the PE "
                       "group (CIs not independent, do not compare by overlap)",
                       "estimand": "sensitivity of measured-subset label-conditioned separation to MI-associated "
                       "label dependence; measurement-selection association with baseline (not clinical value)",
                       "disclosure": "status vocabulary, size buckets, 10 %p bins and 2-decimal AUROC metrics only; "
                       "exact counts and per-fold values sealed; patient-level predictions not stored",
                       "ed_zip_sha256": a.ed_zip_sha, "ecg_zip_sha256": a.ecg_zip_sha,
                       "labevents_sha256": a.labevents_sha, "d_labitems_sha256": a.d_labitems_sha,
                       "patients_sha256": a.patients_sha, "schema_sha256": a.schema_sha,
                       "b1_public_sha256": a.b1_public_sha,
                       "script_sha256": A.sha256(os.path.abspath(__file__)),
                       "b1_module_sha256": A.sha256(os.path.abspath(B.__file__)),
                       "sealed_file_sha256": A.sha256(sp), "python": sys.version.split()[0]}
        os.makedirs(a.out)
        op = os.path.join(a.out, "b1s_public.json")
        json.dump(pub, open(op, "w", encoding="utf-8"), sort_keys=True, indent=1)
        with open(os.path.join(a.out, "B1S_SHA256SUMS"), "w", encoding="utf-8") as f:
            f.write(f"{A.sha256(op)}  b1s_public.json\n")
        print("B1S_VERDICT COMPLETE")
        return 0
    except Exception as e:  # 행 값이 담길 수 있는 메시지는 비공개 로그로만
        traceback.print_exc(file=plog)
        print(f"B1S_VERDICT INVALID exception={type(e).__name__} stage={stage}")
        return 2
    finally:
        sys.stderr = old_err
        plog.close()


if __name__ == "__main__":
    sys.exit(main())
