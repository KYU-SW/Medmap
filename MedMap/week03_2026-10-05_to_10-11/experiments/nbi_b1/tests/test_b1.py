"""NBI-B1 합성 fixture 시험(rev2) — 실제 MIMIC 미사용(가짜 ID·시각·값). B0a 시험의 Gen 재사용.

시간 절약을 위해 시험에서는 bootstrap 반복 수만 줄인다(B.B_BOOT = TEST_B). 운영 상수는 TestConstants 가 소스 문자열로 고정한다.
실행: python3 -m unittest docs/research/nbi/b1/tests/test_b1.py
"""
import contextlib
import io
import json
import os
import random
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
B0 = os.path.join(HERE, "..", "..", "b0")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(B0, "tests"))
import b0a_availability as A  # noqa: E402
import b1_feasibility as B  # noqa: E402
from test_b0a import Gen, gz, sha  # noqa: E402
from test_b0c import DLAB_H, LAB_H, dlab_rows  # noqa: E402

SRC = open(os.path.join(HERE, "..", "b1_feasibility.py"), encoding="utf-8").read()
TEST_B = 16
B.B_BOOT = TEST_B
SCHEMA = os.path.join(HERE, "..", "expected_schema_b1.json")
PAT_H = ["subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group", "dod"]
TROP, TROP2, DDIM = "51003", "51002", "50915"
CT = "2150-01-01 10:20:00"
ST = "2150-01-01 11:00:00"


def classes(gen):
    m = {}
    for subj, sid, seq, code, ver, _ in gen.dx:
        if seq == 1:
            m[sid] = (subj, next(c for c in A.CODES if c in A.classify(ver, A.norm_code(code))))
    return m


class Fx:
    def __init__(self, n_acs=150, n_pe=150, hr_signal=False):
        self.gen = Gen(n_acs=n_acs, n_pe=n_pe, n_peri=0)
        self.cls = classes(self.gen)
        self.lab, self.k = [], 0
        if hr_signal:
            self.gen.tr = [r[:3] + (("120" if self.cls[r[1]][1] == "PE" else "80"),) + r[4:] for r in self.gen.tr]
        self.pat = [(s, "F" if i % 2 else "M", "60", "2150", "2017 - 2019", "") for i, (s, _) in
                    enumerate(sorted(self.cls.values()))]

    def sids(self, cls, n, start=0):
        return [s for s, (_, c) in sorted(self.cls.items()) if c == cls][start:start + n]

    def add(self, cls, n, item=TROP, value=None, num=None, uom="ng/mL", ct=CT, st=ST, start=0, fn=None):
        for i, s in enumerate(self.sids(cls, n, start)):
            v = fn(cls, i) if fn else (num if num is not None else ("0.5" if cls == "PE" else "0.05"))
            self.k += 1
            self.lab.append((self.k, self.cls[s][0], "", "1", item, "", ct, st, value if value is not None else v,
                             v if value is None else (num or ""), uom, "0", "1", "abnormal", "STAT", "c"))
        return self

    def write(self, d, dlab=None):
        ed, ecg = self.gen.write(d)
        p = {}
        for name, h, r in (("lab", LAB_H, self.lab), ("pat", PAT_H, self.pat), ("dlab", DLAB_H, dlab or dlab_rows())):
            p[name] = os.path.join(d, name + ".csv.gz")
            with open(p[name], "wb") as f:
                f.write(gz(h, r))
        ref = os.path.join(d, "ref.json")
        dd = A.compute(ed, ecg)
        with open(ref, "w") as f:
            json.dump(A.build(dd)[0] if dd["verdict"] == "OK" else {"pairs": {}}, f)
        return ed, ecg, p, ref


def built(fx):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, p, _ = fx.write(d)
        return B.build_b1(B.compute_b1(ed, ecg, p["lab"], p["pat"]))


def rows_of(fx):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, p, _ = fx.write(d)
        return B.compute_b1(ed, ecg, p["lab"], p["pat"])["b1_rows"]


