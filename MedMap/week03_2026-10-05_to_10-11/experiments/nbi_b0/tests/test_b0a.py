"""NBI-B0a v2 합성 fixture 시험 — 실제 MIMIC 미사용(가짜 ID·가짜 시각). CMS 공개 코드표 fixture 사용.

실행: python3 -m unittest docs/research/nbi/b0/tests/test_b0a.py
"""
import contextlib
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import b0a_availability as B  # noqa: E402

SCHEMA = os.path.join(HERE, "..", "expected_schema.json")
CMS = json.load(open(os.path.join(HERE, "fixtures", "cms_icd_titles.json"), encoding="utf-8"))
ED_H = ["subject_id", "hadm_id", "stay_id", "intime", "outtime", "gender", "race", "arrival_transport", "disposition"]
DX_H = ["subject_id", "stay_id", "seq_num", "icd_code", "icd_version", "icd_title"]
TR_H = ["subject_id", "stay_id", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain", "acuity",
        "chiefcomplaint"]
VS_H = ["subject_id", "stay_id", "charttime", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "rhythm",
        "pain"]
ECG_H = ["file_name", "study_id", "subject_id", "ecg_time", "ed_stay_id", "ed_hadm_id", "hosp_hadm_id", "ed_diag_ed",
         "ed_diag_hosp", "hosp_diag_hosp", "all_diag_hosp", "all_diag_all", "gender", "age", "anchor_year",
         "anchor_age", "dod", "ecg_no_within_stay", "ecg_taken_in_ed", "ecg_taken_in_hosp", "ecg_taken_in_ed_or_hosp",
         "fold", "strat_fold"]
TITLE = {("ACS", "10"): ("I214", "NSTEMI (non-ST elevation) myocardial infarction"),
         ("ACS", "9"): ("41071", "Subendo infarct, initial"),
         ("PE", "10"): ("I2699", "Other pulmonary embolism without acute cor pulmonale"),
         ("PE", "9"): ("41519", "Pulm embolism/infarct NEC"),
         ("PERI", "10"): ("I309", "Acute pericarditis, unspecified"),
         ("PERI", "9"): ("42090", "Ac pericarditis NOS")}


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def gz(header, rows):
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(header)
    w.writerows(rows)
    return gzip.compress(s.getvalue().encode())


class Gen:
    """합성 데이터 생성기. 대상별 subject 수와 민감 속성을 매개변수로 조절."""

    def __init__(self, n_acs=40, n_pe=40, n_peri=40, vital=None, rhythm_missing=0, icd9_acs=0, multi_pe=0,
                 extra_stays=0, ecg=True, acs_pe_earlier=0, title_override=None):
        self.ed, self.dx, self.tr, self.vs, self.ecg = [], [], [], [], []
        self.sid, self.subj = 30000000, 10000000
        k = 0
        for cls, n in (("ACS", n_acs), ("PE", n_pe), ("PERI", n_peri)):
            for i in range(n):
                ver = "9" if cls == "ACS" and i < icd9_acs else "10"
                codes = [(cls, ver)]
                if cls == "ACS" and i < multi_pe:
                    codes.append(("PE", "10"))
                stay = self.stay(codes, title_override)
                if vital is None or k < vital:
                    rh = "" if i < rhythm_missing else "Sinus"
                    self.vs.append((self.subj, stay, "2150-01-01 10:30:00", "98", "90", "18", "95", "120", "80", rh,
                                    "3"))
                self.tr.append((self.subj, stay, "98", "90", "18", "95", "120", "80", "3", "2", "CP"))
                if ecg:
                    self.ecg.append(["f", "4", self.subj, "2150-01-01 10:05:00", f"{stay}.0"] + ["X"] * 18)
                if cls == "ACS" and i < extra_stays:
                    self.stay([(cls, ver)], title_override, same_subject=True, month=3)
                if cls == "ACS" and i < acs_pe_earlier:  # 같은 subject 의 더 이른 PE stay (쌍 간 포함관계 공격용)
                    self.stay([("PE", "10")], title_override, same_subject=True, year=2149)
                k += 1

    def stay(self, codes, title_override, same_subject=False, month=1, year=2150):
        self.sid += 1
        if not same_subject:
            self.subj += 1
        it = f"{year}-{month:02d}-01 10:00:00"
        ot = f"{year}-{month:02d}-01 16:00:00"
        self.ed.append((self.subj, "", self.sid, it, ot, "F", "X", "WALK IN", "HOME"))
        for j, (cls, ver) in enumerate(codes):
            code, title = TITLE[(cls, ver)]
            self.dx.append((self.subj, self.sid, j + 1, code, ver, title_override or title))
        return self.sid

    def write(self, d):
        ed = os.path.join(d, "ed.zip")
        with zipfile.ZipFile(ed, "w") as z:
            z.writestr(B.ED_PREFIX + "edstays.csv.gz", gz(ED_H, self.ed))
            z.writestr(B.ED_PREFIX + "diagnosis.csv.gz", gz(DX_H, self.dx))
            z.writestr(B.ED_PREFIX + "triage.csv.gz", gz(TR_H, self.tr))
            z.writestr(B.ED_PREFIX + "vitalsign.csv.gz", gz(VS_H, self.vs))
        ecg = os.path.join(d, "ecg.zip")
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(ECG_H)
        w.writerows(self.ecg)
        with zipfile.ZipFile(ecg, "w") as z:
            z.writestr(B.ECG_MEMBER, s.getvalue())
        return ed, ecg


