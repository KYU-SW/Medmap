"""v5-1 기능 검사. 순수 논리 사례는 의학 의미 없음. 의학 분류는 연구용 표현 검사이며 임상 정확도 아님."""
import itertools
import json
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import run_v5_1 as RUN  # noqa: E402  (__main__ 보호로 실행 안 됨)
from hybrid4 import logic as LG4  # noqa: E402
from hybrid5 import classification as CL, concepts as CN, ecg as EC, logic as L, observations as OB  # noqa: E402
from hybrid5.flat import evaluate_flat  # noqa: E402

R5 = RUN.R5


def F(k, v):
    if v is None:
        return L.Fact(k, "NOT_FOUND")
    if v == "C":
        return L.Fact(k, "CONFLICT", None, (True, False), (f"a:{k}", f"b:{k}"))
    return L.Fact(k, "FOUND", v, (v,), (f"s:{k}",))


ITEMS = tuple((f"c{i}", L.Atom(f"c{i}", (True,))) for i in range(5))


def kofn(vals, op, k):
    return L.eval_kofn(L.KofN("t", op, k, ITEMS), {f"c{i}": F(f"c{i}", v) for i, v in enumerate(vals)})


def state(case, i=0):
    p, ts = RUN.CASES[case]()
    return p, R5.evaluate(p, ts[i])


def hyp(res, hid):
    return [h for h in res["hypotheses"] if h["hyp_id"] == hid][0]


class KofNLogic(unittest.TestCase):
    def test_spec_examples(self):
        v = [True, True, None, None, None]
        self.assertEqual(kofn(v, "AT_LEAST_K", 2)["value"], "TRUE")
        self.assertEqual(kofn(v, "AT_LEAST_K", 3)["value"], "UNKNOWN")
        r = kofn(v, "EXACTLY_K", 2)
        self.assertEqual((r["value"], r["minimum_true"], r["maximum_possible_true"]), ("UNKNOWN", 2, 5))
        self.assertEqual(kofn([True, False, False, False, False], "EXACTLY_K", 1)["value"], "TRUE")
        self.assertEqual(kofn([False] * 5, "AT_LEAST_K", 1)["value"], "FALSE")
        self.assertEqual(kofn([None] * 5, "EXACTLY_K", 0)["value"], "UNKNOWN")          # 미기록 ≠ 0개
        self.assertEqual(kofn([True, True, True, False, None], "EXACTLY_K", 2)["value"], "FALSE")

    def test_conflict_vs_unknown(self):
        r = kofn([True, "C", False, False, False], "AT_LEAST_K", 2)
        self.assertEqual((r["value"], r["undetermined_reason"]), ("CONFLICT", "CONFLICT_ONLY"))
        self.assertTrue(r["conflicting_sources"])
        r = kofn([True, "C", None, False, False], "AT_LEAST_K", 3)
        self.assertEqual((r["value"], r["undetermined_reason"]), ("CONFLICT", "CONFLICT_AND_UNKNOWN"))
        r = kofn([True, True, "C", False, False], "AT_LEAST_K", 2)
        self.assertEqual(r["value"], "TRUE")                                          # 충돌이 결과에 영향 없으면 확정

    def test_duplicate_criteria_rejected(self):
        with self.assertRaises(ValueError):
            L.KofN("d", "AT_LEAST_K", 1, (("c1", L.Atom("c1", (True,))), ("c1", L.Atom("c1", (True,)))))

    def test_brute_force_matches_definition(self):
        for vals in itertools.product([True, False, None, "C"], repeat=4):
            for op, k in itertools.product(("AT_LEAST_K", "EXACTLY_K"), range(5)):
                items = tuple((f"c{i}", L.Atom(f"c{i}", (True,))) for i in range(4))
                r = L.eval_kofn(L.KofN("t", op, k, items), {f"c{i}": F(f"c{i}", v) for i, v in enumerate(vals)})
                outs = set()
                und = [i for i, v in enumerate(vals) if v in (None, "C")]
                for bits in itertools.product([True, False], repeat=len(und)):
                    x = sum(1 for v in vals if v is True) + sum(bits)
                    outs.add(x >= k if op == "AT_LEAST_K" else x == k)
                want = "TRUE" if outs == {True} else "FALSE" if outs == {False} else None
                if want:
                    self.assertEqual(r["value"], want, (vals, op, k))
                else:
                    self.assertIn(r["value"], ("UNKNOWN", "CONFLICT"), (vals, op, k))

    def test_same_as_v4_without_kofn(self):
        rnd = random.Random(7)
        keys = ["a", "b", "c", "d"]

        def tree(d):
            if d == 0 or rnd.random() < 0.3:
                return L.Atom(rnd.choice(keys), (rnd.choice(["x", "y"]),))
            t = rnd.choice(["and", "or", "not"])
            if t == "not":
                return L.Not(tree(d - 1))
            kids = tuple(tree(d - 1) for _ in range(rnd.randint(1, 3)))
            return L.And(kids) if t == "and" else L.Or(kids)
        for _ in range(400):
            n = tree(4)
            facts = {k: rnd.choice([L.Fact(k, "FOUND", "x", ("x",), ("s",)), L.Fact(k, "FOUND", "y", ("y",), ("s",)), L.Fact(k, "NOT_FOUND"),
                                    L.Fact(k, "CONFLICT", None, ("x", "y"), ("s1", "s2"))]) for k in keys}
            self.assertEqual(L.eval5(n, facts)["value"], LG4.eval_cond(n, facts)["value"])


