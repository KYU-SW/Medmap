#!/usr/bin/env python3
"""EXP-SN-NBI-002 NBI-B0a (v2) — MIMIC-IV-ED + ECG-Ext-ICD availability / temporal feasibility.

LOCAL ONLY. 원본 zip 을 풀지 않고 스트리밍으로 읽고, 허용 컬럼만 보관한다.
공개 출력 = 사전 고정 어휘의 판정 라벨·pooled 거친 구간값만(숫자 없음). exact count·class별·쌍별·보완 값은
전부 봉인 파일(로컬 제한 폴더, SHA만 공개)에만 쓴다.
stdout = 판정 1줄. traceback·경고는 비공개 로그로만. 판별 성능·검사 결과값·환자 단위 출력 없음.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import statistics
import sys
import traceback
import zipfile

N_MIN = 30  # PROVISIONAL_METHOD_THRESHOLD (manifest [G])
Q_MIN = 30  # 시점 해석 라벨을 내기 위한 최소 n
SHARE_MIN_POOL = 100  # pooled 비율 구간을 공개하는 최소 pooled 크기
PAIRS = {"ACS~PE": ("ACS", "PE"), "ACS~PERI": ("ACS", "PERI")}
ED_PREFIX = "mimic-iv-ed-2.2/ed/"
ECG_MEMBER = "mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1/records_w_diag_icd10.csv"
# 허용 컬럼(이 외 컬럼은 csv 파서가 행 단위로 잠시 거칠 뿐 보관·참조하지 않음)
ALLOW = {
    "edstays": ["subject_id", "stay_id", "intime", "outtime", "hadm_id"],
    "diagnosis": ["stay_id", "icd_code", "icd_version", "icd_title"],
    "triage": ["stay_id", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain", "acuity",
               "chiefcomplaint"],
    "vitalsign": ["stay_id", "charttime", "rhythm"],
    "ecg": ["ed_stay_id", "ecg_time"],
}
# ICD 코드셋 (점 없는 형식, icd_version 조건) — manifest label_definition 과 동일
UA_SET_10 = [r"^I200$", r"^I25110$", r"^I25700$", r"^I25710$", r"^I25720$", r"^I25730$", r"^I25750$", r"^I25760$",
             r"^I25790$"]
CODES = {
    "ACS": {"10": [r"^I21[0-2]", r"^I213$", r"^I214$", r"^I219$", r"^I22"] + UA_SET_10,
            "9": [r"^410\d[01]$", r"^4111$"]},
    "PE": {"10": [r"^I26"], "9": [r"^4151"]},
    "PERI": {"10": [r"^I30", r"^I32$", r"^B3323$", r"^M3212$"], "9": [r"^420", r"^07421$"]},
}
ACS_SUB = {
    "STEMI": {"10": [r"^I21[0-3]"], "9": [r"^410[0-6][01]$", r"^4108[01]$"]},
    "NSTEMI": {"10": [r"^I214$"], "9": [r"^4107[01]$"]},
    "MI_UNSPEC": {"10": [r"^I219$"], "9": [r"^4109[01]$"]},
    "SUBSEQUENT": {"10": [r"^I22"], "9": []},
    "UA": {"10": UA_SET_10, "9": [r"^4111$"]},
}
# 봉인 전용 경계 코드 집계(ACS NOS 비대칭·410.x2 후속 episode) — class 를 만들지 않음
BOUNDARY = {"ICD10_I249": {"10": [r"^I249$"], "9": []}, "ICD9_410x2": {"10": [], "9": [r"^410\d2$"]}}
# 제목 키워드(정규식, 소문자 대상) — CMS 짧은·긴 제목 모두 통과하도록 고정(tests/fixtures/cms_icd_titles.json)
TITLE_KW = {"ACS": (r"infarct", r"stemi", r"\bami\b", r"angina", r"ang pctrs", r"coronary synd"),
            "PE": (r"embol", r"emb/", r"emblsm"),
            "PERI": (r"pericard",)}
B0A_TYPES = ["ECG_LINKED", "VITAL_SERIES", "RHYTHM_MONITOR"]
STATIC_LABELS = {
    "ECG_CONTENT": "PENDING_DATA", "BIOMARKER_TROPONIN": "PENDING_DATA", "BIOMARKER_DDIMER": "PENDING_DATA",
    "BIOMARKER_CKMB": "PENDING_DATA", "LAB_CRP_ESR": "PENDING_DATA", "MEDICAL_RECORD_PRE_T0": "PENDING_DATA",
    "IMAGING_CTPA": "PENDING_DATA", "IMAGING_CCTA": "PENDING_DATA", "IMAGING_VQ": "PENDING_DATA",
    "IMAGING_CXR": "PENDING_DATA", "IMAGING_ECHO": "PENDING_DATA_EXPECTED_NOT_EVALUABLE",
    "PHYSICAL_EXAM": "NOT_AVAILABLE", "QUESTION": "NOT_AVAILABLE",
}
TRIAGE_VITALS = ["temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain"]
POOL_BUCKETS = [(0, 100, "LT_100"), (100, 500, "100_499"), (500, 1000, "500_999"), (1000, 5000, "1000_4999"),
                (5000, 10 ** 12, "GE_5000")]
SHARE_BINS = [f"{10 * i}_{10 * (i + 1)}" for i in range(10)]
# 공개 출력 허용 어휘(모든 leaf 값은 이 집합 안의 문자열이어야 함)
ALLOWED_VALUES = (
    {"EVALUABLE", "NOT_EVALUABLE", "NOT_AVAILABLE_IN_DATA", "TEMPORALLY_UNCERTAIN", "RECORDED_IN_STAY_AVAILABLE",
     "RECORDED_IN_STAY_PARTIAL", "PENDING_DATA", "PENDING_DATA_EXPECTED_NOT_EVALUABLE", "NOT_AVAILABLE",
     "WITHHELD", "EARLY_ROUTINE_POSSIBLE", "LATER_IN_STAY", "INSUFFICIENT_N", "MEETS_NMIN", "BELOW_NMIN",
     "PENDING", "PENDING_DATA_B0C_B0D", "NOT_APPLICABLE"}
    | {b[2] for b in POOL_BUCKETS} | set(SHARE_BINS)
)


# ---------------------------------------------------------------- 공통
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm_id(s):
    s = (s or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s or None


def norm_code(s):
    return (s or "").strip().upper().replace(".", "")


def parse_time(s):
    s = (s or "").strip()
    if not s:
        return None
    return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def rows(zf, member, cols):
    """zip 멤버(csv 또는 csv.gz)를 스트리밍, 허용 컬럼만 dict 로 반환."""
    raw = zf.open(member)
    fh = gzip.open(raw, "rt", encoding="utf-8", newline="") if member.endswith(".gz") \
        else io.TextIOWrapper(raw, encoding="utf-8", newline="")
    with fh:
        rd = csv.reader(fh)
        header = next(rd)
        idx = {c: header.index(c) for c in cols}
        for r in rd:
            yield {c: r[i] for c, i in idx.items()}


def match(table, version, code):
    return any(re.search(p, code) for p in table.get(version, []))


def classify(version, code):
    """코드 → 대상 class 집합 (icd_version 조건)."""
    return {c for c, t in CODES.items() if match(t, version, code)}


def title_ok(cls, title):
    t = (title or "").lower()
    return any(re.search(k, t) for k in TITLE_KW[cls])


def pool_bucket(n):
    return next(lab for lo, hi, lab in POOL_BUCKETS if lo <= n < hi)


def share_bin(w, n):
    return SHARE_BINS[min(int(10 * w / n), 9)]


def timing_label(vals):
    if len(vals) < Q_MIN:
        return "INSUFFICIENT_N"
    return "EARLY_ROUTINE_POSSIBLE" if statistics.median(vals) <= 1.0 else "LATER_IN_STAY"  # 반올림 전 값


def quantiles(vals):
    if len(vals) < Q_MIN:
        return None
    q = statistics.quantiles(sorted(vals), n=4, method="inclusive")
    return dict(zip(("p25", "p50", "p75"), q))


# ---------------------------------------------------------------- 집계
def compute(ed_zip, ecg_zip):
    zed = zipfile.ZipFile(ed_zip)
    zecg = zipfile.ZipFile(ecg_zip)
    stays, n_excl = {}, 0
    for r in rows(zed, ED_PREFIX + "edstays.csv.gz", ALLOW["edstays"]):
        it, ot = parse_time(r["intime"]), parse_time(r["outtime"])
        sid, subj = norm_id(r["stay_id"]), norm_id(r["subject_id"])
        if it is None or ot is None or sid is None or subj is None:
            n_excl += 1
            continue
        stays[sid] = (subj, it, ot, norm_id(r["hadm_id"]) is not None)

    flags, versions, mismatch, sub, bnd = {}, {}, {c: 0 for c in CODES}, {}, {}
    for r in rows(zed, ED_PREFIX + "diagnosis.csv.gz", ALLOW["diagnosis"]):
        sid = norm_id(r["stay_id"])
        if sid not in stays:
            continue
        ver, code = r["icd_version"].strip(), norm_code(r["icd_code"])
        for b, t in BOUNDARY.items():
            if match(t, ver, code):
                bnd.setdefault(sid, set()).add(b)
        for c in classify(ver, code):
            flags.setdefault(sid, set()).add(c)
            versions.setdefault((sid, c), set()).add(ver)
            if not title_ok(c, r["icd_title"]):
                mismatch[c] += 1
            if c == "ACS":
                for s, t in ACS_SUB.items():
                    if match(t, ver, code):
                        sub.setdefault(sid, set()).add(s)
    if any(mismatch.values()):
        return {"verdict": "STOP_TITLE", "stop_classes": sorted(c for c, n in mismatch.items() if n)}

    pairs, main_stays = {}, set()
    for p, (a, b) in PAIRS.items():
        per_subj = {}
        for sid, fl in flags.items():
            A, Bq = a in fl, b in fl
            if not (A or Bq):
                continue
            cls = "a" if A and not Bq else "b" if Bq and not A else "multi"
            per_subj.setdefault(stays[sid][0], []).append((stays[sid][1], int(sid), sid, cls))
        first, nstay = {}, {}
        for subj, lst in per_subj.items():
            lst.sort(key=lambda x: (x[0], x[1]))  # intime, 동률 시 stay_id 숫자 오름차순
            first[subj] = (lst[0][2], lst[0][3])  # 첫 관련 stay 가 multi 면 그대로 multi (다음 stay 로 넘기지 않음)
            nstay[subj] = len(lst)
        pairs[p] = {"first": first, "nstay": nstay, "classes": (a, b)}
        main_stays |= {sid for sid, cls in first.values() if cls != "multi"}

    tri = {}
    for r in rows(zed, ED_PREFIX + "triage.csv.gz", ALLOW["triage"]):
        sid = norm_id(r["stay_id"])
        if sid in main_stays:
            tri[sid] = (all(r[k].strip() for k in TRIAGE_VITALS), bool(r["chiefcomplaint"].strip()),
                        bool(r["acuity"].strip()))
    vit = {}  # sid -> [first_vital_time, first_rhythm_time, pre_flag]
    for r in rows(zed, ED_PREFIX + "vitalsign.csv.gz", ALLOW["vitalsign"]):
        sid = norm_id(r["stay_id"])
        if sid not in main_stays:
            continue
        t = parse_time(r["charttime"])
        if t is None:
            continue
        _, it, ot, _ = stays[sid]
        v = vit.setdefault(sid, [None, None, False])
        if t < it:
            v[2] = True
        elif t <= ot:
            v[0] = t if v[0] is None or t < v[0] else v[0]
            if r["rhythm"].strip():
                v[1] = t if v[1] is None or t < v[1] else v[1]
    ecg, orphan = {}, 0
    for r in rows(zecg, ECG_MEMBER, ALLOW["ecg"]):
        sid = norm_id(r["ed_stay_id"])
        if sid is not None and sid not in stays:
            orphan += 1
        if sid not in main_stays:
            continue
        t = parse_time(r["ecg_time"])
        prev = ecg.get(sid, "NONE")
        if prev == "NONE" or (t is not None and (prev is None or t < prev)):
            ecg[sid] = t
    return {"verdict": "OK", "stays": stays, "n_excl": n_excl, "pairs": pairs, "versions": versions,
            "sub": sub, "bnd": bnd, "flags": flags, "tri": tri, "vit": vit, "ecg": ecg, "orphan": orphan}


def has(t, sid, d):
    if t == "ECG_LINKED":
        return sid in d["ecg"]
    v = d["vit"].get(sid)
    if not v:
        return False
    return v[0] is not None if t == "VITAL_SERIES" else v[1] is not None


def delay_h(t, sid, d):
    it = d["stays"][sid][1]
    if t == "ECG_LINKED":
        x = d["ecg"].get(sid)
    else:
        v = d["vit"].get(sid)
        x = None if not v else (v[0] if t == "VITAL_SERIES" else v[1])
    return None if x is None else (x - it).total_seconds() / 3600


def build(d):
    """반환: (public, sealed). public 은 어휘 문자열만, sealed 는 exact 값 전부."""
    pub = {"pairs": {}}
    sealed = {"global": {"stays_excluded_missing_time_or_id": d["n_excl"], "ecg_orphan_rows": d["orphan"],
                         "boundary": {
                             "ICD10_I249_only_stays": sum("ICD10_I249" in bs and "ACS" not in d["flags"].get(s, set())
                                                          for s, bs in d["bnd"].items()),
                             "ICD9_410x2_stays": sum("ICD9_410x2" in bs for bs in d["bnd"].values())}},
              "pairs": {}}
    acs_sets = {}
    for p, P in d["pairs"].items():
        first = P["first"]
        a_s = sorted(s for s, c in first.values() if c == "a")
        b_s = sorted(s for s, c in first.values() if c == "b")
        pool = a_s + b_s
        n_a, n_b = len(a_s), len(b_s)
        n_m = sum(c == "multi" for _, c in first.values())
        acs_sets[p] = {subj for subj, (s, c) in first.items() if c == "a"}
        evaluable = n_a > 0 and n_b > 0
        S = {"cohort": {"n_a": n_a, "n_b": n_b, "n_multi": n_m, "n_pool": n_a + n_b},
             "avail": {}, "delays_h": {}, "timing_label": {}}
        labels, shares, timing = {}, {}, {}
        for t in B0A_TYPES:
            ca, cb = sum(has(t, s, d) for s in a_s), sum(has(t, s, d) for s in b_s)
            w = ca + cb
            S["avail"][t] = {"pooled": w, "a": ca, "b": cb,
                             "a_admitted": sum(has(t, s, d) and d["stays"][s][3] for s in a_s),
                             "b_admitted": sum(has(t, s, d) and d["stays"][s][3] for s in b_s)}
            if not evaluable:
                labels[t] = "NOT_EVALUABLE"
            elif w == 0:
                labels[t] = "NOT_AVAILABLE_IN_DATA"
            elif t == "ECG_LINKED":
                labels[t] = "TEMPORALLY_UNCERTAIN"
            else:
                labels[t] = "RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= N_MIN else "RECORDED_IN_STAY_PARTIAL"
            shares[t] = share_bin(w, n_a + n_b) if evaluable and n_a + n_b >= SHARE_MIN_POOL else "WITHHELD"
            vals = [x for x in (delay_h(t, s, d) for s in pool) if x is not None]
            S["delays_h"][t] = quantiles(vals)
            timing[t] = "TEMPORALLY_UNCERTAIN" if t == "ECG_LINKED" else \
                ("NOT_EVALUABLE" if not evaluable else timing_label(vals))
            S["timing_label"][t] = timing[t]
        S["vital_no_rhythm"] = sum(has("VITAL_SERIES", s, d) and not has("RHYTHM_MONITOR", s, d) for s in pool)
        S["icd_version"] = {cl: {"v9": sum(d["versions"].get((s, dis), set()) == {"9"} for s in lst),
                                 "v10": sum(d["versions"].get((s, dis), set()) == {"10"} for s in lst),
                                 "mixed": sum(len(d["versions"].get((s, dis), set())) > 1 for s in lst)}
                            for cl, lst, dis in (("a", a_s, P["classes"][0]), ("b", b_s, P["classes"][1]))}
        S["triage"] = {k: sum(d["tri"].get(s, (False, False, False))[i] for s in pool)
                       for i, k in enumerate(("vitals_complete", "chiefcomplaint_present", "acuity_present"))}
        S["admitted"] = {"pooled": sum(d["stays"][s][3] for s in pool), "a": sum(d["stays"][s][3] for s in a_s),
                         "b": sum(d["stays"][s][3] for s in b_s)}
        S["pre_t0_vitals"] = sum(bool(d["vit"].get(s, [None, None, False])[2]) for s in pool)
        ns = list(P["nstay"].values())
        S["stays_per_subject"] = {"k1": sum(x == 1 for x in ns), "k2": sum(x == 2 for x in ns),
                                  "k3_5": sum(3 <= x <= 5 for x in ns), "k6p": sum(x >= 6 for x in ns)}
        if P["classes"][0] == "ACS":
            S["acs_subclass"] = {k: sum(k in d["sub"].get(x, set()) for x in a_s) for k in ACS_SUB}
        ecg_rule = None
        if p == "ACS~PERI":
            ecg_rule = "MEETS_NMIN" if evaluable and min(S["avail"]["ECG_LINKED"]["a"],
                                                         S["avail"]["ECG_LINKED"]["b"]) >= N_MIN else "BELOW_NMIN"
        sealed["pairs"][p] = S
        pub["pairs"][p] = {
            "pair_status": "EVALUABLE" if evaluable else "NOT_EVALUABLE",
            "cohort_pooled_bucket": pool_bucket(n_a + n_b),
            "labels": {**labels, **(STATIC_LABELS if evaluable else {k: "NOT_EVALUABLE" for k in STATIC_LABELS})},
            "pooled_share_bin": shares,
            "timing": timing,
            "pair_rule_inputs": {"ecg_linked_both_classes_nmin": ecg_rule if ecg_rule else "NOT_APPLICABLE",
                                 "acs_pe_eligibility": "PENDING_DATA_B0C_B0D" if p == "ACS~PE" else "NOT_APPLICABLE"},
        }
    if "ACS~PE" in acs_sets and "ACS~PERI" in acs_sets:  # 쌍 간 포함관계(차집합)는 봉인에만
        sealed["cross_pair"] = {"acs_in_PE_not_PERI": len(acs_sets["ACS~PE"] - acs_sets["ACS~PERI"]),
                                "acs_in_PERI_not_PE": len(acs_sets["ACS~PERI"] - acs_sets["ACS~PE"])}
    pub["pair_decision"] = {"b1_primary_pair": "PENDING"}
    return pub, sealed


def flatten(o, pre=""):
    out = []
    if isinstance(o, dict):
        for k in sorted(o):
            out += flatten(o[k], f"{pre}.{k}" if pre else k)
    else:
        out.append((pre, o))
    return out


def guard(pub):
    """공개 leaf 값이 전부 허용 어휘 문자열인지. 위반 경로 목록 반환."""
    return [k for k, v in flatten(pub) if not (isinstance(v, str) and v in ALLOWED_VALUES)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("ed-zip", "ed-zip-sha", "ecg-zip", "ecg-zip-sha", "schema", "schema-sha", "out", "sealed",
              "private-log"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    for p in (a.out, a.sealed):
        if os.path.exists(p):
            print("B0A_VERDICT INVALID reason=output_exists stage=preflight")
            return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.private_log)), exist_ok=True)
    plog = open(a.private_log, "a", encoding="utf-8")
    old_err, sys.stderr = sys.stderr, plog
    stage = "preflight"
    try:
        for p, h in ((a.ed_zip, a.ed_zip_sha), (a.ecg_zip, a.ecg_zip_sha), (a.schema, a.schema_sha)):
            if sha256(p) != h:
                print("B0A_VERDICT INVALID reason=sha_mismatch stage=preflight")
                return 2
        stage = "data"
        d = compute(a.ed_zip, a.ecg_zip)
        if d["verdict"] == "STOP_TITLE":
            print("B0A_VERDICT STOP_TITLE classes=" + ",".join(d["stop_classes"]))
            return 3
        pub, sealed = build(d)
        schema = json.load(open(a.schema, encoding="utf-8"))
        if sorted(k for k, _ in flatten(pub)) != sorted(schema["keys"]):
            print("B0A_VERDICT INVALID reason=schema_mismatch stage=data")
            return 2
        if guard(pub):
            print("B0A_VERDICT INVALID reason=output_guard stage=data")
            return 2
        os.makedirs(a.sealed)
        os.chmod(a.sealed, 0o700)
        sp = os.path.join(a.sealed, "b0a_sealed.json")
        json.dump(sealed, open(sp, "w", encoding="utf-8"), sort_keys=True, indent=1, default=str)
        pub["meta"] = {"experiment": "EXP-SN-NBI-002", "phase": "B0a", "n_min": N_MIN, "q_min": Q_MIN,
                       "share_min_pool": SHARE_MIN_POOL, "disclosure": "labels and coarse pooled bins only; "
                       "all exact, class-wise, pair-wise and complement values sealed",
                       "ed_zip_sha256": a.ed_zip_sha, "ecg_zip_sha256": a.ecg_zip_sha,
                       "schema_sha256": a.schema_sha, "script_sha256": sha256(os.path.abspath(__file__)),
                       "sealed_file_sha256": sha256(sp), "python": sys.version.split()[0]}
        os.makedirs(a.out)
        op = os.path.join(a.out, "b0a_public.json")
        json.dump(pub, open(op, "w", encoding="utf-8"), sort_keys=True, indent=1)
        with open(os.path.join(a.out, "B0A_SHA256SUMS"), "w", encoding="utf-8") as f:
            f.write(f"{sha256(op)}  b0a_public.json\n")
        print("B0A_VERDICT COMPLETE")
        return 0
    except Exception as e:  # 행 값이 담길 수 있는 메시지는 비공개 로그로만
        traceback.print_exc(file=plog)
        print(f"B0A_VERDICT INVALID exception={type(e).__name__} stage={stage}")
        return 2
    finally:
        sys.stderr = old_err
        plog.close()


if __name__ == "__main__":
    sys.exit(main())
