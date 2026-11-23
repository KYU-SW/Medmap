"""입력 유형별 End-to-End 검사(합성 문장). 기대값은 카탈로그 관계와 프로토콜에서 정함 — 코드 출력에 맞추지 않음. 임상 정확도 아님."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from hybrid2 import lexicon as LX, parser as PS, pipeline as P, relations as RL  # noqa: E402
from hybrid2.pipeline import CaseTimeline, Document  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, Provenance  # noqa: E402

PE = "DX:Pulmonary embolism"
CTX = {"pretest": "INTERMEDIATE", "suspected": True}


def hyp(concept=PE, label="Pulmonary embolism", status=DxStatus.WORKING_DIAGNOSIS):
    return DiagnosisAssertion("h", "c", label, status, AssertedBy.SIMULATED, 0.0, Provenance("t", "t", DataClass.SYNTHETIC), concept_id=concept)


def run(text, doc="CTPA_REPORT", ctx=CTX, h=None, concept=None):
    recs = P.extract(text, doc)
    if concept:
        recs = [r for r in recs if r["concept"] == concept]
    return [P.assess_record(r, h or hyp(), ctx) for r in recs]


def one(text, **k):
    rs = run(text, concept=k.pop("concept", "PE_DIAGNOSIS"), **k)
    assert len(rs) == 1, rs
    return rs[0]


class Expressions(unittest.TestCase):
    """같은 병명이라도 다섯 표현을 다르게 처리."""

    def test_no_evidence(self):
        r = one("No evidence of pulmonary embolism.")
        self.assertEqual((r["assertion"], r["direction"], r["relation_id"]), ("NEGATED", "WEAKEN", "PE-CTPA-NEGATIVE"))

    def test_possible(self):
        r = one("Possible pulmonary embolism.")
        self.assertEqual((r["assertion"], r["direction"]), ("UNCERTAIN", "ABSTAIN"))

    def test_history(self):
        r = one("History of pulmonary embolism.", doc="NOTE")
        self.assertEqual((r["assertion"], r["direction"], r["relation"]), ("HISTORICAL", "INSUFFICIENT_EVIDENCE", "ASSOCIATED_WITH"))

    def test_rule_out(self):
        r = one("Rule out pulmonary embolism.")
        self.assertEqual((r["assertion"], r["direction"], r["abstain_reason"]), ("PURPOSE_OR_DIFFERENTIAL", "ABSTAIN", "TEST_PURPOSE_NOT_RESULT"))

    def test_confirmed_without_test_source(self):
        r = one("Pulmonary embolism confirmed.", doc="NOTE")          # 어떤 검사인지 없음 → 방향 없음, 의사 진술로 확인 필요
        self.assertEqual((r["assertion"], r["direction"], r["abstain_reason"]), ("PRESENT", "ABSTAIN", "DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE"))

    def test_indication_section(self):
        self.assertEqual(one("INDICATION: Shortness of breath, pulmonary embolism?")["abstain_reason"], "TEST_PURPOSE_NOT_RESULT")

    def test_ruled_out_vs_rule_out(self):
        self.assertEqual(one("Pulmonary embolism was ruled out.")["assertion"], "NEGATED")
        self.assertEqual(one("Pulmonary embolism cannot be ruled out.")["assertion"], "UNCERTAIN")

    def test_family(self):
        self.assertEqual(one("His mother had a pulmonary embolism.", doc="NOTE")["abstain_reason"], "OTHER_PERSON_NOT_PATIENT")

    def test_conditional(self):
        self.assertEqual(one("If pulmonary embolism is present, treat.", doc="NOTE")["abstain_reason"], "CONDITIONAL_STATEMENT")


class Types(unittest.TestCase):
    """입력 유형 1~12."""

    def test_1_positive_with_level_and_context(self):
        r = one("IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries.")
        self.assertEqual((r["direction"], r["relation_id"]), ("SUPPORT", "PE-CTPA-POSITIVE"))
        self.assertTrue(r["sources"] and r["sources"][0]["quote"] and r["physician_confirmation_needed"])

    def test_1b_level_missing_no_support(self):
        r = one("Acute pulmonary embolism.")
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["level"]))

    def test_1c_subsegmental_uncertain(self):
        self.assertEqual(one("Isolated subsegmental pulmonary embolism.")["direction"], "UNCERTAIN")

    def test_1d_low_pretest_outside_scope(self):
        self.assertEqual(one("Segmental pulmonary embolism.", ctx={"pretest": "LOW"})["direction"], "UNCERTAIN")

    def test_example_filling_defect_not_support(self):              # 사용자 예시: 지침이 CTPA 충만 결손을 PE 소견으로 정의하는 문구 미확인
        r = one("The CT report describes a filling defect in a pulmonary artery.", concept="FILLING_DEFECT")
        self.assertEqual((r["direction"], r["relation_id"]), ("UNCERTAIN", "PE-FILLING-DEFECT"))
        self.assertEqual(r["graph_node"], "CONCEPT:ctpa_filling_defect")

    def test_2_negative_needs_pretest(self):
        self.assertEqual(one("No evidence of pulmonary embolism.", ctx={})["direction"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(one("No evidence of pulmonary embolism.", ctx={"pretest": "HIGH"})["direction"], "UNCERTAIN")
        self.assertEqual(one("No PE.")["direction"], "WEAKEN")          # CTPA 맥락 약어

    def test_2b_partial_negative_not_weaken(self):
        self.assertEqual(one("No central pulmonary embolism.")["abstain_reason"], "PARTIAL_NEGATIVE_REPORT")

    def test_3_uncertain(self):
        self.assertEqual(one("Limited study; pulmonary embolism cannot be excluded.")["direction"], "ABSTAIN")

    def test_4_purpose(self):
        self.assertEqual(one("CTPA to evaluate for pulmonary embolism.", doc="NOTE")["abstain_reason"], "TEST_PURPOSE_NOT_RESULT")

    def test_5_history_not_current(self):
        self.assertNotIn(one("Prior pulmonary embolism in 2019.", doc="NOTE")["direction"], ("SUPPORT", "WEAKEN"))

    def test_6_order_is_not_result(self):
        r = one("CTPA ordered for pulmonary embolism.", doc="NOTE")
        self.assertEqual(r["abstain_reason"], "NO_RESULT_YET")

    def test_7_pending(self):
        self.assertEqual(one("CTPA result is pending for pulmonary embolism.", doc="NOTE")["abstain_reason"], "NO_RESULT_YET")

    def test_10_hypothesis_not_in_graph(self):
        r = one("No evidence of pulmonary embolism.", h=hyp("DX:Pneumonia", "Pneumonia"))
        self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "HYPOTHESIS_NOT_IN_GRAPH"))

    def test_11_finding_without_verified_relation(self):
        r = one("The patient has dyspnea.", doc="NOTE", concept="HP:0002094")
        self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION"))
        self.assertTrue(r["graph_edges_shown"] and not any(x["used_for_direction"] for x in r["graph_edges_shown"]))

    def test_12_one_finding_many_hypotheses(self):                 # 같은 소견: PE 관계만 검증, 다른 가설은 약화·지지 아님
        for t in ("No evidence of pulmonary embolism.", "Segmental pulmonary embolism."):
            self.assertIn(one(t)["direction"], ("WEAKEN", "SUPPORT"))
            r = one(t, h=hyp("DX:Pericarditis", "Pericarditis"))
            self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "NO_VERIFIED_RELATION_FOR_HYPOTHESIS"))


class Labs(unittest.TestCase):
    def d(self, t, **k):
        return one(t, doc="LAB", concept="DDIMER", **k)

    def test_normal(self):
        self.assertEqual(self.d("D-dimer was normal.")["direction"], "WEAKEN")
        self.assertEqual(self.d("D-dimer was normal.", ctx={"pretest": "HIGH"})["direction"], "NOT_APPLICABLE")
        self.assertEqual(self.d("D-dimer was normal.", ctx={})["direction"], "INSUFFICIENT_EVIDENCE")

    def test_elevated_not_support(self):
        r = self.d("D-dimer was elevated.")
        self.assertEqual((r["direction"], r["relation_id"]), ("NO_CLEAR_EFFECT", "PE-DDIMER-ELEVATED"))

    def test_other_analyte_words_not_used(self):                     # 공개 표본 1차에서 발견한 잘못된 약화 사례 유형(문장은 새로 작성)
        self.assertEqual(self.d("D-dimer 6.27 (NV < 0.5) and ferritin in normal range.")["abstain_reason"], "VALUE_WITHOUT_ASSAY_INTERPRETATION")
        self.assertEqual(self.d("A slightly elevated D-dimer, otherwise blood tests were within normal range.")["direction"], "NO_CLEAR_EFFECT")
        self.assertEqual(self.d("Blood tests normal, elevated D-dimer levels (>700).")["direction"], "NO_CLEAR_EFFECT")

    def test_value_only_abstains(self):
        self.assertEqual(self.d("D-dimer 620 ng/mL.")["abstain_reason"], "VALUE_WITHOUT_ASSAY_INTERPRETATION")

    def test_dvt_needs_proximal_ultrasound(self):
        self.assertEqual(one("Compression ultrasound shows femoral deep vein thrombosis.", doc="NOTE", concept="DVT")["direction"], "SUPPORT")
        self.assertEqual(one("Compression ultrasound shows calf deep vein thrombosis.", doc="NOTE", concept="DVT")["direction"], "ABSTAIN")
        self.assertEqual(one("Deep vein thrombosis in the femoral vein.", doc="NOTE", concept="DVT")["direction"], "ABSTAIN")
        self.assertEqual(one("Compression ultrasound shows femoral deep vein thrombosis.", doc="NOTE", concept="DVT", ctx={})["direction"], "INSUFFICIENT_EVIDENCE")

    def test_perfusion(self):
        self.assertEqual(one("Perfusion scan was normal.", doc="NOTE", concept="PERFUSION_SCAN")["direction"], "WEAKEN")


class Linking(unittest.TestCase):
    def test_unknown_not_forced(self):
        self.assertEqual(P.extract("The zorblatt was unremarkable.", "NOTE"), [])

    def test_ambiguous(self):
        recs = P.extract("Embolism was noted.", "NOTE")
        self.assertEqual([r["link_status"] for r in recs], ["AMBIGUOUS"])
        self.assertEqual(P.assess_record(recs[0], hyp(), CTX)["abstain_reason"], "AMBIGUOUS_CONCEPT")

    def test_pe_abbreviation_needs_ctpa_context(self):
        self.assertEqual(P.extract("PE was normal.", "NOTE")[0]["link_status"], "AMBIGUOUS")
        self.assertEqual(P.extract("No PE.", "CTPA_REPORT")[0]["concept"], "PE_DIAGNOSIS")

    def test_hpo_supported_vs_not_in_graph(self):
        r = P.extract("He has hemoptysis.", "NOTE")[0]
        self.assertEqual((r["concept"], r["graph_node"]), ("HP:0002105", "HP:0002105"))
        r = P.extract("She has pancreatitis.", "NOTE")[0]
        self.assertEqual(r["link_status"], "LINKED")
        self.assertEqual(r["graph_node"], "")                              # HPO 에는 있고 그래프에는 없음

    def test_modifier_terms_not_findings(self):                      # 공개 표본 1차에서 발견: 'left', 'occasional' 이 HPO 수식어로 연결됨
        self.assertEqual(P.extract("Occasional pain on the left side, mild.", "NOTE")[0]["surface"].lower(), "pain")
        self.assertEqual(len(P.extract("Occasional pain on the left side, mild.", "NOTE")), 1)

    def test_v3b_conflict_not_silently_resolved(self):                 # EXP-04 에서 관찰: v3b 가 'ruling out' 을 ACUTE_POS 로 분류
        rec = {"link_status": "LINKED", "assertion": PS.NEGATED, "concept": "PE_DIAGNOSIS", "text": "x", "sentence": "Acute pulmonary embolism.", "ctpa_context": True, "surface": "x"}
        self.assertEqual(P.finding_state(rec)["reason"], "EXTRACTOR_CONFLICT")


class Catalog(unittest.TestCase):
    def test_all_relations_have_source_and_scope(self):
        c = RL.load()
        self.assertTrue(c["relations"])
        for r in c["relations"]:
            self.assertTrue(r["evidence"] and r["applicability"], r["id"])

    def _bad(self, f):
        c = copy.deepcopy(RL.load())
        f(c)
        with self.assertRaises(RL.CatalogError):
            RL.validate(c)

    def test_missing_quote_rejected(self):
        self._bad(lambda c: c["relations"][0]["evidence"][0].update(quote=""))

    def test_association_cannot_output_direction(self):
        self._bad(lambda c: c["relations"][-1]["by_context"].__setitem__(0, {"when": {}, "direction": "SUPPORT"}))

    def test_unverified_rejected(self):
        self._bad(lambda c: c["relations"][0].update(verification="ASSUMED"))

    def test_graph_never_gives_direction(self):                        # 그래프만 있는 소견은 관계 카탈로그 없이는 방향 없음
        for hp in ("HP:0002094", "HP:0002105", "HP:0001649", "HP:0100749"):
            self.assertFalse(RL.lookup(RL.load(), PE, hp))


class Time(unittest.TestCase):
    def setUp(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h1", "Pulmonary embolism", PE, 0.0)
        for e, a in (("ORDER", 1.0), ("COLLECT", 2.0), ("RESULT", 4.0), ("CORRECT", 7.0)):
            t.add_test_event("ctpa", e, a)
        t.add_document(Document("o", "CTPA was ordered to rule out pulmonary embolism.", "NOTE", 1.0, 1.0))
        t.add_document(Document("r1", "IMPRESSION: No evidence of pulmonary embolism.", "CTPA_REPORT", 2.0, 4.0))
        t.add_document(Document("r2", "IMPRESSION: Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 2.0, 7.0, supersedes="r1"))
        self.t = t

    def s(self, at):
        return self.t.state(at, CTX)

    def test_order_gives_no_direction(self):
        s = self.s(1.5)
        self.assertEqual((s["hypotheses"]["Pulmonary embolism"]["support"], s["hypotheses"]["Pulmonary embolism"]["weaken"], s["tests"]["ctpa"]), ([], [], "ORDERED"))

    def test_pending_no_result_before_available(self):               # 시행(2) 후 결과 이용(4) 전에는 판독이 쓰이지 않음
        s = self.s(3.0)
        self.assertEqual((s["visible_documents"], s["tests"]["ctpa"]), (["o"], "PENDING"))
        self.assertFalse(s["hypotheses"]["Pulmonary embolism"]["review_candidate"])

    def test_new_result(self):
        h = self.s(4.0)["hypotheses"]["Pulmonary embolism"]
        self.assertEqual((h["weaken"], h["review_candidate"]), (["PE-CTPA-NEGATIVE"], True))

    def test_correction_not_retroactive(self):
        self.assertEqual(self.s(6.9)["hypotheses"]["Pulmonary embolism"]["weaken"], ["PE-CTPA-NEGATIVE"])
        h = self.s(7.0)["hypotheses"]["Pulmonary embolism"]
        self.assertEqual((h["weaken"], h["support"]), ([], ["PE-CTPA-POSITIVE"]))

    def test_hypothesis_change(self):
        self.t.set_hypothesis("h2", "Pericarditis", "DX:Pericarditis", 5.0, supersedes="h1")
        self.assertEqual(list(self.s(4.0)["hypotheses"]), ["Pulmonary embolism"])
        s = self.s(5.0)
        self.assertEqual(list(s["hypotheses"]), ["Pericarditis"])
        self.assertEqual(s["hypotheses"]["Pericarditis"]["weaken"], [])     # PE 약화가 심낭염 근거가 되지 않음

    def test_engine_cross_check(self):                               # EXP-03 엔진과 같은 공개 집합·같은 방향
        ra = P.T1 and __import__("reassess")
        tl = ra.Timeline("c")
        tl.set_hypothesis(ra.HypothesisEvent("h1", "c", PE, 0.0))
        tl.add(ra.Evidence("r1", "c", "IMAGING_REPORT", "s", "s", 2.0, 4.0, 4.0, "NEGATIVE", concept=ra.CTPA_CONCEPT, pe_class="NEGATIVE"))
        tl.add(ra.Evidence("r2", "c", "IMAGING_REPORT", "s", "s", 2.0, 7.0, 7.0, "POSITIVE", concept=ra.CTPA_CONCEPT, pe_class="ACUTE_POS", supersedes="r1"))
        want = {3.0: "INSUFFICIENT", 4.0: "CONFLICT", 7.0: "SUPPORTED"}
        got = {3.0: [], 4.0: ["PE-CTPA-NEGATIVE"], 7.0: ["PE-CTPA-POSITIVE"]}
        for at in want:
            self.assertEqual(ra.assess(tl, at).summary, want[at])
            h = self.s(at)["hypotheses"]["Pulmonary embolism"]
            self.assertEqual(h["weaken"] + h["support"], got[at])


class OutputShape(unittest.TestCase):
    def test_required_fields_and_no_probability(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h", "Pulmonary embolism", PE, 0.0)
        t.add_document(Document("r", "No evidence of pulmonary embolism.", "CTPA_REPORT", 1.0, 2.0))
        r = t.state(3.0, CTX)["results"][0]
        for k in ("input_sentence", "extracted_surface", "standard_codes", "hypothesis", "direction", "judgeable", "relation", "sources", "applicability", "uncertainty", "abstain_reason", "observed_at", "available_at", "physician_confirmation_needed"):
            self.assertIn(k, r)
        self.assertFalse([k for k in r if "prob" in k.lower() or "score" in k.lower()])
        self.assertEqual((r["observed_at"], r["available_at"]), (1.0, 2.0))
        json.dumps(r)


if __name__ == "__main__":
    unittest.main()
