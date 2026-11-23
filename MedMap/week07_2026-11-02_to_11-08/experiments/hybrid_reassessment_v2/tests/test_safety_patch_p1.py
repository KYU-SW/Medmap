"""Safety Patch P1 회귀 검사(새로 작성한 합성 문장). 기대값은 지침 적용 범위·작업 요구에서 정함. 임상 정확도 아님."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from hybrid2_p1 import clinical_context as CC, pipeline as P, relations as RL  # noqa: E402
from hybrid2_p1.pipeline import CaseTimeline, Document  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, Provenance  # noqa: E402

PE = "DX:Pulmonary embolism"
CTX = {"pretest": "INTERMEDIATE", "suspected": True}


def hyp(status=DxStatus.WORKING_DIAGNOSIS):
    return DiagnosisAssertion("h", "c", "Pulmonary embolism", status, AssertedBy.SIMULATED, 0.0, Provenance("t", "t", DataClass.SYNTHETIC), concept_id=PE)


def rec(text, concept, doc="NOTE"):
    return [r for r in P.extract(text, doc) if r["concept"] == concept]


def out(text, concept="DDIMER", ctx=CTX, doc="NOTE", h=None):
    rs = [P.assess_record(r, h or hyp(), ctx) for r in rec(text, concept, doc)]
    assert len(rs) == 1, (text, rs)
    return rs[0]


def asg(text, concept="PE_DIAGNOSIS", doc="NOTE"):
    return [r["assertion"] for r in rec(text, concept, doc)]


class DdimerClinicalPhase(unittest.TestCase):
    """A·B·C: 치료·추적의 정상 D-dimer 는 약화 금지, 맥락 부족은 보류, 의심 평가는 유지."""

    def _na(self, text, phase, **k):
        r = out(text, **k)
        self.assertEqual((r["direction"], r["clinical_context"]["phase"]), ("NOT_APPLICABLE", phase), text)
        self.assertEqual(r["relation_id"], "PE-DDIMER-NORMAL")
        return r

    def test_under_treatment_with_followup(self):
        r = self._na("At three months of follow-up her D-dimer was normal on rivaroxaban.", CC.UNDER_TREATMENT)
        self.assertTrue(r["clinical_context"]["context_conflict"])        # 입력은 의심, 문장은 치료 → 문장 우선, 충돌 표시

    def test_under_treatment_with_pe_mention(self):
        self._na("On apixaban for pulmonary embolism, the D-dimer was within normal limits.", CC.UNDER_TREATMENT)

    def test_post_treatment(self):
        self._na("D-dimer was normal after completion of anticoagulation for pulmonary embolism.", CC.POST_TREATMENT)

    def test_followup_after_pe(self):
        self._na("Follow-up D-dimer was normal after pulmonary embolism.", CC.POST_TREATMENT)

    def test_confirmed_in_sentence(self):
        self._na("She was diagnosed with pulmonary embolism, and D-dimer was normal.", CC.CONFIRMED)

    def test_confirmed_hypothesis_status_not_contradicted(self):
        r = self._na("D-dimer was normal.", CC.CONFIRMED, h=hyp(DxStatus.CONFIRMED_DIAGNOSIS))
        self.assertEqual(r["clinical_context"]["basis"], "HYPOTHESIS_STATUS")

    def test_input_phase(self):
        self._na("D-dimer was normal.", CC.UNDER_TREATMENT, ctx={"pretest": "LOW", "clinical_phase": CC.UNDER_TREATMENT})

    def test_treatment_phase_decided_without_pretest(self):             # 범위 밖이면 임상 확률을 더 묻지 않고, 이유를 함께 표시
        r = out("D-dimer was normal.", ctx={"clinical_phase": CC.UNDER_TREATMENT})
        self.assertEqual((r["direction"], r["missing_context"]), ("NOT_APPLICABLE", []))
        self.assertTrue(any("진단 알고리즘" in x for x in r["uncertainty"]))

    def test_recurrence_not_weaken(self):
        r = out("D-dimer was normal in the evaluation of recurrent pulmonary embolism.")
        self.assertEqual((r["direction"], r["clinical_context"]["phase"]), ("UNCERTAIN", CC.RECURRENCE))

    def test_no_recurrence_is_not_recurrence_evaluation(self):
        self.assertNotEqual(CC.sentence_signals("No recurrent pulmonary embolism at follow-up.")["phase"], CC.RECURRENCE)

    def _hold(self, text, ctx=CTX):
        r = out(text, ctx=ctx)
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["clinical_phase"]), text)
        self.assertEqual(r["clinical_context"]["phase"], CC.UNKNOWN)

    def test_followup_without_more_context_holds(self):
        self._hold("D-dimer was normal at follow-up.")

    def test_anticoagulant_without_target_holds(self):                  # 항응고 이유를 모르면 치료 단계로 단정하지 않음
        self._hold("On warfarin, D-dimer was normal.")

    def test_phase_not_stated_holds(self):
        self._hold("D-dimer was normal.", ctx={"pretest": "LOW"})

    def test_suspected_evaluation_keeps_relation(self):                 # C: 불필요한 차단 금지
        self.assertEqual(out("D-dimer was normal.")["direction"], "WEAKEN")
        self.assertEqual(out("D-dimer was normal.", ctx={"pretest": "LOW", "clinical_phase": CC.SUSPECTED})["direction"], "WEAKEN")
        self.assertEqual(out("D-dimer was normal, and the patient was not on anticoagulation.")["direction"], "WEAKEN")
        self.assertEqual(out("D-dimer was normal before starting heparin.")["direction"], "WEAKEN")

    def test_weaken_states_unverified_assay(self):
        self.assertTrue(any("검사법" in x for x in out("D-dimer was normal.")["uncertainty"]))

    def test_high_pretest_and_point_of_care(self):
        self.assertEqual(out("D-dimer was normal.", ctx={"pretest": "HIGH", "suspected": True})["direction"], "NOT_APPLICABLE")
        self.assertEqual(out("Point-of-care D-dimer was normal.")["direction"], "NOT_APPLICABLE")
        self.assertEqual(out("Point-of-care D-dimer was normal.", ctx={"pretest": "LOW", "suspected": True})["direction"], "WEAKEN")
        self.assertEqual(out("Point-of-care ultrasound was done; D-dimer was normal.")["direction"], "WEAKEN")   # 다른 검사의 현장 검사 표현

    def test_elevated_never_support_in_any_phase(self):
        for t in ("D-dimer was elevated.", "On apixaban for pulmonary embolism, D-dimer was elevated.", "D-dimer was elevated in the evaluation of recurrent pulmonary embolism."):
            self.assertEqual(out(t)["direction"], "NO_CLEAR_EFFECT", t)

    def test_values_do_not_set_phase(self):
        self.assertIsNone(CC.sentence_signals("D-dimer 180 ng/mL (normal < 500).")["phase"])
        self.assertIsNone(CC.sentence_signals("D-dimer 9000 ng/mL.")["phase"])

    def test_no_probability_field(self):
        cc = out("D-dimer was normal.")["clinical_context"]
        self.assertFalse([k for k in cc if "prob" in k.lower() or "score" in k.lower()])

    def test_catalog_valid_and_source_quotes(self):
        rel = RL.lookup(RL.load(), PE, "DDIMER_NORMAL")
        self.assertEqual(rel["verification"], "SOURCE_TEXT_CHECKED")
        self.assertTrue(all(e["quote"] for e in rel["evidence"]))
        self.assertEqual(RL.lookup(RL.load(), PE, "DDIMER_ELEVATED")["relation"], "EVALUATES_HYPOTHESIS")


class AssertionPolarity(unittest.TestCase):
    """D: 확인·배제·음성을 반대로 읽지 않음."""

    def test_confirmed_after_other_negated_item(self):
        self.assertEqual(asg("Given absence of contraindications to surgery, and a confirmed diagnosis of severe pulmonary embolism, thrombolysis was started."), ["PRESENT"])

    def test_list_negation_kept(self):
        self.assertEqual(asg("No fever, cough, or pulmonary embolism."), ["NEGATED"])
        self.assertEqual(asg("No fever, cough and pulmonary embolism."), ["NEGATED"])
        self.assertEqual(asg("No evidence of pulmonary embolism."), ["NEGATED"])

    def test_negation_of_confirmed_kept(self):
        self.assertEqual(asg("Without confirmed pulmonary embolism."), ["NEGATED"])
        self.assertEqual(asg("No confirmed infection or pulmonary embolism."), ["NEGATED"])

    def test_unclear_scope_held(self):
        self.assertEqual(asg("No signs of infection in the surgical wound, and the large pulmonary embolism remained."), ["UNCERTAIN"])

    def test_excluded_with_adverb(self):
        for t in ("Pulmonary embolism was again excluded.", "Pulmonary embolism was subsequently ruled out.", "Pulmonary embolism had been excluded."):
            self.assertEqual(asg(t), ["NEGATED"], t)

    def test_excluded_not_flipped_by_negation(self):
        self.assertEqual(asg("Pulmonary embolism cannot be excluded."), ["UNCERTAIN"])
        self.assertEqual(asg("Pulmonary embolism was not excluded."), ["UNCERTAIN"])
        self.assertEqual(asg("Pulmonary embolism was confirmed."), ["PRESENT"])

    def test_previously_excluded_is_not_current_or_history(self):
        for t in ("Pulmonary embolism was previously excluded.", "Pulmonary embolism had previously been ruled out.", "Previously excluded pulmonary embolism."):
            self.assertEqual(asg(t), ["UNCERTAIN"], t)
            r = out(t, concept="PE_DIAGNOSIS")
            self.assertEqual(r["direction"], "ABSTAIN", t)
            self.assertNotEqual(r["relation_id"], "PE-HISTORY-VTE")

    def test_scan_negative(self):
        self.assertEqual(asg("Deep vein thrombosis (DVT) scan was negative.", "DVT"), ["NEGATED", "NEGATED"])
        self.assertEqual(asg("DVT ultrasound was normal.", "DVT"), ["NEGATED"])

    def test_scan_positive_not_negated(self):
        self.assertEqual(asg("Deep vein thrombosis (DVT) scan was positive.", "DVT"), ["PRESENT", "PRESENT"])

    def test_v3b_conflict_guard_kept(self):                             # v3b 가 반대면 음성 판독도 기권
        r = out("Chest CTPA ruled out thromboembolic pulmonary embolism.", concept="PE_DIAGNOSIS")
        self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "EXTRACTOR_CONFLICT"))


class TestStatus(unittest.TestCase):
    """E: 주문·대기·완료 구분."""

    def test_result_after_order(self):
        self.assertEqual(asg("A D-dimer was requested and returned elevated.", "DDIMER"), ["PRESENT"])
        self.assertEqual(asg("CTPA was ordered and showed pulmonary embolism."), ["PRESENT"])

    def test_order_without_result(self):
        for t in ("A D-dimer was requested.", "D-dimer was ordered to show the trend.", "A decision was made to proceed with D-dimer testing."):
            self.assertEqual(asg(t, "DDIMER"), ["ORDERED_NOT_RESULTED"], t)
            self.assertEqual(out(t)["abstain_reason"], "NO_RESULT_YET", t)

    def test_decision_then_result_is_result(self):                      # 패치 후 재생에서 발견한 부작용
        self.assertEqual(asg("A decision was made to perform CTPA, which ruled out a pulmonary embolus."), ["NEGATED"])
        self.assertEqual(asg("A decision was made to perform CTPA which confirmed pulmonary embolism."), ["PRESENT"])

    def test_decision_to_proceed_ctpa_not_positive_report(self):
        r = out("A decision was made to proceed with CTPA for pulmonary embolism.", concept="PE_DIAGNOSIS")
        self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "NO_RESULT_YET"))

    def test_pending_kept_over_result_word(self):
        self.assertEqual(asg("CTPA for pulmonary embolism is pending.", "PE_DIAGNOSIS"), ["RESULT_PENDING"])

    def test_purpose_vs_confirmed(self):
        for t in ("CTPA was performed to confirm pulmonary embolism.", "CTPA was performed to investigate pulmonary embolism."):
            r = out(t, concept="PE_DIAGNOSIS")
            self.assertEqual((r["assertion"], r["abstain_reason"]), ("PURPOSE_OR_DIFFERENTIAL", "TEST_PURPOSE_NOT_RESULT"), t)


class AbbreviationLegend(unittest.TestCase):
    """약어 풀이만 있는 CTPA 는 검사 근거가 아님(패치 후 재생에서 발견한 부작용)."""

    def test_legend_gives_no_ctpa_context(self):
        for t in ("CTPA: computed tomography pulmonary angiography Owing to shock and a confirmed diagnosis of segmental pulmonary embolism, thrombolysis was started.",
                  "CTPA, computed tomography pulmonary angiography; segmental pulmonary embolism was treated."):
            r = out(t, concept="PE_DIAGNOSIS")
            self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE"), t)

    def test_real_study_keeps_context(self):
        r = out("CTPA revealed segmental pulmonary embolism.", concept="PE_DIAGNOSIS")
        self.assertEqual((r["direction"], r["relation_id"]), ("SUPPORT", "PE-CTPA-POSITIVE"))
        self.assertEqual(out("Chest CTPA, which was ordered urgently, revealed segmental pulmonary embolism.", concept="PE_DIAGNOSIS")["direction"], "SUPPORT")


class CaseTimelinePhase(unittest.TestCase):
    """F·G: 공개된 문서만 근거, 소급 없음, 출처·시간 유지."""

    def t(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h1", "Pulmonary embolism", PE, 0.0)
        return t

    def dd(self, s):
        return [r for r in s["results"] if r["concept"] == "DDIMER"][0]

    def test_positive_ctpa_then_normal_ddimer(self):
        t = self.t()
        t.add_document(Document("r", "IMPRESSION: Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 1.0, 2.0))
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 9.0, 10.0))
        s = t.state(11.0, CTX)
        self.assertEqual(self.dd(s)["direction"], "NOT_APPLICABLE")
        self.assertEqual(s["hypotheses"]["Pulmonary embolism"]["weaken"], [])
        self.assertEqual(self.dd(s)["clinical_context"]["basis"], "PRIOR_VISIBLE_DOCUMENT")

    def test_result_available_later_not_retroactive(self):              # D-dimer 이후 공개된 양성 판독은 그 시점 판단을 바꾸지 않음
        t = self.t()
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 1.0, 2.0))
        t.add_document(Document("r", "IMPRESSION: Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 3.0, 5.0))
        self.assertEqual(self.dd(t.state(3.0, CTX))["direction"], "WEAKEN")
        self.assertEqual(self.dd(t.state(6.0, CTX))["direction"], "WEAKEN")

    def test_unavailable_document_not_used(self):
        t = self.t()
        t.add_document(Document("r", "Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 1.0, 8.0))
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 2.0, 3.0))
        self.assertEqual(self.dd(t.state(4.0, CTX))["direction"], "WEAKEN")
        self.assertEqual(t.state(4.0, CTX)["visible_documents"], ["d"])

    def test_corrected_report_no_longer_confirms(self):                 # 정정된 양성 판독은 확진 신호가 아님
        t = self.t()
        t.add_document(Document("r1", "Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 1.0, 2.0))
        t.add_document(Document("r2", "No evidence of pulmonary embolism.", "CTPA_REPORT", 1.0, 4.0, supersedes="r1"))
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 5.0, 6.0))
        self.assertEqual(self.dd(t.state(7.0, CTX))["direction"], "WEAKEN")

    def test_treatment_note_earlier_blocks(self):
        t = self.t()
        t.add_document(Document("n", "Started apixaban for pulmonary embolism.", "NOTE", 1.0, 2.0))
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 3.0, 4.0))
        self.assertEqual(self.dd(t.state(5.0, CTX))["clinical_context"]["phase"], CC.UNDER_TREATMENT)

    def test_source_and_time_fields_kept_when_not_applicable(self):
        t = self.t()
        t.add_document(Document("d", "At follow-up her D-dimer was normal on rivaroxaban.", "LAB", 3.0, 4.0))
        r = self.dd(t.state(5.0, CTX))
        self.assertEqual((r["direction"], r["observed_at"], r["available_at"], r["as_of"]), ("NOT_APPLICABLE", 3.0, 4.0, 5.0))
        self.assertTrue(r["sources"] and all(x["quote"] and x["url"] for x in r["sources"]))
        self.assertTrue(r["physician_confirmation_needed"] and r["uncertainty"])


if __name__ == "__main__":
    unittest.main()
