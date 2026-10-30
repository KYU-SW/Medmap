#!/usr/bin/env python3
"""NBI-B1 변이 시험(rev2) — 임시 사본에서 규칙을 하나씩 깨뜨리고 합성 시험이 실패(KILLED)하는지 확인. 실데이터 미사용.

실행: python3 docs/research/nbi/b1/tests/mutation_b1.py
동치 변이 제외: no_outtime_cap(wend 의 outtime 상한 제거) — 적격 조건 in_st 가 이미 st ≤ outtime 을 요구함.
"""
import os
import shutil
import subprocess
import sys
import tempfile

B1 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B0 = os.path.abspath(os.path.join(B1, "..", "b0"))
FIRST = 'e = el[0]'
MUTANTS = [
    ("flag_column_read", '"value", "valuenum", "valueuom"]', '"value", "valuenum", "valueuom", "flag"]'),
    ("chiefcomplaint_read", 'TRIAGE_ALLOW = ["stay_id", "temperature",', 'TRIAGE_ALLOW = ["stay_id", "chiefcomplaint", "temperature",'),
    ("label_in_features", 'base = [age, 1.0 if g == "F" else (0.0 if g == "M" else None)]', 'base = [age, 1.0 if cls == "PE" else 0.0]'),
    ("window_extended", "WINDOW_H = 6 ", "WINDOW_H = 24 "),
    ("pre_arrival_collection_allowed", "elig = in_st and st <= wend and (ct is None or ct >= it)", "elig = in_st and st <= wend"),
    ("charttime_missing_ineligible", "elig = in_st and st <= wend and (ct is None or ct >= it)",
     "elig = in_st and st <= wend and (ct is not None and ct >= it)"),
    ("no_assignment", "in_st = st is not None and it <= st <= ot and assigned(subj, st) == sid",
     "in_st = st is not None and it <= st <= ot"),
    ("time_missing_window_stay", "tmiss = st is None and ct is not None and it <= ct <= wend and",
     "tmiss = st is None and ct is not None and it <= ct <= ot and"),
    ("first_by_latest", FIRST, "e = el[-1]"),
    ("first_by_extreme_value", FIRST, 'e = max(el, key=lambda e: (parse_value(e["value"], e["valuenum"])[0] or 0))'),
    ("tie_break_reordered", 'key=lambda e: (e["st"], e["ct"] or e["st"], e["item"], e["seq"])', 'key=lambda e: (e["st"], e["item"], e["seq"])'),
    ("assays_pooled", 'r["labs"][c]["status"] in USABLE and r["labs"][c]["item"] == item]', 'r["labs"][c]["status"] in USABLE]'),
    ("no_unit_check", "    if len(units) > 1:", "    if False:"),
    ("unit_missing_counted", 'if kind in USABLE and not unit_norm(e["uom"]):', "if False:"),
    ("unit_not_normalized", 'return re.sub(r"\\s+", "", (u or "")).lower()', 'return (u or "").strip()'),
    ("censored_dropped", "    if m:\n        b = float(m.group(2))", "    if False:\n        b = float(m.group(2))"),
    ("censored_as_bound", "return (b - CENS_OFFSET if m.group(1) == \"<\" else b + CENS_OFFSET)", "return (b"),
    ("censored_sign_flipped", 'if m.group(1) == "<" else b + CENS_OFFSET', 'if m.group(1) == ">" else b + CENS_OFFSET'),
    ("not_measured_as_zero", 'labs[c] = {"status": "NOT_MEASURED"}',
     'labs[c] = {"status": "MEASURED_NUMERIC", "item": CONCEPTS[c][0], "x": 0.0, "uom": "ng/mL", "bound": None}'),
    ("time_missing_counted", 'elif any(e["tmiss"] for e in es):', "elif False:"),
    ("vital_range_removed", "vit[k] = x if x is not None and lo <= x <= hi else None", "vit[k] = x"),
    ("age_not_corrected", "age = age0 + (stays[sid][1].year - ay) if", "age = age0 if"),
    ("nmin_lowered", "    elif min(na, npe) < N_MIN_B1:", "    elif min(na, npe) < 1:"),
    ("baseline_nmin_bypass", "if evaluable and min(na, npe) >= N_MIN_B1:", "if evaluable:"),
    ("train_on_test", "tr = [i for i in range(n) if folds[i] != f]", "tr = list(range(n))"),
    ("unstratified_folds", "            folds[i] = r % K_FOLDS", "            folds[i] = subj_hash(subjects[i]) % K_FOLDS"),
    ("prep_fit_on_all", "        Xtr, Xte = prep(rtr, rte)",
     "        Xall, _ = prep(rtr + rte, rte)\n        Xtr, Xte = Xall[:len(rtr)], Xall[len(rtr):]"),
    ("ecdf_on_all", "tv = sorted(lab[i] for i in tr)", "tv = sorted(lab)"),
    ("pooled_oof_auroc", "a0, a1, av = fold_auroc(s0, y, folds), fold_auroc(s1, y, folds), auroc(x, y)",
     "a0, a1, av = auroc(s0, y), auroc(s1, y), auroc(x, y)"),
    ("boot_unpaired", "vals.append(fold_auroc(oof(bb, yy, ff, lab=ll), yy, ff) - a0)",
     "j = resample(y, rng)\n                vals.append(fold_auroc(oof([base[i] for i in j], [y[i] for i in j], [folds[i] for i in j], "
     "lab=[lab[i] for i in j]), [y[i] for i in j], [folds[i] for i in j]) - a0)"),
    ("boot_unstratified", "return [pos[rng.randrange(len(pos))] for _ in pos] + [neg[rng.randrange(len(neg))] for _ in neg]",
     "return [rng.randrange(len(y)) for _ in y]"),
    ("boot_refolds_replicates", "ff = [base[i] for i in idx], [y[i] for i in idx], [folds[i] for i in idx]",
     "ff = [base[i] for i in idx], [y[i] for i in idx], strat_folds([str(k) for k in range(len(idx))], [y[i] for i in idx])"),
    ("ci_80", "return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]",
     "return vals[int(0.1 * len(vals))], vals[int(0.9 * len(vals)) - 1]"),
    ("boot_count_changed", "B_BOOT, BOOT_SEED = 1000, 20261006", "B_BOOT, BOOT_SEED = 50, 20261006"),
    ("ridge_changed", "RIDGE = 1.0 ", "RIDGE = 100.0 "),
    ("feasible_inverted", 'return "FEASIBLE" if (hi - lo) / 2 <= FEASIBLE_HALF_WIDTH else', 'return "FEASIBLE" if (hi - lo) / 2 > FEASIBLE_HALF_WIDTH else'),
    ("feasible_strict_lt", 'return "FEASIBLE" if (hi - lo) / 2 <= FEASIBLE_HALF_WIDTH else', 'return "FEASIBLE" if (hi - lo) / 2 < FEASIBLE_HALF_WIDTH else'),
    ("half_width_changed", "FEASIBLE_HALF_WIDTH = 0.10 ", "FEASIBLE_HALF_WIDTH = 0.50 "),
    ("expose_exact_n", 'P = {"n_bucket_acs": n_bucket(na), "n_bucket_pe": n_bucket(npe)}', 'P = {"n_bucket_acs": str(na), "n_bucket_pe": n_bucket(npe)}'),
    ("measured_bin_no_min", '"acs_measured_bin": A.share_bin(meas_a, na) if evaluable and na >= A.SHARE_MIN_POOL',
     '"acs_measured_bin": A.share_bin(meas_a, na) if evaluable and na >= 1'),
    ("measured_bin_pooled_denominator", '"acs_measured_bin": A.share_bin(meas_a, na) if', '"acs_measured_bin": A.share_bin(meas_a, na + npe) if'),
    ("dq_excludes_unusable", 'dq = sum(sum(stat[k]) for k in ("MEASURED_UNUSABLE", "UNIT_MISSING", "TIME_MISSING"))',
     'dq = sum(sum(stat[k]) for k in ("UNIT_MISSING", "TIME_MISSING"))'),
    ("no_guard", "        if guard(pub):", "        if False:"),
    ("guard_no_range", "if not (METRIC_RX.match(v) and lo <= float(v) <= 1.0):", "if not METRIC_RX.match(v):"),
    ("guard_loose_regex", 'METRIC_RX = re.compile(r"^-?\\d\\.\\d\\d$")', 'METRIC_RX = re.compile(r"^-?\\d+\\.\\d+$")'),
    ("no_cohort_check", '            if not cohort_matches(pub, json.load(open(ref, encoding="utf-8"))):', "            if False:"),
    ("no_item_map_check", "        if im != C.ITEMS or any(", "        if False and any("),
    ("sealed_before_checks", "        im = C.item_map(a.d_labitems)", "        os.makedirs(a.sealed)\n        im = C.item_map(a.d_labitems)"),
]