def margs(d, ed, ecg, p, ref, schema=SCHEMA, refs=None):
    refs = refs or {}
    a = ["--ed-zip", ed, "--ecg-zip", ecg, "--labevents", p["lab"], "--d-labitems", p["dlab"], "--patients", p["pat"],
         "--schema", schema, "--b0a-public", refs.get("a", ref), "--b0c-public", refs.get("c", ref),
         "--b0d-public", refs.get("d", ref)]
    out = []
    for i in range(0, len(a), 2):
        out += [a[i], a[i + 1], a[i] + "-sha", sha(a[i + 1])]
    return out + ["--out", os.path.join(d, "out"), "--sealed", os.path.join(d, "sealed"),
                  "--private-log", os.path.join(d, "priv", "p.log")]


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = B.main(argv)
    return rc, buf.getvalue()


def status(rows, c="TROPONIN"):
    out = {}
    for r in rows.values():
        out[r["labs"][c]["status"]] = out.get(r["labs"][c]["status"], 0) + 1
    return out


def noisy(sep):
    """결정적 잡음 값: PE 쪽 평균을 sep 만큼 이동(합성)."""
    rng = random.Random(7)
    vals = {"ACS": [rng.gauss(0, 1) for _ in range(400)], "PE": [rng.gauss(sep, 1) for _ in range(400)]}
    return lambda c, i: f"{vals[c][i] + 5:.4f}"


class TestConstants(unittest.TestCase):
    def test_production_constants_fixed_in_source(self):
        for s in ("B_BOOT, BOOT_SEED = 1000, 20261006", "FEASIBLE_HALF_WIDTH = 0.10", "RIDGE = 1.0", "WINDOW_H = 6 ",
                  "N_MIN_B1 = 50 ", "K_FOLDS = 5", "BOOT_FAIL_MAX = 0.01", 'SPLIT_SALT = "EXP-SN-NBI-003"'):
            self.assertIn(s, SRC, s)

    def test_decide_boundary(self):
        self.assertEqual(B.decide(0.0, 0.2), "FEASIBLE")  # 반폭 정확히 0.10
        self.assertEqual(B.decide(0.0, 0.1998), "FEASIBLE")
        self.assertEqual(B.decide(0.0, 0.2002), "EVALUABLE_IMPRECISE")

    def test_pct_ci_is_95(self):
        self.assertEqual(B.pct_ci(list(range(1000))), (25, 974))
        self.assertEqual(B.pct_ci(list(range(999, -1, -1))), (25, 974))


