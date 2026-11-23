"""격리 연구 코드 구현 정합성 테스트(합성·지어낸 값만). 임상 정확도 검사가 아니다."""
import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from hybrid import adapters as AD, diagnosis_input as DI, er_reason as ER, knowledge as KG, metrics as M, temporal as T  # noqa: E402
from hybrid.schema import *  # noqa: E402,F403

PE = "DX:Pulmonary embolism"
NEG = "IMPRESSION: No evidence of pulmonary embolism."
POS = "FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism."


def P(ref="syn:1", dc=DataClass.SYNTHETIC, **k):
    return Provenance("synthetic", ref, dc, **k)


def H(concept=PE, status=DxStatus.WORKING_DIAGNOSIS, by=AssertedBy.SIMULATED):
    return DiagnosisAssertion("h", "c", "PE", status, by, 0.0, P(), concept_id=concept)


def Ev(kind=EvidenceKind.SYMPTOM, text="x", concept="", pol=Polarity.PRESENT, at=1.0, eid="e1", **k):
    return EvidenceItem(eid, "c", kind, text, P(eid), observed_at=at, recorded_at=at, available_at=at, polarity=pol, concept_id=concept, **k)


def In(e, h=None, as_of=1.0, dc=DataClass.SYNTHETIC, prior=()):
    return ReasonerInput("i", "c", h or H(), e, "", prior, as_of, dc)


class Schema(unittest.TestCase):
    def test_status_matters_not_just_name(self):
        for st, ok in ((DxStatus.WORKING_DIAGNOSIS, True), (DxStatus.CONFIRMED_DIAGNOSIS, True), (DxStatus.DIFFERENTIAL_DIAGNOSIS, True), (DxStatus.RULED_OUT_DIAGNOSIS, False),
                       (DxStatus.HISTORICAL_DIAGNOSIS, False), (DxStatus.UNKNOWN, False)):
            self.assertEqual(H(status=st).usable_as_hypothesis(), ok, st)

    def test_source_required(self):
        with self.assertRaises(ValueError):
            Provenance("", "", DataClass.SYNTHETIC)

    def test_output_invariants(self):
        with self.assertRaises(ValueError):
            ReasonerOutput("i", "r", OutcomeStatus.ANSWERED)
        with self.assertRaises(ValueError):
            ReasonerOutput("i", "r", OutcomeStatus.ABSTAIN, Effect.SUPPORT)
        with self.assertRaises(ValueError):
            ReasonerOutput("i", "r", OutcomeStatus.ANSWERED, Effect.SUPPORT, grade=3)