def main():
    src = open(os.path.join(B1, "b1_feasibility.py"), encoding="utf-8").read()
    res = []
    for name, old, new in MUTANTS:
        if src.count(old) != 1:
            res.append((name, "NOT_APPLIED"))
            continue
        with tempfile.TemporaryDirectory() as d:
            b1, b0 = os.path.join(d, "nbi", "b1"), os.path.join(d, "nbi", "b0")
            os.makedirs(os.path.join(b1, "tests"))
            os.makedirs(os.path.join(b0, "tests", "fixtures"))
            open(os.path.join(b1, "b1_feasibility.py"), "w", encoding="utf-8").write(src.replace(old, new))
            shutil.copy(os.path.join(B1, "expected_schema_b1.json"), b1)
            shutil.copy(os.path.join(B1, "tests", "test_b1.py"), os.path.join(b1, "tests"))
            for f in ("b0a_availability.py", "b0c_availability.py", "expected_schema.json", "expected_schema_b0c.json"):
                shutil.copy(os.path.join(B0, f), b0)
            for f in ("test_b0a.py", "test_b0c.py"):
                shutil.copy(os.path.join(B0, "tests", f), os.path.join(b0, "tests"))
            shutil.copy(os.path.join(B0, "tests", "fixtures", "cms_icd_titles.json"), os.path.join(b0, "tests", "fixtures"))
            try:
                r = subprocess.run([sys.executable, "-W", "ignore", "-B", "-m", "unittest", "tests/test_b1.py"], cwd=b1,
                                   capture_output=True, timeout=600)
                res.append((name, "SURVIVED" if r.returncode == 0 else "KILLED"))
            except subprocess.TimeoutExpired:
                res.append((name, "KILLED_TIMEOUT"))
        print(name, res[-1][1], flush=True)
    bad = [n for n, s in res if not s.startswith("KILLED")]
    print("MUTATION_SUMMARY killed=%d total=%d" % (len(res) - len(bad), len(res)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
