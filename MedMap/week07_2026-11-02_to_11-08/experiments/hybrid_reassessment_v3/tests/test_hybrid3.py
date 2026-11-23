"""v3 기능 검사(새로 작성한 합성 문장). 방향 기대값은 카탈로그의 검증 관계와 적용 조건에서만 정함. 임상 정확도 아님."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from hybrid3 import concepts as CP, context as CX, reasoner as R  # noqa: E402
from hybrid3.kg import EvidenceGraph  # noqa: E402
from hybrid3.reasoner import Case, Doc, Hypothesis  # noqa: E402
from hybrid.schema import DxStatus  # noqa: E402

PE = "DX:Pulmonary embolism"
SUSP = "Pulmonary embolism is suspected. Clinical probability was assessed as intermediate using the Wells score."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
NEG = "IMPRESSION: No evidence of pulmonary embolism."
ENG = R.Engine()


def cur(eid="E1"):
    return Hypothesis("h1", "Pulmonary embolism", PE, 0.0, episode_id=eid)


def run(docs, as_of, hyps=None, engine=ENG):
    c = Case("c", engine)
    for h in hyps or [cur()]:
        c.add_hypothesis(h)
    for d in docs:
        c.add_document(d)
    return c.state(as_of)


def pick(state, surface_concept="PE_DIAGNOSIS", doc=None, episode=None):
    return [r for r in state["results"] if r["concept"] == surface_concept and (doc is None or r["document"] == doc) and (episode is None or r["episode_id"] == episode)]


def facts(text):
    return {(f["key"], str(f["value"])) for f in CX.extract_facts(Doc("d", text, "NOTE", 0.0, 0.0))}


class SentenceAnalysis(unittest.TestCase):
    def test_example_sentence(self):
        a = R.analyze_text("The patient was diagnosed with pulmonary embolism one month ago and is currently receiving anticoagulation.")
        ev = {e["concept"]: e for e in a["events"]}
        self.assertEqual((ev["PE_DIAGNOSIS"]["kind"], ev["PE_DIAGNOSIS"]["temporal"]), ("DISEASE", "PAST"))
        self.assertEqual((ev["ANTICOAGULATION"]["kind"], ev["ANTICOAGULATION"]["treatment_status"]), ("TREATMENT", "CURRENT"))
        ep = [f for f in a["facts"] if f["key"] == "pe_episode_statement"][0]
        self.assertEqual((ep["value"]["status"], ep["value"]["relative_time"]), ("DIAGNOSED_STATEMENT", "one month ago"))
        self.assertTrue(all(f["physician_confirmation_status"] == "UNCONFIRMED" and f["source_type"] == "RECORD" for f in a["facts"]))   # 'diagnosed' 문구 ≠ 의사 확인
        self.assertIn(("clinical_phase_signal", "UNDER_TREATMENT"), {(f["key"], str(f["value"])) for f in a["facts"]})

    def test_expressions(self):
        want = {"Confirmed pulmonary embolism.": "PRESENT", "Suspected pulmonary embolism.": "UNCERTAIN", "Possible pulmonary embolism.": "UNCERTAIN",
                "Rule out pulmonary embolism.": "PURPOSE_OR_DIFFERENTIAL", "No evidence of pulmonary embolism.": "NEGATED", "History of pulmonary embolism.": "HISTORICAL",
                "Recurrent pulmonary embolism is suspected.": "UNCERTAIN", "Pulmonary embolism resolved after treatment.": "HISTORICAL"}
        for t, a in want.items():
            ev = [e for e in R.analyze_text(t)["events"] if e["concept"] == "PE_DIAGNOSIS"]
            self.assertEqual([e["assertion"] for e in ev], [a], t)
        self.assertEqual([e["subtype"] for e in R.analyze_text("Recurrent pulmonary embolism is suspected.")["events"]], ["PE_RECURRENT"])
        self.assertIn(("clinical_phase_signal", "RECURRENCE_EVALUATION"), facts("Recurrent pulmonary embolism is suspected."))
        self.assertIn(("clinical_phase_signal", "POST_TREATMENT_FOLLOWUP"), facts("Follow-up imaging after treatment for pulmonary embolism was performed."))

    def test_p1_fixes_kept(self):
        ev = R.analyze_text("Given absence of contraindications to surgery, and a confirmed diagnosis of severe pulmonary embolism, thrombolysis was started.")["events"]
        self.assertEqual([e["assertion"] for e in ev if e["concept"] == "PE_DIAGNOSIS"], ["PRESENT"])
        self.assertEqual({e["assertion"] for e in R.analyze_text("Deep venous thrombosis (DVT) scan was negative.")["events"] if e["concept"] == "DVT"}, {"NEGATED"})
        self.assertEqual([e["test_status"] for e in R.analyze_text("A D-dimer was requested.")["events"]], ["ORDERED"])
        legend = [e for e in R.analyze_text("CTPA: computed tomography pulmonary angiography; segmental pulmonary embolism was treated.")["events"] if e["concept"] == "CTPA_STUDY"]
        self.assertTrue(legend and all(e["role"] == "DEFINITION_ONLY" for e in legend))


class ConceptLinking(unittest.TestCase):
    def test_doc_abbreviation_and_subtype(self):
        rs = CP.extract("CTPA revealed subsegmental pulmonary embolism (SSPE). The SSPE was isolated.", "CTPA_REPORT")
        sspe = [r for r in rs if r["surface"] == "SSPE"]
        self.assertTrue(sspe and all((r["concept"], r["subtype"]) == ("PE_DIAGNOSIS", "PE_SUBSEGMENTAL") for r in sspe))
        self.assertTrue(all(CP.finding_state(r).get("level") == "SUBSEGMENTAL" for r in sspe))

    def test_sspe_undefined_not_linked(self):
        self.assertEqual({r["link_status"] for r in CP.extract("Very distal SSPE seen.", "NOTE")}, {"AMBIGUOUS"})

    def test_pe_abbreviation_rules(self):
        self.assertEqual(CP.extract("PE suspected.", "NOTE")[0]["link_status"], "AMBIGUOUS")                       # 문서 단서 없음
        self.assertEqual(CP.extract("PE suspected. Wells score 4.", "NOTE")[0]["concept"], "PE_DIAGNOSIS")
        self.assertEqual(CP.extract("On PE, lungs clear. Pulmonary embolism suspected.", "NOTE")[0]["link_status"], "AMBIGUOUS")   # 신체검진 표기

    def test_subtypes_not_merged(self):
        r = [x for x in CP.extract("Proximal DVT on compression ultrasound.", "NOTE") if x["concept"] == "DVT"][0]
        self.assertEqual(r["subtype"], "DVT_PROXIMAL")
        self.assertEqual([x["concept"] for x in CP.extract("Chest CT showed no abnormality.", "NOTE") if x["link_status"] == "LINKED"], [])   # 일반 흉부 CT ≠ CTPA

    def test_unknown_test_marked(self):
        r = [x for x in CP.extract("Echocardiography showed a dilated aorta.", "NOTE") if x["link_status"] == "UNSUPPORTED"]
        self.assertEqual((len(r), CP.finding_state(r[0])["reason"]), (1, "CONCEPT_NOT_SUPPORTED"))


class Context(unittest.TestCase):
    def test_pretest_stated(self):
        f = facts("Clinical probability was assessed as low.")
        self.assertIn(("pretest", "LOW"), f)
        self.assertIn(("pretest_method", "NOT_STATED"), f)

    def test_score_not_converted(self):
        f = facts("The Wells score was 4 points.")
        self.assertFalse([x for x in f if x[0] == "pretest"])
        self.assertTrue([x for x in f if x[0] == "probability_score"])
        self.assertFalse([x for x in facts("PE unlikely by two-level Wells.") if x[0] == "pretest"])
        self.assertFalse([x for x in facts("Moderate risk for a pulmonary embolism.") if x[0] == "pretest"])   # 위험도 ≠ 임상 확률

    def test_test_purpose_is_suspicion_not_diagnosis(self):
        a = R.analyze_text("CTPA was performed to exclude pulmonary embolism.")
        self.assertEqual([e["assertion"] for e in a["events"] if e["concept"] == "PE_DIAGNOSIS"], ["PURPOSE_OR_DIFFERENTIAL"])
        self.assertIn(("suspected", "True"), {(f["key"], str(f["value"])) for f in a["facts"]})

    def test_followup_not_suspected(self):
        f = facts("The patient is undergoing follow-up imaging after treatment for pulmonary embolism.")
        self.assertNotIn(("suspected", "True"), f)

    def test_conflict(self):
        s = run([Doc("a", "Clinical probability was low.", "NOTE", 0.0, 1.0), Doc("b", "Clinical probability was high.", "NOTE", 0.0, 1.5)], 2.0)
        self.assertEqual(s["context"]["pretest"]["status"], "CONFLICT")


class EndToEnd(unittest.TestCase):
    def test_case1_support_via_graph(self):
        r = pick(run([Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", POS, "CTPA_REPORT", 2.0, 4.0)], 5.0), doc="r")[0]
        self.assertEqual((r["direction"], r["relation_id"]), ("SUPPORT", "PE-CTPA-POSITIVE"))
        self.assertIn("STATE:CTPA_REPORTS_PE", r["graph_path"])
        self.assertTrue(r["sources"] and all(s["quote"] for s in r["sources"]))
        self.assertEqual(r["conditions_used"]["pretest"], "INTERMEDIATE")

    def test_case2_negative_and_ddimer_conditions(self):
        self.assertEqual(pick(run([Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", NEG, "CTPA_REPORT", 2.0, 4.0)], 5.0), doc="r")[0]["direction"], "WEAKEN")
        low = "Pulmonary embolism is suspected. Clinical probability was assessed as low."
        s = run([Doc("n", low, "NOTE", 0.5, 1.0), Doc("l", "D-dimer measured by ELISA was normal, below the age-adjusted cut-off.", "LAB", 1.5, 2.0)], 3.0)
        self.assertEqual(pick(s, "DDIMER")[0]["direction"], "WEAKEN")
        s = run([Doc("n", low, "NOTE", 0.5, 1.0), Doc("l", "D-dimer was normal.", "LAB", 1.5, 2.0)], 3.0)
        r = pick(s, "DDIMER")[0]
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["ddimer_assay", "ddimer_cutoff"]))
        self.assertEqual({g["class"] for g in r["gaps"]}, {"B"})

    def test_relation_specific_conditions(self):                       # 관류 정상은 임상 확률을 요구하지 않음(카탈로그 조건)
        s = run([Doc("n", "Pulmonary embolism is suspected.", "NOTE", 0.5, 1.0), Doc("p", "Perfusion scan was normal.", "NOTE", 2.0, 3.0)], 4.0)
        self.assertEqual(pick(s, "PERFUSION_SCAN")[0]["direction"], "WEAKEN")

    def test_case3_followup_not_weaken_past(self):
        s = run([Doc("n0", "Pulmonary embolism was diagnosed one month ago and she is currently receiving apixaban.", "NOTE", 30.0, 30.0),
                 Doc("r9", "Follow-up CTPA after three months of anticoagulation showed no pulmonary embolism.", "CTPA_REPORT", 90.0, 91.0)], 95.0,
                [Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0)])
        self.assertEqual([r["direction"] for r in pick(s, doc="r9")], ["NOT_APPLICABLE"])

    def test_case4_5_order_and_time(self):
        s = run([Doc("o", "CTPA was ordered to rule out pulmonary embolism.", "NOTE", 1.0, 1.0)], 1.5)
        self.assertFalse([r for r in s["results"] if r["direction"] in R.DIRECTIONAL])
        self.assertIn("NO_RESULT_YET", [r["abstain_reason"] for r in s["results"]])
        docs = [Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", POS, "CTPA_REPORT", 2.0, 4.0), Doc("r2", NEG, "CTPA_REPORT", 2.0, 7.0, supersedes="r")]
        self.assertEqual(run(docs, 3.0)["hypotheses"]["Pulmonary embolism|E1"]["support"], [])
        self.assertEqual(run(docs, 6.9)["hypotheses"]["Pulmonary embolism|E1"]["support"], ["PE-CTPA-POSITIVE"])
        h = run(docs, 7.0)["hypotheses"]["Pulmonary embolism|E1"]
        self.assertEqual((h["support"], h["weaken"]), ([], ["PE-CTPA-NEGATIVE"]))

    def test_case6_mixed(self):
        s = run([Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", "No deep vein thrombosis was seen on ultrasound, but CTPA showed segmental pulmonary embolism.", "NOTE", 2.0, 4.0)], 5.0)
        self.assertEqual(pick(s, "DVT")[0]["assertion"], "NEGATED")
        self.assertEqual(pick(s, doc="r")[0]["direction"], "SUPPORT")

    def test_case8_unsupported(self):
        s = run([Doc("e", "Echocardiography showed a pericardial effusion.", "NOTE", 0.0, 1.0)], 2.0, [cur(), Hypothesis("h2", "Aortic dissection", "DX:Aortic dissection", 0.0, episode_id="E9")])
        self.assertTrue(all(r["abstain_reason"] == "HYPOTHESIS_NOT_IN_GRAPH" for r in s["results"] if r["episode_id"] == "E9"))
        self.assertIn("CONCEPT_NOT_SUPPORTED", [r["abstain_reason"] for r in s["results"]])
        self.assertFalse([r for r in s["results"] if r["direction"] in R.DIRECTIONAL])

    def test_case10_no_invented_context(self):
        s = run([Doc("r", POS, "CTPA_REPORT", 2.0, 4.0), Doc("l", "D-dimer was normal.", "LAB", 1.5, 2.0)], 5.0)
        self.assertFalse([r for r in s["results"] if r["direction"] in R.DIRECTIONAL])
        r = pick(s, doc="r")[0]
        self.assertEqual((r["direction"], sorted(r["missing_context"])), ("INSUFFICIENT_EVIDENCE", ["clinical_phase", "pretest"]))

    def test_recurrence_separated(self):
        hy = [Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), Hypothesis("h3", "Pulmonary embolism", PE, 200.0, episode_id="E2", kind="RECURRENCE", target_time=200.0)]
        s = run([Doc("n2", "Recurrent pulmonary embolism is suspected.", "NOTE", 200.0, 200.0), Doc("r2", NEG, "CTPA_REPORT", 201.0, 202.0)], 203.0, hy)
        self.assertEqual(pick(s, doc="r2", episode="E0")[0]["direction"], "NOT_APPLICABLE")
        self.assertEqual(pick(s, doc="r2", episode="E2")[0]["direction"], "UNCERTAIN")

    def test_instability_out_of_scope(self):
        s = run([Doc("n", "Pulmonary embolism is suspected; high clinical probability. The patient is in obstructive shock.", "NOTE", 0.5, 1.0), Doc("r", POS, "CTPA_REPORT", 2.0, 4.0)], 5.0)
        self.assertEqual(pick(s, doc="r")[0]["direction"], "NOT_APPLICABLE")

    def test_case51_type_still_blocked(self):
        s = run([Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("l", "After one month of follow-up the D-dimer was within normal limits on apixaban.", "LAB", 30.0, 31.0)], 32.0)
        self.assertEqual(pick(s, "DDIMER")[0]["direction"], "NOT_APPLICABLE")

    def test_explanation_fields(self):
        r = pick(run([Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", POS, "CTPA_REPORT", 2.0, 4.0)], 5.0), doc="r")[0]
        t = R.explain(r)
        for k in ("[진단 가설]", "[근거 문장]", "[연결 개념]", "[그래프 경로]", "[적용 조건]", "[출처]", "[판단] SUPPORT"):
            self.assertIn(k, t)
        self.assertFalse([k for k in r if "prob" in k.lower() or "score" in k.lower()])


class GraphContribution(unittest.TestCase):
    DOCS = [Doc("n", SUSP, "NOTE", 0.5, 1.0), Doc("r", POS, "CTPA_REPORT", 2.0, 4.0)]

    def d(self, g):
        return pick(run(self.DOCS, 5.0, engine=R.Engine(g)), doc="r")[0]

    def test_removing_edge_removes_judgement(self):
        self.assertEqual(self.d(EvidenceGraph())["direction"], "SUPPORT")
        r = self.d(EvidenceGraph(disabled_relations=["PE-CTPA-POSITIVE"]))
        self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "NO_VERIFIED_GRAPH_RELATION"))
        self.assertEqual(self.d(EvidenceGraph(disabled_relations=["PE-CTPA-NEGATIVE"]))["direction"], "SUPPORT")   # 무관한 간선은 영향 없음

    def test_without_base_graph_hypothesis_unsupported(self):
        self.assertEqual(self.d(EvidenceGraph(use_base=False))["abstain_reason"], "HYPOTHESIS_NOT_IN_GRAPH")

    def test_base_associations_never_direction(self):
        s = run([Doc("n", SUSP + " The patient has dyspnea and tachycardia.", "NOTE", 0.5, 1.0)], 2.0)
        hp = [r for r in s["results"] if r["concept"].startswith("HP:")]
        self.assertTrue(hp and all(r["direction"] == "ABSTAIN" and not any(e["used_for_direction"] for e in r["graph_context_edges"]) for r in hp))


if __name__ == "__main__":
    unittest.main()