class TestSplitAndFit(unittest.TestCase):
    def test_strat_folds_deterministic_balanced(self):
        subj = [str(10000000 + i) for i in range(203)]
        y = [1 if i < 61 else 0 for i in range(203)]
        f = B.strat_folds(subj, y)
        self.assertEqual(f, B.strat_folds(subj, y))
        cnt = [[sum(1 for i in range(203) if f[i] == k and y[i] == t) for k in range(B.K_FOLDS)] for t in (0, 1)]
        self.assertTrue(all(max(c) - min(c) <= 1 for c in cnt))

    def test_oof_trains_only_on_other_folds(self):
        seen = []
        orig = B.fit_logreg

        def spy(X, y):
            seen.append(len(X))
            return orig(X, y)
        y = [i % 2 for i in range(200)]
        folds = B.strat_folds([str(i) for i in range(200)], y)
        B.fit_logreg = spy
        try:
            B.oof([[float(i % 7), None] for i in range(200)], y, folds)
        finally:
            B.fit_logreg = orig
        self.assertEqual(sorted(seen), sorted(200 - folds.count(f) for f in range(B.K_FOLDS)))

    def test_test_rows_do_not_affect_other_predictions(self):
        rng = random.Random(3)
        y = [i % 2 for i in range(120)]
        base = [[rng.gauss(0, 1), rng.gauss(0, 1)] for _ in range(120)]
        lab = [rng.gauss(y[i], 1) for i in range(120)]
        folds = B.strat_folds([str(i) for i in range(120)], y)
        s = B.oof(base, y, folds, lab=lab)
        j = 0
        base2 = [r[:] for r in base]
        base2[j] = [50.0, -50.0]
        lab2 = lab[:]
        lab2[j] = 99.0
        s2 = B.oof(base2, y, folds, lab=lab2)
        same_fold = [i for i in range(120) if folds[i] == folds[j] and i != j]
        self.assertTrue(all(abs(s[i] - s2[i]) < 1e-12 for i in same_fold))

    def test_rank_outside_train_range(self):
        self.assertEqual((B.ecdf_rank([1.0, 2.0, 3.0], 0.0), B.ecdf_rank([1.0, 2.0, 3.0], 9.0)), (0.0, 1.0))
        self.assertEqual(B.ecdf_rank([1.0, 2.0, 2.0, 3.0], 2.0), 0.5)

    def test_lab_rank_standardized_like_baseline(self):
        tr, _ = B.prep([[float(i), (i + 0.5) / 100] for i in range(100)], [[0.0, 0.5]])
        sd = (sum(r[1] ** 2 for r in tr) / len(tr)) ** 0.5
        self.assertAlmostEqual(sd, 1.0, places=6)

    def test_fold_average_removes_pooled_bias(self):
        y = [1 if i < 53 else 0 for i in range(114)]
        folds = B.strat_folds([str(i) for i in range(114)], y)
        s = B.oof([[1.0] for _ in range(114)], y, folds)  # 정보 없음: fold 절편만 다름
        self.assertEqual(B.fold_auroc(s, y, folds), 0.5)
        self.assertNotEqual(B.auroc(s, y), 0.5)

    def test_resample_preserves_class_sizes(self):
        y = [1] * 30 + [0] * 70
        idx = B.resample(y, random.Random(1))
        self.assertEqual((sum(y[i] for i in idx), len(idx)), (30, 100))

    def test_paired_bootstrap_zero_when_lab_uninformative_constant(self):
        rng = random.Random(5)
        y = [i % 2 for i in range(120)]
        base = [[rng.gauss(y[i], 1)] for i in range(120)]
        folds = B.strat_folds([str(i) for i in range(120)], y)
        lo, hi, fail = B.boot_ci(base, y, folds, lab=[1.0] * 120)  # 상수 lab → M1 = M0 → paired Δ ≡ 0
        self.assertEqual((lo, hi, fail), (0.0, 0.0, 0))

    def test_bootstrap_refits(self):
        calls = []
        orig = B.oof

        def spy(*a, **k):
            calls.append(1)
            return orig(*a, **k)
        rng = random.Random(9)
        y = [i % 2 for i in range(100)]
        base = [[rng.gauss(y[i], 1)] for i in range(100)]
        folds = B.strat_folds([str(i) for i in range(100)], y)
        B.oof = spy
        try:
            B.boot_ci(base, y, folds, lab=[rng.gauss(0, 1) for _ in range(100)])
        finally:
            B.oof = orig
        self.assertEqual(len(calls), 2 * TEST_B)


    def test_bootstrap_replicates_keep_original_fold(self):
        y = [i % 2 for i in range(100)]
        folds = B.strat_folds([str(i) for i in range(100)], y)
        bad = []
        orig = B.oof

        def spy(bb, yy, ff, lab=None):
            bad.extend(k for k in range(len(bb)) if ff[k] != folds[int(bb[k][0])])
            return orig(bb, yy, ff, lab=lab)
        B.oof = spy
        try:
            B.boot_ci([[float(i)] for i in range(100)], y, folds)
        finally:
            B.oof = orig
        self.assertEqual(bad, [])


