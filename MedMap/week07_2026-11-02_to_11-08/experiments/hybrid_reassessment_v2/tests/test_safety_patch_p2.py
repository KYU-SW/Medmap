"""Safety Patch P2 기준(CASE 1~12, 새로 작성한 합성 문장). 기대값은 P2 안전 정책에서 정함. 임상 정확도 아님."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from hybrid2_p2 import clinical_context as CC, evidence_conditions as EC, pipeline as P, relations as RL  # noqa: E402
from hybrid2_p2.pipeline import CaseTimeline, Document  # noqa: E402
from hybrid.schema import AssertedBy, DataClass, DiagnosisAssertion, DxStatus, Provenance  # noqa: E402

PE = "DX:Pulmonary embolism"
DIRECTIONAL = ("SUPPORT", "WEAKEN")


def rec_(v, s="RECORD"):
    return {"value": v, "source": s}


REC = {"pretest": rec_("INTERMEDIATE"), "suspected": rec_(True)}                  # 기록에서 확인된 값
REC_LOW = {"pretest": rec_("LOW"), "suspected": rec_(True)}
ASSUMED = {"pretest": "INTERMEDIATE", "suspected": True}                          # P1 공개 문장 실행 가정(출처 미지정)


def hyp(status=DxStatus.WORKING_DIAGNOSIS, label="Pulmonary embolism"):
    return DiagnosisAssertion("h", "c", label, status, AssertedBy.SIMULATED, 0.0, Provenance("t", "t", DataClass.SYNTHETIC), concept_id=PE)


def out(text, concept="DDIMER", ctx=REC, doc="NOTE", h=None):
    rs = [P.assess_record(r, h or hyp(), ctx) for r in P.extract(text, doc) if r["concept"] == concept]
    assert len(rs) == 1, (text, rs)
    return rs[0]


class Case01_ConditionsStated(unittest.TestCase):
    def test_high_sensitivity_intermediate(self):
        r = out("ELISA D-dimer was normal, below the age-adjusted cut-off.")
        self.assertEqual((r["direction"], r["relation_id"]), ("WEAKEN", "PE-DDIMER-NORMAL"))
        self.assertEqual((r["test_conditions"]["assay"], r["test_conditions"]["cutoff"]), (EC.HIGH, EC.AGE))
        self.assertEqual(r["assumed_context_used"], [])

    def test_moderate_assay_only_low(self):
        t = "Moderately sensitive D-dimer was normal, below the fixed cut-off."
        self.assertEqual(out(t, ctx=REC_LOW)["direction"], "WEAKEN")
        self.assertEqual(out(t)["direction"], "NOT_APPLICABLE")

    def test_conditions_from_lab_record(self):
        ctx = {**REC, "ddimer_assay": rec_(EC.HIGH), "ddimer_cutoff": rec_(EC.FIXED)}
        self.assertEqual(out("D-dimer was normal.", ctx=ctx)["direction"], "WEAKEN")

    def test_high_pretest_out_of_scope(self):
        self.assertEqual(out("ELISA D-dimer was normal, below the age-adjusted cut-off.", ctx={"pretest": rec_("HIGH"), "suspected": rec_(True)})["direction"], "NOT_APPLICABLE")


class Case02_ConditionsMissing(unittest.TestCase):
    def test_plain_normal_holds(self):
        r = out("D-dimer was normal.")
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["ddimer_assay", "ddimer_cutoff"]))

    def test_assay_without_cutoff_holds(self):
        self.assertEqual(out("ELISA D-dimer was normal.")["missing_context"], ["ddimer_cutoff"])

    def test_pretest_missing_holds(self):
        r = out("ELISA D-dimer was normal, below the age-adjusted cut-off.", ctx={"suspected": rec_(True)})
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["pretest"]))

    def test_value_does_not_imply_assay(self):
        self.assertIsNone(EC.ddimer_conditions("D-dimer 180 ng/mL was normal.", {})["assay"])

    def test_elevated_never_support(self):
        self.assertEqual(out("ELISA D-dimer was elevated above the age-adjusted cut-off.")["direction"], "NO_CLEAR_EFFECT")


class Case03_TreatmentDdimer(unittest.TestCase):
    def test_confirmed_hypothesis_under_treatment(self):
        r = out("ELISA D-dimer was normal on apixaban, below the age-adjusted cut-off.", h=hyp(DxStatus.CONFIRMED_DIAGNOSIS))
        self.assertEqual(r["direction"], "NOT_APPLICABLE")

    def test_case51_type_not_weaken(self):                              # 2차 51번 유형(문장 새로 작성)
        self.assertEqual(out("After two months of follow-up the D-dimer was within normal limits on rivaroxaban and aspirin.")["direction"], "NOT_APPLICABLE")


class Case04_FollowupCtpa(unittest.TestCase):
    def test_followup_ctpa_negative(self):
        r = out("Follow-up CTPA after anticoagulation showed no pulmonary embolism.", concept="PE_DIAGNOSIS", doc="CTPA_REPORT")
        self.assertNotIn(r["direction"], DIRECTIONAL)
        self.assertEqual(r["direction"], "NOT_APPLICABLE")

    def test_confirmed_hypothesis_negative_report(self):
        r = out("No evidence of pulmonary embolism.", concept="PE_DIAGNOSIS", doc="CTPA_REPORT", h=hyp(DxStatus.CONFIRMED_DIAGNOSIS))
        self.assertEqual(r["direction"], "NOT_APPLICABLE")

    def test_followup_without_target_holds(self):                       # 추적 표현만 있고 PE·치료 언급 없음
        r = out("Perfusion scan was normal at follow-up.", concept="PERFUSION_SCAN")
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["clinical_phase"]))


class Case05_FollowupPerfusion(unittest.TestCase):
    def test_after_treatment(self):
        self.assertEqual(out("Perfusion scan was normal at follow-up after treatment for pulmonary embolism.", concept="PERFUSION_SCAN")["direction"], "NOT_APPLICABLE")

    def test_confirmed_hypothesis(self):
        self.assertEqual(out("Perfusion scan was normal.", concept="PERFUSION_SCAN", h=hyp(DxStatus.CONFIRMED_DIAGNOSIS))["direction"], "NOT_APPLICABLE")

    def test_suspected_still_weakens(self):                             # 의심 평가의 기존 관계는 유지
        self.assertEqual(out("Perfusion scan was normal.", concept="PERFUSION_SCAN")["direction"], "WEAKEN")


class Case06_RecurrenceSeparate(unittest.TestCase):
    def test_recurrence_and_past_episode_differ(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h1", "Pulmonary embolism", PE, 0.0)
        t.add_document(Document("r", "IMPRESSION: No evidence of pulmonary embolism.", "CTPA_REPORT", 20.0, 21.0))
        rec_ctx = {**REC, "hypothesis_target": {"diagnosis_episode_id": "E2", "kind": "RECURRENCE", "hypothesis_target_time": 20.0}}
        past_ctx = {**REC, "hypothesis_target": {"diagnosis_episode_id": "E1", "kind": "PAST_EPISODE", "hypothesis_target_time": 2.0}}
        a = [r for r in t.state(22.0, rec_ctx)["results"] if r["concept"] == "PE_DIAGNOSIS"][0]
        b = [r for r in t.state(22.0, past_ctx)["results"] if r["concept"] == "PE_DIAGNOSIS"][0]
        self.assertEqual((a["direction"], a["clinical_context"]["phase_after_target"]), ("UNCERTAIN", CC.RECURRENCE))
        self.assertEqual(b["direction"], "NOT_APPLICABLE")
        self.assertEqual((a["hypothesis_target"]["diagnosis_episode_id"], b["hypothesis_target"]["diagnosis_episode_id"]), ("E2", "E1"))

    def test_recurrence_in_sentence(self):
        rs = [P.assess_record(r, hyp(), REC) for r in P.extract("CTPA for suspected recurrent pulmonary embolism showed no pulmonary embolism.", "CTPA_REPORT") if r["concept"] == "PE_DIAGNOSIS"]
        self.assertTrue(rs)
        self.assertFalse([r for r in rs if r["direction"] in DIRECTIONAL])      # 문장 안 'suspected' 로 두 언급 모두 불확실 → 관계 단계 전 기권


class Case07_PhaseUnknown(unittest.TestCase):
    def test_no_phase_holds(self):
        for t, c in (("Perfusion scan was normal.", "PERFUSION_SCAN"), ("No evidence of pulmonary embolism.", "PE_DIAGNOSIS")):
            r = out(t, concept=c, doc="CTPA_REPORT", ctx={"pretest": rec_("LOW")})
            self.assertEqual(r["direction"], "INSUFFICIENT_EVIDENCE", t)
            self.assertIn("clinical_phase", r["missing_context"])


class Case08_OrderOnly(unittest.TestCase):
    def test_order(self):
        for t, c in (("CTPA ordered for pulmonary embolism.", "PE_DIAGNOSIS"), ("A D-dimer was requested.", "DDIMER")):
            r = out(t, concept=c)
            self.assertEqual((r["direction"], r["abstain_reason"]), ("ABSTAIN", "NO_RESULT_YET"), t)


class Case09_10_Time(unittest.TestCase):
    def tl(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h1", "Pulmonary embolism", PE, 0.0)
        return t

    def test_late_result_only_after_available(self):
        t = self.tl()
        t.add_document(Document("d", "ELISA D-dimer was normal, below the age-adjusted cut-off.", "LAB", 1.0, 5.0))
        self.assertEqual(t.state(4.0, REC)["results"], [])
        self.assertEqual(t.state(5.0, REC)["hypotheses"]["Pulmonary embolism"]["weaken"], ["PE-DDIMER-NORMAL"])

    def test_correction_not_retroactive(self):
        t = self.tl()
        t.add_document(Document("r1", "IMPRESSION: No evidence of pulmonary embolism.", "CTPA_REPORT", 2.0, 4.0))
        t.add_document(Document("r2", "IMPRESSION: Acute pulmonary embolism in the segmental arteries.", "CTPA_REPORT", 2.0, 7.0, supersedes="r1"))
        self.assertEqual(t.state(6.9, REC)["hypotheses"]["Pulmonary embolism"]["weaken"], ["PE-CTPA-NEGATIVE"])
        h = t.state(7.0, REC)["hypotheses"]["Pulmonary embolism"]
        self.assertEqual((h["weaken"], h["support"]), ([], ["PE-CTPA-POSITIVE"]))     # 양성 판독이 스스로를 확진 단계로 만들지 않음

    def test_source_time_fields_kept(self):
        t = self.tl()
        t.add_document(Document("d", "D-dimer was normal.", "LAB", 3.0, 4.0))
        r = t.state(5.0, REC)["results"][0]
        self.assertEqual((r["observed_at"], r["available_at"], r["as_of"]), (3.0, 4.0, 5.0))
        self.assertTrue(r["sources"] and all(x["quote"] and x["url"] for x in r["sources"]) and r["physician_confirmation_needed"])


class Case11_PastEpisode(unittest.TestCase):
    def test_later_test_does_not_readjudicate(self):
        t = CaseTimeline("c")
        t.set_hypothesis("h1", "Pulmonary embolism", PE, 0.0)
        t.add_document(Document("d", "ELISA D-dimer was normal, below the age-adjusted cut-off.", "LAB", 10.0, 11.0))
        ctx = {**REC, "hypothesis_target": {"diagnosis_episode_id": "E1", "kind": "PAST_EPISODE", "hypothesis_target_time": 2.0}}
        r = t.state(12.0, ctx)["results"][0]
        self.assertEqual(r["direction"], "NOT_APPLICABLE")

    def test_time_unknown_holds(self):
        ctx = {**REC, "hypothesis_target": {"diagnosis_episode_id": "E1", "kind": "PAST_EPISODE", "hypothesis_target_time": 2.0}}
        r = out("ELISA D-dimer was normal, below the age-adjusted cut-off.", ctx=ctx)
        self.assertEqual((r["direction"], r["missing_context"]), ("INSUFFICIENT_EVIDENCE", ["evidence_observed_at"]))


class Case12_NoInventedContext(unittest.TestCase):
    CASES = (("IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries.", "PE_DIAGNOSIS"), ("No evidence of pulmonary embolism.", "PE_DIAGNOSIS"),
             ("Perfusion scan was normal.", "PERFUSION_SCAN"), ("ELISA D-dimer was normal, below the age-adjusted cut-off.", "DDIMER"),
             ("Compression ultrasound shows femoral deep vein thrombosis.", "DVT"))

    def test_unsourced_values_not_used(self):
        for t, c in self.CASES:
            for ctx in (ASSUMED, {}, {"pretest": "UNKNOWN", "suspected": "UNKNOWN"}, {"pretest": rec_("INTERMEDIATE", "SYNTHETIC_ASSUMPTION"), "suspected": rec_(True, "SYNTHETIC_ASSUMPTION")}):
                r = out(t, concept=c, doc="CTPA_REPORT", ctx=ctx)
                self.assertNotIn(r["direction"], DIRECTIONAL, (t, ctx))
                self.assertEqual(r["output_mode"], "CLINICAL")

    def test_patient_report_not_clinical_probability(self):
        r = out("No evidence of pulmonary embolism.", concept="PE_DIAGNOSIS", doc="CTPA_REPORT", ctx={"pretest": rec_("LOW", "PATIENT_REPORTED"), "suspected": rec_(True, "PATIENT_REPORTED")})
        self.assertEqual(r["direction"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(r["context_provenance"]["pretest"]["used"])

    def test_synthetic_mode_is_labelled(self):
        r = out(self.CASES[0][0], concept="PE_DIAGNOSIS", doc="CTPA_REPORT", ctx={**ASSUMED, "mode": "SYNTHETIC_ASSUMPTION"})
        self.assertEqual((r["direction"], r["output_mode"]), ("SUPPORT", "SYNTHETIC_ASSUMPTION"))
        self.assertEqual(r["assumed_context_used"], ["pretest", "suspected"])

    def test_record_values_used(self):
        r = out(self.CASES[0][0], concept="PE_DIAGNOSIS", doc="CTPA_REPORT")
        self.assertEqual((r["direction"], r["assumed_context_used"]), ("SUPPORT", []))

    def test_bad_source_rejected(self):
        with self.assertRaises(ValueError):
            EC.normalize_context({"pretest": rec_("LOW", "GUESS")})
        with self.assertRaises(ValueError):
            EC.normalize_context({"mode": "DEMO"})


class Catalog(unittest.TestCase):
    def test_no_new_relations_and_quotes(self):
        p1 = RL.load(HERE / "knowledge/evidence_relations_p1.json")
        p2 = RL.load()
        self.assertEqual([(r["id"], r["hypothesis"], r["finding"], r["relation"]) for r in p1["relations"]], [(r["id"], r["hypothesis"], r["finding"], r["relation"]) for r in p2["relations"]])
        for r in p2["relations"]:
            self.assertTrue(all(e["quote"] for e in r["evidence"]), r["id"])


if __name__ == "__main__":
    unittest.main()