class Observations(unittest.TestCase):
    def ex(self, t, **k):
        return OB.extract(t, "P", "E1", "r", 10.0, 20.0)

    def test_hs_is_assay_not_result(self):
        o = self.ex("High-sensitivity troponin T was 9 ng/L.")[0]
        self.assertEqual((o.assay_type, o.result_qualifier, o.analyte), ("HIGH_SENSITIVITY", "UNKNOWN", "TROPONIN_T"))

    def test_reference_not_a_result(self):
        os = self.ex("CRP 45 mg/L (reference < 5 mg/L), elevated.")
        self.assertEqual([(o.numeric_value, o.reference_upper, o.result_qualifier) for o in os], [(45.0, 5.0, "elevated")])
        o = self.ex("Troponin I 0.079 ng/mL (normal: <0.04 ng/mL).")[0]
        self.assertEqual((o.reference_upper, o.result_qualifier), (0.04, "UNKNOWN"))       # 'normal' 기준 문구는 해석이 아님

    def test_sex_specific_reference_and_offsets(self):
        os = self.ex("High-sensitivity troponin T was 18 ng/L at baseline and 35 ng/L at 3 hours (99th percentile URL for women 14 ng/L).")
        self.assertEqual([(o.observation_time, o.reference_percentile, o.reference_population) for o in os], [(10.0, "99th", "FEMALE"), (13.0, "99th", "FEMALE")])

    def test_no_reference_not_invented(self):
        o = self.ex("High-sensitivity troponin T was 30 ng/L.")[0]
        self.assertEqual((o.reference_upper, OB.above_reference(o)["status"]), (None, "UNKNOWN"))

    def test_no_analyte_no_observation(self):
        self.assertEqual(self.ex("The value was 42 ng/L."), [])
        self.assertEqual(self.ex("Troponin was elevated."), [])

    def test_comparability_and_delta(self):
        a, b = RUN.trop("a", 0, 10), RUN.trop("b", 1, 30)
        s = OB.build_series([a, b], 5.0, "FEMALE")[0]["pairs"][0]
        self.assertEqual((s["comparable"], s["abs_delta"], s["rel_delta"]), (True, 20.0, 2.0))
        self.assertIn("MATH_ONLY", s["delta_status"])
        for other, why in ((RUN.trop("c", 1, 0.03, unit="ng/mL"), "UNIT"), (RUN.trop("d", 1, 30, assay="UNKNOWN"), "ASSAY")):
            p = OB.build_series([a, other], 5.0)[0]["pairs"][0]
            self.assertTrue(p["abs_delta"] is None and why in p["delta_status"])
        p = OB.build_series([a, RUN.trop("e", 1, 5, cmp="<")], 5.0)[0]["pairs"][0]
        self.assertIn("CENSORED", p["delta_status"])
        self.assertEqual(len(OB.build_series([a, RUN.trop("f", 1, 0.03, analyte="TROPONIN_I", unit="ng/mL")], 5.0)), 2)   # I·T 별도 계열

    def test_sex_not_confirmed(self):
        o = RUN.trop("a", 0, 30)
        self.assertEqual(OB.above_reference(o, "UNKNOWN")["sex_specific_reference"], "SEX_SPECIFIC_NOT_CONFIRMED")
        self.assertEqual(OB.above_reference(o, "MALE")["sex_specific_reference"], "SEX_SPECIFIC_NOT_CONFIRMED")