class TestTemporal(unittest.TestCase):
    def test_first_eligible_by_storetime_not_extreme(self):
        rows = rows_of(Fx().add("ACS", 150, num="9.9", st="2150-01-01 12:00:00").add("ACS", 150, num="0.01", st=ST))
        self.assertEqual({r["labs"]["TROPONIN"]["x"] for r in rows.values() if r["cls"] == "ACS"}, {0.01})

    def test_tie_break_by_charttime(self):
        rows = rows_of(Fx().add("ACS", 5, num="7.0", ct="2150-01-01 10:40:00").add("ACS", 5, num="3.0", ct=CT))
        self.assertEqual({r["labs"]["TROPONIN"].get("x") for r in rows.values() if r["cls"] == "ACS"} - {None}, {3.0})

    def test_window_boundary_and_late_exclusion(self):
        self.assertEqual(status(rows_of(Fx().add("ACS", 10, st="2150-01-01 16:00:00"))).get("MEASURED_NUMERIC"), 10)
        g = Fx()
        g.gen.ed = [r[:4] + ("2150-01-01 20:00:00",) + r[5:] for r in g.gen.ed]
        self.assertEqual(status(rows_of(g.add("ACS", 10, st="2150-01-01 16:00:01"))).get("TIME_INELIGIBLE"), 10)

    def test_after_outtime_and_pre_arrival_collection(self):
        g = Fx()
        g.gen.ed = [r[:4] + ("2150-01-01 12:00:00",) + r[5:] for r in g.gen.ed]
        r = rows_of(g.add("ACS", 10, st="2150-01-01 12:30:00", ct="2150-01-01 11:00:00"))
        self.assertEqual(status(r).get("TIME_INELIGIBLE"), 10)
        r = rows_of(Fx().add("ACS", 10, ct="2150-01-01 09:30:00", st="2150-01-01 10:30:00"))
        self.assertEqual(status(r).get("TIME_INELIGIBLE"), 10)

    def test_charttime_missing_still_eligible(self):
        self.assertEqual(status(rows_of(Fx().add("ACS", 10, ct=""))).get("MEASURED_NUMERIC"), 10)

    def test_time_missing_only_within_window(self):
        g = Fx()
        g.gen.ed = [r[:4] + ("2150-01-01 20:00:00",) + r[5:] for r in g.gen.ed]
        self.assertEqual(status(rows_of(g.add("ACS", 6, st="", ct="2150-01-01 15:00:00"))).get("TIME_MISSING"), 6)
        g = Fx()
        g.gen.ed = [r[:4] + ("2150-01-01 20:00:00",) + r[5:] for r in g.gen.ed]
        self.assertEqual(status(rows_of(g.add("ACS", 6, st="", ct="2150-01-01 17:00:00"))).get("TIME_INELIGIBLE"), 6)

    def test_overlapping_later_stay_takes_event(self):
        fx = Fx(n_acs=60, n_pe=0)
        for sid, (subj, c) in list(fx.cls.items()):
            fx.gen.sid += 1
            fx.gen.ed.append((subj, "", fx.gen.sid, "2150-01-01 12:00:00", "2150-01-01 13:00:00", "F", "X", "WALK IN",
                              "HOME"))
        r = rows_of(fx.add("ACS", 60, ct="2150-01-01 12:10:00", st="2150-01-01 12:30:00"))
        self.assertEqual(status(r).get("NOT_MEASURED"), 60)


