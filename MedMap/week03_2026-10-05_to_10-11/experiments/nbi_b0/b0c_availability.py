#!/usr/bin/env python3
"""EXP-SN-NBI-002 NBI-B0c — MIMIC-IV hosp lab/biomarker availability / temporal feasibility.

LOCAL ONLY. 코호트는 고정 B0a 모듈(b0a_availability.compute)을 그대로 재사용한다(동일 코호트·동일 class·동일 주 단위).
labevents 는 허용 컬럼(subject_id·itemid·charttime·storetime)만 보관하고, 검사 결과값(value·valuenum·flag 등)은
읽지 않는다. 가용 시각 = storetime(manifest [D]). 연결 = subject_id ∧ storetime ∈ window, hadm_id 미사용([E]).
공개 출력 = 사전 고정 어휘의 판정 라벨·pooled 거친 구간값만(숫자 없음). exact count·class별 값·window별 값·지연 수치는
봉인 파일(로컬 제한 폴더, SHA만 공개)에만. stdout = 판정 1줄. 판별 성능·결과값·환자 단위 출력 없음.
"""
import argparse
import bisect
import csv
import datetime as dt
import gzip
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b0a_availability as A  # noqa: E402  (고정 B0a 모듈: 코호트·코드표·공통 함수, 수정 금지)

LAB_TYPES = ["BIOMARKER_TROPONIN", "BIOMARKER_DDIMER", "BIOMARKER_CKMB", "LAB_CRP_ESR"]
PRE_TYPE = "MEDICAL_RECORD_PRE_T0"
# 개념 규칙(manifest [D] B0c + rev6 사전 검토 보완: CKMB 'isoenzyme mb', CRP 'high-sensitivity crp'), fluid == 'Blood'
LAB_RULES = {
    "BIOMARKER_TROPONIN": ("troponin",),
    "BIOMARKER_DDIMER": ("d-dimer",),
    "BIOMARKER_CKMB": ("ck-mb", "creatine kinase, mb", "isoenzyme mb"),
    "LAB_CRP_ESR": ("c-reactive protein", "sedimentation", "high-sensitivity crp"),
}
LAB_FLUID = "Blood"
# 고정 itemid(d_labitems sha256 b7afdda7… 에 규칙을 적용한 결과, 실행 시 재계산해 불일치하면 INVALID)
ITEMS = {
    "BIOMARKER_TROPONIN": frozenset({"51002", "51003", "52642"}),
    "BIOMARKER_DDIMER": frozenset({"50915", "51196", "52551"}),
    "BIOMARKER_CKMB": frozenset({"50908", "50911", "51580", "51595"}),
    "LAB_CRP_ESR": frozenset({"50889", "51288", "51652"}),
}
ITEM2TYPE = {i: t for t, s in ITEMS.items() for i in s}
LAB_ALLOW = ["subject_id", "itemid", "charttime", "storetime"]  # 결과값 컬럼은 참조하지 않음
DLAB_ALLOW = ["itemid", "label", "fluid"]
ADM_ALLOW = ["subject_id", "dischtime"]
WINDOWS_H = (1, 3, 6)  # 봉인 전용(공개는 W_STAY 만)
AROUND_H = 24  # pre-T0 / post-ED 서술용(봉인 전용)
UNCERTAIN_MISSING_SHARE = 0.5  # stay 단위(rev7): 체류 중 채취 stay 중 storetime 전부 결측 stay 비율 ≥ 이 값 ∧ 그 stay 수 ≥ Q_MIN
#                                이면 TEMPORALLY_UNCERTAIN (사전 고정, 민감도 분석 금지)
N_MIN, Q_MIN, SHARE_MIN_POOL = A.N_MIN, A.Q_MIN, A.SHARE_MIN_POOL
ALLOWED_VALUES = (
    {"EVALUABLE", "NOT_EVALUABLE", "NOT_AVAILABLE_IN_DATA", "TEMPORALLY_UNCERTAIN", "RECORDED_IN_STAY_AVAILABLE",
     "RECORDED_IN_STAY_PARTIAL", "PRE_T0_RECORD_AVAILABLE", "PRE_T0_RECORD_PARTIAL", "WITHHELD",
     "EARLY_ROUTINE_POSSIBLE", "LATER_IN_STAY", "INSUFFICIENT_N", "NOT_APPLICABLE", "ELIGIBLE", "PENDING_DATA_B0D",
     "PENDING", "ACS~PE"}
    | {b[2] for b in A.POOL_BUCKETS} | set(A.SHARE_BINS)
)


