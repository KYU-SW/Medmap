#!/usr/bin/env python3
"""NBI-B0a v2 변이 시험 — 임시 사본에서 규칙을 하나씩 깨뜨리고 합성 시험이 실패(KILLED)하는지 확인. 실데이터 미사용.

실행: python3 docs/research/nbi/b0/tests/mutation_b0a.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MUTANTS = [
    ("expose_pool_count", 'shares[t] = share_bin(w, n_a + n_b) if evaluable and n_a + n_b >= SHARE_MIN_POOL else "WITHHELD"',
     "shares[t] = str(w)"),
    ("expose_class_size", '"cohort_pooled_bucket": pool_bucket(n_a + n_b),', '"cohort_pooled_bucket": str(n_a),'),
    ("old_title_kw", 'r"infarct", r"stemi", r"\\bami\\b", r"angina", r"ang pctrs", r"coronary synd"',
     '"infarction", "angina", "coronary syndrome"'),
    ("i249_in_acs", 'r"^I22"] + UA_SET_10', 'r"^I22", r"^I249$"] + UA_SET_10'),
    ("no_guard", "        if guard(pub):", "        if False:"),
    ("no_multi", 'cls = "a" if A and not Bq else "b" if Bq and not A else "multi"', 'cls = "a" if A else "b"'),
    ("no_outtime_bound", "        elif t <= ot:", "        elif True:"),
    ("skip_multi_first", "first[subj] = (lst[0][2], lst[0][3])",
     'first[subj] = next(((x[2], x[3]) for x in lst if x[3] != "multi"), (lst[0][2], lst[0][3]))'),
    ("timing_rounded", "statistics.median(vals) <= 1.0", "round(statistics.median(vals) * 2) / 2 <= 1.0"),
    ("no_title_check", "    if any(mismatch.values()):", "    if False:"),
    ("no_dot_strip", '.strip().upper().replace(".", "")', ".strip().upper()"),
    ("boundary_lost", '"ICD9_410x2": {"10": [], "9": [r"^410\\d2$"]}', '"ICD9_410x2": {"10": [], "9": []}'),
    ("share_min_removed", "SHARE_MIN_POOL = 100", "SHARE_MIN_POOL = 0"),
    ("tie_break_reversed", "lst.sort(key=lambda x: (x[0], x[1]))", "lst.sort(key=lambda x: (x[0], -x[1]))"),
    ("ecg_allow_extra", '"ecg": ["ed_stay_id", "ecg_time"],', '"ecg": ["ed_stay_id", "ecg_time", "ed_diag_ed"],'),
    ("stop_writes_sealed_first", "        if d[\"verdict\"] == \"STOP_TITLE\":", "        os.makedirs(a.sealed)\n        if d[\"verdict\"] == \"STOP_TITLE\":"),
]


def main():
    src = open(os.path.join(B, "b0a_availability.py"), encoding="utf-8").read()
    res = []
    for name, old, new in MUTANTS:
        if src.count(old) != 1:
            res.append((name, "NOT_APPLIED"))
            continue
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tests", "fixtures"))
            open(os.path.join(d, "b0a_availability.py"), "w", encoding="utf-8").write(src.replace(old, new))
            shutil.copy(os.path.join(B, "tests", "test_b0a.py"), os.path.join(d, "tests"))
            shutil.copy(os.path.join(B, "tests", "fixtures", "cms_icd_titles.json"), os.path.join(d, "tests", "fixtures"))
            shutil.copy(os.path.join(B, "expected_schema.json"), d)
            r = subprocess.run([sys.executable, "-W", "ignore", "-B", "-m", "unittest", "tests/test_b0a.py"], cwd=d,
                               capture_output=True)
            res.append((name, "SURVIVED" if r.returncode == 0 else "KILLED"))
    for n, s in res:
        print(f"{n} {s}")
    bad = [n for n, s in res if s != "KILLED"]
    print("MUTATION_SUMMARY killed=%d total=%d" % (len(res) - len(bad), len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
