"""NBI-B1S 합성 fixture 시험 — 실제 MIMIC 미사용(가짜 ID·시각·값). B1 시험의 Fx 재사용.

시간 절약을 위해 bootstrap 반복 수만 줄인다(B.B_BOOT = TEST_B). 운영 상수는 test_constants 가 소스 문자열로 고정한다.
실행: python3 -m unittest docs/research/nbi/b1s/tests/test_b1s.py
"""
import contextlib
import copy
import io
import json
import os
import random
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "b1", "tests"))
import b1s_sensitivity as S  # noqa: E402
from test_b1 import Fx, sha  # noqa: E402  (B1 합성 fixture; import 시 B.B_BOOT 가 시험값으로 바뀜)

B, A = S.B, S.A
TEST_B = 16
B.B_BOOT = TEST_B
SRC = open(os.path.join(HERE, "..", "b1s_sensitivity.py"), encoding="utf-8").read()
SCHEMA = os.path.join(HERE, "..", "expected_schema_b1s.json")
with open(SCHEMA, encoding="utf-8") as _f:
    SCHEMA_KEYS = json.load(_f)["keys"]
UA_CODE = ("I200", "Unstable angina")


def make(n_mi=140, n_ua=60, n_pe=150, mi_meas=100, ua_meas=60, pe_meas=100, signal=True, mixed=0, seed=1):
    """ACS 앞쪽 n_mi 는 NSTEMI(I214), 뒤쪽 n_ua 는 UA(I200). mixed 개는 MI stay 에 UA 코드 추가."""
    fx = Fx(n_acs=n_mi + n_ua, n_pe=n_pe)
    acs = fx.sids("ACS", n_mi + n_ua)
    ua = set(acs[n_mi:])
    dx = []
    for subj, sid, seq, code, ver, title in fx.gen.dx:
        if sid in ua:
            code, title = UA_CODE
        dx.append((subj, sid, seq, code, ver, title))
    for k, sid in enumerate(acs[:mixed]):
        dx.append((fx.cls[sid][0], sid, 2, UA_CODE[0], "10", UA_CODE[1]))
    fx.gen.dx = dx
    rng = random.Random(seed)

    def val(cls, i):
        mu = (0.3 if cls == "PE" else 0.6) if signal else 0.45
        return f"{max(0.001, rng.gauss(mu, 0.2)):.3f}"
    fx.add("ACS", mi_meas, fn=val)
    fx.add("ACS", ua_meas, fn=val, start=n_mi)
    fx.add("PE", pe_meas, fn=val)
    return fx


def compute(fx):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, p, _ = fx.write(d)
        return B.compute_b1(ed, ecg, p["lab"], p["pat"])


def rows_of(d):
    return sorted(d["b1_rows"].values(), key=lambda r: int(r["subject"]))


def b1_public(d):
    return B.build_b1(copy.deepcopy(d))[0]


def run_main(fx, b1_pub=None, schema=SCHEMA, out_exists=False):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, p, _ = fx.write(d)
        dd = B.compute_b1(ed, ecg, p["lab"], p["pat"])
        bp = os.path.join(d, "b1_public.json")
        with open(bp, "w") as f:
            json.dump(b1_pub if b1_pub is not None else B.build_b1(dd)[0], f)
        out = os.path.join(d, "out")
        if out_exists:
            os.makedirs(out)
        a = ["--ed-zip", ed, "--ed-zip-sha", sha(ed), "--ecg-zip", ecg, "--ecg-zip-sha", sha(ecg),
             "--labevents", p["lab"], "--labevents-sha", sha(p["lab"]), "--d-labitems", p["dlab"],
             "--d-labitems-sha", sha(p["dlab"]), "--patients", p["pat"], "--patients-sha", sha(p["pat"]),
             "--schema", schema, "--schema-sha", sha(schema), "--b1-public", bp, "--b1-public-sha", sha(bp),
             "--out", out, "--sealed", os.path.join(d, "sealed"), "--private-log", os.path.join(d, "priv", "p.log")]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = S.main(a)
        pub = sealed = None
        if rc == 0:
            with open(os.path.join(out, "b1s_public.json")) as f:
                pub = json.load(f)
            with open(os.path.join(d, "sealed", "b1s_sealed.json")) as f:
                sealed = json.load(f)
        return rc, buf.getvalue(), pub, sealed