def args(d, ed, ecg, schema=SCHEMA):
    return ["--ed-zip", ed, "--ed-zip-sha", sha(ed), "--ecg-zip", ecg, "--ecg-zip-sha", sha(ecg),
            "--schema", schema, "--schema-sha", sha(schema), "--out", os.path.join(d, "out"),
            "--sealed", os.path.join(d, "sealed"), "--private-log", os.path.join(d, "priv", "p.log")]


def run(a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = B.main(a)
    return rc, buf.getvalue()


def public_of(gen):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg = gen.write(d)
        return B.build(B.compute(ed, ecg))


class TestCodesCMS(unittest.TestCase):
    def test_cms_targets_classified_and_titles_pass(self):
        for t in CMS["targets"]:
            self.assertEqual(B.classify(t["icd_version"], t["icd_code"]), {t["class"]}, t["icd_code"])
            for k in ("short", "long"):
                self.assertTrue(B.title_ok(t["class"], t[k]), (t["icd_code"], k, t[k]))
                self.assertTrue(B.title_ok(t["class"], t[k].upper()), (t["icd_code"], "upper"))

    def test_cms_counts_fixed(self):
        from collections import Counter
        self.assertEqual(Counter(t["class"] for t in CMS["targets"]), {"ACS": 45, "PE": 12, "PERI": 12})

    def test_excluded_and_boundary_not_classified(self):
        for e in CMS["excluded_neighbors"] + CMS["boundary"]:
            self.assertEqual(B.classify(e["icd_version"], e["icd_code"]), set(), e["icd_code"])
        codes = {(b["icd_version"], b["icd_code"]) for b in CMS["boundary"]}
        self.assertIn(("10", "I249"), codes)
        self.assertEqual(sum(v == "9" for v, _ in codes), 10)  # 410.x2 전부

    def test_specific_codes(self):
        for v, c, exp in (("10", "I213", {"ACS"}), ("10", "I25790", {"ACS"}), ("10", "I25740", set()),
                          ("10", "I21A1", set()), ("10", "I249", set()), ("9", "41072", set()),
                          ("9", "4111", {"ACS"}), ("10", "I32", {"PERI"}), ("9", "4200", {"PERI"}),
                          ("10", "I409", set()), ("10", "A1884", set()), ("10", "4111", set()),
                          ("9", "I214", set()), ("10", "I21.4", {"ACS"})):
            self.assertEqual(B.classify(v, B.norm_code(c)), exp, c)

    def test_bad_title_fails(self):
        self.assertFalse(B.title_ok("PE", "Something unrelated"))
        self.assertFalse(B.title_ok("ACS", "Camel"))  # \bami\b 경계


class TestPublicMinimal(unittest.TestCase):
    def test_vocab_only_no_numbers(self):
        pub, sealed = public_of(Gen())
        self.assertEqual(B.guard(pub), [])
        for k, v in B.flatten(pub):
            self.assertIsInstance(v, str, k)
            self.assertIn(v, B.ALLOWED_VALUES, k)
        self.assertEqual(sorted(k for k, _ in B.flatten(pub)), sorted(json.load(open(SCHEMA))["keys"]))

    def test_share_and_bucket(self):
        self.assertEqual(B.pool_bucket(99), "LT_100")
        self.assertEqual(B.pool_bucket(100), "100_499")
        self.assertEqual(B.share_bin(0, 120), "0_10")
        self.assertEqual(B.share_bin(120, 120), "90_100")
        self.assertEqual(B.share_bin(13, 120), "10_20")
        pub, _ = public_of(Gen(n_acs=60, n_pe=60))
        self.assertEqual(pub["pairs"]["ACS~PE"]["pooled_share_bin"]["VITAL_SERIES"], "90_100")
        self.assertEqual(pub["pairs"]["ACS~PERI"]["cohort_pooled_bucket"], "100_499")


class TestAttacks(unittest.TestCase):
    """민감 값만 바꾼 두 합성 데이터셋의 공개 출력이 같아야 함(역산 불가). 봉인에는 차이가 남아야 함."""

    def same_public(self, g1, g2, sealed_path):
        p1, s1 = public_of(g1)
        p2, s2 = public_of(g2)
        self.assertEqual(p1, p2)
        v1, v2 = s1, s2
        for k in sealed_path:
            v1, v2 = v1[k], v2[k]
        self.assertNotEqual(v1, v2)

    def test_A1_small_stays_per_subject(self):
        self.same_public(Gen(extra_stays=1), Gen(extra_stays=2), ["pairs", "ACS~PE", "stays_per_subject", "k2"])

    def test_A2_nesting_vital_rhythm(self):
        self.same_public(Gen(rhythm_missing=5), Gen(rhythm_missing=6), ["pairs", "ACS~PE", "vital_no_rhythm"])

    def test_A4_zero_cell_icd_version(self):
        self.same_public(Gen(icd9_acs=0), Gen(icd9_acs=1), ["pairs", "ACS~PE", "icd_version", "a", "v9"])

    def test_A5b_complement_near_threshold(self):
        self.same_public(Gen(vital=119), Gen(vital=118), ["pairs", "ACS~PERI", "avail", "VITAL_SERIES", "pooled"])

    def test_A7_cross_pair_difference(self):
        self.same_public(Gen(acs_pe_earlier=0), Gen(acs_pe_earlier=3), ["cross_pair", "acs_in_PERI_not_PE"])

    def test_multi_small(self):
        self.same_public(Gen(multi_pe=1), Gen(multi_pe=2), ["pairs", "ACS~PE", "cohort", "n_multi"])


class TestRun(unittest.TestCase):
    def test_complete_run_and_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg = Gen().write(d)
            rc, out = run(args(d, ed, ecg))
            self.assertEqual((rc, out.strip()), (0, "B0A_VERDICT COMPLETE"))
            pub = json.load(open(os.path.join(d, "out", "b0a_public.json")))
            vals = [v for k, v in B.flatten({k: v for k, v in pub.items() if k != "meta"})]
            self.assertTrue(all(isinstance(v, str) and v in B.ALLOWED_VALUES for v in vals))
            self.assertFalse([v for v in vals if re.fullmatch(r"\d+", v)])  # 정수 count 문자열 없음
            sp = os.path.join(d, "sealed", "b0a_sealed.json")
            self.assertEqual(pub["meta"]["sealed_file_sha256"], sha(sp))
            sealed = json.load(open(sp))
            self.assertEqual(sealed["pairs"]["ACS~PE"]["cohort"]["n_a"], 40)
            self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["ECG_LINKED"], "TEMPORALLY_UNCERTAIN")
            self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["VITAL_SERIES"], "RECORDED_IN_STAY_AVAILABLE")
            self.assertEqual(pub["pairs"]["ACS~PE"]["timing"]["VITAL_SERIES"], "EARLY_ROUTINE_POSSIBLE")
            self.assertEqual(pub["pairs"]["ACS~PERI"]["pair_rule_inputs"]["ecg_linked_both_classes_nmin"],
                             "MEETS_NMIN")
            self.assertEqual(pub["pair_decision"]["b1_primary_pair"], "PENDING")

    def test_cohort_rules(self):
        _, s = public_of(Gen(n_acs=3, n_pe=2, n_peri=1, multi_pe=1))
        self.assertEqual(s["pairs"]["ACS~PE"]["cohort"], {"n_a": 2, "n_b": 2, "n_multi": 1, "n_pool": 4})
        self.assertEqual(s["pairs"]["ACS~PERI"]["cohort"], {"n_a": 3, "n_b": 1, "n_multi": 0, "n_pool": 4})

    def test_first_stay_multi_not_skipped(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1, multi_pe=1)  # subject1 첫 stay = ACS+PE
        g.subj = 10000001
        g.stay([("ACS", "10")], None, same_subject=True, month=6)  # 같은 subject 의 나중 ACS 단독 stay
        _, s = public_of(g)
        self.assertEqual(s["pairs"]["ACS~PE"]["cohort"]["n_multi"], 1)
        self.assertEqual(s["pairs"]["ACS~PE"]["cohort"]["n_a"], 0)

    def test_tie_break_stay_id(self):
        g = Gen(n_acs=0, n_pe=1, n_peri=1)
        g.subj = 10000099
        g.ed.append((10000099, "", 30000099, "2150-01-01 10:00:00", "2150-01-01 16:00:00", "F", "X", "W", "H"))
        g.ed.append((10000099, "", 30000098, "2150-01-01 10:00:00", "2150-01-01 16:00:00", "F", "X", "W", "H"))
        g.dx.append((10000099, 30000099, 1, "I2699", "10", "Other pulmonary embolism"))
        g.dx.append((10000099, 30000098, 1, "I214", "10", "NSTEMI myocardial infarction"))
        _, s = public_of(g)
        self.assertEqual(s["pairs"]["ACS~PE"]["cohort"]["n_a"], 1)  # stay_id 30000098(ACS)이 먼저

    def test_outtime_bound(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1, vital=0)
        g.vs.append((g.subj, g.sid, "2150-01-01 17:00:00", "98", "90", "18", "95", "120", "80", "Sinus", "3"))
        _, s = public_of(g)
        self.assertEqual(s["pairs"]["ACS~PERI"]["avail"]["VITAL_SERIES"]["pooled"], 0)

    def test_pre_t0(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1, vital=0)
        g.vs.append((10000001, 30000001, "2150-01-01 09:00:00", "98", "90", "18", "95", "120", "80", "", "3"))
        _, s = public_of(g)
        self.assertEqual(s["pairs"]["ACS~PE"]["pre_t0_vitals"], 1)

    def test_nmin_partial_label(self):
        pub, _ = public_of(Gen(n_acs=5, n_pe=5, n_peri=5))
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["VITAL_SERIES"], "RECORDED_IN_STAY_PARTIAL")
        self.assertEqual(pub["pairs"]["ACS~PE"]["pooled_share_bin"]["VITAL_SERIES"], "WITHHELD")
        self.assertEqual(pub["pairs"]["ACS~PE"]["timing"]["VITAL_SERIES"], "INSUFFICIENT_N")
        self.assertEqual(pub["pairs"]["ACS~PERI"]["pair_rule_inputs"]["ecg_linked_both_classes_nmin"], "BELOW_NMIN")

    def test_timing_uses_unrounded(self):
        self.assertEqual(B.timing_label([1.0] * 30), "EARLY_ROUTINE_POSSIBLE")
        self.assertEqual(B.timing_label([1.25] * 30), "LATER_IN_STAY")

    def test_not_evaluable_pair(self):
        pub, _ = public_of(Gen(n_peri=0))
        self.assertEqual(pub["pairs"]["ACS~PERI"]["pair_status"], "NOT_EVALUABLE")
        self.assertEqual(pub["pairs"]["ACS~PERI"]["labels"]["IMAGING_CTPA"], "NOT_EVALUABLE")

    def test_boundary_sealed(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1)
        g.dx.append((10000001, 30000001, 9, "I249", "10", "Acute ischemic heart disease, unspecified"))
        g.ed.append((10000077, "", 30000077, "2150-01-01 10:00:00", "2150-01-01 12:00:00", "F", "X", "W", "H"))
        g.dx.append((10000077, 30000077, 1, "I249", "10", "Acute ischemic heart disease, unspecified"))
        g.dx.append((10000077, 30000077, 2, "41072", "9", "Subendo infarct, subseq"))
        _, s = public_of(g)
        self.assertEqual(s["global"]["boundary"], {"ICD10_I249_only_stays": 1, "ICD9_410x2_stays": 1})

    def test_title_stop_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg = Gen(title_override="Something unrelated").write(d)
            rc, out = run(args(d, ed, ecg))
            self.assertEqual(rc, 3)
            self.assertIn("STOP_TITLE", out)
            self.assertFalse(os.path.exists(os.path.join(d, "out")))
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))

    def test_ecg_allowlist(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg = Gen(n_acs=1, n_pe=1, n_peri=1).write(d)
            r = next(B.rows(zipfile.ZipFile(ecg), B.ECG_MEMBER, B.ALLOW["ecg"]))
            self.assertEqual(sorted(r), ["ecg_time", "ed_stay_id"])

    def test_orphan_ecg(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1)
        g.ecg.append(["f", "4", "1", "2150-01-01 10:05:00", "39999999"] + ["X"] * 18)
        _, s = public_of(g)
        self.assertEqual(s["global"]["ecg_orphan_rows"], 1)

    def test_preflight_invalid_paths(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg = Gen(n_acs=1, n_pe=1, n_peri=1).write(d)
            a = args(d, ed, ecg)
            a[a.index("--ed-zip-sha") + 1] = "0" * 64
            rc, out = run(a)
            self.assertEqual(rc, 2)
            self.assertIn("stage=preflight", out)
            os.makedirs(os.path.join(d, "out"))
            rc, out = run(args(d, ed, ecg))
            self.assertIn("output_exists stage=preflight", out)

    def test_exception_hides_values(self):
        g = Gen(n_acs=1, n_pe=1, n_peri=1)
        g.ed.append((10009999, "", 39999998, "NOT-A-TIME-12345678", "2150-01-01 10:00:00", "F", "X", "W", "H"))
        with tempfile.TemporaryDirectory() as d:
            ed, ecg = g.write(d)
            rc, out = run(args(d, ed, ecg))
            self.assertEqual(rc, 2)
            self.assertIn("exception=ValueError stage=data", out)
            self.assertNotIn("12345678", out)
            self.assertIn("12345678", open(os.path.join(d, "priv", "p.log")).read())

    def test_guard_blocks_numeric_value(self):
        orig = B.build

        def inj(d):
            p, s = orig(d)
            p["pairs"]["ACS~PE"]["pair_status"] = "17"
            return p, s
        B.build = inj
        try:
            with tempfile.TemporaryDirectory() as d:
                ed, ecg = Gen(n_acs=1, n_pe=1, n_peri=1).write(d)
                rc, out = run(args(d, ed, ecg))
                self.assertEqual(rc, 2)
                self.assertIn("output_guard", out)
                self.assertFalse(os.path.exists(os.path.join(d, "out")))
        finally:
            B.build = orig

    def test_schema_blocks_extra_key(self):
        orig = B.build
        B.build = lambda d: ({**orig(d)[0], "extra": "PENDING"}, orig(d)[1])
        try:
            with tempfile.TemporaryDirectory() as d:
                ed, ecg = Gen(n_acs=1, n_pe=1, n_peri=1).write(d)
                rc, out = run(args(d, ed, ecg))
                self.assertIn("schema_mismatch", out)
        finally:
            B.build = orig


if __name__ == "__main__":
    unittest.main()
