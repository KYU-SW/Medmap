#!/usr/bin/env python3
"""NBI-B0c 변이 시험 — 임시 사본에서 규칙을 하나씩 깨뜨리고 합성 시험이 실패(KILLED)하는지 확인. 실데이터 미사용.

실행: python3 docs/research/nbi/b0/tests/mutation_b0c.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MUTANTS = [
    ("value_column_read", 'LAB_ALLOW = ["subject_id", "itemid", "charttime", "storetime"]',
     'LAB_ALLOW = ["subject_id", "itemid", "charttime", "storetime", "valuenum"]'),
    ("charttime_as_available", "                if k not in first or st < first[k]:\n                    first[k] = st",
     "                if k not in first or st < first[k]:\n                    first[k] = ct"),
    ("no_outtime_bound", "            if it <= st <= ot and assigned(subj, st) == sid:",
     "            if it <= st and assigned(subj, st) == sid:"),
    ("no_overlap_assignment", "            if it <= st <= ot and assigned(subj, st) == sid:",
     "            if it <= st <= ot:"),
    ("pre_t0_collected_counted", "                if ct is not None and ct < it:", "                if False:"),
    ("no_uncertain_rule", "            elif uncertain:", "            elif False:"),
    ("share_min_removed", "if ok and n >= SHARE_MIN_POOL else", "if ok and n >= 0 else"),
    ("expose_pooled_count", "            shares[t] = bin_or_withheld(w, n_a + n_b, evaluable)",
     "            shares[t] = str(w)"),
    ("nmin_lowered", '"RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= N_MIN else', '"RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= 1 else'),
    ("partial_counts_as_eligible", 'hit = any(labels[t] == "RECORDED_IN_STAY_AVAILABLE" for t',
     'hit = any(labels[t] not in ("NOT_EVALUABLE", "NOT_AVAILABLE_IN_DATA") for t'),
    ("ddimer_dropped_from_rule", 'for t in ("BIOMARKER_TROPONIN", "BIOMARKER_DDIMER"))', 'for t in ("BIOMARKER_TROPONIN",))'),
    ("no_guard", "        if guard(pub):", "        if False:"),
    ("no_item_map_check", "        if item_map(a.d_labitems) != ITEMS:", "        if False:"),
    ("no_cohort_check", "        if not cohort_matches_b0a(", "        if False and not cohort_matches_b0a("),
    ("sealed_before_checks", "        if item_map(a.d_labitems) != ITEMS:",
     "        os.makedirs(a.sealed)\n        if item_map(a.d_labitems) != ITEMS:"),
    ("uncertain_event_unit", "uncertain = len(all_miss) >= Q_MIN and len(all_miss) / len(coll) >= UNCERTAIN_MISSING_SHARE",
     "uncertain = (miss / (miss + okn) if miss + okn else 0) >= UNCERTAIN_MISSING_SHARE"),
    ("uncertain_boundary_gt", "len(all_miss) / len(coll) >= UNCERTAIN_MISSING_SHARE", "len(all_miss) / len(coll) > UNCERTAIN_MISSING_SHARE"),
    ("uncertain_no_min_stays", "uncertain = len(all_miss) >= Q_MIN and", "uncertain = len(all_miss) >= 1 and"),
    ("strata_public", '"labels": labels, "pooled_share_bin": shares, "timing": timing,',
     '"labels": labels, "pooled_share_bin": shares, "timing": timing, "share_bin_admitted": dict(shares),'),
    ("prior_admission_not_strict", "            if x < stays[sid][1]:", "            if x < stays[sid][1] + dt.timedelta(days=1):"),
]


def main():
    src = open(os.path.join(B, "b0c_availability.py"), encoding="utf-8").read()
    res = []
    for name, old, new in MUTANTS:
        if src.count(old) != 1:
            res.append((name, "NOT_APPLIED"))
            continue
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tests", "fixtures"))
            open(os.path.join(d, "b0c_availability.py"), "w", encoding="utf-8").write(src.replace(old, new))
            for f in ("b0a_availability.py", "expected_schema.json", "expected_schema_b0c.json"):
                shutil.copy(os.path.join(B, f), d)
            for f in ("test_b0a.py", "test_b0c.py"):
                shutil.copy(os.path.join(B, "tests", f), os.path.join(d, "tests"))
            shutil.copy(os.path.join(B, "tests", "fixtures", "cms_icd_titles.json"), os.path.join(d, "tests", "fixtures"))
            r = subprocess.run([sys.executable, "-W", "ignore", "-B", "-m", "unittest", "tests/test_b0c.py"], cwd=d,
                               capture_output=True)
            res.append((name, "SURVIVED" if r.returncode == 0 else "KILLED"))
    for n, s in res:
        print(f"{n} {s}")
    bad = [n for n, s in res if s != "KILLED"]
    print("MUTATION_SUMMARY killed=%d total=%d" % (len(res) - len(bad), len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
