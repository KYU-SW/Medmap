"""NBI-A0 builder 합성 fixture 시험 — 실제 ck-v0·corpus 미사용.

실행: python3 -m unittest docs/research/nbi/a0/tests/test_build_nbi_a0.py
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_nbi_a0 as B  # noqa: E402


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fact(fid, dp, rel, kind, tt, text, quote, unit, favors=None, **extra):
    return {"fact_id": fid, "disease_or_pair": dp, "relation_type": rel, "favors": favors,
            "finding_text": text, "finding_value": "present", "finding_kind": kind, "test_type": tt,
            "source_id": unit.split("#")[0], "unit_id": unit, "quote": quote, "source_strength": None,
            "evidence_id": extra.get("evidence_id"), "evidence_value": None, "mapped": False}


UNITS = {
    "SYN-0001#u0001": ["Convex ST elevation favors infarction.", "Q wave favors infarction."],
    "SYN-0001#u0002": ["(part 1/2) Concave ST elevation favors pericarditis.", "(part 2/2) Second part text."],
    "SYN-0002#u0001": ["Q waves on ECG can occur in both.", "CT angiography can also be used to separate them."],
    "SYN-0002#u0002": ["Troponin should be measured.", "Chest pain history is asked."],
}
FACTS = [
    fact("A1b3-0044", "ACS~PERI", "DIFFERENTIATING", "TEST_RESULT", "ECG", "convex ST elevation",
         "Convex ST elevation favors infarction.", "SYN-0001#u0001", favors="ACS"),
    fact("A1b3-0046", "ACS~PERI", "DIFFERENTIATING", "TEST_RESULT", "ECG", "Q wave on ECG",
         "Q wave favors infarction.", "SYN-0001#u0001", favors="ACS"),
    fact("A1b3-0047", "ACS~PERI", "DIFFERENTIATING", "TEST_RESULT", "ECG", "concave ST elevation",
         "Concave ST elevation favors pericarditis.", "SYN-0001#u0002", favors="PERI"),
    fact("S-OVL", "ACS~PERI", "OVERLAPPING", "TEST_RESULT", "ECG", "Q waves on ECG",
         "Q waves on ECG can occur in both.", "SYN-0002#u0001"),
    fact("S-EMPTY", "ACS~PERI", "OVERLAPPING", "OTHER", "ECG", "ECG", "Q waves on ECG can occur in both.",
         "SYN-0002#u0001"),
    fact("S-PE-TR", "ACS~PE", "TEST_REQUIRED", "TEST_RESULT", "IMAGING", "CT angiography",
         "CT angiography can also be used to separate them.", "SYN-0002#u0001"),
    fact("S-ACS-TR", "ACS", "TEST_REQUIRED", "TEST_RESULT", "BIOMARKER", "troponin",
         "Troponin should be measured.", "SYN-0002#u0002"),
    fact("S-ACS-Q", "ACS", "TEST_REQUIRED", "SYMPTOM_HISTORY", None, "chest pain history",
         "Chest pain history is asked.", "SYN-0002#u0002"),
    fact("S-PE-BAD", "PE", "TEST_REQUIRED", "TEST_RESULT", "BIOMARKER", "D-dimer",
         "This sentence is not in the unit.", "SYN-0002#u0002"),
    fact("S-PERI-SUP", "PERI", "SUPPORTING", "TEST_RESULT", "ECG", "ST elevation convex",
         "Concave ST elevation favors pericarditis.", "SYN-0001#u0002"),
    # quote 가 같은 source 의 다른 unit 에만 있음: PV1(citation)=True, PV2(unit 수준)=False, source 수준=True
    fact("S-OTHERUNIT", "ACS", "TEST_REQUIRED", "TEST_RESULT", "BIOMARKER", "CT other unit",
         "CT angiography can also be used to separate them.", "SYN-0002#u0002"),
    # PV1=False 인데 PV2=True
    fact("S-PV1FALSE", "PE", "TEST_REQUIRED", "TEST_RESULT", "IMAGING", "chest pain history imaging",
         "Chest pain history is asked.", "SYN-0002#u0002"),
]
CITE_FALSE = {"S-PE-BAD", "S-PV1FALSE"}
PRECOUNT = {"pairs": {
    "ACS~PE": {"true=ACS|WD=PE": {"n_U_possible": 0}, "true=PE|WD=ACS": {"n_U_possible": 2},
               "verdict_precount": "NOT_EVALUABLE"},
    "ACS~PERI": {"true=ACS|WD=PERI": {"n_U_possible": 0}, "true=PERI|WD=ACS": {"n_U_possible": 2},
                 "verdict_precount": "NOT_EVALUABLE"}}}
EXPECTED = {
    "ablations": {
        "AB3_CF1": {
            "ACS~PERI": {"R1_ids": ["A1b3-0044", "A1b3-0046", "A1b3-0047"], "R1_conflict_ids": ["A1b3-0046"],
                         "conflict_pairs": [["A1b3-0046", "S-OVL"]],
                         "n_favors": {"ACS": 1, "PERI": 1}, "R2_ids": [],
                         "R3_by_target": {"ACS": 3, "PERI": 0}, "pv_fail_ids": ["S-OTHERUNIT"],
                         "status": {"true=ACS|WD=PERI": "HISTORY_INSUFFICIENT",
                                    "true=PERI|WD=ACS": "HISTORY_EVALUABLE"}},
            "ACS~PE": {"R1_ids": [], "R2_ids": ["S-PE-TR"], "R2_types": {"IMAGING": 1}, "n_R2_usable": 1,
                       "R3_by_target": {"ACS": 3, "PE": 2},
                       "pv_fail_ids": ["S-OTHERUNIT", "S-PE-BAD", "S-PV1FALSE"],
                       "status": {"true=ACS|WD=PE": "HISTORY_INSUFFICIENT", "true=PE|WD=ACS": "HISTORY_EVALUABLE"}},
        },
        "AB1_R1_only": {"ACS~PE": {"status": {"true=ACS|WD=PE": "ABSTAIN"}}},
        "AB4_no_CF": {"ACS~PERI": {"n_favors": {"ACS": 2, "PERI": 1}}},
        "AB5_known_conflict_excluded": {"ACS~PERI": {"n_favors": {"ACS": 1, "PERI": 0}}},
        "AB6_tier1_only": {"ACS~PERI": {"R1_ids": [], "n_favors": {"ACS": 0, "PERI": 0}},
                           "ACS~PE": {"R2_ids": ["S-PE-TR"]}},
        "CF2_sensitivity": {"ACS~PERI": {"R1_conflict_ids": ["A1b3-0044", "A1b3-0046", "A1b3-0047"],
                                         "n_favors": {"ACS": 0, "PERI": 0}}},
    },
    "H": {"AB3_CF1": {"H1": "PASS", "H2": "PASS"}, "AB1_R1_only": {"H2": "FAIL"},
          "AB5_known_conflict_excluded": {"H1": "FAIL", "H2": "PASS"},
          "AB6_tier1_only": {"H1": "FAIL", "H2": "PASS"}, "CF2_sensitivity": {"H1": "FAIL"}},
    "grid_redundant": 0, "forbidden_hits": 0,
    "pv1_pv2_disagree": ["S-OTHERUNIT", "S-OTHERUNIT", "S-PV1FALSE"],
}


class Fixture:
    def __init__(self, d, expected=EXPECTED, dup_mismatch=False):
        self.d = d
        ck = os.path.join(d, "ckv0")
        os.makedirs(ck)
        rows = list(FACTS) + [dict(FACTS[0], evidence_id="E_1", mapped=True)]
        if dup_mismatch:
            rows.append(dict(FACTS[1], favors="PERI"))
        with open(os.path.join(ck, "ck-v0.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        json.dump(PRECOUNT, open(os.path.join(ck, "precount.json"), "w"))
        json.dump({"rows": [{"fact_id": r["fact_id"], "quote_match": r["fact_id"] not in CITE_FALSE} for r in FACTS]},
                  open(os.path.join(ck, "citation_check.json"), "w"))
        with open(os.path.join(ck, "CKV0_SHA256SUMS"), "w") as f:
            for n in ("ck-v0.jsonl", "precount.json", "citation_check.json"):
                f.write(f"{sha(os.path.join(ck, n))}  {n}\n")
        st = os.path.join(d, "stage1")
        os.makedirs(os.path.join(st, "input"))
        with open(os.path.join(st, "input", "SYN.c01.txt"), "w") as f:
            for uid, parts in UNITS.items():
                for p in parts:
                    f.write(f"[{uid}] (Sec) <p> {p}\n")
        with open(os.path.join(st, "INPUT_SHA256SUMS"), "w") as f:
            f.write(f"{sha(os.path.join(st, 'input', 'SYN.c01.txt'))}  input/SYN.c01.txt\n")
        self.cov = os.path.join(d, "coverage.csv")
        with open(self.cov, "w") as f:
            f.write("source_id,tier,source_type\nSYN-0001,TIER2,narrative_review\nSYN-0002,TIER1,guideline\n")
        self.t0 = os.path.join(d, "design.md")
        with open(self.t0, "w") as f:
            f.write("# T0 forbidden fields (fixture)\n")
        self.exp = os.path.join(d, "expected.json")
        json.dump(expected, open(self.exp, "w"))
        self.ck, self.st = ck, st

    def args(self, out):
        return ["--ckv0", self.ck, "--ckv0-sha", sha(os.path.join(self.ck, "ck-v0.jsonl")),
                "--units-sums", os.path.join(self.st, "INPUT_SHA256SUMS"),
                "--units-sums-sha", sha(os.path.join(self.st, "INPUT_SHA256SUMS")),
                "--t0-forbidden-ref", self.t0, "--t0-forbidden-ref-sha", sha(self.t0),
                "--coverage", self.cov, "--coverage-sha", sha(self.cov),
                "--expected", self.exp, "--expected-sha", sha(self.exp), "--out", out]


class TestNormalize(unittest.TestCase):
    def test_cf1_q_wave(self):
        self.assertEqual(B.norm_cf1("Q wave on ECG"), "q wave")
        self.assertEqual(B.norm_cf1("Q waves on ECG"), "q wave")
        self.assertTrue(B.cf_match("Q wave on ECG", "Q waves on ECG", "CF1"))

    def test_empty_excluded(self):
        self.assertEqual(B.norm_cf1("ECG"), "")
        self.assertFalse(B.cf_match("ECG", "ECG", "CF1"))

    def test_cf2_overlap(self):
        self.assertFalse(B.cf_match("convex ST elevation", "ST elevation (STEMI mimic)", "CF1"))
        self.assertTrue(B.cf_match("convex ST elevation", "ST elevation (STEMI mimic)", "CF2"))

    def test_cf2_opposite_supporting_scope(self):
        facts = {f["fact_id"]: {k: f[k] for k in B.RULE_FIELDS} for f in FACTS}
        c = facts["A1b3-0044"]
        self.assertIn("S-PERI-SUP", B.conflicts(c, facts, "ACS~PERI", "CF2"))
        self.assertNotIn("S-PERI-SUP", B.conflicts(c, facts, "ACS~PERI", "CF1"))

    def test_forbidden_new_words(self):
        for w in ("needed", "necessary", "essential", "indicated"):
            self.assertTrue(any(__import__("re").search(p, w, 2) for p in B.FORBIDDEN), w)

    def test_wording(self):
        self.assertEqual(B.wording("CT can also be used")[0], "PERMISSIVE")
        self.assertEqual(B.wording("Troponin should be measured")[0], "STRONG")
        self.assertEqual(B.wording("ECG")[0], "UNMARKED")
        self.assertEqual(B.wording("should be available and may be used")[0], "MIXED")
        for q in ("is frequently necessary", "is essential", "preferred biomarker", "first-line test",
                  "findings warrant imaging", "perform D-dimer", "recommendations state"):
            self.assertEqual(B.wording(q)[0], "STRONG", q)
        self.assertEqual(B.wording("Troponin should be measured")[1], ["should"])

    def test_type_map(self):
        self.assertEqual(B.info_type({"test_type": None, "finding_kind": "EXAM_SIGN"}), "PHYSICAL_EXAM")
        self.assertEqual(B.info_type({"test_type": "VITALS", "finding_kind": "EXAM_SIGN"}), "VITAL_SIGN")
        self.assertEqual(B.info_type({"test_type": None, "finding_kind": "RISK_FACTOR"}), "QUESTION")
        for tt, it in (("ECG", "ECG"), ("IMAGING", "IMAGING"), ("BIOMARKER", "BIOMARKER"),
                       ("PHYSICAL_EXAM", "PHYSICAL_EXAM"), ("RECORDS", "MEDICAL_RECORD")):
            self.assertEqual(B.info_type({"test_type": tt, "finding_kind": "OTHER"}), it)
        self.assertEqual(B.info_type({"test_type": None, "finding_kind": "TEST_RESULT"}), "OTHER")


class TestRun(unittest.TestCase):
    def test_conformant_and_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d)
            self.assertEqual(B.main(fx.args(os.path.join(d, "o1"))), 0)
            self.assertEqual(B.main(fx.args(os.path.join(d, "o2"))), 0)
            s1 = open(os.path.join(d, "o1", "NBI_A0_SHA256SUMS")).read()
            s2 = open(os.path.join(d, "o2", "NBI_A0_SHA256SUMS")).read()
            self.assertEqual(s1, s2)
            rep = json.load(open(os.path.join(d, "o1", "nbi_a0_report.json")))
            self.assertEqual(rep["verdict"], "CONFORMANT")
            cands = [json.loads(x) for x in open(os.path.join(d, "o1", "nbi_a0_candidates.jsonl"))]
            q = [c for c in cands if c["fact_id"] == "S-ACS-Q"][0]
            self.assertTrue(q["is_history"])
            bad = [c for c in cands if c["fact_id"] == "S-PE-BAD"][0]
            self.assertFalse(bad["pv2"])
            self.assertEqual({c["relation_class"] for c in cands if c["rule"] != "R1"}, {"SOURCE_TEST_MENTION"})
            self.assertEqual({c["candidate_role"] for c in cands},
                             {"SOURCE_LABELED_DISCRIMINATOR", "PAIR_LEVEL_TEST_MENTION", "DISEASE_LEVEL_TEST_MENTION"})
            ou = [c for c in cands if c["fact_id"] == "S-OTHERUNIT"][0]
            self.assertTrue(ou["pv1"] and not ou["pv2"] and ou["pv2_source_level"] and not ou["pv_ok"])
            pf = [c for c in cands if c["fact_id"] == "S-PV1FALSE"][0]
            self.assertTrue(not pf["pv1"] and pf["pv2"] and not pf["pv_ok"])
            rev = json.load(open(os.path.join(d, "o1", "nbi_a0_review.json")))
            r = [x for x in rev if x["direction"] == "true=ACS|WD=PERI"][0]
            self.assertNotIn("NIC-ACS~PERI-A1b3-0046", r["next_information_candidates"])
            self.assertIn("NIC-ACS~PERI-A1b3-0044", r["next_information_candidates"])
            self.assertEqual(r["r1_favors_wd"], ["NIC-ACS~PERI-A1b3-0047"])
            self.assertEqual(r["r1_favors_alternative"], ["NIC-ACS~PERI-A1b3-0044"])

    def test_part_join_pv2(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d)
            ut = B.unit_texts(os.path.join(fx.st, "input"))
            self.assertEqual(ut["SYN-0001#u0002"], "(Sec) <p> Concave ST elevation favors pericarditis. (Sec) <p> Second part text.")

    def test_nonconformant(self):
        bad = json.loads(json.dumps(EXPECTED))
        bad["ablations"]["AB3_CF1"]["ACS~PERI"]["n_favors"]["ACS"] = 2
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d, expected=bad)
            self.assertEqual(B.main(fx.args(os.path.join(d, "o"))), 2)
            rep = json.load(open(os.path.join(d, "o", "nbi_a0_report.json")))
            self.assertEqual(rep["verdict"], "NONCONFORMANT")

    def test_out_exists_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d)
            os.makedirs(os.path.join(d, "o"))
            with self.assertRaises(SystemExit):
                B.main(fx.args(os.path.join(d, "o")))

    def test_sha_mismatch_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d)
            a = fx.args(os.path.join(d, "o"))
            a[a.index("--ckv0-sha") + 1] = "0" * 64
            with self.assertRaises(SystemExit):
                B.main(a)

    def test_dedupe_mismatch_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(d, dup_mismatch=True)
            with self.assertRaises(SystemExit):
                B.main(fx.args(os.path.join(d, "o")))

    def test_forbidden_word_invalid(self):
        orig = dict(B.RELATION_NOTE)
        B.RELATION_NOTE["SOURCE_TEST_MENTION"] = "this test must be done"
        try:
            with tempfile.TemporaryDirectory() as d:
                fx = Fixture(d)
                self.assertEqual(B.main(fx.args(os.path.join(d, "o"))), 2)
                rep = json.load(open(os.path.join(d, "o", "nbi_a0_report.json")))
                self.assertEqual(rep["verdict"], "INVALID")
        finally:
            B.RELATION_NOTE.clear()
            B.RELATION_NOTE.update(orig)


if __name__ == "__main__":
    unittest.main()
