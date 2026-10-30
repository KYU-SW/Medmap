#!/usr/bin/env python3
"""NBI-B0d 변이 시험 — 임시 사본에서 규칙을 하나씩 깨뜨리고 합성 시험이 실패(KILLED)하는지 확인. 실데이터 미사용.

실행: python3 docs/research/nbi/b0/tests/mutation_b0d.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MUTANTS = [
    ("text_column_read", 'RAD_ALLOW = ["note_id", "subject_id", "note_type", "charttime", "storetime"]',
     'RAD_ALLOW = ["note_id", "subject_id", "note_type", "charttime", "storetime", "text"]'),
    ("hadm_id_read", 'RAD_ALLOW = ["note_id", "subject_id", "note_type", "charttime", "storetime"]',
     'RAD_ALLOW = ["note_id", "subject_id", "hadm_id", "note_type", "charttime", "storetime"]'),
    ("cpt_used_for_concept", '        if r["field_name"] != "exam_name":',
     '        if r["field_name"] not in ("exam_name", "cpt_code"):'),
    ("coronary_cta_included", 'RULES = {"IMAGING_CTA_CHEST": re.compile(r"^CTA CHEST\\b")',
     'RULES = {"IMAGING_CTA_CHEST": re.compile(r"^CTA (CHEST|CORONARY)\\b")'),
    ("cxr_included_in_chest_ct", '"IMAGING_CHEST_CT": re.compile(r"^CT CHEST\\b")}',
     '"IMAGING_CHEST_CT": re.compile(r"^(CT )?CHEST\\b")}'),
    ("lcs_included", '"IMAGING_CHEST_CT": re.compile(r"^CT CHEST\\b")}', '"IMAGING_CHEST_CT": re.compile(r"CT CHEST\\b")}'),
    ("no_exam_map_check", "        if exams != EXAMS:", "        if False:"),
    ("addendum_counted", '        if r["note_type"].strip() != REPORT_NOTE_TYPE:', "        if False:"),
    ("report_uses_charttime", "                    elif kr not in first or st < first[kr]:\n                        first[kr] = st",
     "                    elif kr not in first or st < first[kr]:\n                        first[kr] = ct or st"),
    ("study_uses_storetime", "                    if ks not in first or ct < first[ks]:\n                        first[ks] = ct",
     "                    if ks not in first or ct < first[ks]:\n                        first[ks] = st or ct"),
    ("layers_merged", "            in_st = st is not None and it <= st <= ot and assigned(subj, st) == sid",
     "            in_st = in_ct or (st is not None and it <= st <= ot and assigned(subj, st) == sid)"),
    ("no_outtime_bound_study", "            in_ct = ct is not None and it <= ct <= ot and assigned(subj, ct) == sid",
     "            in_ct = ct is not None and it <= ct and assigned(subj, ct) == sid"),
    ("no_outtime_bound_report", "            in_st = st is not None and it <= st <= ot and assigned(subj, st) == sid",
     "            in_st = st is not None and it <= st and assigned(subj, st) == sid"),
    ("no_overlap_assignment", "            in_ct = ct is not None and it <= ct <= ot and assigned(subj, ct) == sid",
     "            in_ct = ct is not None and it <= ct <= ot"),
    ("pre_t0_study_counted", "                    if ct is not None and ct < it:\n                        pre_study[kr] = 1",
     "                    if False:\n                        pre_study[kr] = 1"),
    ("no_uncertain_rule", "            elif uncertain:", "            elif False:"),
    ("uncertain_event_unit", "uncertain = len(all_miss) >= Q_MIN and len(all_miss) / len(seen) >= UNCERTAIN_MISSING_SHARE",
     "uncertain = (A_ev := sum(d['miss_n'].get((s, t), 0) for s in pool)) >= Q_MIN and A_ev / max(1, A_ev + sum("
     "d['ok_n'].get((s, t), 0) for s in pool)) >= UNCERTAIN_MISSING_SHARE"),
    ("uncertain_boundary_gt", "len(all_miss) / len(seen) >= UNCERTAIN_MISSING_SHARE",
     "len(all_miss) / len(seen) > UNCERTAIN_MISSING_SHARE"),
    ("uncertain_no_min_stays", "uncertain = len(all_miss) >= Q_MIN and", "uncertain = len(all_miss) >= 1 and"),
    ("share_min_removed", "if ok and n >= SHARE_MIN_POOL else", "if ok and n >= 0 else"),
    ("expose_pooled_count", "            shares[t] = bin_or_withheld(w, n_a + n_b, evaluable)",
     "            shares[t] = str(w)"),
    ("nmin_lowered", '"RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= N_MIN else',
     '"RECORDED_IN_STAY_AVAILABLE" if min(ca, cb) >= 1 else'),
    ("strata_public", '"labels": labels, "pooled_share_bin": shares, "timing": timing,',
     '"labels": labels, "pooled_share_bin": shares, "timing": timing, "share_bin_admitted": dict(shares),'),
    ("no_guard", "        if guard(pub):", "        if False:"),
    ("no_cohort_check", "            if not cohort_matches(pub, json.load(open(ref, encoding=\"utf-8\"))):",
     "            if False:"),
    ("b0c_ref_skipped", "        for ref in (a.b0a_public, a.b0c_public):", "        for ref in (a.b0a_public,):"),
    ("sealed_before_checks", "        exams, note_c = exam_scan(a.radiology_detail)",
     "        os.makedirs(a.sealed)\n        exams, note_c = exam_scan(a.radiology_detail)"),
    ("duplicate_latest_not_earliest", "                    if ks not in first or ct < first[ks]:",
     "                    if ks not in first or ct > first[ks]:"),
]


def main():
    src = open(os.path.join(B, "b0d_availability.py"), encoding="utf-8").read()
    res = []
    for name, old, new in MUTANTS:
        if src.count(old) != 1:
            res.append((name, "NOT_APPLIED"))
            continue
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tests", "fixtures"))
            os.makedirs(os.path.join(d, "b0d"))
            open(os.path.join(d, "b0d_availability.py"), "w", encoding="utf-8").write(src.replace(old, new))
            for f in ("b0a_availability.py", "expected_schema.json", "expected_schema_b0d.json"):
                shutil.copy(os.path.join(B, f), d)
            shutil.copy(os.path.join(B, "b0d", "exam_map.json"), os.path.join(d, "b0d"))
            for f in ("test_b0a.py", "test_b0d.py"):
                shutil.copy(os.path.join(B, "tests", f), os.path.join(d, "tests"))
            shutil.copy(os.path.join(B, "tests", "fixtures", "cms_icd_titles.json"), os.path.join(d, "tests", "fixtures"))
            r = subprocess.run([sys.executable, "-W", "ignore", "-B", "-m", "unittest", "tests/test_b0d.py"], cwd=d,
                               capture_output=True)
            res.append((name, "SURVIVED" if r.returncode == 0 else "KILLED"))
    for n, s in res:
        print(f"{n} {s}")
    bad = [n for n, s in res if s != "KILLED"]
    print("MUTATION_SUMMARY killed=%d total=%d" % (len(res) - len(bad), len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
