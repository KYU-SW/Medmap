"""NBI-B0c 합성 fixture 시험 — 실제 MIMIC 미사용(가짜 ID·가짜 시각·가짜 사전 라벨). B0a 시험의 Gen 재사용.

실행: python3 -m unittest docs/research/nbi/b0/tests/test_b0c.py
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import b0a_availability as A  # noqa: E402
import b0c_availability as C  # noqa: E402
from test_b0a import Gen, gz, sha  # noqa: E402

SCHEMA = os.path.join(HERE, "..", "expected_schema_b0c.json")
LAB_H = ["labevent_id", "subject_id", "hadm_id", "specimen_id", "itemid", "order_provider_id", "charttime", "storetime",
         "value", "valuenum", "valueuom", "ref_range_lower", "ref_range_upper", "flag", "priority", "comments"]
ADM_H = ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime", "admission_type", "admit_provider_id",
         "admission_location", "discharge_location", "insurance", "language", "marital_status", "race", "edregtime",
         "edouttime", "hospital_expire_flag"]
DLAB_H = ["itemid", "label", "fluid", "category"]
KW = {"BIOMARKER_TROPONIN": "Troponin", "BIOMARKER_DDIMER": "D-Dimer", "BIOMARKER_CKMB": "CK-MB",
      "LAB_CRP_ESR": "C-Reactive Protein"}
TROP, DDIM = "51003", "50915"
IN = "2150-01-01 10:00:00"


def dlab_rows(drop=None, extra=()):
    """가짜 사전: 고정 itemid 에 규칙에 맞는 가짜 라벨 + 매핑되면 안 되는 방해 항목."""
    out = [(i, f"{KW[t]} synthetic {i}", "Blood", "Chemistry") for t in C.LAB_TYPES for i in sorted(C.ITEMS[t])
           if i != drop]
    out += [("90001", "Fibrin Degradation Products", "Blood", "Hematology"),
            ("90002", "Creatine Kinase (CK)", "Blood", "Chemistry"),
            ("90003", "Troponin urine synthetic", "Urine", "Chemistry")] + list(extra)
    return out


def classes(gen):
    """첫 진단 행 기준 stay -> (subject, class) — 합성 Gen 구조 전용."""
    m = {}
    for subj, sid, seq, code, ver, _ in gen.dx:
        if seq == 1:
            m[sid] = (subj, next(c for c in A.CODES if c in A.classify(ver, A.norm_code(code))))
    return m


def admit(gen, cls, n):
    """합성 Gen 의 edstays 에 hadm_id 를 채워 입원 stay 로 만든다(class 별 앞 n 개)."""
    cl = classes(gen)
    sids = [s for s, (_, c) in sorted(cl.items()) if c == cls][:n]
    gen.ed = [(r[0], "8" + str(r[2]) if r[2] in sids else r[1]) + tuple(r[2:]) for r in gen.ed]
    return gen


class Lab:
    def __init__(self, gen):
        self.gen, self.rows, self.adm, self.k = gen, [], [], 0
        self.cls = classes(gen)

    def add(self, cls, n, item=TROP, ct="2150-01-01 10:20:00", st="2150-01-01 11:10:00", start=0):
        sids = [s for s, (_, c) in sorted(self.cls.items()) if c == cls][start:start + n]
        for s in sids:
            self.k += 1
            self.rows.append((self.k, self.cls[s][0], "", "1", item, "", ct, st, "999.9", "999.9", "ng/mL", "0", "1",
                              "abnormal", "STAT", "secret-comment"))
        return self

    def add_adm(self, cls, n, disch="2149-06-01 12:00:00"):
        sids = [s for s, (_, c) in sorted(self.cls.items()) if c == cls][:n]
        for s in sids:
            self.adm.append((self.cls[s][0], "9" + str(s), "2149-05-30 12:00:00", disch, "", "EW EMER.", "P1", "ER",
                             "HOME", "Other", "ENGLISH", "SINGLE", "WHITE", "", "", "0"))
        return self

    def write(self, d, dlab=None):
        ed, ecg = self.gen.write(d)
        paths = {}
        for name, h, r in (("lab", LAB_H, self.rows), ("adm", ADM_H, self.adm), ("dlab", DLAB_H, dlab or dlab_rows())):
            paths[name] = os.path.join(d, name + ".csv.gz")
            open(paths[name], "wb").write(gz(h, r))
        b0a_pub = os.path.join(d, "b0a_public.json")
        dd = A.compute(ed, ecg)
        json.dump(A.build(dd)[0] if dd["verdict"] == "OK" else {"pairs": {}}, open(b0a_pub, "w"))
        return ed, ecg, paths, b0a_pub


def built(lab):
    with tempfile.TemporaryDirectory() as d:
        ed, ecg, p, _ = lab.write(d)
        return C.build_b0c(C.compute_b0c(ed, ecg, p["lab"], p["adm"]))


def margs(d, ed, ecg, p, b0a_pub, schema=SCHEMA):
    a = ["--ed-zip", ed, "--ecg-zip", ecg, "--labevents", p["lab"], "--d-labitems", p["dlab"],
         "--admissions", p["adm"], "--schema", schema, "--b0a-public", b0a_pub]
    out = []
    for i in range(0, len(a), 2):
        out += [a[i], a[i + 1], a[i] + "-sha", sha(a[i + 1])]
    return out + ["--out", os.path.join(d, "out"), "--sealed", os.path.join(d, "sealed"),
                  "--private-log", os.path.join(d, "priv", "p.log")]


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = C.main(argv)
    return rc, buf.getvalue()


class TestItemMap(unittest.TestCase):
    def test_rule_reproduces_frozen_items_and_rejects_distractors(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "dl.csv.gz")
            open(p, "wb").write(gz(DLAB_H, dlab_rows()))
            self.assertEqual(C.item_map(p), C.ITEMS)
            open(p, "wb").write(gz(DLAB_H, dlab_rows(drop="51595")))
            self.assertNotEqual(C.item_map(p), C.ITEMS)

    def test_no_value_columns_read(self):
        self.assertEqual(C.LAB_ALLOW, ["subject_id", "itemid", "charttime", "storetime"])
        src = open(os.path.join(HERE, "..", "b0c_availability.py"), encoding="utf-8").read()
        for col in ("valuenum", '"value"', "ref_range", '"flag"', "comments", "hadm_id\"]"):
            self.assertNotIn(col, src.split("LAB_ALLOW = ")[1].split("\n")[0], col)
        self.assertNotRegex(src, r"\[\"valuenum\"\]|\[\"value\"\]|\[\"flag\"\]")

    def test_items_disjoint(self):
        seen = [i for s in C.ITEMS.values() for i in s]
        self.assertEqual(len(seen), len(set(seen)))


class TestLabels(unittest.TestCase):
    def test_available_eligible_decision(self):
        pub, s = built(Lab(Gen()).add("ACS", 35).add("PE", 35).add("PERI", 35))
        P = pub["pairs"]["ACS~PE"]
        self.assertEqual(P["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_AVAILABLE")
        self.assertEqual(P["labels"]["BIOMARKER_DDIMER"], "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(P["pair_rule_inputs"]["acs_pe_eligibility"], "ELIGIBLE")
        self.assertEqual(pub["pair_decision"]["b1_primary_pair"], "ACS~PE")
        self.assertEqual(pub["pairs"]["ACS~PERI"]["pair_rule_inputs"]["acs_pe_eligibility"], "NOT_APPLICABLE")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]["a"], 35)

    def test_ddimer_alone_also_eligible(self):
        pub, _ = built(Lab(Gen()).add("ACS", 31, item=DDIM).add("PE", 31, item=DDIM))
        self.assertEqual(pub["pairs"]["ACS~PE"]["pair_rule_inputs"]["acs_pe_eligibility"], "ELIGIBLE")

    def test_partial_not_eligible(self):
        pub, _ = built(Lab(Gen()).add("ACS", 35).add("PE", 10))
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_PARTIAL")
        self.assertEqual(pub["pairs"]["ACS~PE"]["pair_rule_inputs"]["acs_pe_eligibility"], "PENDING_DATA_B0D")
        self.assertEqual(pub["pair_decision"]["b1_primary_pair"], "PENDING")

    def test_not_evaluable_pair(self):
        pub, _ = built(Lab(Gen(n_pe=0)).add("ACS", 35))
        P = pub["pairs"]["ACS~PE"]
        self.assertEqual(P["pair_status"], "NOT_EVALUABLE")
        self.assertTrue(all(v == "NOT_EVALUABLE" for v in P["labels"].values()))
        self.assertEqual(P["pair_rule_inputs"]["acs_pe_eligibility"], "PENDING_DATA_B0D")
        self.assertEqual(pub["pair_decision"]["b1_primary_pair"], "PENDING")

    def test_storetime_missing_uncertain(self):
        lab = Lab(Gen()).add("ACS", 35, st="").add("PE", 35, st="").add("ACS", 10, start=35).add("PE", 5, start=35)
        pub, s = built(lab)
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "TEMPORALLY_UNCERTAIN")
        self.assertEqual(pub["pairs"]["ACS~PE"]["timing"]["BIOMARKER_TROPONIN"], "TEMPORALLY_UNCERTAIN")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]["storetime_missing_events"], 70)

    def test_uncertain_is_stay_unit_not_event_unit(self):
        # 정상 35/35 + 한 stay 에 결측 사건 70건: 사건 단위였다면 UNCERTAIN, stay 단위면 AVAILABLE (gate 7 S-unit-uncertain)
        lab = Lab(Gen()).add("ACS", 35).add("PE", 35)
        for _ in range(70):
            lab.add("ACS", 1, st="", start=36)
        pub, s = built(lab)
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_AVAILABLE")
        self.assertEqual(s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]["stays_all_storetime_missing"], 1)

    def test_uncertain_boundary_exactly_half(self):
        pub, s = built(Lab(Gen(n_acs=60, n_pe=60, n_peri=0)).add("ACS", 30, st="").add("ACS", 30, start=30)
                       .add("PE", 30))  # 30/90 < 0.5
        a = s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]
        self.assertEqual((a["stays_all_storetime_missing"], a["stays_collected_in_stay"]), (30, 90))
        self.assertNotEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "TEMPORALLY_UNCERTAIN")
        lab3 = Lab(Gen(n_acs=60, n_pe=40, n_peri=0)).add("ACS", 30, st="").add("ACS", 30, start=30)
        pub3, s3 = built(lab3)
        a3 = s3["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]
        self.assertEqual((a3["stays_all_storetime_missing"], a3["stays_collected_in_stay"]), (30, 60))
        self.assertEqual(pub3["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "TEMPORALLY_UNCERTAIN")  # 정확히 0.5

    def test_uncertain_needs_min_stays(self):
        pub, _ = built(Lab(Gen()).add("ACS", 1, st=""))  # 결측 1건뿐
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "NOT_AVAILABLE_IN_DATA")
        pub, _ = built(Lab(Gen()).add("ACS", 29, st="").add("PE", 1))  # 29/30 결측이지만 < Q_MIN
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_PARTIAL")

    def test_storetime_missing_below_share_stays_certain(self):
        pub, _ = built(Lab(Gen()).add("ACS", 35).add("PE", 35).add("ACS", 5, st="", start=35))
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_AVAILABLE")


class TestTimeWindow(unittest.TestCase):
    def avail(self, ct, st):
        pub, s = built(Lab(Gen()).add("ACS", 35, ct=ct, st=st).add("PE", 35, ct=ct, st=st))
        return pub["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]

    def test_storetime_at_outtime_inclusive(self):
        self.assertEqual(self.avail("2150-01-01 15:00:00", "2150-01-01 16:00:00")[0], "RECORDED_IN_STAY_AVAILABLE")

    def test_storetime_after_outtime_not_available(self):
        lab, s = self.avail("2150-01-01 15:00:00", "2150-01-01 16:00:01")
        self.assertEqual(lab, "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["post_ed_24h_stays"], 70)

    def test_collected_before_arrival_not_available(self):
        lab, s = self.avail("2150-01-01 09:30:00", "2150-01-01 10:30:00")
        self.assertEqual(lab, "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["pre_t0_collected_stays"], 70)

    def test_result_before_arrival_not_available(self):
        lab, s = self.avail("2150-01-01 08:00:00", "2150-01-01 09:00:00")
        self.assertEqual(lab, "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(s["pre_t0_24h_stays"], 70)

    def test_timing_labels(self):
        early = built(Lab(Gen()).add("ACS", 35, st="2150-01-01 10:50:00").add("PE", 35, st="2150-01-01 10:50:00"))[0]
        late = built(Lab(Gen()).add("ACS", 35, st="2150-01-01 12:00:00").add("PE", 35, st="2150-01-01 12:00:00"))[0]
        few = built(Lab(Gen()).add("ACS", 10).add("PE", 10))[0]
        self.assertEqual(early["pairs"]["ACS~PE"]["timing"]["BIOMARKER_TROPONIN"], "EARLY_ROUTINE_POSSIBLE")
        self.assertEqual(late["pairs"]["ACS~PE"]["timing"]["BIOMARKER_TROPONIN"], "LATER_IN_STAY")
        self.assertEqual(few["pairs"]["ACS~PE"]["timing"]["BIOMARKER_TROPONIN"], "INSUFFICIENT_N")

    def test_overlapping_later_stay_takes_event(self):
        gen = Gen(n_acs=35, n_pe=35, n_peri=0)
        cls = classes(gen)
        for sid, (subj, c) in list(cls.items()):  # 같은 subject, 주 stay 와 겹치는 진단 없는 stay(12:00–13:00)
            gen.sid += 1
            gen.ed.append((subj, "", gen.sid, "2150-01-01 12:00:00", "2150-01-01 13:00:00", "F", "X", "WALK IN", "HOME"))
        late = built(Lab(gen).add("ACS", 35, ct="2150-01-01 12:10:00", st="2150-01-01 12:30:00")
                     .add("PE", 35, ct="2150-01-01 12:10:00", st="2150-01-01 12:30:00"))[0]
        early = built(Lab(gen).add("ACS", 35).add("PE", 35))[0]
        self.assertEqual(late["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "NOT_AVAILABLE_IN_DATA")
        self.assertEqual(early["pairs"]["ACS~PE"]["labels"]["BIOMARKER_TROPONIN"], "RECORDED_IN_STAY_AVAILABLE")

    def test_windows_sealed(self):
        s = built(Lab(Gen()).add("ACS", 35, st="2150-01-01 12:30:00").add("PE", 35))[1]
        w = s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]["windows"]
        self.assertEqual((w["W1"]["a"], w["W3"]["a"], w["W1"]["b"], w["W3"]["b"]), (0, 35, 0, 35))  # 11:10 은 W1 밖


class TestPreT0Record(unittest.TestCase):
    def test_prior_discharge_counts_and_after_does_not(self):
        pub, s = built(Lab(Gen()).add_adm("ACS", 35).add_adm("PE", 35)
                       .add_adm("PERI", 35, disch="2150-01-01 11:00:00"))
        self.assertEqual(pub["pairs"]["ACS~PE"]["labels"]["MEDICAL_RECORD_PRE_T0"], "PRE_T0_RECORD_AVAILABLE")
        self.assertEqual(s["pairs"]["ACS~PERI"]["avail"]["MEDICAL_RECORD_PRE_T0"]["b"], 0)
        self.assertEqual(pub["pairs"]["ACS~PE"]["timing"]["MEDICAL_RECORD_PRE_T0"], "NOT_APPLICABLE")


class TestPublicMinimal(unittest.TestCase):
    def test_schema_and_vocab(self):
        pub, _ = built(Lab(Gen()).add("ACS", 35).add("PE", 35))
        keys = json.load(open(SCHEMA, encoding="utf-8"))["keys"]
        self.assertEqual(sorted(k for k, _ in A.flatten(pub)), sorted(keys))
        self.assertEqual(len(keys), 37)
        self.assertEqual(C.guard(pub), [])
        for k, v in A.flatten(pub):
            self.assertIsInstance(v, str, k)
            self.assertIsNone(re.fullmatch(r"[\d.]+", v), k)  # 숫자 그대로의 값 없음

    def test_small_pool_withheld(self):
        pub, _ = built(Lab(Gen()).add("ACS", 35).add("PE", 35))  # n_pool 80
        self.assertEqual(pub["pairs"]["ACS~PE"]["pooled_share_bin"]["BIOMARKER_TROPONIN"], "WITHHELD")

    def test_strata_sealed_only(self):
        # gate 7 S-classblind-proxy: 입원≈class 인 쌍에서 층 구간이 class 비율 대리가 되므로 공개 금지, 봉인에만
        outs = set()
        for k in (14, 15, 40, 120):
            gen = admit(Gen(n_acs=150, n_pe=150, n_peri=0), "ACS", 150)
            pub, s = built(Lab(gen).add("ACS", 150).add("PE", k))
            self.assertFalse(any("admitted" in key for key, _ in A.flatten(pub)))
            a = s["pairs"]["ACS~PE"]["avail"]["BIOMARKER_TROPONIN"]
            self.assertEqual((s["pairs"]["ACS~PE"]["cohort"]["n_admitted"], a["stratum_admitted_recorded"],
                              a["stratum_not_admitted_recorded"]), (150, 150, k))
            outs.add(json.dumps(pub["pairs"]["ACS~PE"]["labels"], sort_keys=True))
        self.assertGreaterEqual(len(outs), 1)

    def test_attack_small_cell_invisible(self):
        outs = set()
        for k in range(1, 11):  # PE 쪽 기록 stay 1..10 변화
            pub, _ = built(Lab(Gen(n_acs=150, n_pe=150, n_peri=0)).add("ACS", 150).add("PE", k))
            outs.add(json.dumps(pub, sort_keys=True))
        self.assertEqual(len(outs), 1)
        outs = set()
        for k in range(1, 11):
            pub, _ = built(Lab(Gen()).add("ACS", 35).add("PE", k))  # n_pool < 100
            outs.add(json.dumps(pub, sort_keys=True))
        self.assertEqual(len(outs), 1)

    def test_deterministic(self):
        lab = Lab(Gen()).add("ACS", 35).add("PE", 35).add_adm("ACS", 3)
        self.assertEqual(built(lab), built(lab))


class TestMain(unittest.TestCase):
    def test_complete_and_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            lab = Lab(Gen()).add("ACS", 35).add("PE", 35)
            ed, ecg, p, b = lab.write(d)
            rc, out = run(margs(d, ed, ecg, p, b))
            self.assertEqual((rc, out.strip()), (0, "B0C_VERDICT COMPLETE"))
            pub = json.load(open(os.path.join(d, "out", "b0c_public.json")))
            self.assertEqual(pub["meta"]["sealed_file_sha256"], sha(os.path.join(d, "sealed", "b0c_sealed.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "out", "B0C_SHA256SUMS")))
            self.assertEqual(oct(os.stat(os.path.join(d, "sealed")).st_mode & 0o777), "0o700")

    def test_aborts(self):
        cases = {
            "sha_mismatch": lambda a: a.__setitem__(a.index("--labevents-sha") + 1, "0" * 64),
            "item_map_mismatch": None,
            "cohort_mismatch_b0a": None,
        }
        for reason in cases:
            with tempfile.TemporaryDirectory() as d:
                lab = Lab(Gen()).add("ACS", 35).add("PE", 35)
                ed, ecg, p, b = lab.write(d, dlab=dlab_rows(drop="51002") if reason == "item_map_mismatch" else None)
                if reason == "cohort_mismatch_b0a":
                    x = json.load(open(b))
                    x["pairs"]["ACS~PE"]["cohort_pooled_bucket"] = "GE_5000"
                    json.dump(x, open(b, "w"))
                a = margs(d, ed, ecg, p, b)
                if cases[reason]:
                    cases[reason](a)
                rc, out = run(a)
                self.assertEqual(rc, 2, reason)
                self.assertIn(f"reason={reason}", out)
                self.assertFalse(os.path.exists(os.path.join(d, "out")), reason)
                if reason != "cohort_mismatch_b0a":
                    self.assertFalse(os.path.exists(os.path.join(d, "sealed")), reason)

    def test_guard_blocks_numeric_leaf(self):
        orig = C.build_b0c

        def leaky(d):
            pub, sealed = orig(d)
            pub["pairs"]["ACS~PE"]["pooled_share_bin"]["BIOMARKER_TROPONIN"] = "37"
            return pub, sealed
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, b = Lab(Gen()).add("ACS", 35).add("PE", 35).write(d)
            C.build_b0c = leaky
            try:
                rc, out = run(margs(d, ed, ecg, p, b))
            finally:
                C.build_b0c = orig
            self.assertEqual(rc, 2)
            self.assertIn("reason=output_guard", out)
            self.assertFalse(os.path.exists(os.path.join(d, "out")))
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))

    def test_output_exists(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, b = Lab(Gen()).write(d)
            os.makedirs(os.path.join(d, "sealed"))
            rc, out = run(margs(d, ed, ecg, p, b))
            self.assertEqual(rc, 2)
            self.assertIn("output_exists", out)

    def test_stop_title_no_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, b = Lab(Gen(title_override="Something unrelated")).write(d)
            rc, out = run(margs(d, ed, ecg, p, b))
            self.assertEqual(rc, 3)
            self.assertFalse(os.path.exists(os.path.join(d, "sealed")))
            self.assertFalse(os.path.exists(os.path.join(d, "out")))

    def test_stdout_has_no_numbers_or_ids(self):
        with tempfile.TemporaryDirectory() as d:
            ed, ecg, p, b = Lab(Gen()).add("ACS", 35).add("PE", 35).write(d)
            _, out = run(margs(d, ed, ecg, p, b))
            self.assertEqual(out, "B0C_VERDICT COMPLETE\n")
            self.assertNotRegex(out.replace("B0C", ""), r"\d")


if __name__ == "__main__":
    unittest.main()
