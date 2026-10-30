#!/usr/bin/env python3
"""EXP-SN-NBI-003 NBI-B1 (rev2) — ACS vs PE retrospective FEASIBILITY of Troponin / D-dimer label-conditioned separation.

LOCAL ONLY. 코호트·라벨은 고정 B0a 모듈(b0a_availability.compute)의 ACS~PE 쌍 그대로(ED 퇴원 ICD = 참조 라벨, 입력 금지).
index = ED intime(T0). 입력 allowlist(사전 고정):
  baseline(T0 상태) = 나이(patients anchor_age·anchor_year 로 stay 연도 보정), 성별(patients gender), triage 활력 6개
  lab = 고정 itemid(B0c 동결 사전 매핑)의 첫 적격 결과 1개 — 가용 시각 storetime ∈ [intime, min(intime+6h, outtime)]
        ∧ charttime ≥ intime(또는 결측) ∧ [E] 배정 stay. 측정법(itemid)별로만 분석(합치지 않음), 정규화 단위 불일치면 NOT_EVALUABLE.
금지: 진단 코드·퇴원 정보·chiefcomplaint·acuity·pain·hadm_id·disposition·dod·flag·ref_range·priority·comments·radiology·ECG 진단,
      검사 시행 여부·순서를 입력으로 사용, threshold 이분화, hyperparameter 탐색.
분석 A(측정 subset): 측정법별 ΔAUROC = fold 평균 OOF AUROC(baseline + 표준화 lab 순위) − fold 평균 OOF AUROC(baseline),
      95 % CI = class 층화 subject 재적합 bootstrap(복제 subject 는 원 fold 유지). 분석 B(측정 선택): class별 측정 비율 구간 — 기술만.
공개 = 사전 고정 키·어휘·소수 2자리 지표(값 범위 검사)뿐. exact n·class 수·계수·환자 단위 예측은 봉인(예측은 저장하지 않음).
"""
import argparse
import bisect
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import random
import re
import sys
import traceback
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "b0"))
import b0a_availability as A  # noqa: E402  (고정 B0a 모듈: 코호트·코드표, 수정 금지)
import b0c_availability as C  # noqa: E402  (고정 B0c 모듈: itemid 매핑 재검증, 수정 금지)