class Temporal(unittest.TestCase):
    def test_future_and_unknown_not_visible(self):
        a = Ev(at=1.0, eid="a")
        b = Ev(at=5.0, eid="b")
        c = EvidenceItem("c", "c", EvidenceKind.LAB, "x", P(), available_at=None)
        d = EvidenceItem("d", "c", EvidenceKind.LAB, "x", P(), observed_at=4.0, available_at=2.0)
        self.assertEqual([e.evidence_id for e in T.visible_evidence([a, b, c, d], 3.0)], ["a"])

    def test_correction_only_from_its_time(self):
        a = Ev(at=1.0, eid="a")
        b = Ev(at=5.0, eid="b", supersedes="a")
        self.assertEqual([e.evidence_id for e in T.visible_evidence([a, b], 4.0)], ["a"])
        self.assertEqual([e.evidence_id for e in T.visible_evidence([a, b], 6.0)], ["b"])

    def test_diagnosis_history_kept(self):
        a = H()
        b = DiagnosisAssertion("h2", "c", "PE", DxStatus.RULED_OUT_DIAGNOSIS, AssertedBy.PHYSICIAN, 5.0, P(), supersedes="h")
        self.assertEqual([x.assertion_id for x in T.diagnosis_state([a, b], 4.0)], ["h"])
        self.assertEqual([x.assertion_id for x in T.diagnosis_state([a, b], 6.0)], ["h2"])

    def test_test_status_sequence(self):
        E_ = lambda ev, at: TestEvent("t", "c", ev, at, P())
        ev = [E_("ORDER", 1), E_("COLLECT", 2), E_("RESULT", 3), E_("REVIEW", 4)]
        want = {0.5: TestStatus.NOT_ORDERED, 1: TestStatus.ORDERED, 2: TestStatus.PENDING, 3: TestStatus.RESULT_AVAILABLE, 4: TestStatus.REVIEWED}
        for at, st in want.items():
            self.assertEqual(T.test_status(ev, "t", at), st, at)
        self.assertEqual(T.test_status([], "t", 9), TestStatus.UNKNOWN)                      # 기록 없음 ≠ 시행 안 함
        self.assertEqual(T.test_status(ev + [E_("CANCEL", 5)], "t", 6), TestStatus.CANCELLED)
        self.assertEqual(T.test_status(ev + [E_("CORRECT", 5)], "t", 6), TestStatus.RESULT_AVAILABLE)   # 정정되면 재확인 필요
        self.assertTrue(T.is_duplicate_candidate(ev, "t", 3))
        self.assertFalse(T.is_duplicate_candidate([], "t", 3))
        self.assertFalse(T.is_duplicate_candidate(ev + [E_("CANCEL", 5)], "t", 6))

    def test_review_before_result_ignored(self):
        ev = [TestEvent("t", "c", "ORDER", 1, P()), TestEvent("t", "c", "REVIEW", 2, P())]
        self.assertEqual(T.test_status(ev, "t", 3), TestStatus.ORDERED)