class TestB1S(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = compute(make(mixed=10))
        cls.rows = rows_of(cls.d)

    def test_constants(self):
        for s in ('CONCEPT, ITEM = "TROPONIN", "51003"', 'MI_SUB = ("STEMI", "NSTEMI", "MI_UNSPEC", "SUBSEQUENT")',
                  "PERM_SEED = 20261007", "NC_TOL = 0.02", "SEL_MIN_AUROC = 0.60", "ATTEN_RATIO = 0.5"):
            self.assertIn(s, SRC)
        self.assertNotIn("B.B_BOOT =", SRC)
        self.assertNotIn("B.N_MIN_B1 =", SRC)

    def test_subtype_separation(self):
        st = [S.subtype(r) for r in self.rows]
        self.assertEqual(st.count("PE"), 150)
        self.assertEqual(st.count("UA"), 60)
        self.assertEqual(st.count("MI"), 140)  # MI+UA 동반 10명은 MI
        self.assertEqual(st.count("UNASSIGNED"), 0)
        self.assertEqual(S.subtype({"cls": "ACS", "acs_sub": []}), "UNASSIGNED")
        self.assertEqual(S.subtype({"cls": "ACS", "acs_sub": ["NSTEMI", "UA"]}), "MI")
        self.assertEqual(S.subtype({"cls": "ACS", "acs_sub": ["UA"]}), "UA")

    def test_subset_leakage_and_subject_split(self):
        _, sealed = S.build_b1s(copy.deepcopy(self.d), b1_public(self.d))
        sc = sealed["subtype_counts"]
        self.assertEqual(sc["UA"]["measured_51003"], 60)
        self.assertEqual(sealed["mi_with_ua_code"], 10)
        mi = [r for r in self.rows if S.subtype(r) in ("MI", "PE")]
        ua = [r for r in self.rows if S.subtype(r) in ("UA", "PE")]
        self.assertFalse(any(S.subtype(r) == "UA" for r in mi))
        self.assertFalse(any(S.subtype(r) == "MI" for r in ua))
        for sub in (mi, ua, self.rows):
            subj = [r["subject"] for r in sub]
            self.assertEqual(len(subj), len(set(subj)))  # subject 1행 → fold 는 subject 단위

    def test_measured_outcome_rule(self):
        fx = make(n_mi=60, n_ua=0, n_pe=60, mi_meas=0, ua_meas=0, pe_meas=0)
        fx.add("ACS", 10, item="51002", fn=lambda c, i: "0.1")  # 첫 적격이 다른 측정법
        fx.add("ACS", 10, start=10, fn=lambda c, i: "0.1", st="2150-01-01 17:00:00")  # 6 h 밖
        fx.add("ACS", 10, start=20, fn=lambda c, i: "0.1")
        rows = rows_of(compute(fx))
        m = [S.measured(r) for r in rows if r["cls"] == "ACS"]
        self.assertEqual(sum(m), 10)
        self.assertTrue(all(r["labs"]["TROPONIN"]["item"] == "51003" for r in rows if S.measured(r)))

    def test_selection_uses_baseline_only(self):
        p1, s1 = S.selection(copy.deepcopy(self.rows))
        alt = copy.deepcopy(self.rows)
        for r in alt:
            r["cls"], r["y"], r["acs_sub"] = "PE", 1 - r["y"], ["UA"]
            r["labs"]["DDIMER"] = {"status": "MEASURED_NUMERIC", "item": "50915", "x": 9.9}
            if S.measured(r):
                r["labs"]["TROPONIN"]["x"] = 123.0
        p2, s2 = S.selection(alt)
        self.assertEqual((p1, s1), (p2, s2))
        self.assertNotIn("labs", S.selection.__code__.co_names)  # 입력은 r["base"] 만

    def test_selection_paths(self):
        _, sealed = S.build_b1s(copy.deepcopy(self.d), b1_public(self.d))
        pub, _ = S.build_b1s(copy.deepcopy(self.d), b1_public(self.d))
        self.assertEqual(pub["test_b"]["within_acs"]["status"], "INSUFFICIENT_DATA")  # 미측정 ACS 40 < 50
        self.assertIn(pub["test_b"]["pooled"]["status"], S.SEL_STATUS - {"INSUFFICIENT_DATA"})
        self.assertIn(pub["test_b"]["within_pe"]["status"], S.SEL_STATUS - {"INSUFFICIENT_DATA"})
        self.assertEqual(sealed["test_b"]["pooled"]["n_unmeasured"], 90)

    def test_insufficient_ua(self):
        d = compute(make(n_mi=140, n_ua=40, ua_meas=40))
        pub, _ = S.build_b1s(d, b1_public(d))
        self.assertEqual(pub["test_a"]["ua_vs_pe"]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(pub["test_a"]["ua_vs_pe"]["delta"], "WITHHELD")
        self.assertEqual((pub["test_a"]["interpretation"], pub["test_a"]["reason"]),
                         ("REFERENCE_SENSITIVITY_NOT_EVALUABLE", "UA_INSUFFICIENT_DATA"))

    def test_same_rule_as_b1_cell(self):
        a0, a1, dl = S.point(self.rows)
        P, Sd = B.cell(self.rows, "TROPONIN", "51003")
        self.assertEqual((a0, a1), (Sd["auroc_m0"], Sd["auroc_m1"]))

    def test_reproduction_check(self):
        ref = b1_public(self.d)
        pub, _ = S.build_b1s(copy.deepcopy(self.d), ref)
        self.assertEqual(pub["reproduction"]["status"], "REPRODUCED")
        bad = copy.deepcopy(ref)
        bad["TROPONIN"]["assays"]["51003"]["delta"] = "0.99"
        self.assertEqual(S.build_b1s(copy.deepcopy(self.d), bad), ("INVALID", "b1_reproduction_mismatch"))
        bad = copy.deepcopy(ref)
        bad["pair"]["cohort_pooled_bucket"] = "GE_5000"
        self.assertEqual(S.build_b1s(copy.deepcopy(self.d), bad), ("INVALID", "b1_cohort_mismatch"))

    def test_interpret_table(self):
        F, I = {"status": "FEASIBLE"}, {"status": "EVALUABLE_IMPRECISE"}

        def s(d, lo, hi, av=0.3):
            return {"delta": d, "delta_ci": [lo, hi], "auroc_value_only": av}
        cases = [
            ((F, s(.1, .05, .15), {"status": "INSUFFICIENT_DATA"}, {}), "UA_INSUFFICIENT_DATA"),
            ((F, s(.1, .05, .15), {"status": "NOT_EVALUABLE_UNIT"}, {}), "UA_NOT_EVALUABLE_UNIT"),
            ((F, s(.1, .05, .15), {"status": "NOT_EVALUABLE_MODEL"}, {}), "UA_NOT_EVALUABLE_MODEL"),
            (({"status": "INSUFFICIENT_DATA"}, {}, F, s(.0, -.05, .05)), "MI_NOT_EVALUABLE"),
            ((F, s(.1, .05, .15), I, s(.08, .01, .3)), "UA_CI_ABOVE_ZERO"),
            ((F, s(.02, -.01, .05), F, s(.0, -.05, .05)), "MI_CI_NOT_ABOVE_ZERO"),
            ((F, s(.1, .05, .15), I, s(.0, -.1, .2)), "UA_IMPRECISE"),
            ((F, s(.1, .05, .15), I, s(.08, .01, .3, av=.7)), "UA_DIRECTION_REVERSED"),
            ((F, s(.1, .05, .15), F, s(.02, -.03, .07, av=.5)), "UA_DIRECTION_REVERSED"),
            ((F, s(.1, .05, .15, av=.7), F, s(.03, .01, .05, av=.6)), "UA_CI_ABOVE_ZERO"),
            ((F, s(.1, .05, .15), F, s(.04, -.02, .09)), "UA_ATTENUATED"),
            ((F, s(.1, .05, .15), F, s(.05, -.02, .12)), "UA_ATTENUATION_UNRESOLVED"),
            ((F, s(.1, .05, .15), F, s(.05, -.02, .10)), "UA_ATTENUATION_UNRESOLVED"),
            ((F, s(.1, .05, .15), F, s(.06, -.01, .13)), "UA_NOT_ATTENUATED"),
        ]
        lab = {"UA_CI_ABOVE_ZERO": "SIGNAL_PERSISTS_BEYOND_MI_SUBTYPE", "UA_ATTENUATED": "SIGNAL_MOSTLY_REFERENCE_DEPENDENT"}
        for args, reason in cases:
            self.assertEqual(S.interpret(*args), (lab.get(reason, "REFERENCE_SENSITIVITY_NOT_EVALUABLE"), reason))

    def test_negative_control(self):
        pub, sealed = S.build_b1s(copy.deepcopy(self.d), b1_public(self.d))
        self.assertGreater(sealed["test_a"]["mi_vs_pe"]["delta"], 0.05)  # 합성 신호 존재
        self.assertLess(abs(sealed["negative_control"]["delta"]), abs(sealed["reproduction"]["delta"]))
        self.assertIn(pub["negative_control"]["status"], {"NC_PASS", "NC_FLAG"})

    def test_guard_and_schema(self):
        pub, _ = S.build_b1s(copy.deepcopy(self.d), b1_public(self.d))
        self.assertEqual(S.guard(pub), [])
        self.assertEqual(sorted(k for k, _ in A.flatten(pub)), sorted(SCHEMA_KEYS))
        for k, v in (("test_a.mi_vs_pe.n_bucket_acs", "123"), ("test_b.pooled.auroc", 0.7),
                     ("test_b.pooled.ci_lo", "0.712"), ("test_a.mi_vs_pe.delta", "1.50"),
                     ("test_a.interpretation", "SIGNAL_GOOD")):
            bad = copy.deepcopy(pub)
            a, *mid, leaf = k.split(".")
            node = bad[a]
            for m in mid:
                node = node[m]
            node[leaf] = v
            self.assertEqual(S.guard(bad), [k])
        bad = copy.deepcopy(pub)
        bad["test_a"]["n_ua"] = "LT_50"
        self.assertEqual(S.guard(bad), ["test_a.n_ua"])

    def test_end_to_end_deterministic_and_no_counts(self):
        fx = make(seed=3)
        rc1, out1, p1, s1 = run_main(fx)
        rc2, _, p2, _ = run_main(fx)
        self.assertEqual((rc1, rc2), (0, 0))
        self.assertIn("B1S_VERDICT COMPLETE", out1)
        p1.pop("meta"), p2.pop("meta")
        self.assertEqual(p1, p2)
        txt = json.dumps(p1)
        for n in ("140", "150", "60", "100", "90"):
            self.assertNotIn(f'"{n}"', txt)
        self.assertEqual(s1["subtype_counts"]["PE"]["all"], 150)

    def test_one_run_guard_and_aborts(self):
        fx = make(n_mi=60, n_ua=0, n_pe=60, mi_meas=60, ua_meas=0, pe_meas=60)
        rc, out, _, _ = run_main(fx, out_exists=True)
        self.assertEqual(rc, 2)
        self.assertIn("reason=output_exists", out)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"keys": ["x"]}, f)
        rc, out, _, _ = run_main(fx, schema=f.name)
        os.unlink(f.name)
        self.assertIn("reason=schema_mismatch", out)


if __name__ == "__main__":
    unittest.main()