def rows_gz(path, cols):
    """csv.gz 스트리밍, 허용 컬럼만 dict 로 반환(B0a rows 와 같은 방식)."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        idx = {c: header.index(c) for c in cols}
        for r in rd:
            yield {c: r[i] for c, i in idx.items()}


def item_map(dlab_path):
    """d_labitems 에 개념 규칙을 적용한 itemid 집합(사전 데이터, 환자 정보 아님)."""
    got = {t: set() for t in LAB_RULES}
    for r in rows_gz(dlab_path, DLAB_ALLOW):
        lab = (r["label"] or "").lower()
        if r["fluid"] != LAB_FLUID:
            continue
        for t, keys in LAB_RULES.items():
            if any(k in lab for k in keys):
                got[t].add(r["itemid"].strip())
    return {t: frozenset(s) for t, s in got.items()}


def compute_b0c(ed_zip, ecg_zip, lab_path, adm_path):
    d = A.compute(ed_zip, ecg_zip)
    if d["verdict"] != "OK":
        return d
    stays = d["stays"]
    main = set()
    for P in d["pairs"].values():
        main |= {sid for sid, cls in P["first"].values() if cls != "multi"}
    subj_main = {}
    for sid in main:
        subj_main.setdefault(stays[sid][0], []).append(sid)
    # 겹치는 stay 배정 규칙([E]): 사건 시각 이전(≤) intime 중 가장 늦은 stay — 같은 subject 의 모든 stay 대상
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

    first = {}  # (sid, type) -> 가장 이른 storetime (W_STAY 안, charttime ≥ intime)
    st_ok, st_missing = {}, {}  # (sid,type) -> 체류 중 채취(charttime ∈ stay) 사건 수: storetime 있음 / 없음
    pre_collected, pre24, post24, item_n = {}, {}, {}, {}
    for r in rows_gz(lab_path, LAB_ALLOW):
        t = ITEM2TYPE.get(r["itemid"].strip())
        if t is None:
            continue
        subj = A.norm_id(r["subject_id"])
        if subj not in subj_main:
            continue
        ct, st = A.parse_time(r["charttime"]), A.parse_time(r["storetime"])
        for sid in subj_main[subj]:
            _, it, ot, _ = stays[sid]
            k = (sid, t)
            if ct is not None and it <= ct <= ot and assigned(subj, ct) == sid:
                if st is None:
                    st_missing[k] = st_missing.get(k, 0) + 1
                else:
                    st_ok[k] = st_ok.get(k, 0) + 1
            if st is None:
                continue
            if it <= st <= ot and assigned(subj, st) == sid:
                if ct is not None and ct < it:
                    pre_collected[k] = pre_collected.get(k, 0) + 1  # 도착 전 채취·체류 중 결과: 가용으로 세지 않음
                    continue
                if k not in first or st < first[k]:
                    first[k] = st
                item_n[(sid, r["itemid"].strip())] = 1
            elif it - dt.timedelta(hours=AROUND_H) <= st < it:
                pre24[k] = 1
            elif ot < st <= ot + dt.timedelta(hours=AROUND_H):
                post24[k] = 1
    prior_adm = set()
    for r in rows_gz(adm_path, ADM_ALLOW):
        subj = A.norm_id(r["subject_id"])
        if subj not in subj_main:
            continue
        x = A.parse_time(r["dischtime"])
        if x is None:
            continue
        for sid in subj_main[subj]:
            if x < stays[sid][1]:
                prior_adm.add(sid)
    d.update({"lab_first": first, "st_ok": st_ok, "st_missing": st_missing, "pre_collected": pre_collected,
              "pre24": pre24, "post24": post24, "item_n": item_n, "prior_adm": prior_adm})
    return d


def has_lab(t, sid, d, hours=None):
    x = d["lab_first"].get((sid, t))
    if x is None:
        return False
    return hours is None or x <= d["stays"][sid][1] + dt.timedelta(hours=hours)


def lab_delay(t, sid, d):
    x = d["lab_first"].get((sid, t))
    return None if x is None else (x - d["stays"][sid][1]).total_seconds() / 3600


def bin_or_withheld(w, n, ok):
    return A.share_bin(w, n) if ok and n >= SHARE_MIN_POOL else "WITHHELD"


def build_b0c(d):
    """반환: (public, sealed). public 은 어휘 문자열만, sealed 는 exact 값 전부."""
    pub, sealed = {"pairs": {}}, {"pairs": {}}
    eligible = False
    for p, P in d["pairs"].items():
        first = P["first"]
        a_s = sorted(s for s, c in first.values() if c == "a")
        b_s = sorted(s for s, c in first.values() if c == "b")
        pool = a_s + b_s
        n_a, n_b = len(a_s), len(b_s)
        evaluable = n_a > 0 and n_b > 0
        adm = [s for s in pool if d["stays"][s][3]]
        nadm = [s for s in pool if not d["stays"][s][3]]
        S = {"cohort": {"n_a": n_a, "n_b": n_b, "n_pool": n_a + n_b, "n_admitted": len(adm),
                        "n_not_admitted": len(nadm)}, "avail": {}, "delays_h": {}, "timing_label": {}}
        labels, shares, timing = {}, {}, {}
        for t in LAB_TYPES:
            ca, cb = sum(has_lab(t, s, d) for s in a_s), sum(has_lab(t, s, d) for s in b_s)
            w = ca + cb
            miss = sum(d["st_missing"].get((s, t), 0) for s in pool)
            okn = sum(d["st_ok"].get((s, t), 0) for s in pool)
            coll = [s for s in pool if d["st_ok"].get((s, t), 0) + d["st_missing"].get((s, t), 0) > 0]
            all_miss = [s for s in coll if d["st_ok"].get((s, t), 0) == 0]
            uncertain = len(all_miss) >= Q_MIN and len(all_miss) / len(coll) >= UNCERTAIN_MISSING_SHARE
            S["avail"][t] = {
                "pooled": w, "a": ca, "b": cb,
                "a_admitted": sum(has_lab(t, s, d) and d["stays"][s][3] for s in a_s),
                "b_admitted": sum(has_lab(t, s, d) and d["stays"][s][3] for s in b_s),
                "windows": {f"W{h}": {"a": sum(has_lab(t, s, d, h) for s in a_s),
                                      "b": sum(has_lab(t, s, d, h) for s in b_s)} for h in WINDOWS_H},
                "storetime_missing_events": miss, "storetime_present_events": okn,
                "stays_collected_in_stay": len(coll), "stays_all_storetime_missing": len(all_miss),
                "stratum_admitted_recorded": sum(has_lab(t, s, d) for s in adm),
                "stratum_not_admitted_recorded": sum(has_lab(t, s, d) for s in nadm),
                "pre_t0_collected_stays": sum((s, t) in d["pre_collected"] for s in pool),
                "pre_t0_24h_stays": sum((s, t) in d["pre24"] for s in pool),
                "post_ed_24h_stays": sum((s, t) in d["post24"] for s in pool),
                "items": {i: sum((s, i) in d["item_n"] for s in pool) for i in sorted(ITEMS[t])},
            }
            if not evaluable:
                labels[t] = "NOT_EVALUABLE"
            elif uncertain:
                labels[t] = "TEMPORALLY_UNCERTAIN"
            elif w == 0:
                labels[t] = "NOT_AVAILABLE_IN_DATA"
            else:
                labels[t] = "RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= N_MIN else "RECORDED_IN_STAY_PARTIAL"
            shares[t] = bin_or_withheld(w, n_a + n_b, evaluable)
            vals = [x for x in (lab_delay(t, s, d) for s in pool) if x is not None]
            S["delays_h"][t] = A.quantiles(vals)
            timing[t] = "NOT_EVALUABLE" if not evaluable else \
                ("TEMPORALLY_UNCERTAIN" if labels[t] == "TEMPORALLY_UNCERTAIN" else A.timing_label(vals))
            S["timing_label"][t] = timing[t]
        pa, pb = sum(s in d["prior_adm"] for s in a_s), sum(s in d["prior_adm"] for s in b_s)
        S["avail"][PRE_TYPE] = {"pooled": pa + pb, "a": pa, "b": pb}
        if not evaluable:
            labels[PRE_TYPE] = "NOT_EVALUABLE"
        elif pa + pb == 0:
            labels[PRE_TYPE] = "NOT_AVAILABLE_IN_DATA"
        else:
            labels[PRE_TYPE] = "PRE_T0_RECORD_AVAILABLE" if min(pa, pb) >= N_MIN else "PRE_T0_RECORD_PARTIAL"
        shares[PRE_TYPE] = bin_or_withheld(pa + pb, n_a + n_b, evaluable)
        timing[PRE_TYPE] = "NOT_APPLICABLE"
        rule = "NOT_APPLICABLE"
        if p == "ACS~PE":  # manifest [H]: TROPONIN·DDIMER·CTPA 중 하나라도 AVAILABLE → 적격 확정, CTPA 는 B0d 대기
            hit = any(labels[t] == "RECORDED_IN_STAY_AVAILABLE" for t in ("BIOMARKER_TROPONIN", "BIOMARKER_DDIMER"))
            rule = "ELIGIBLE" if hit else "PENDING_DATA_B0D"
            eligible = hit
        sealed["pairs"][p] = S
        pub["pairs"][p] = {
            "pair_status": "EVALUABLE" if evaluable else "NOT_EVALUABLE",
            "cohort_pooled_bucket": A.pool_bucket(n_a + n_b),
            "labels": labels, "pooled_share_bin": shares, "timing": timing,  # 입원/비입원 층은 봉인 전용(rev7)
            "pair_rule_inputs": {"acs_pe_eligibility": rule},
        }
    pub["pair_decision"] = {"b1_primary_pair": "ACS~PE" if eligible else "PENDING"}
    return pub, sealed


def guard(pub):
    return [k for k, v in A.flatten(pub) if not (isinstance(v, str) and v in ALLOWED_VALUES)]


def cohort_matches_b0a(pub, b0a_pub):
    """B0a 공개 출력과 쌍 상태·코호트 구간이 같아야 동일 코호트로 인정."""
    return all(pub["pairs"][p]["pair_status"] == b0a_pub["pairs"][p]["pair_status"]
               and pub["pairs"][p]["cohort_pooled_bucket"] == b0a_pub["pairs"][p]["cohort_pooled_bucket"]
               for p in A.PAIRS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("ed-zip", "ed-zip-sha", "ecg-zip", "ecg-zip-sha", "labevents", "labevents-sha", "d-labitems",
              "d-labitems-sha", "admissions", "admissions-sha", "schema", "schema-sha", "b0a-public",
              "b0a-public-sha", "out", "sealed", "private-log"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    for p in (a.out, a.sealed):
        if os.path.exists(p):
            print("B0C_VERDICT INVALID reason=output_exists stage=preflight")
            return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.private_log)), exist_ok=True)
    plog = open(a.private_log, "a", encoding="utf-8")
    old_err, sys.stderr = sys.stderr, plog
    stage = "preflight"
    try:
        for p, h in ((a.ed_zip, a.ed_zip_sha), (a.ecg_zip, a.ecg_zip_sha), (a.labevents, a.labevents_sha),
                     (a.d_labitems, a.d_labitems_sha), (a.admissions, a.admissions_sha), (a.schema, a.schema_sha),
                     (a.b0a_public, a.b0a_public_sha)):
            if A.sha256(p) != h:
                print("B0C_VERDICT INVALID reason=sha_mismatch stage=preflight")
                return 2
        if item_map(a.d_labitems) != ITEMS:
            print("B0C_VERDICT INVALID reason=item_map_mismatch stage=preflight")
            return 2
        stage = "data"
        d = compute_b0c(a.ed_zip, a.ecg_zip, a.labevents, a.admissions)
        if d["verdict"] == "STOP_TITLE":
            print("B0C_VERDICT STOP_TITLE classes=" + ",".join(d["stop_classes"]))
            return 3
        pub, sealed = build_b0c(d)
        schema = json.load(open(a.schema, encoding="utf-8"))
        if sorted(k for k, _ in A.flatten(pub)) != sorted(schema["keys"]):
            print("B0C_VERDICT INVALID reason=schema_mismatch stage=data")
            return 2
        if guard(pub):
            print("B0C_VERDICT INVALID reason=output_guard stage=data")
            return 2
        if not cohort_matches_b0a(pub, json.load(open(a.b0a_public, encoding="utf-8"))):
            print("B0C_VERDICT INVALID reason=cohort_mismatch_b0a stage=data")
            return 2
        os.makedirs(a.sealed)
        os.chmod(a.sealed, 0o700)
        sp = os.path.join(a.sealed, "b0c_sealed.json")
        json.dump(sealed, open(sp, "w", encoding="utf-8"), sort_keys=True, indent=1, default=str)
        pub["meta"] = {"experiment": "EXP-SN-NBI-002", "phase": "B0c", "n_min": N_MIN, "q_min": Q_MIN,
                       "share_min_pool": SHARE_MIN_POOL, "uncertain_missing_share": UNCERTAIN_MISSING_SHARE,
                       "availability_time": "storetime", "disclosure": "labels and coarse pooled bins only; "
                       "all exact, class-wise, window-wise and value-free intermediate counts sealed",
                       "ed_zip_sha256": a.ed_zip_sha, "ecg_zip_sha256": a.ecg_zip_sha,
                       "labevents_sha256": a.labevents_sha, "d_labitems_sha256": a.d_labitems_sha,
                       "admissions_sha256": a.admissions_sha, "b0a_public_sha256": a.b0a_public_sha,
                       "schema_sha256": a.schema_sha, "script_sha256": A.sha256(os.path.abspath(__file__)),
                       "b0a_module_sha256": A.sha256(os.path.abspath(A.__file__)),
                       "sealed_file_sha256": A.sha256(sp), "python": sys.version.split()[0]}
        os.makedirs(a.out)
        op = os.path.join(a.out, "b0c_public.json")
        json.dump(pub, open(op, "w", encoding="utf-8"), sort_keys=True, indent=1)
        with open(os.path.join(a.out, "B0C_SHA256SUMS"), "w", encoding="utf-8") as f:
            f.write(f"{A.sha256(op)}  b0c_public.json\n")
        print("B0C_VERDICT COMPLETE")
        return 0
    except Exception as e:  # 행 값이 담길 수 있는 메시지는 비공개 로그로만
        traceback.print_exc(file=plog)
        print(f"B0C_VERDICT INVALID exception={type(e).__name__} stage={stage}")
        return 2
    finally:
        sys.stderr = old_err
        plog.close()


if __name__ == "__main__":
    sys.exit(main())