class TestValuesUnits(unittest.TestCase):
    def test_censored_order_and_unusable(self):
        r = rows_of(Fx().add("ACS", 5, value="<0.02", num="").add("ACS", 5, start=5, num="0.01")
                    .add("PE", 5, value="> 9", num="").add("PE", 5, start=5, num="50").add("PE", 5, start=10,
                                                                                              value="HEMOLYZED", num=""))
        xs = sorted((v["labs"]["TROPONIN"]["x"], v["labs"]["TROPONIN"]["bound"]) for v in r.values()
                    if v["labs"]["TROPONIN"]["status"] in B.USABLE)
        self.assertEqual([k for _, k in xs][:5], ["<0.02"] * 5)  # '<0.02' 가 측정값 0.01 보다 아래
        self.assertEqual([k for _, k in xs][-5:], [">9.0"] * 5)  # '>9' 가 측정값 50 보다 위
        self.assertEqual(status(r).get("MEASURED_UNUSABLE"), 5)

    def test_missing_unit_and_normalization(self):
        self.assertEqual(status(rows_of(Fx().add("ACS", 7, uom=" "))).get("UNIT_MISSING"), 7)
        pub, s = built(Fx().add("ACS", 60).add("PE", 60, uom=" NG/ML "))
        self.assertNotEqual(pub["TROPONIN"]["assays"][TROP]["status"], "NOT_EVALUABLE_UNIT")
        self.assertEqual(s["concepts"]["TROPONIN"]["assays"][TROP]["units_normalized"], ["ng/ml"])

    def test_unit_inconsistent_assay_not_evaluable(self):
        pub, _ = built(Fx().add("ACS", 100).add("PE", 100).add("ACS", 50, start=100, uom="ng/L"))
        self.assertEqual(pub["TROPONIN"]["assays"][TROP]["status"], "NOT_EVALUABLE_UNIT")
        self.assertEqual(pub["TROPONIN"]["assays"][TROP]["delta"], "WITHHELD")

    def test_assays_never_pooled(self):
        fx = Fx().add("ACS", 60).add("PE", 60).add("ACS", 60, start=60, item=TROP2).add("PE", 60, start=60, item=TROP2)
        _, s = built(fx)
        sc = s["concepts"]["TROPONIN"]["assays"]
        self.assertEqual((sc[TROP]["n_acs"], sc[TROP2]["n_acs"]), (60, 60))

    def test_not_measured_is_not_normal_and_bins(self):
        pub, s = built(Fx(n_acs=100, n_pe=200).add("ACS", 50).add("PE", 60))
        sc = s["concepts"]["TROPONIN"]
        self.assertEqual(sc["assays"][TROP]["n_acs"] + sc["assays"][TROP]["n_pe"], 110)
        self.assertEqual(sc["status_counts_acs_pe"]["NOT_MEASURED"], [50, 140])
        m = pub["TROPONIN"]["measurement"]
        self.assertEqual((m["acs_measured_bin"], m["pe_measured_bin"]), ("50_60", "30_40"))  # 분모 = class n

    def test_class_under_100_withheld(self):
        m = built(Fx(n_acs=60, n_pe=200).add("ACS", 55).add("PE", 120))[0]["TROPONIN"]["measurement"]
        self.assertEqual((m["acs_measured_bin"], m["pe_measured_bin"]), ("WITHHELD", "60_70"))

    def test_data_quality_numerator(self):
        fx = Fx().add("ACS", 60, value="HEMOLYZED", num="").add("PE", 60, value="HEMOLYZED", num="") \
            .add("ACS", 20, start=60, uom="")
        self.assertEqual(built(fx)[0]["TROPONIN"]["measurement"]["data_quality_issue_bin"], "90_100")
        fx2 = Fx().add("ACS", 60, value="HEMOLYZED", num="").add("PE", 60, value="HEMOLYZED", num="") \
            .add("ACS", 60, start=60).add("PE", 60, start=60)
        self.assertEqual(built(fx2)[0]["TROPONIN"]["measurement"]["data_quality_issue_bin"], "50_60")

    def test_unusable_first_not_replaced_but_recorded(self):
        fx = Fx().add("ACS", 30, value="HEMOLYZED", num="").add("ACS", 30, num="0.2", st="2150-01-01 12:00:00")
        self.assertEqual(status(rows_of(fx)).get("MEASURED_UNUSABLE"), 30)
        _, s = built(fx)
        self.assertEqual(s["concepts"]["TROPONIN"]["later_usable_after_unusable_first"], 30)