PAIR = "ACS~PE"
CONCEPTS = {"TROPONIN": ("51002", "51003", "52642"), "DDIMER": ("50915", "51196", "52551")}
CONCEPT_B0C = {"TROPONIN": "BIOMARKER_TROPONIN", "DDIMER": "BIOMARKER_DDIMER"}
ITEM2CONCEPT = {i: c for c, ids in CONCEPTS.items() for i in ids}
LAB_ALLOW = ["subject_id", "itemid", "charttime", "storetime", "value", "valuenum", "valueuom"]
TRIAGE_ALLOW = ["stay_id", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp"]
PAT_ALLOW = ["subject_id", "gender", "anchor_age", "anchor_year"]
VITAL_RANGE = {"temperature": (90.0, 110.0), "heartrate": (20.0, 250.0), "resprate": (4.0, 60.0),
               "o2sat": (50.0, 100.0), "sbp": (40.0, 300.0), "dbp": (20.0, 200.0)}
BASE = ["age", "female", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp"]
WINDOW_H = 6  # 사전 고정(manifest [C] W6), 결과 보고 변경 금지
N_MIN_B1 = 50  # 진입 문턱: 측정법별 class 당 최소 측정 subject(단일 AUROC Hanley–McNeil 근거, FEASIBLE 은 실측 CI 로 따로 판정)
K_FOLDS = 5
SPLIT_SALT = "EXP-SN-NBI-003"
RIDGE = 1.0  # 표준화 특징(baseline·lab 순위 모두) 계수 L2(절편 제외), 고정 — 탐색 없음
IRLS_MAX, IRLS_TOL = 100, 1e-8
B_BOOT, BOOT_SEED = 1000, 20261006  # 재적합 bootstrap 반복 수·seed(결과 전 고정)
BOOT_FAIL_MAX = 0.01  # 재적합 실패 반복 비율이 이 값 초과면 NOT_EVALUABLE_MODEL
FEASIBLE_HALF_WIDTH = 0.10  # ΔAUROC 95 % CI 반폭(반올림 전) ≤ 이 값이면 FEASIBLE(정밀도 기준, 방향·크기 무관)
CENS_OFFSET = 1e12  # 중도절단 순위 배치: '<b' 는 모든 측정값 아래, '>b' 는 위(경계값끼리는 b 순서)
N_BUCKETS = [(0, 50, "LT_50"), (50, 100, "50_99"), (100, 500, "100_499"), (500, 1000, "500_999"),
             (1000, 5000, "1000_4999"), (5000, float("inf"), "GE_5000")]
CENS = re.compile(r"^\s*([<>])\s*=?\s*([0-9]*\.?[0-9]+)\s*$")
USABLE = ("MEASURED_NUMERIC", "MEASURED_CENSORED")
CELL_STATUS = {"FEASIBLE", "EVALUABLE_IMPRECISE", "INSUFFICIENT_DATA", "NOT_EVALUABLE_UNIT", "NOT_EVALUABLE_MODEL",
               "NOT_EVALUABLE_PAIR"}
CONCEPT_STATUS = {"FEASIBLE", "EVALUABLE", "INSUFFICIENT_DATA", "NOT_EVALUABLE"}
METRIC_RX = re.compile(r"^-?\d\.\d\d$")
AUROC_KEYS = ("auroc", "ci_lo", "ci_hi", "auroc_m0", "auroc_m1", "auroc_value_only")
DELTA_KEYS = ("delta", "delta_ci_lo", "delta_ci_hi")
LEAF_VOCAB = {
    "status": CELL_STATUS | CONCEPT_STATUS | {"EVALUABLE", "NOT_EVALUABLE"},
    "cohort_pooled_bucket": {b[2] for b in A.POOL_BUCKETS},
    "n_bucket_acs": {b[2] for b in N_BUCKETS} | {"WITHHELD"},
    "n_bucket_pe": {b[2] for b in N_BUCKETS} | {"WITHHELD"},
    "acs_measured_bin": set(A.SHARE_BINS) | {"WITHHELD"},
    "pe_measured_bin": set(A.SHARE_BINS) | {"WITHHELD"},
    "data_quality_issue_bin": set(A.SHARE_BINS) | {"WITHHELD"},
}


# ---------------------------------------------------------------- 공통
def rows_gz(path, cols):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        idx = {c: header.index(c) for c in cols}
        for r in rd:
            yield {c: r[i] for c, i in idx.items()}


def to_float(s):
    try:
        x = float((s or "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def parse_value(value, valuenum):
    """(순위용 값, 종류, 경계값). valuenum 숫자 → NUMERIC; '<b'·'<=b'·'>b'·'>=b'(공백 허용) → CENSORED,
    순위용 값은 '<' = −CENS_OFFSET + b(모든 측정값 아래), '>' = +CENS_OFFSET + b(위); 그 외 → UNUSABLE."""
    x = to_float(valuenum)
    if x is not None:
        return x, "MEASURED_NUMERIC", None
    m = CENS.match(value or "")
    if m:
        b = float(m.group(2))
        return (b - CENS_OFFSET if m.group(1) == "<" else b + CENS_OFFSET), "MEASURED_CENSORED", m.group(1) + str(b)
    return None, "MEASURED_UNUSABLE", None


def unit_norm(u):
    """단위 비교용 정규화(사전 고정): 앞뒤 공백 제거·내부 공백 제거·소문자."""
    return re.sub(r"\s+", "", (u or "")).lower()


def subj_hash(subj):
    return int(hashlib.sha256(f"{SPLIT_SALT}|{subj}".encode()).hexdigest(), 16)


def fold_of(subj):
    return subj_hash(subj) % K_FOLDS


def strat_folds(subjects, y):
    """class 층화 subject fold: class 안에서 hash 순서로 정렬 후 순번 % K (fold 간 prevalence 차이 ≤ 1명)."""
    folds = [None] * len(subjects)
    for t in (0, 1):
        idx = sorted((i for i in range(len(subjects)) if y[i] == t), key=lambda i: (subj_hash(subjects[i]), subjects[i]))
        for r, i in enumerate(idx):
            folds[i] = r % K_FOLDS
    return folds


def n_bucket(n):
    return next(lbl for lo, hi, lbl in N_BUCKETS if lo <= n < hi)


def fmt(x):
    return "WITHHELD" if x is None else f"{x:.2f}"


def decide(lo, hi):
    """셀 판정(반올림 전 값): ΔAUROC 95 % CI 반폭 ≤ FEASIBLE_HALF_WIDTH → FEASIBLE."""
    return "FEASIBLE" if (hi - lo) / 2 <= FEASIBLE_HALF_WIDTH else "EVALUABLE_IMPRECISE"


def auroc(scores, y):
    """Mann–Whitney AUROC(동점 평균 순위). y=1(PE) 쪽 점수가 높을수록 1."""
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    n1 = sum(y)
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return None
    return (sum(r for r, t in zip(ranks, y) if t) - n1 * (n1 + 1) / 2) / (n1 * n0)


def fold_auroc(scores, y, folds):
    """fold 별 AUROC 의 평균(fold 간 절편 차이로 생기는 pooled OOF 편향 제거). 한 class 만 있는 fold 는 제외."""
    per = {}
    for i in range(len(y)):
        per.setdefault(folds[i], []).append(i)
    vals = [a for a in (auroc([scores[i] for i in m], [y[i] for i in m]) for m in per.values()) if a is not None]
    return sum(vals) / len(vals) if vals else None


def solve(M, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(M)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            raise ArithmeticError("singular")
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def fit_logreg(X, y):
    """L2(RIDGE, 절편 제외) 로지스틱 IRLS. 수렴 실패 시 ArithmeticError."""
    p = len(X[0]) + 1
    w = [0.0] * p
    for _ in range(IRLS_MAX):
        H = [[0.0] * p for _ in range(p)]
        g = [0.0] * p
        for xi, yi in zip(X, y):
            z = [1.0] + xi
            eta = sum(a * b for a, b in zip(w, z))
            mu = 1 / (1 + math.exp(-max(-30.0, min(30.0, eta))))
            s = max(mu * (1 - mu), 1e-10)
            for a in range(p):
                g[a] += (yi - mu) * z[a]
                za = s * z[a]
                for b in range(a, p):
                    H[a][b] += za * z[b]
        for a in range(1, p):
            g[a] -= RIDGE * w[a]
            H[a][a] += RIDGE
        for a in range(p):
            for b in range(a):
                H[a][b] = H[b][a]
        step = solve(H, g)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < IRLS_TOL:
            return w
    raise ArithmeticError("not_converged")


def predict(w, X):
    return [sum(a * b for a, b in zip(w, [1.0] + xi)) for xi in X]


def prep(train, test):
    """학습 fold 기준 중앙값 대치 + 표준화(sd 0 이면 0). 시험 행은 변환만 받는다(적합에 쓰지 않음)."""
    p = len(train[0])
    med, mu, sd = [], [], []
    for j in range(p):
        v = sorted(r[j] for r in train if r[j] is not None)
        m = (v[(len(v) - 1) // 2] + v[len(v) // 2]) / 2 if v else 0.0
        filled = [r[j] if r[j] is not None else m for r in train]
        a = sum(filled) / len(filled)
        s = math.sqrt(sum((x - a) ** 2 for x in filled) / len(filled))
        med.append(m)
        mu.append(a)
        sd.append(s)

    def tf(rows):
        return [[((r[j] if r[j] is not None else med[j]) - mu[j]) / sd[j] if sd[j] > 0 else 0.0 for j in range(p)]
                for r in rows]
    return tf(train), tf(test)


def ecdf_rank(train_vals, v):
    """학습 fold 경험분포 백분위(동점 절반) — 측정법 내부 순위 변환(단위 무관, 이분화 없음). 범위 밖이면 0 또는 1."""
    lo = bisect.bisect_left(train_vals, v)
    hi = bisect.bisect_right(train_vals, v)
    return (lo + 0.5 * (hi - lo)) / len(train_vals)


def oof(base, y, folds, lab=None):
    """K-fold out-of-fold 선형예측(folds 는 호출자가 고정). lab 이 있으면 학습 fold 순위 특징을 붙인 뒤
    baseline 과 함께 학습 fold 평균·SD 로 표준화(같은 RIDGE 척도)."""
    n = len(y)
    pred = [None] * n
    for f in range(K_FOLDS):
        tr = [i for i in range(n) if folds[i] != f]
        te = [i for i in range(n) if folds[i] == f]
        if not te:
            continue
        if len({y[i] for i in tr}) < 2:
            raise ArithmeticError("fold_single_class")
        rtr, rte = [base[i] for i in tr], [base[i] for i in te]
        if lab is not None:
            tv = sorted(lab[i] for i in tr)
            rtr = [r + [ecdf_rank(tv, lab[i])] for r, i in zip(rtr, tr)]
            rte = [r + [ecdf_rank(tv, lab[i])] for r, i in zip(rte, te)]
        Xtr, Xte = prep(rtr, rte)
        w = fit_logreg(Xtr, [y[i] for i in tr])
        for i, s in zip(te, predict(w, Xte)):
            pred[i] = s
    return pred


def resample(y, rng):
    """class 층화 subject 재표집 index(각 class 크기 보존)."""
    pos = [i for i, t in enumerate(y) if t]
    neg = [i for i, t in enumerate(y) if not t]
    return [pos[rng.randrange(len(pos))] for _ in pos] + [neg[rng.randrange(len(neg))] for _ in neg]


def pct_ci(vals):
    """95 % 백분위 구간(정렬된 반복값)."""
    vals = sorted(vals)
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def boot_ci(base, y, folds, lab=None):
    """재적합 bootstrap(B_BOOT, BOOT_SEED): 반복마다 class 층화 재표집 → 복제 subject 는 원 fold 유지 → M0(·M1) 재적합 →
    fold 평균 AUROC. lab 이 있으면 paired Δ(같은 재표집). 반환 (lo, hi, 실패 반복 수)."""
    rng = random.Random(BOOT_SEED)
    vals, fail = [], 0
    for _ in range(B_BOOT):
        idx = resample(y, rng)
        bb, yy, ff = [base[i] for i in idx], [y[i] for i in idx], [folds[i] for i in idx]
        try:
            a0 = fold_auroc(oof(bb, yy, ff), yy, ff)
            if lab is None:
                vals.append(a0)
            else:
                ll = [lab[i] for i in idx]
                vals.append(fold_auroc(oof(bb, yy, ff, lab=ll), yy, ff) - a0)
        except ArithmeticError:
            fail += 1
    if not vals:
        return None, None, fail
    lo, hi = pct_ci(vals)
    return lo, hi, fail


# ---------------------------------------------------------------- 집계
def compute_b1(ed_zip, ecg_zip, lab_path, pat_path):
    d = A.compute(ed_zip, ecg_zip)
    if d["verdict"] != "OK":
        return d
    stays = d["stays"]
    first = d["pairs"][PAIR]["first"]
    main = {sid: ("ACS" if cls == "a" else "PE") for sid, cls in first.values() if cls != "multi"}
    subj_of = {sid: stays[sid][0] for sid in main}
    subj_main = {}
    for sid in main:
        subj_main.setdefault(subj_of[sid], []).append(sid)
    subj_all = {}
    for sid, (subj, it, _, _) in stays.items():
        if subj in subj_main:
            subj_all.setdefault(subj, []).append((it, int(sid), sid))
    for v in subj_all.values():
        v.sort()
    keys = {s: [x[0] for x in v] for s, v in subj_all.items()}

    def assigned(subj, t):
        i = bisect.bisect_right(keys[subj], t) - 1
        return subj_all[subj][i][2] if i >= 0 else None

    triage = {}
    zed = zipfile.ZipFile(ed_zip)
    for r in A.rows(zed, A.ED_PREFIX + "triage.csv.gz", TRIAGE_ALLOW):
        sid = A.norm_id(r["stay_id"])
        if sid in main and sid not in triage:
            vit = {}
            for k, (lo, hi) in VITAL_RANGE.items():
                x = to_float(r[k])
                vit[k] = x if x is not None and lo <= x <= hi else None
            triage[sid] = vit
    pat = {}
    for r in rows_gz(pat_path, PAT_ALLOW):
        s = A.norm_id(r["subject_id"])
        if s in subj_main:
            pat[s] = (r["gender"].strip(), to_float(r["anchor_age"]), to_float(r["anchor_year"]))
    ev = {}  # (sid, concept) -> 사건 목록
    seq = 0
    for r in rows_gz(lab_path, LAB_ALLOW):
        item = r["itemid"].strip()
        c = ITEM2CONCEPT.get(item)
        if c is None:
            continue
        subj = A.norm_id(r["subject_id"])
        if subj not in subj_main:
            continue
        seq += 1
        ct, st = A.parse_time(r["charttime"]), A.parse_time(r["storetime"])
        for sid in subj_main[subj]:
            _, it, ot, _ = stays[sid]
            wend = min(it + dt.timedelta(hours=WINDOW_H), ot)
            in_ct = ct is not None and it <= ct <= ot and assigned(subj, ct) == sid
            in_st = st is not None and it <= st <= ot and assigned(subj, st) == sid
            if not (in_ct or in_st):
                continue
            elig = in_st and st <= wend and (ct is None or ct >= it)
            tmiss = st is None and ct is not None and it <= ct <= wend and assigned(subj, ct) == sid
            ev.setdefault((sid, c), []).append({
                "elig": elig, "tmiss": tmiss, "st": st, "ct": ct, "item": item, "seq": seq,
                "value": r["value"], "valuenum": r["valuenum"], "uom": r["valueuom"].strip()})
    subj_rows = {}
    for sid, cls in main.items():
        g, age0, ay = pat.get(subj_of[sid], ("", None, None))
        age = age0 + (stays[sid][1].year - ay) if age0 is not None and ay is not None else None
        vit = triage.get(sid, {k: None for k in VITAL_RANGE})
        base = [age, 1.0 if g == "F" else (0.0 if g == "M" else None)] + [vit[k] for k in BASE[2:]]
        labs = {}
        for c in CONCEPTS:
            es = ev.get((sid, c), [])
            el = sorted((e for e in es if e["elig"]), key=lambda e: (e["st"], e["ct"] or e["st"], e["item"], e["seq"]))
            if el:
                e = el[0]
                x, kind, bound = parse_value(e["value"], e["valuenum"])
                if kind in USABLE and not unit_norm(e["uom"]):
                    kind = "UNIT_MISSING"
                later_usable = kind not in USABLE and any(
                    parse_value(o["value"], o["valuenum"])[1] in USABLE and unit_norm(o["uom"]) for o in el[1:])
                labs[c] = {"status": kind, "item": e["item"], "x": x, "uom": e["uom"], "bound": bound,
                           "later_usable": later_usable}
            elif any(e["tmiss"] for e in es):
                labs[c] = {"status": "TIME_MISSING"}
            elif es:
                labs[c] = {"status": "TIME_INELIGIBLE"}
            else:
                labs[c] = {"status": "NOT_MEASURED"}
        subj_rows[sid] = {"subject": subj_of[sid], "cls": cls, "y": 1 if cls == "PE" else 0, "base": base,
                          "labs": labs, "acs_sub": sorted(d.get("sub", {}).get(sid, set()))}
    d.update({"b1_rows": subj_rows})
    return d


def base_summary(rows):
    """봉인용 기술: 특징별 평균·결측 수(Table 1 재료)."""
    out = {}
    for j, f in enumerate(BASE):
        v = [r["base"][j] for r in rows if r["base"][j] is not None]
        out[f] = {"n": len(rows), "missing": len(rows) - len(v), "mean": sum(v) / len(v) if v else None}
    return out


def cell(rows, c, item):
    """측정법 1개 분석. 반환 (공개 dict, 봉인 dict)."""
    sub = [r for r in rows if r["labs"][c]["status"] in USABLE and r["labs"][c]["item"] == item]
    sub.sort(key=lambda r: int(r["subject"]))
    na = sum(1 for r in sub if r["cls"] == "ACS")
    npe = len(sub) - na
    units = sorted({unit_norm(r["labs"][c]["uom"]) for r in sub})
    S = {"n_acs": na, "n_pe": npe, "units_normalized": units,
         "units_raw": sorted({r["labs"][c]["uom"] for r in sub}),
         "n_censored": sum(1 for r in sub if r["labs"][c]["status"] == "MEASURED_CENSORED"),
         "censor_bounds_distinct": len({r["labs"][c]["bound"] for r in sub if r["labs"][c]["bound"]}),
         "acs_subclass": {k: sum(1 for r in sub if r["cls"] == "ACS" and k in r["acs_sub"]) for k in A.ACS_SUB},
         "baseline_by_class": {cl: base_summary([r for r in sub if r["cls"] == cl]) for cl in ("ACS", "PE")}}
    P = {"n_bucket_acs": n_bucket(na), "n_bucket_pe": n_bucket(npe)}
    for k in ("auroc_m0", "auroc_m1", "delta", "delta_ci_lo", "delta_ci_hi", "auroc_value_only"):
        P[k] = "WITHHELD"
    if len(units) > 1:
        P["status"] = "NOT_EVALUABLE_UNIT"
    elif min(na, npe) < N_MIN_B1:
        P["status"] = "INSUFFICIENT_DATA"
    else:
        subj = [r["subject"] for r in sub]
        y = [r["y"] for r in sub]
        x = [r["labs"][c]["x"] for r in sub]
        base = [r["base"] for r in sub]
        folds = strat_folds(subj, y)
        try:
            s0 = oof(base, y, folds)
            s1 = oof(base, y, folds, lab=x)
            lo, hi, fail = boot_ci(base, y, folds, lab=x)
            if lo is None or fail > BOOT_FAIL_MAX * B_BOOT:
                raise ArithmeticError(f"bootstrap_failures={fail}")
        except ArithmeticError as e:
            P["status"] = "NOT_EVALUABLE_MODEL"
            S["model_error"] = str(e)
            return P, S
        a0, a1, av = fold_auroc(s0, y, folds), fold_auroc(s1, y, folds), auroc(x, y)
        S.update({"auroc_m0": a0, "auroc_m1": a1, "delta": a1 - a0, "delta_ci": [lo, hi], "boot_failures": fail,
                  "auroc_value_only": av,
                  "fold_class_counts": {f: [sum(1 for i in range(len(y)) if folds[i] == f and y[i] == t)
                                            for t in (0, 1)] for f in range(K_FOLDS)}})
        P.update({"auroc_m0": fmt(a0), "auroc_m1": fmt(a1), "delta": fmt(a1 - a0), "delta_ci_lo": fmt(lo),
                  "delta_ci_hi": fmt(hi), "auroc_value_only": fmt(av), "status": decide(lo, hi)})
    return P, S


def concept_status(cells):
    st = [v["status"] for v in cells.values()]
    if "FEASIBLE" in st:
        return "FEASIBLE"
    if "EVALUABLE_IMPRECISE" in st:
        return "EVALUABLE"
    if "INSUFFICIENT_DATA" in st:
        return "INSUFFICIENT_DATA"
    return "NOT_EVALUABLE"


def build_b1(d):
    rows = sorted(d["b1_rows"].values(), key=lambda r: int(r["subject"]))
    na = sum(1 for r in rows if r["cls"] == "ACS")
    npe = len(rows) - na
    evaluable = na > 0 and npe > 0
    pub = {"pair": {"status": "EVALUABLE" if evaluable else "NOT_EVALUABLE",
                    "cohort_pooled_bucket": A.pool_bucket(na + npe)}}
    sealed = {"pair": {"n_acs": na, "n_pe": npe,
                       "baseline_by_class": {cl: base_summary([r for r in rows if r["cls"] == cl])
                                             for cl in ("ACS", "PE")}}, "concepts": {}}
    bl = {"status": "NOT_EVALUABLE_PAIR", "auroc": "WITHHELD", "ci_lo": "WITHHELD", "ci_hi": "WITHHELD"}
    if evaluable and min(na, npe) >= N_MIN_B1:
        y = [r["y"] for r in rows]
        base = [r["base"] for r in rows]
        folds = strat_folds([r["subject"] for r in rows], y)
        try:
            a0 = fold_auroc(oof(base, y, folds), y, folds)
            lo, hi, fail = boot_ci(base, y, folds)
            if lo is None or fail > BOOT_FAIL_MAX * B_BOOT:
                raise ArithmeticError(f"bootstrap_failures={fail}")
            bl = {"status": decide(lo, hi), "auroc": fmt(a0), "ci_lo": fmt(lo), "ci_hi": fmt(hi)}
            sealed["baseline"] = {"auroc": a0, "ci": [lo, hi], "boot_failures": fail}
        except ArithmeticError as e:
            bl["status"] = "NOT_EVALUABLE_MODEL"
            sealed["baseline"] = {"model_error": str(e)}
    elif evaluable:
        bl["status"] = "INSUFFICIENT_DATA"
    pub["baseline"] = bl
    for c, items in CONCEPTS.items():
        cells, scells = {}, {}
        for item in items:
            if evaluable:
                cells[item], scells[item] = cell(rows, c, item)
            else:
                cells[item] = {"status": "NOT_EVALUABLE_PAIR", "n_bucket_acs": "WITHHELD", "n_bucket_pe": "WITHHELD",
                               **{k: "WITHHELD" for k in ("auroc_m0", "auroc_m1", "delta", "delta_ci_lo",
                                                          "delta_ci_hi", "auroc_value_only")}}
        stat = {k: [sum(1 for r in rows if r["cls"] == cl and r["labs"][c]["status"] == k) for cl in ("ACS", "PE")]
                for k in ("MEASURED_NUMERIC", "MEASURED_CENSORED", "MEASURED_UNUSABLE", "UNIT_MISSING", "TIME_MISSING",
                          "TIME_INELIGIBLE", "NOT_MEASURED")}
        meas_a = stat["MEASURED_NUMERIC"][0] + stat["MEASURED_CENSORED"][0]
        meas_p = stat["MEASURED_NUMERIC"][1] + stat["MEASURED_CENSORED"][1]
        dq = sum(sum(stat[k]) for k in ("MEASURED_UNUSABLE", "UNIT_MISSING", "TIME_MISSING"))
        any_ev = sum(sum(v) for k, v in stat.items() if k != "NOT_MEASURED")
        meas = [r for r in rows if r["labs"][c]["status"] in USABLE]
        unmeas = [r for r in rows if r["labs"][c]["status"] not in USABLE]
        pub[c] = {
            "status": concept_status(cells) if evaluable else "NOT_EVALUABLE",
            "measurement": {
                "acs_measured_bin": A.share_bin(meas_a, na) if evaluable and na >= A.SHARE_MIN_POOL else "WITHHELD",
                "pe_measured_bin": A.share_bin(meas_p, npe) if evaluable and npe >= A.SHARE_MIN_POOL else "WITHHELD",
                "data_quality_issue_bin": A.share_bin(dq, any_ev) if evaluable and any_ev >= A.SHARE_MIN_POOL
                else "WITHHELD"},
            "assays": cells}
        sealed["concepts"][c] = {
            "status_counts_acs_pe": stat, "assays": scells,
            "later_usable_after_unusable_first": sum(1 for r in rows if r["labs"][c].get("later_usable")),
            "baseline_measured_vs_unmeasured": {"measured": base_summary(meas), "unmeasured": base_summary(unmeas)}}
    return pub, sealed


def guard(pub):
    """키별 허용: status·구간 키 = 해당 어휘, 지표 키 = WITHHELD 또는 소수 2자리 + 값 범위(AUROC [0,1], Δ [−1,1])."""
    bad = []
    for k, v in A.flatten(pub):
        leaf = k.rsplit(".", 1)[-1]
        if not isinstance(v, str):
            bad.append(k)
        elif leaf in LEAF_VOCAB:
            if v not in LEAF_VOCAB[leaf]:
                bad.append(k)
        elif leaf in AUROC_KEYS or leaf in DELTA_KEYS:
            if v == "WITHHELD":
                continue
            lo = 0.0 if leaf in AUROC_KEYS else -1.0
            if not (METRIC_RX.match(v) and lo <= float(v) <= 1.0):
                bad.append(k)
        else:
            bad.append(k)
    return bad


def cohort_matches(pub, ref_pub):
    r = ref_pub["pairs"][PAIR]
    return pub["pair"]["status"] == r["pair_status"] and pub["pair"]["cohort_pooled_bucket"] == r["cohort_pooled_bucket"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("ed-zip", "ed-zip-sha", "ecg-zip", "ecg-zip-sha", "labevents", "labevents-sha", "d-labitems",
              "d-labitems-sha", "patients", "patients-sha", "schema", "schema-sha", "b0a-public", "b0a-public-sha",
              "b0c-public", "b0c-public-sha", "b0d-public", "b0d-public-sha", "out", "sealed", "private-log"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    for p in (a.out, a.sealed):
        if os.path.exists(p):
            print("B1_VERDICT INVALID reason=output_exists stage=preflight")
            return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.private_log)), exist_ok=True)
    plog = open(a.private_log, "a", encoding="utf-8")
    old_err, sys.stderr = sys.stderr, plog
    stage = "preflight"
    try:
        for p, h in ((a.ed_zip, a.ed_zip_sha), (a.ecg_zip, a.ecg_zip_sha), (a.labevents, a.labevents_sha),
                     (a.d_labitems, a.d_labitems_sha), (a.patients, a.patients_sha), (a.schema, a.schema_sha),
                     (a.b0a_public, a.b0a_public_sha), (a.b0c_public, a.b0c_public_sha),
                     (a.b0d_public, a.b0d_public_sha)):
            if A.sha256(p) != h:
                print("B1_VERDICT INVALID reason=sha_mismatch stage=preflight")
                return 2
        im = C.item_map(a.d_labitems)
        if im != C.ITEMS or any(frozenset(CONCEPTS[c]) != C.ITEMS[CONCEPT_B0C[c]] for c in CONCEPTS):
            print("B1_VERDICT INVALID reason=item_map_mismatch stage=preflight")
            return 2
        stage = "data"
        d = compute_b1(a.ed_zip, a.ecg_zip, a.labevents, a.patients)
        if d["verdict"] == "STOP_TITLE":
            print("B1_VERDICT STOP_TITLE classes=" + ",".join(d["stop_classes"]))
            return 3
        pub, sealed = build_b1(d)
        schema = json.load(open(a.schema, encoding="utf-8"))
        if sorted(k for k, _ in A.flatten(pub)) != sorted(schema["keys"]):
            print("B1_VERDICT INVALID reason=schema_mismatch stage=data")
            return 2
        if guard(pub):
            print("B1_VERDICT INVALID reason=output_guard stage=data")
            return 2
        for ref in (a.b0a_public, a.b0c_public, a.b0d_public):
            if not cohort_matches(pub, json.load(open(ref, encoding="utf-8"))):
                print("B1_VERDICT INVALID reason=cohort_mismatch stage=data")
                return 2
        os.makedirs(a.sealed)
        os.chmod(a.sealed, 0o700)
        sp = os.path.join(a.sealed, "b1_sealed.json")
        json.dump(sealed, open(sp, "w", encoding="utf-8"), sort_keys=True, indent=1, default=str)
        pub["meta"] = {"experiment": "EXP-SN-NBI-003", "phase": "B1", "pair": PAIR, "index_time": "ED intime",
                       "lab_availability_time": "storetime", "window_h": WINDOW_H, "n_min_b1": N_MIN_B1,
                       "k_folds": K_FOLDS,
                       "split": "class-stratified sha256(salt|subject_id) order, rank mod k; fold-averaged AUROC",
                       "ridge": RIDGE, "n_boot": B_BOOT, "boot_seed": BOOT_SEED, "boot": "refit, replicate keeps fold",
                       "feasible_half_width": FEASIBLE_HALF_WIDTH,
                       "estimand": "label-conditioned separation in the measured subset (not clinical value)",
                       "disclosure": "status vocabulary, size buckets, 10 %p bins and 2-decimal AUROC metrics only; "
                       "exact counts, coefficients and per-fold values sealed; patient-level predictions not stored",
                       "ed_zip_sha256": a.ed_zip_sha, "ecg_zip_sha256": a.ecg_zip_sha,
                       "labevents_sha256": a.labevents_sha, "d_labitems_sha256": a.d_labitems_sha,
                       "patients_sha256": a.patients_sha, "schema_sha256": a.schema_sha,
                       "b0a_public_sha256": a.b0a_public_sha, "b0c_public_sha256": a.b0c_public_sha,
                       "b0d_public_sha256": a.b0d_public_sha,
                       "script_sha256": A.sha256(os.path.abspath(__file__)),
                       "b0a_module_sha256": A.sha256(os.path.abspath(A.__file__)),
                       "b0c_module_sha256": A.sha256(os.path.abspath(C.__file__)),
                       "sealed_file_sha256": A.sha256(sp), "python": sys.version.split()[0]}
        os.makedirs(a.out)
        op = os.path.join(a.out, "b1_public.json")
        json.dump(pub, open(op, "w", encoding="utf-8"), sort_keys=True, indent=1)
        with open(os.path.join(a.out, "B1_SHA256SUMS"), "w", encoding="utf-8") as f:
            f.write(f"{A.sha256(op)}  b1_public.json\n")
        print("B1_VERDICT COMPLETE")
        return 0
    except Exception as e:  # 행 값이 담길 수 있는 메시지는 비공개 로그로만
        traceback.print_exc(file=plog)
        print(f"B1_VERDICT INVALID exception={type(e).__name__} stage={stage}")
        return 2
    finally:
        sys.stderr = old_err
        plog.close()


if __name__ == "__main__":
    sys.exit(main())