class Adapters(unittest.TestCase):
    def test_future_input_refused_by_all(self):
        e = Ev(at=5.0, concept="HP:0002094")
        for r in (AD.BaselineEngineAdapter(), AD.GraphReasoner(), AD.RulesReasoner(), AD.LLMReasoner(), AD.HybridReasoner()):
            self.assertEqual(r.assess(In(e, as_of=1.0)).reason_code, "TEMPORAL_INPUT_VIOLATION", r.name)

    def test_future_prior_refused(self):
        self.assertEqual(AD.GraphReasoner().assess(In(Ev(concept="HP:0002094"), prior=(Ev(at=9.0, eid="p"),))).reason_code, "TEMPORAL_INPUT_VIOLATION")

    def test_model_candidate_hypothesis_refused(self):
        self.assertEqual(AD.HybridReasoner().assess(In(Ev(), H(by=AssertedBy.MODEL_EXTRACTED))).reason_code, "HYPOTHESIS_NOT_USABLE")

    def test_baseline_same_as_engine(self):
        ra = AD._ra()
        out = AD.BaselineEngineAdapter().assess(In(Ev(EvidenceKind.SYMPTOM, "dyspnea", "HP:0002094")))
        rel, rule = ra.relation(ra.Evidence("e1", "c", "SYMPTOM", "s", "s", 1.0, 1.0, 1.0, "POSITIVE", concept="HP:0002094"), PE)
        self.assertEqual((rel, rule), ("SUPPORTS", "R7"))
        self.assertEqual((out.effect, out.reason_code), (Effect.SUPPORT, "ENGINE_R7"))

    def test_baseline_abstains_when_unmapped(self):
        self.assertEqual(AD.BaselineEngineAdapter().assess(In(Ev(text="free text"))).status, OutcomeStatus.ABSTAIN)
        self.assertEqual(AD.BaselineEngineAdapter().assess(In(Ev(concept="HP:0002094"), H(concept=""))).reason_code, "HYPOTHESIS_NOT_IN_ENGINE_VOCABULARY")

    def test_graph_has_no_weakening(self):
        g = AD.GraphReasoner()
        self.assertEqual(g.assess(In(Ev(concept="HP:0002094"))).effect, Effect.SUPPORT)
        self.assertEqual(g.assess(In(Ev(concept="HP:0002094", pol=Polarity.ABSENT))).status, OutcomeStatus.ABSTAIN)
        self.assertEqual(g.assess(In(Ev(concept="HP:9999999"))).reason_code, "NO_GRAPH_PATH")

    def test_rules_only_registered(self):
        r = AD.RulesReasoner()
        self.assertEqual(r.assess(In(Ev(EvidenceKind.IMAGING_REPORT, NEG))).effect, Effect.CONTRADICTION)
        self.assertEqual(r.assess(In(Ev(EvidenceKind.IMAGING_REPORT, POS))).effect, Effect.SUPPORT)
        self.assertIn("SYSTEM_DEFINED", r.assess(In(Ev(EvidenceKind.IMAGING_REPORT, NEG))).flags)
        self.assertEqual(r.assess(In(Ev(EvidenceKind.IMAGING_REPORT, NEG), H(concept="DX:Myocarditis"))).reason_code, "NO_REGISTERED_RULE")
        self.assertEqual(r.assess(In(Ev(concept="HP:0002094"))).reason_code, "NO_REGISTERED_RULE")

    def test_llm_disabled_and_restricted_never_sent(self):
        calls = []
        cl = lambda x: calls.append(x) or {"effect": "SUPPORT", "evidence_quote": "x"}
        self.assertEqual(AD.LLMReasoner().assess(In(Ev())).status, OutcomeStatus.NOT_IMPLEMENTED)
        r = AD.LLMReasoner(cl, AD.LLMPolicy(enabled=True))
        self.assertEqual(r.assess(In(Ev(), dc=DataClass.RESTRICTED)).reason_code, "RESTRICTED_DATA_NOT_SENT")
        self.assertEqual(calls, [])
        r2 = AD.LLMReasoner(cl, AD.LLMPolicy(enabled=True, is_local_runtime=True))        # 승인 기록 없는 로컬도 거부
        self.assertEqual(r2.assess(In(Ev(), dc=DataClass.RESTRICTED)).reason_code, "RESTRICTED_DATA_NOT_SENT")
        self.assertEqual(calls, [])

    def test_llm_output_validated(self):
        mk = lambda raw: AD.LLMReasoner(lambda x: raw, AD.LLMPolicy(enabled=True))
        e = Ev(text="pain on deep breath")
        self.assertEqual(mk({"effect": "SUPPORT", "evidence_quote": "not in input"}).assess(In(e)).reason_code, "LLM_ATTRIBUTION_NOT_IN_INPUT")
        self.assertEqual(mk({"effect": "NOPE", "evidence_quote": "pain"}).assess(In(e)).reason_code, "LLM_OUTPUT_INVALID")
        self.assertEqual(mk({"effect": "WEAKEN", "grade": 7, "evidence_quote": "pain"}).assess(In(e)).reason_code, "LLM_OUTPUT_INVALID")
        ok = mk({"effect": "WEAKEN", "grade": -1, "evidence_quote": "pain"}).assess(In(e))
        self.assertEqual((ok.effect, ok.grade, ok.flags), (Effect.WEAKEN, -1, ("LLM_UNVERIFIED",)))

    def test_hybrid_composition(self):
        self.assertEqual(AD.HybridReasoner().assess(In(Ev(text="free"))).status, OutcomeStatus.ABSTAIN)
        self.assertEqual(AD.HybridReasoner().assess(In(Ev(EvidenceKind.IMAGING_REPORT, NEG))).effect, Effect.CONTRADICTION)
        weak = AD.LLMReasoner(lambda x: {"effect": "WEAKEN", "evidence_quote": "dyspnea"}, AD.LLMPolicy(enabled=True))
        out = AD.HybridReasoner(llm=weak).assess(In(Ev(text="dyspnea", concept="HP:0002094")))           # 그래프 SUPPORT vs LLM WEAKEN
        self.assertEqual((out.effect, out.reason_code), (Effect.UNCERTAIN, "COMPONENT_CONFLICT"))