class Ecg(unittest.TestCase):
    def f(self, t):
        return EC.extract(t, "e", 1.0, 2.0)

    def test_structure(self):
        r = self.f("ECG: 2 mm ST elevation in leads V2-V4 with reciprocal ST depression in II, III, aVF.")["findings"]
        self.assertEqual([(x.finding_type, x.lead_or_distribution["leads"], x.lead_or_distribution["distribution"]) for x in r],
                         [("ST_ELEVATION", ["V2-V4"], "REGIONAL"), ("ST_DEPRESSION", ["II", "III", "aVF"], "REGIONAL")])
        self.assertEqual((r[0].numeric_measurement, r[0].reciprocal_change_reported), (2.0, True))

    def test_diffuse_and_no_lead_guessing(self):
        r = self.f("ECG showed diffuse ST elevation and PR depression.")["findings"]
        self.assertEqual([(x.finding_type, x.lead_or_distribution["distribution"]) for x in r], [("ST_ELEVATION", "DIFFUSE"), ("PR_DEPRESSION", "NOT_STATED")])
        r = self.f("ST elevation in some leads.")["findings"][0]
        self.assertEqual(r.lead_or_distribution["leads"], "NOT_STATED")
        self.assertTrue(r.notes)

    def test_negation_unsupported(self):
        r = self.f("No PR depression; sinus rhythm, heart rate 102 bpm.")
        self.assertEqual((r["findings"][0].assertion_status, r["rhythm"][0]["rhythm"], r["heart_rate"][0]["value"]), ("NEGATED", "sinus rhythm", 102))
        self.assertTrue(self.f("ECG showed a Brugada pattern.")["unstructured_ecg_statements"])

    def test_pr_depression_not_psychiatric(self):
        p, r = state("C07_diffuse_ste")
        h = hyp(r, "h_peri")
        self.assertEqual(len(h["excluded_by_v5_override"]), 1)
        self.assertTrue(all(p.g.nodes[e]["base_concept"] == "HP:0000716" for e in h["excluded_by_v5_override"]))


class Concepts(unittest.TestCase):
    def test_axes_separate_and_validated(self):
        h = CN.MultiHypothesis("h", "V5:DX:MI", "E1", 0.0, presentation_axis="NSTEMI", mechanism_axis="SECONDARY")
        self.assertEqual((h.presentation_axis, h.mechanism_axis), ("NSTEMI", "SECONDARY"))
        for kw in ({"mechanism_axis": "STEMI"}, {"presentation_axis": "PRIMARY"}):
            with self.assertRaises(ValueError):
                CN.MultiHypothesis("h", "V5:DX:MI", "E1", 0.0, **kw)
        with self.assertRaises(ValueError):
            CN.MultiHypothesis("h", "DX:Aortic dissection", "E1", 0.0)

    def test_mentions(self):
        m = CN.find_disease_mentions("Final diagnosis: NSTEMI. A type 2 MI was documented. ACS excluded.")
        self.assertEqual([(x["concept_id"], x["attributes"]) for x in m], [("V5:DX:MI", {"presentation": "NSTEMI"}), ("V5:DX:MI", {"legacy_type": "2"})])   # type 2 → 기전 축 미대응, ACS 약어 미연결
        self.assertEqual(CN.find_disease_mentions("Takotsubo cardiomyopathy."), [])

    def test_no_mi_under_acs_parent(self):
        self.assertNotIn(("V5:DX:ACS", "MI"), CN.SPECTRUM)


class Classification(unittest.TestCase):
    def cls(self, case):
        return hyp(state(case)[1], "h_peri")["classifications"][0]

    def test_grades(self):
        want = {"C14_pericarditis_definite_research": ("DEFINITE", [3, 4]), "C14b_pericarditis_possible_research": ("POSSIBLE", [1, 1]),
                "C10b_pericarditis_all_negative": ("UNLIKELY_REJECTED", [0, 0]), "C10c_pericarditis_not_recorded": ("GRADE_UNDETERMINED", [0, 5]),
                "C07_diffuse_ste": ("POSSIBLE_OR_DEFINITE_UNRESOLVED", [1, 5]), "C12_duplicate_criterion": ("POSSIBLE_OR_DEFINITE_UNRESOLVED", [1, 5])}
        for case, (g, rng) in want.items():
            c = self.cls(case)
            self.assertEqual((c["guideline_classification"], c["criteria_count_range"]), (g, rng), case)
            self.assertTrue(c["evidence_direction"].startswith("NOT_DERIVED") and c["clinical_review_status"] == CL.RESEARCH)

    def test_prerequisite_and_conflict(self):
        self.assertEqual(self.cls("C13_no_presentation")["guideline_classification"], "NOT_GENERATED_PREREQUISITE_UNKNOWN")
        c = self.cls("C11_conflict")
        self.assertEqual((c["criteria_states"]["PERI_RUB"], c["uncertainty_state"]), ("CONFLICT", "CONFLICT"))

    def test_duplicate_crp_counted_once(self):
        c = self.cls("C12_duplicate_criterion")
        self.assertEqual(c["classification_conditions"]["AT_LEAST_2"]["confirmed_true_count"], 1)

    def test_imaging_sensitivity_reported(self):
        self.assertIn("imaging_merged_one_item", self.cls("C14_pericarditis_definite_research")["imaging_count_sensitivity"])

    def test_injury_not_mi(self):
        h = hyp(state("C03b_troponin_series_with_reported_rise")[1], "h_acs")
        c = h["classifications"][0]
        self.assertEqual(c["acute_injury"], "MEETS_CRITERIA_RESEARCH")
        self.assertTrue(c["mi_assessment"].startswith("NOT_ASSESSED") and c["evidence_direction"] == "NOT_DERIVED")
        self.assertEqual((h["supporting_evidence_ids"], h["weakening_evidence_ids"]), ([], []))
        c = hyp(state("C03_troponin_series")[1], "h_acs")["classifications"][0]
        self.assertEqual(c["acute_injury"], "UNDETERMINED_UNKNOWN")                       # 수학적 변화만으로 상승·하강 판정 안 함

    def test_existential_above_not_conflict(self):
        c = hyp(state("C15_late_result", 1)[1], "h_acs")["classifications"][0]
        self.assertIs(c["criteria_states"]["INJ_ABOVE_SEX_SPECIFIC_URL"], True)
        c = hyp(state("C15_late_result", 0)[1], "h_acs")["classifications"][0]
        self.assertIs(c["criteria_states"]["INJ_ABOVE_SEX_SPECIFIC_URL"], False)