class TestBaseline(unittest.TestCase):
    def test_vital_range_and_age_correction(self):
        fx = Fx(n_acs=5, n_pe=0)
        fx.gen.tr = [r[:3] + ("500",) + r[4:] for r in fx.gen.tr]
        fx.pat = [(p[0], p[1], "60", "2148") + p[4:] for p in fx.pat]
        for r in rows_of(fx).values():
            self.assertEqual((r["base"][0], r["base"][3]), (62.0, None))

    def test_label_not_in_features(self):
        self.assertEqual(B.BASE, ["age", "female", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp"])
        for col in ("flag", "ref_range_lower", "ref_range_upper", "priority", "comments", "hadm_id"):
            self.assertNotIn(col, B.LAB_ALLOW)
        self.assertNotIn("dod", B.PAT_ALLOW)
        self.assertNotIn("anchor_year_group", B.PAT_ALLOW)
        for col in ("acuity", "chiefcomplaint", "pain"):
            self.assertNotIn(col, B.TRIAGE_ALLOW)
        self.assertNotRegex(SRC, r"\[\"(icd_code|icd_title|disposition|chiefcomplaint|acuity|flag|priority)\"\]")
        fx = Fx().add("ACS", 150).add("PE", 150)
        fx.pat = [(p[0], "F") + p[2:] for p in fx.pat]  # 기저 전부 상수 → 라벨 누출이 없으면 정확히 0.5
        _, s = built(fx)
        self.assertEqual(s["baseline"]["auroc"], 0.5)

    def test_baseline_signal_and_nmin(self):
        self.assertEqual(built(Fx(hr_signal=True))[0]["baseline"]["auroc"], "1.00")
        self.assertEqual(built(Fx(n_acs=60, n_pe=49))[0]["baseline"]["status"], "INSUFFICIENT_DATA")
        self.assertNotEqual(built(Fx(n_acs=60, n_pe=50))[0]["baseline"]["status"], "INSUFFICIENT_DATA")


class TestCells(unittest.TestCase):
    def test_feasible_value_orientation(self):
        fx = Fx(n_acs=200, n_pe=200).add("ACS", 200, fn=lambda c, i: str(0.01 + i * 0.001)) \
            .add("PE", 200, fn=lambda c, i: str(0.25 + i * 0.001))
        pub, _ = built(fx)
        c = pub["TROPONIN"]["assays"][TROP]
        self.assertEqual((c["status"], c["auroc_value_only"]), ("FEASIBLE", "1.00"))
        self.assertEqual(pub["TROPONIN"]["status"], "FEASIBLE")
        self.assertGreater(float(c["delta"]), 0.3)
        self.assertEqual(pub["DDIMER"]["status"], "INSUFFICIENT_DATA")

    def test_cell_uses_fold_averaged_auroc(self):
        fx = Fx(n_acs=61, n_pe=53).add("ACS", 61, num="1.0").add("PE", 53, num="1.0")
        fx.pat = [(p[0], "F") + p[2:] for p in fx.pat]  # 기저·lab 모두 상수 → fold 평균이면 정확히 0.5
        _, s = built(fx)
        a = s["concepts"]["TROPONIN"]["assays"][TROP]
        self.assertEqual((a["auroc_m0"], a["auroc_m1"]), (0.5, 0.5))

    def test_imprecise_case(self):
        pub, _ = built(Fx(n_acs=50, n_pe=50).add("ACS", 50, fn=noisy(0.8)).add("PE", 50, fn=noisy(0.8)))
        self.assertEqual(pub["TROPONIN"]["assays"][TROP]["status"], "EVALUABLE_IMPRECISE")
        self.assertEqual(pub["TROPONIN"]["status"], "EVALUABLE")

    def test_nmin_boundaries_both_classes(self):
        for a, p, ok in ((50, 50, True), (50, 49, False), (49, 50, False)):
            st = built(Fx(n_acs=60, n_pe=60).add("ACS", a).add("PE", p))[0]["TROPONIN"]["assays"][TROP]["status"]
            self.assertEqual(st != "INSUFFICIENT_DATA", ok, (a, p))

    def test_small_n_suppressed_and_invisible(self):
        outs = set()
        for k in range(1, 11):
            pub, _ = built(Fx().add("ACS", 150).add("PE", k))
            self.assertEqual(pub["TROPONIN"]["assays"][TROP]["status"], "INSUFFICIENT_DATA")
            outs.add(json.dumps({c: pub[c] for c in ("pair", "TROPONIN", "DDIMER")}, sort_keys=True))
        self.assertEqual(len(outs), 1)

    def test_not_evaluable_pair(self):
        pub, _ = built(Fx(n_pe=0).add("ACS", 100))
        self.assertEqual(pub["pair"]["status"], "NOT_EVALUABLE")
        self.assertEqual(pub["TROPONIN"]["assays"][TROP]["status"], "NOT_EVALUABLE_PAIR")

    def test_sealed_descriptives(self):
        _, s = built(Fx().add("ACS", 60, value="<0.01", num="").add("PE", 60))
        a = s["concepts"]["TROPONIN"]["assays"][TROP]
        self.assertEqual((a["n_censored"], a["censor_bounds_distinct"]), (60, 1))
        self.assertIn("baseline_measured_vs_unmeasured", s["concepts"]["TROPONIN"])
        self.assertEqual(set(a["acs_subclass"]), set(A.ACS_SUB))

    def test_deterministic(self):
        fx = Fx().add("ACS", 80, fn=lambda c, i: str(i % 9)).add("PE", 80, fn=lambda c, i: str(i % 11))
        self.assertEqual(built(fx), built(fx))


class TestPublic(unittest.TestCase):
    def test_schema_and_no_counts(self):
        pub, _ = built(Fx().add("ACS", 150).add("PE", 150))
        keys = json.load(open(SCHEMA, encoding="utf-8"))["keys"]
        self.assertEqual(sorted(k for k, _ in A.flatten(pub)), sorted(keys))
        self.assertEqual(len(keys), 68)
        self.assertEqual(B.guard(pub), [])
        for k, v in A.flatten(pub):
            self.assertIsNone(re.fullmatch(r"\d+", v), k)

    def test_guard_rejects_counts_ranges_and_key_mixups(self):
        pub, _ = built(Fx().add("ACS", 150).add("PE", 150))
        t = pub["TROPONIN"]["assays"][TROP]
        t["n_bucket_acs"], t["delta"], t["auroc_m0"], t["status"] = "137", "0.123", "1.50", "50_99"
        pub["baseline"]["ci_lo"] = "12.34"
        self.assertEqual(len(B.guard(pub)), 5)


class TestMain(unittest.TestCase):
    def test_complete_outputs_and_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, ref = Fx().add("ACS", 150).add("PE", 150).write(d)
            rc, out = run(margs(d, ed, ecg, p, ref))
            self.assertEqual((rc, out), (0, "B1_VERDICT COMPLETE\n"))
            pub = json.load(open(os.path.join(d, "out", "b1_public.json")))
            self.assertEqual(pub["meta"]["sealed_file_sha256"], sha(os.path.join(d, "sealed", "b1_sealed.json")))
            self.assertEqual(oct(os.stat(os.path.join(d, "sealed")).st_mode & 0o777), "0o700")
            self.assertNotRegex(open(os.path.join(d, "out", "b1_public.json")).read(), r"\b1000\d{4}\b|2150-")

    def test_aborts(self):
        for reason in ("sha_mismatch", "item_map_mismatch", "cohort_mismatch", "schema_mismatch"):
            with tempfile.TemporaryDirectory() as d:
                fx = Fx().add("ACS", 60).add("PE", 60)
                ed, ecg, p, ref = fx.write(d, dlab=dlab_rows(drop="51002") if reason == "item_map_mismatch" else None)
                schema, refs = SCHEMA, {}
                if reason == "cohort_mismatch":
                    x = json.load(open(ref))
                    x["pairs"]["ACS~PE"]["cohort_pooled_bucket"] = "GE_5000"
                    bad = os.path.join(d, "bad.json")
                    json.dump(x, open(bad, "w"))
                    refs = {"d": bad}
                if reason == "schema_mismatch":
                    schema = os.path.join(d, "s.json")
                    k = json.load(open(SCHEMA))
                    k["keys"] = k["keys"][1:]
                    json.dump(k, open(schema, "w"))
                a = margs(d, ed, ecg, p, ref, schema=schema, refs=refs)
                if reason == "sha_mismatch":
                    a[a.index("--patients-sha") + 1] = "0" * 64
                rc, out = run(a)
                self.assertEqual(rc, 2, reason)
                self.assertIn("reason=" + reason, out)
                self.assertFalse(os.path.exists(os.path.join(d, "out")), reason)
                self.assertFalse(os.path.exists(os.path.join(d, "sealed")), reason)

    def test_guard_blocks_leaky_output(self):
        orig = B.build_b1

        def leaky(d):
            pub, sealed = orig(d)
            pub["TROPONIN"]["assays"][TROP]["n_bucket_acs"] = "137"
            return pub, sealed
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, ref = Fx().add("ACS", 60).add("PE", 60).write(d)
            B.build_b1 = leaky
            try:
                rc, out = run(margs(d, ed, ecg, p, ref))
            finally:
                B.build_b1 = orig
            self.assertEqual(rc, 2)
            self.assertIn("reason=output_guard", out)
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))

    def test_one_run_guard(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, ref = Fx().add("ACS", 60).add("PE", 60).write(d)
            self.assertEqual(run(margs(d, ed, ecg, p, ref))[0], 0)
            rc, out = run(margs(d, ed, ecg, p, ref))
            self.assertEqual(rc, 2)
            self.assertIn("output_exists", out)

    def test_stop_title(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fx()
            fx.gen = Gen(n_acs=10, n_pe=10, n_peri=0, title_override="Something unrelated")
            ed, ecg, p, ref = fx.write(d)
            rc, _ = run(margs(d, ed, ecg, p, ref))
            self.assertEqual(rc, 3)
            self.assertFalse(os.path.exists(os.path.join(d, "out")))


if __name__ == "__main__":
    unittest.main()