class Metrics(unittest.TestCase):
    def setUp(self):
        self.refs = [ReferenceLabel(f"i{k}", f"c{k // 2}", g) for k, g in enumerate((-2, -1, 1, 2, 0, -1))]

    def test_abstain_stays_in_denominator(self):
        o = {"i0": ReasonerOutput("i0", "r", OutcomeStatus.ANSWERED, Effect.WEAKEN), "i2": ReasonerOutput("i2", "r", OutcomeStatus.ANSWERED, Effect.WEAKEN), "i1": abstain("i1", "r", "x"), "i4": not_implemented("i4", "r", "x")}
        m = M.evaluate(self.refs, o)
        self.assertEqual(m["coverage"], 2 / 6)
        self.assertEqual(m["abstention_rate"], 1 / 6)
        self.assertEqual(m["not_implemented_rate"], 1 / 6)
        self.assertEqual(m["missing_output"], 2)
        self.assertEqual(m["direction_agreement_all_items"], 1 / 6)
        self.assertEqual(m["direction_agreement_conditional_answered"], 1 / 2)
        self.assertEqual(m["weakening_recall_all_items"], 1 / 3)
        self.assertEqual(m["opposite_direction_rate_conditional"], 1 / 2)

    def test_uncertain_answer_is_not_correct(self):
        o = {"i0": ReasonerOutput("i0", "r", OutcomeStatus.ANSWERED, Effect.UNCERTAIN)}
        self.assertEqual(M.evaluate(self.refs, o)["direction_agreement_all_items"], 0.0)

    def test_weighted_kappa_hand_values(self):
        self.assertEqual(M.linear_weighted_kappa([(-2, -2), (2, 2)]), 1.0)
        # (-2,-2),(-2,0),(2,2),(2,2): O 합 w = .5, 기대 = (행 -2:2, 행 2:2 × 열 -2:1, 0:1, 2:2)/4 → 2*(0*1+.5*1+1*2)/4 + 2*(1*1+.5*1+0)/4 = 1.25+.75=2 → 1-.5/2=.75
        self.assertAlmostEqual(M.linear_weighted_kappa([(-2, -2), (-2, 0), (2, 2), (2, 2)]), 0.75)
        self.assertIsNone(M.linear_weighted_kappa([]))
        self.assertIsNone(M.linear_weighted_kappa([(1, 1), (1, 1)]))

    def test_cluster_bootstrap_resamples_cases(self):
        o = {r.item_id: ReasonerOutput(r.item_id, "r", OutcomeStatus.ANSWERED, Effect.WEAKEN) for r in self.refs}
        b = M.cluster_bootstrap(self.refs, o, "direction_agreement_all_items", n=200)
        self.assertEqual(b["n_cases"], 3)
        self.assertLessEqual(b["ci"][0], b["ci"][1])
        p = M.paired_cluster_bootstrap(self.refs, o, {}, "coverage", n=50)   # 없는 출력 쪽 coverage 0
        self.assertEqual(p["diff_ci"], [1.0, 1.0])


class Knowledge(unittest.TestCase):
    A = dict(assertion_id="k", subject="s", obj="o", source_ref="r", source_version="v")

    def test_no_auto_promotion(self):
        for kind in ("ONTOLOGY", "COOCCURRENCE"):
            with self.assertRaises(ValueError):
                KG.KnowledgeAssertion(relation="SUPPORTS_HYPOTHESIS", source_kind=kind, source_quote="q", applicability="a", **self.A)
        with self.assertRaises(ValueError):
            KG.KnowledgeAssertion(relation="WEAKENS_HYPOTHESIS", source_kind="GUIDELINE", **self.A)     # 인용·적용 조건 없음

    def test_proposed_not_used(self):
        a = KG.KnowledgeAssertion(relation="WEAKENS_HYPOTHESIS", source_kind="GUIDELINE", source_quote="q", applicability="a", **self.A)
        self.assertFalse(a.usable_for_reasoning())
        b = KG.KnowledgeAssertion(relation="HAS_FINDING", source_kind="ONTOLOGY", **self.A)
        self.assertFalse(b.usable_for_reasoning())

    def test_legacy_graph_not_directional(self):
        g = AD._ra().graph()
        e = g.out_edges("HP:0002094", "SUGGESTS")[0]
        self.assertFalse(KG.legacy_edge_view(e)["directional_evidence"])


