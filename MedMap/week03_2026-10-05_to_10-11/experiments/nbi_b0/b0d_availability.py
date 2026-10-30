#!/usr/bin/env python3
"""EXP-SN-NBI-002 NBI-B0d — MIMIC-IV-Note radiology imaging study/report availability / temporal feasibility.

LOCAL ONLY. 코호트는 고정 B0a 모듈(b0a_availability.compute)을 그대로 재사용한다(동일 코호트·동일 class·동일 주 단위).
영상 개념은 radiology_detail 의 exam_name 정확 문자열(사전 고정 b0d/exam_map.json)로만 정한다 — 보고서 본문(text)·
indication·impression·소견 문구·cpt_code·exam_code·hadm_id 는 읽지 않는다.
두 층을 분리한다: STUDY = RR 판독문의 charttime(검사/기록 시각 대리) ∈ ED 체류, REPORT = RR storetime(서명·저장 시각)
∈ ED 체류. addendum(AR)은 쓰지 않는다. 연결 = subject_id ∧ 시각 ∈ window([E]), hadm_id 미사용.
공개 출력 = 사전 고정 어휘의 라벨·pooled 거친 구간값만(숫자 없음). exact·class별·window별·지연·판독 지연 수치는
봉인 파일(로컬 제한 폴더, SHA만 공개)에만. stdout = 판정 1줄. 영상 결과·판별 성능·환자 단위 출력 없음.
"""
import argparse
import bisect
import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b0a_availability as A  # noqa: E402  (고정 B0a 모듈: 코호트·코드표·공통 함수, 수정 금지)

csv.field_size_limit(1 << 30)  # radiology text 필드는 파서가 지나가기만 함(보관·참조 안 함)

CONCEPTS = ["IMAGING_CTA_CHEST", "IMAGING_CHEST_CT"]
LAYERS = ["STUDY", "REPORT"]
TYPES = [f"{c}_{l}" for c in CONCEPTS for l in LAYERS]
# 개념 규칙(exam_name 대문자 정확 문자열의 접두, b0d_exam_map.py 와 동일)
RULES = {"IMAGING_CTA_CHEST": re.compile(r"^CTA CHEST\b"), "IMAGING_CHEST_CT": re.compile(r"^CT CHEST\b")}
# 고정 exam_name(radiology_detail sha256 9d3f6c44… 정찰 어휘에 규칙을 적용한 결과, 실행 시 재계산해 불일치하면 INVALID)
EXAMS = {
    "IMAGING_CTA_CHEST": frozenset({"CTA CHEST", "CTA CHEST W&W/O C&RECONS, NON-CORONARY"}),
    "IMAGING_CHEST_CT": frozenset({"CT CHEST W&W/O C", "CT CHEST W/CONTRAST", "CT CHEST W/CONTRAST W/ONC TABLE",
                                   "CT CHEST W/O CONTRAST"}),
}
RAD_ALLOW = ["note_id", "subject_id", "note_type", "charttime", "storetime"]  # text·hadm_id 는 참조하지 않음
DET_ALLOW = ["note_id", "field_name", "field_value"]
REPORT_NOTE_TYPE = "RR"
WINDOWS_H = (1, 3, 6)  # 봉인 전용(공개는 W_STAY 만)
AROUND_H = 24  # pre-T0 / post-ED 서술용(봉인 전용)
UNCERTAIN_MISSING_SHARE = 0.5  # stay 단위: 상대 시각으로 체류 중 확인된 stay 중 이 층 시각이 전부 결측인 stay 비율 ≥ 이 값
#                                ∧ 그 stay 수 ≥ Q_MIN 이면 TEMPORALLY_UNCERTAIN (사전 고정, 민감도 분석 금지, B0c rev7 와 동일)
N_MIN, Q_MIN, SHARE_MIN_POOL = A.N_MIN, A.Q_MIN, A.SHARE_MIN_POOL
ALLOWED_VALUES = (
    {"EVALUABLE", "NOT_EVALUABLE", "NOT_AVAILABLE_IN_DATA", "TEMPORALLY_UNCERTAIN", "RECORDED_IN_STAY_AVAILABLE",
     "RECORDED_IN_STAY_PARTIAL", "WITHHELD", "EARLY_ROUTINE_POSSIBLE", "LATER_IN_STAY", "INSUFFICIENT_N"}
    | {b[2] for b in A.POOL_BUCKETS} | set(A.SHARE_BINS)
)