class GraphAndTime(unittest.TestCase):
    def test_three_hypotheses_and_legacy(self):
        _, r = state("C01_three_hypotheses")
        self.assertEqual(sorted(h["concept_id"] for h in r["hypotheses"]), sorted(["DX:Pulmonary embolism", "V5:DX:ACS", "DX:Pericarditis"]))
        self.assertTrue(hyp(r, "h_pe")["legacy_v4"]["label"].startswith("LEGACY_V4"))
        self.assertEqual(hyp(r, "h_acs")["weakening_evidence_ids"], [])                    # PE 판단을 ACS 로 옮기지 않음
        self.assertEqual(r["active_direction_relations_v5"], 0)

    def test_late_and_corrected(self):
        p, ts = RUN.CASES["C15_late_result"]()
        ids = lambda t: [x["obs_id"] for s in R5.evaluate(p, t)["hypotheses"][0]["series"] for x in s["points"]]  # noqa: E731
        self.assertEqual((ids(4.0), ids(5.0)), (["OBS:early"], ["OBS:early", "OBS:late"]))
        p, ts = RUN.CASES["C16_corrected_troponin"]()
        self.assertEqual((ids(2.0), ids(3.0)), (["OBS:v1", "OBS:v2"], ["OBS:v1", "OBS:v2c"]))
        self.assertIn("OBS:v2", p.g.nodes)
        self.assertTrue(p.g.outs("OBS:v2c", "CORRECTS"))

    def test_candidates_not_promoted(self):
        h = hyp(state("C17_candidates_vs_working_dx")[1], "h_peri")
        self.assertEqual(sorted(c["diagnosis_status"] for c in h["ai_candidates_unconfirmed"]), ["AI_CANDIDATE_UNCONFIRMED", "RECORD_HISTORY"])

    def test_unresolved_episode(self):
        p = RUN.pg_("U", eps=("E1", "E2"))
        p.add_multi_hypothesis(RUN.H5("h", RUN.ACS))
        p.add_observation(RUN.trop("OBS:x", 0, 20))
        h = R5.evaluate(p, 1.0)["hypotheses"][0]
        self.assertEqual((h["series"], h["unresolved_episode_link_ids"]), ([], ["OBS:x"]))

    def test_graph_equals_flat_all_cases(self):
        for name, f in RUN.CASES.items():
            p, ts = f()
            for t in ts:
                g = R5.evaluate(p, t)
                legacy = {h["hyp_id"]: h["legacy_v4"]["items"] for h in g["hypotheses"] if "legacy_v4" in h}
                self.assertEqual(RUN.strip(g), RUN.strip(evaluate_flat(p, t, legacy)), name)


class Preservation(unittest.TestCase):
    def test_registry(self):
        r = RUN.registry_compat()
        self.assertEqual((r["n"], r["active_in_registry"], r["activated_in_v5_1"]), (37, 0, 0))
        self.assertTrue(all("DO_NOT_ACTIVATE" in x["v5_1_status"] for x in r["rows"] if x["v5_0b_group"] == "C"))

    def test_no_v4_or_registry_modification(self):
        ref = (HERE / "hybrid5/__init__.py").stat().st_mtime
        old = [HERE.parent / "hybrid_reassessment_v4/hybrid4" / f for f in ("logic.py", "graphs.py", "reason.py", "flat.py")] + [RUN.REG]
        self.assertTrue(all(f.stat().st_mtime < ref for f in old))


if __name__ == "__main__":
    unittest.main()