class DiagnosisInput(unittest.TestCase):
    def test_ai_never_confirms(self):
        c = DI.UtteranceCandidate("u", "c", "text", "PE", DxStatus.CONFIRMED_DIAGNOSIS, "PHYSICIAN", P())
        a = DI.to_assertion(c, 1.0)
        self.assertFalse(a.usable_as_hypothesis())
        with self.assertRaises(ValueError):
            DI.physician_confirm(a, DxStatus.WORKING_DIAGNOSIS, 2.0, "", "h1")
        b = DI.physician_confirm(a, DxStatus.WORKING_DIAGNOSIS, 2.0, "confirm:1", "h1")
        self.assertTrue(b.usable_as_hypothesis())
        self.assertEqual((b.status, b.supersedes, b.asserted_by), (DxStatus.WORKING_DIAGNOSIS, "u", AssertedBy.PHYSICIAN))


class ERReason(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        c = {f"differential_{i}": "" for i in range(1, 6)} | {f"evidence_{i}": "" for i in range(1, 6)}
        rows = [{"encounterkey": "K1", "One_Sentence_Extracted": "SYNTH", **c, "differential_1": "SYNTH_A", "evidence_1": "SYNTH_E1", "evidence_2": "SYNTH_E2"}]
        self._w("t.csv", rows)
        self._w("r.csv", [{"encounterkey": "K1", "differential": "SYNTH_A", "evidence": "SYNTH_E2", "dxupdate": "-1", "rationale": "SECRET_RATIONALE", "dxtrajectory": "{}"},
                          {"encounterkey": "K1", "differential": "SYNTH_A", "evidence": "NOT_FOUND", "dxupdate": "1", "rationale": "x", "dxtrajectory": "{}"}])
        (self.tmp / "ok.json").write_text(json.dumps({"physionet_access_granted_on": "x", "version": "1.1.0", "dua_reviewed_on": "x", "external_llm_allowed": False, "approved_by_user": True}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _w(self, n, rows):
        import csv
        with open(self.tmp / n, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    def test_no_approval_no_read(self):
        with self.assertRaises(ER.ApprovalMissing):
            ER.build_items(self.tmp / "absent1", self.tmp / "absent2", self.tmp / "none.json")

    def test_incomplete_approval_refused(self):
        (self.tmp / "bad.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
        with self.assertRaises(ER.ApprovalMissing):
            ER.check_approval(self.tmp / "bad.json")

    def test_labels_not_in_model_input(self):
        ins, refs, st = ER.build_items(self.tmp / "t.csv", self.tmp / "r.csv", self.tmp / "ok.json")
        self.assertEqual((st["n_items"], st["n_rows_unmatched"]), (1, 1))
        self.assertEqual((refs[0].grade, ins[0].evidence.available_at), (-1, 2.0))
        self.assertEqual([e.text for e in ins[0].prior_evidence], ["SYNTH_E1"])                   # 이전 단계만
        self.assertNotIn("SECRET_RATIONALE", repr(ins[0]))
        self.assertEqual(ins[0].data_class, DataClass.RESTRICTED)

    def test_split_by_case(self):
        self.assertEqual(ER.split_of("K1"), ER.split_of("K1"))
        names = {ER.split_of(f"K{i}") for i in range(200)}
        self.assertEqual(names, {"DEVELOPMENT", "VALIDATION", "HELD_OUT_TEST"})

    def test_schema_mismatch(self):
        self._w("x.csv", [{"encounterkey": "K"}])
        with self.assertRaises(ValueError):
            ER.build_items(self.tmp / "x.csv", self.tmp / "r.csv", self.tmp / "ok.json")


class Isolation(unittest.TestCase):
    def test_no_network_or_llm_sdk_imports(self):
        bad = {"requests", "httpx", "urllib", "socket", "openai", "anthropic", "aiohttp"}
        for f in (HERE / "hybrid").glob("*.py"):
            t = ast.parse(f.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(t) if isinstance(n, ast.ImportFrom)}
            self.assertFalse(mods & bad, f.name)


if __name__ == "__main__":
    unittest.main()