def rows_gz(path, cols):
    """csv.gz 스트리밍, 허용 컬럼만 dict 로 반환(B0a/B0c rows 와 같은 방식)."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        idx = {c: header.index(c) for c in cols}
        for r in rd:
            yield {c: r[i] for c, i in idx.items()}


def concept_of(name):
    n = name.strip().upper()
    return [c for c in CONCEPTS if RULES[c].search(n)]


def exam_scan(det_path):
    """radiology_detail: (규칙 재적용 결과 {개념: exam_name 집합}, {note_id: 개념 집합}). exam_name 행만 사용."""
    got = {c: set() for c in CONCEPTS}
    note_c = {}
    for r in rows_gz(det_path, DET_ALLOW):
        if r["field_name"] != "exam_name":
            continue
        name = r["field_value"].strip()
        for c in concept_of(name):
            got[c].add(name)
            note_c.setdefault(r["note_id"].strip(), set()).add(c)
    return {c: frozenset(s) for c, s in got.items()}, note_c


def compute_b0d(ed_zip, ecg_zip, rad_path, note_c):
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

    first = {}  # (sid, type) -> 가장 이른 시각(STUDY = charttime, REPORT = storetime), 체류 안
    ok_n, miss_n = {}, {}  # (sid, type) -> 다른 층 시각으로 체류 중 확인된 사건 중 이 층 시각 있음 / 결측
    pre_study, pre24, post24, rep_after_ed, lag_h = {}, {}, {}, {}, {}
    ar_skipped = 0
    for r in rows_gz(rad_path, RAD_ALLOW):
        cs = note_c.get(r["note_id"].strip())
        if not cs:
            continue
        if r["note_type"].strip() != REPORT_NOTE_TYPE:
            ar_skipped += 1
            continue
        subj = A.norm_id(r["subject_id"])
        if subj not in subj_main:
            continue
        ct, st = A.parse_time(r["charttime"]), A.parse_time(r["storetime"])
        for sid in subj_main[subj]:
            _, it, ot, _ = stays[sid]
            in_ct = ct is not None and it <= ct <= ot and assigned(subj, ct) == sid
            in_st = st is not None and it <= st <= ot and assigned(subj, st) == sid
            for c in cs:
                ks, kr = (sid, c + "_STUDY"), (sid, c + "_REPORT")
                # STUDY 층: charttime ∈ W_STAY ∧ 배정 stay
                if in_ct:
                    if ks not in first or ct < first[ks]:
                        first[ks] = ct
                    if st is None:
                        miss_n[kr] = miss_n.get(kr, 0) + 1  # 체류 중 검사, 판독 시각 결측
                    else:
                        ok_n[kr] = ok_n.get(kr, 0) + 1
                        if st > ot:
                            rep_after_ed[kr] = 1  # 체류 중 검사, 판독 서명은 ED 이탈 후
                        lag_h.setdefault(kr, []).append((st - ct).total_seconds() / 3600)
                elif ct is not None:  # 봉인 서술: 체류 밖 검사 시각(±24 h)
                    if it - dt.timedelta(hours=AROUND_H) <= ct < it:
                        pre24[ks] = 1
                    elif ot < ct <= ot + dt.timedelta(hours=AROUND_H):
                        post24[ks] = 1
                # REPORT 층: storetime ∈ W_STAY ∧ 배정 stay ∧ (charttime ≥ intime 또는 charttime 결측)
                if in_st:
                    if ct is None:
                        miss_n[ks] = miss_n.get(ks, 0) + 1  # 체류 중 판독, 검사 시각 결측
                    else:
                        ok_n[ks] = ok_n.get(ks, 0) + 1
                    if ct is not None and ct < it:
                        pre_study[kr] = 1  # 도착 전 검사·체류 중 판독: 가용으로 세지 않음
                    elif kr not in first or st < first[kr]:
                        first[kr] = st
    d.update({"img_first": first, "ok_n": ok_n, "miss_n": miss_n, "pre_study": pre_study, "pre24": pre24,
              "post24": post24, "rep_after_ed": rep_after_ed, "lag_h": lag_h, "ar_skipped": ar_skipped})
    return d


def has_img(t, sid, d, hours=None):
    x = d["img_first"].get((sid, t))
    if x is None:
        return False
    return hours is None or x <= d["stays"][sid][1] + dt.timedelta(hours=hours)


def img_delay(t, sid, d):
    x = d["img_first"].get((sid, t))
    return None if x is None else (x - d["stays"][sid][1]).total_seconds() / 3600


def bin_or_withheld(w, n, ok):
    return A.share_bin(w, n) if ok and n >= SHARE_MIN_POOL else "WITHHELD"


def build_b0d(d):
    """반환: (public, sealed). public 은 어휘 문자열만, sealed 는 exact 값 전부."""
    pub, sealed = {"pairs": {}}, {"pairs": {}, "ar_notes_skipped": d["ar_skipped"]}
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
        for t in TYPES:
            ca, cb = sum(has_img(t, s, d) for s in a_s), sum(has_img(t, s, d) for s in b_s)
            w = ca + cb
            seen = [s for s in pool if d["ok_n"].get((s, t), 0) + d["miss_n"].get((s, t), 0) > 0]
            all_miss = [s for s in seen if d["ok_n"].get((s, t), 0) == 0]
            uncertain = len(all_miss) >= Q_MIN and len(all_miss) / len(seen) >= UNCERTAIN_MISSING_SHARE
            A_ = {
                "pooled": w, "a": ca, "b": cb,
                "a_admitted": sum(has_img(t, s, d) and d["stays"][s][3] for s in a_s),
                "b_admitted": sum(has_img(t, s, d) and d["stays"][s][3] for s in b_s),
                "windows": {f"W{h}": {"a": sum(has_img(t, s, d, h) for s in a_s),
                                      "b": sum(has_img(t, s, d, h) for s in b_s)} for h in WINDOWS_H},
                "time_missing_events": sum(d["miss_n"].get((s, t), 0) for s in pool),
                "time_present_events": sum(d["ok_n"].get((s, t), 0) for s in pool),
                "stays_seen_in_stay": len(seen), "stays_all_time_missing": len(all_miss),
                "stratum_admitted_recorded": sum(has_img(t, s, d) for s in adm),
                "stratum_not_admitted_recorded": sum(has_img(t, s, d) for s in nadm),
            }
            if t.endswith("_REPORT"):
                A_["pre_t0_study_stays"] = sum((s, t) in d["pre_study"] for s in pool)
                A_["report_after_ed_stays"] = sum((s, t) in d["rep_after_ed"] for s in pool)
                lags = [x for s in pool for x in d["lag_h"].get((s, t), [])]
                A_["report_lag_h_event_quantiles"] = A.quantiles(lags)
            else:
                A_["pre_t0_24h_stays"] = sum((s, t) in d["pre24"] for s in pool)
                A_["post_ed_24h_stays"] = sum((s, t) in d["post24"] for s in pool)
            S["avail"][t] = A_
            if not evaluable:
                labels[t] = "NOT_EVALUABLE"
            elif uncertain:
                labels[t] = "TEMPORALLY_UNCERTAIN"
            elif w == 0:
                labels[t] = "NOT_AVAILABLE_IN_DATA"
            else:
                labels[t] = "RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= N_MIN else "RECORDED_IN_STAY_PARTIAL"
            shares[t] = bin_or_withheld(w, n_a + n_b, evaluable)
            vals = [x for x in (img_delay(t, s, d) for s in pool) if x is not None]
            S["delays_h"][t] = A.quantiles(vals)
            timing[t] = "NOT_EVALUABLE" if not evaluable else \
                ("TEMPORALLY_UNCERTAIN" if labels[t] == "TEMPORALLY_UNCERTAIN" else A.timing_label(vals))
            S["timing_label"][t] = timing[t]
        sealed["pairs"][p] = S
        pub["pairs"][p] = {
            "pair_status": "EVALUABLE" if evaluable else "NOT_EVALUABLE",
            "cohort_pooled_bucket": A.pool_bucket(n_a + n_b),
            "labels": labels, "pooled_share_bin": shares, "timing": timing,  # 입원/비입원 층은 봉인 전용
        }
    return pub, sealed


def guard(pub):
    return [k for k, v in A.flatten(pub) if not (isinstance(v, str) and v in ALLOWED_VALUES)]


def cohort_matches(pub, ref_pub):
    """기준 공개 출력(B0a·B0c)과 쌍 상태·코호트 구간이 같아야 동일 코호트로 인정."""
    return all(pub["pairs"][p]["pair_status"] == ref_pub["pairs"][p]["pair_status"]
               and pub["pairs"][p]["cohort_pooled_bucket"] == ref_pub["pairs"][p]["cohort_pooled_bucket"]
               for p in A.PAIRS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("ed-zip", "ed-zip-sha", "ecg-zip", "ecg-zip-sha", "radiology", "radiology-sha", "radiology-detail",
              "radiology-detail-sha", "schema", "schema-sha", "b0a-public", "b0a-public-sha", "b0c-public",
              "b0c-public-sha", "out", "sealed", "private-log"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    for p in (a.out, a.sealed):
        if os.path.exists(p):
            print("B0D_VERDICT INVALID reason=output_exists stage=preflight")
            return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.private_log)), exist_ok=True)
    plog = open(a.private_log, "a", encoding="utf-8")
    old_err, sys.stderr = sys.stderr, plog
    stage = "preflight"
    try:
        for p, h in ((a.ed_zip, a.ed_zip_sha), (a.ecg_zip, a.ecg_zip_sha), (a.radiology, a.radiology_sha),
                     (a.radiology_detail, a.radiology_detail_sha), (a.schema, a.schema_sha),
                     (a.b0a_public, a.b0a_public_sha), (a.b0c_public, a.b0c_public_sha)):
            if A.sha256(p) != h:
                print("B0D_VERDICT INVALID reason=sha_mismatch stage=preflight")
                return 2
        exams, note_c = exam_scan(a.radiology_detail)
        if exams != EXAMS:
            print("B0D_VERDICT INVALID reason=exam_map_mismatch stage=preflight")
            return 2
        stage = "data"
        d = compute_b0d(a.ed_zip, a.ecg_zip, a.radiology, note_c)
        if d["verdict"] == "STOP_TITLE":
            print("B0D_VERDICT STOP_TITLE classes=" + ",".join(d["stop_classes"]))
            return 3
        pub, sealed = build_b0d(d)
        schema = json.load(open(a.schema, encoding="utf-8"))
        if sorted(k for k, _ in A.flatten(pub)) != sorted(schema["keys"]):
            print("B0D_VERDICT INVALID reason=schema_mismatch stage=data")
            return 2
        if guard(pub):
            print("B0D_VERDICT INVALID reason=output_guard stage=data")
            return 2
        for ref in (a.b0a_public, a.b0c_public):
            if not cohort_matches(pub, json.load(open(ref, encoding="utf-8"))):
                print("B0D_VERDICT INVALID reason=cohort_mismatch stage=data")
                return 2
        os.makedirs(a.sealed)
        os.chmod(a.sealed, 0o700)
        sp = os.path.join(a.sealed, "b0d_sealed.json")
        json.dump(sealed, open(sp, "w", encoding="utf-8"), sort_keys=True, indent=1, default=str)
        pub["meta"] = {"experiment": "EXP-SN-NBI-002", "phase": "B0d", "n_min": N_MIN, "q_min": Q_MIN,
                       "share_min_pool": SHARE_MIN_POOL, "uncertain_missing_share": UNCERTAIN_MISSING_SHARE,
                       "study_time": "radiology charttime (RR)", "report_time": "radiology storetime (RR)",
                       "concept_source": "radiology_detail exam_name exact strings (frozen); no report text",
                       "disclosure": "labels and coarse pooled bins only; all exact, class-wise, window-wise, "
                       "delay and report-lag values sealed",
                       "ed_zip_sha256": a.ed_zip_sha, "ecg_zip_sha256": a.ecg_zip_sha,
                       "radiology_sha256": a.radiology_sha, "radiology_detail_sha256": a.radiology_detail_sha,
                       "b0a_public_sha256": a.b0a_public_sha, "b0c_public_sha256": a.b0c_public_sha,
                       "schema_sha256": a.schema_sha, "script_sha256": A.sha256(os.path.abspath(__file__)),
                       "b0a_module_sha256": A.sha256(os.path.abspath(A.__file__)),
                       "sealed_file_sha256": A.sha256(sp), "python": sys.version.split()[0]}
        os.makedirs(a.out)
        op = os.path.join(a.out, "b0d_public.json")
        json.dump(pub, open(op, "w", encoding="utf-8"), sort_keys=True, indent=1)
        with open(os.path.join(a.out, "B0D_SHA256SUMS"), "w", encoding="utf-8") as f:
            f.write(f"{A.sha256(op)}  b0d_public.json\n")
        print("B0D_VERDICT COMPLETE")
        return 0
    except Exception as e:  # 행 값이 담길 수 있는 메시지는 비공개 로그로만
        traceback.print_exc(file=plog)
        print(f"B0D_VERDICT INVALID exception={type(e).__name__} stage={stage}")
        return 2
    finally:
        sys.stderr = old_err
        plog.close()


if __name__ == "__main__":
    sys.exit(main())
