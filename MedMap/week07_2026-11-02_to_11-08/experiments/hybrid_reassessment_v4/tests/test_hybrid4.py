"""v4 기능 검사. 순수 논리는 의학 의미 없는 합성 조건, 의학 방향은 P2 카탈로그 관계에서만. 임상 정확도 아님."""
import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from hybrid4 import graphs as GR, logic as LG, reason as RS  # noqa: E402
from hybrid4.graphs import Doc, Episode, Hypothesis  # noqa: E402
from hybrid.schema import AssertedBy, DxStatus  # noqa: E402

PE = "DX:Pulmonary embolism"
REL = GR.normalized_relations()
G, FL = RS.Reasoner(REL, "graph"), RS.Reasoner(REL, "flat")
SUSP = "Pulmonary embolism is suspected. Clinical probability was assessed as intermediate using the Wells score. The patient is hemodynamically stable."
POS = "IMPRESSION: Acute pulmonary embolism in the right lower lobe segmental arteries."
NEG = "IMPRESSION: No evidence of pulmonary embolism."


def fact(k, v=None, status="FOUND"):
    return LG.Fact(k, status, v, (v,) if status == "FOUND" else ("a", "b") if status == "CONFLICT" else (), ("s",))


def patient(docs, eps=None, hyps=None):
    pg = GR.PatientGraph("SYN-T")
    for e in eps or [Episode("E1", "CURRENT_EVALUATION")]:
        pg.add_episode(e)
    for h, c in hyps or [(Hypothesis("h1", "Pulmonary embolism", PE, 0.0, episode_id="E1"), True)]:
        pg.add_hypothesis(h, c)
    for d, ep in docs:
        pg.add_record(d, ep)
    return pg


def items(res, hyp="h1"):
    return [i for h in res["hypotheses"] if h["hyp_id"] == hyp for i in h["items"]]


def rel_item(res, rid, hyp="h1"):
    x = [i for i in items(res, hyp) if i["relation_id"] == rid]
    assert len(x) == 1, x
    return x[0]


class FourValuedLogic(unittest.TestCase):
    A, B = LG.Atom("a", ("x",)), LG.Atom("b", ("y",))

    def v(self, node, **f):
        return LG.eval_cond(node, {k: (fact(k, v) if v not in ("UNKNOWN", "CONFLICT") else fact(k, status="NOT_FOUND" if v == "UNKNOWN" else "CONFLICT")) for k, v in f.items()})["value"]

    def test_and(self):
        n = LG.And((self.A, self.B))
        self.assertEqual(self.v(n, a="x", b="y"), "TRUE")
        self.assertEqual(self.v(n, a="x", b="UNKNOWN"), "UNKNOWN")                # UNKNOWN 이 TRUE 가 되지 않음
        self.assertEqual(self.v(n, a="z", b="UNKNOWN"), "FALSE")
        self.assertEqual(self.v(n, a="x", b="CONFLICT"), "CONFLICT")
        r = LG.eval_cond(n, {"a": fact("a", "z"), "b": fact("b", status="CONFLICT")})
        self.assertEqual((r["value"], len(r["conflicts"])), ("FALSE", 1))       # FALSE 로 결정돼도 충돌 기록은 남음

    def test_or_not(self):
        n = LG.Or((self.A, self.B))
        self.assertEqual(self.v(n, a="z", b="y"), "TRUE")
        self.assertEqual(self.v(n, a="z", b="UNKNOWN"), "UNKNOWN")                # 모두 FALSE 일 때만 FALSE
        self.assertEqual(self.v(n, a="z", b="w"), "FALSE")
        self.assertEqual(self.v(n, a="CONFLICT", b="y"), "TRUE")                  # 다른 경로의 확인된 TRUE 는 유지
        self.assertEqual(self.v(LG.Not(self.A), a="UNKNOWN"), "UNKNOWN")          # NOT UNKNOWN ≠ TRUE
        self.assertEqual(self.v(LG.Not(self.A), a="z"), "TRUE")

    def test_gate_unknown_blocks_direction(self):
        s = LG.Structured("SYN", gates=[{"cond": [LG.Atom("g", ("bad",))], "outcome": "NOT_APPLICABLE", "note": "", "unknown_policy": "HOLD", "origin": "SYN"}],
                          required=[self.A], directional_outcome="SUPPORT")
        self.assertEqual(LG.decide(s, {"a": fact("a", "x"), "g": fact("g", "ok")})["direction"], "SUPPORT")
        d = LG.decide(s, {"a": fact("a", "x")})
        self.assertEqual((d["direction"], d["stage"], d["missing"]), ("INSUFFICIENT_EVIDENCE", "EXCLUSION_GATE_UNRESOLVED", ["g"]))
        self.assertEqual(LG.decide(s, {"a": fact("a", "x"), "g": fact("g", status="CONFLICT")})["stage"], "EXCLUSION_GATE_UNRESOLVED")
        self.assertEqual(LG.decide(s, {"a": fact("a", "x"), "g": fact("g", "bad")})["direction"], "NOT_APPLICABLE")

    def test_block_only_if_true_gate(self):
        s = LG.Structured("SYN", gates=[{"cond": [LG.Atom("g", (True,))], "outcome": "NOT_APPLICABLE", "note": "", "unknown_policy": "BLOCK_ONLY_IF_TRUE", "origin": "SYN"}],
                          required=[self.A], directional_outcome="WEAKEN")
        d = LG.decide(s, {"a": fact("a", "x")})
        self.assertEqual((d["direction"], d["missing"], d["optional_unchecked"]), ("WEAKEN", [], ["g"]))


class CatalogConversion(unittest.TestCase):
    def test_semantics_preserved_against_p2_apply(self):
        """같은 맥락에서 P2 apply 와 v4 decide 의 방향이 같아야 함(값이 확정된 모든 조합)."""
        RL = GR.CP.RLX
        cat = GR.EvidenceGraph().catalog
        vals = {"clinical_phase": ["SUSPECTED_ACUTE_PE_EVALUATION", "CONFIRMED_PE", "UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP", "RECURRENCE_EVALUATION"],
                "pretest": ["LOW", "INTERMEDIATE", "HIGH"], "level": ["SUBSEGMENTAL", "SEGMENTAL_OR_PROXIMAL"], "ddimer_assay": ["HIGH_SENSITIVITY", "MODERATE_SENSITIVITY", "POINT_OF_CARE"],
                "ddimer_cutoff": ["FIXED", "AGE_ADJUSTED"], "suspected": [True]}
        import itertools
        n = 0
        for r in cat["relations"]:
            keys = sorted({k for x in r["by_context"] for k in x["when"]} | set(r.get("requires_context", [])))
            s = LG.structure(r)
            for combo in itertools.product(*[vals[k] for k in keys]):
                ctx = dict(zip(keys, combo))
                self.assertEqual(LG.decide(s, {k: fact(k, v) for k, v in ctx.items()})["direction"], RL.apply(r, ctx)["direction"], (r["id"], ctx))
                n += 1
        self.assertGreater(n, 100)

    def test_ddimer_or_paths_from_catalog(self):
        s = [r for r in REL if r["relation_id"] == "PE-DDIMER-NORMAL"][0]["structured"]
        self.assertEqual([a.key for a in s.required], ["clinical_phase", "ddimer_cutoff"])
        self.assertEqual(len(s.alternatives), 2)


class PatientGraphAndEpisodes(unittest.TestCase):
    def test_extraction_becomes_nodes(self):
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)])
        ev = [v for v in pg.g.nodes.values() if v["kind"] == "EVIDENCE" and v["source_record_id"] == "r1"][0]
        self.assertEqual((ev["base_concept"], ev["evidence_value"], ev["diagnosis_episode_id"], ev["confirmation_status"]), ("PE_DIAGNOSIS", "CTPA_REPORTS_PE", "E1", "UNCONFIRMED"))
        self.assertTrue(pg.g.outs(ev["evidence_id"], "DERIVED_FROM") and pg.g.outs(ev["evidence_id"], "HAS_RESULT_STATE"))
        self.assertTrue([v for v in pg.g.nodes.values() if v["kind"] == "CONTEXT_FACT" and v["key"] == "pretest"])

    def test_unresolved_episode_not_attached(self):
        eps = [Episode("E0", "PAST_EPISODE", "", 1.0), Episode("E2", "RECURRENCE", "", 200.0)]
        hy = [(Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), True),
              (Hypothesis("h3", "Pulmonary embolism", PE, 200.0, episode_id="E2", kind="RECURRENCE", target_time=200.0), True)]
        pg = patient([(Doc("u1", NEG, "CTPA_REPORT", 150.0, 151.0), None)], eps, hy)
        r = G.evaluate(pg, 210.0)                                           # 두 가설 모두 활성인 시점
        self.assertFalse(items(r, "h0") + items(r, "h3"))
        self.assertEqual([h["unresolved_episode_evidence"][0]["source_record_id"] for h in r["hypotheses"]], ["u1", "u1"])

    def test_episode_relink_changes_target(self):
        eps = [Episode("E0", "PAST_EPISODE", "", 1.0), Episode("E2", "RECURRENCE", "", 200.0)]
        hy = [(Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), True),
              (Hypothesis("h3", "Pulmonary embolism", PE, 200.0, episode_id="E2", kind="RECURRENCE", target_time=200.0), True)]
        a = G.evaluate(patient([(Doc("r2", NEG, "CTPA_REPORT", 201.0, 202.0), "E2")], eps, hy), 203.0)
        b = G.evaluate(patient([(Doc("r2", NEG, "CTPA_REPORT", 201.0, 202.0), "E0")], eps, hy), 203.0)
        self.assertEqual((rel_item(a, "PE-CTPA-NEGATIVE", "h3")["direction"], items(a, "h0")), ("UNCERTAIN", []))
        self.assertEqual((rel_item(b, "PE-CTPA-NEGATIVE", "h0")["direction"], items(b, "h3")), ("NOT_APPLICABLE", []))

    def test_correction_append_only_and_time(self):
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None), (Doc("r2", NEG, "CTPA_REPORT", 2.0, 7.0, supersedes="r1"), None)])
        self.assertIn("REC:r1", pg.g.nodes)
        self.assertTrue(pg.g.outs("REC:r2", "CORRECTS"))
        self.assertEqual(items(G.evaluate(pg, 3.0)) and [i["direction"] for i in items(G.evaluate(pg, 3.0)) if i["relation_id"]], [])
        self.assertEqual(rel_item(G.evaluate(pg, 6.9), "PE-CTPA-POSITIVE")["direction"], "SUPPORT")
        r = G.evaluate(pg, 7.0)
        self.assertEqual((rel_item(r, "PE-CTPA-NEGATIVE")["direction"], [i for i in items(r) if i["source_record_id"] == "r1"]), ("WEAKEN", []))

    def test_ai_candidate_not_promoted(self):
        hy = [(Hypothesis("h5", "Pericarditis", "DX:Pericarditis", 0.0, episode_id="E1"), True),
              (Hypothesis("h6", "Pulmonary embolism", PE, 0.0, episode_id="E1", asserted_by=AssertedBy.MODEL_EXTRACTED), False)]
        pg = patient([(Doc("n1", "Pulmonary embolism was confirmed according to the outside note.", "NOTE", 0.5, 1.0), None)], hyps=hy)
        r = G.evaluate(pg, 2.0)
        h6 = [h for h in r["hypotheses"] if h["hyp_id"] == "h6"][0]
        self.assertEqual((h6["usable"], h6["items"]), (False, []))
        cand = [v for v in pg.g.nodes.values() if v["kind"] == "AI_DIAGNOSIS_CANDIDATE"]
        self.assertTrue(cand and all(not c["physician_confirmed"] and not c["usable_as_hypothesis"] for c in cand))


class Reasoning(unittest.TestCase):
    def test_multiple_evidence_kept_separately(self):
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("u1", "Compression ultrasound shows femoral deep vein thrombosis.", "NOTE", 1.0, 1.5), None),
                      (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)])
        r = G.evaluate(pg, 5.0)
        self.assertEqual((rel_item(r, "PE-PROXIMAL-DVT")["direction"], rel_item(r, "PE-CTPA-NEGATIVE")["direction"]), ("SUPPORT", "WEAKEN"))
        t = RS.review_tree(r, pg)[0]
        self.assertEqual((len(t["supporting"]), len(t["weakening"])), (1, 1))
        self.assertFalse([k for k in t if "score" in k or "prob" in k])

    def test_unknown_and_conflict(self):
        r = G.evaluate(patient([(Doc("n1", "Pulmonary embolism is suspected.", "NOTE", 0.5, 1.0), None), (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)]), 5.0)
        i = rel_item(r, "PE-CTPA-NEGATIVE")
        self.assertEqual((i["direction"], [g["item"] for g in i["gaps"]]), ("INSUFFICIENT_EVIDENCE", ["pretest"]))
        self.assertIn("REQUIRED", i["gaps"][0]["condition_location"])
        r = G.evaluate(patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("n2", "Clinical probability was assessed as high.", "NOTE", 0.6, 1.1), None),
                                (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)]), 5.0)
        i = rel_item(r, "PE-CTPA-NEGATIVE")
        self.assertEqual(i["direction"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(sorted(i["decision"]["conflicts"][0]["sources"]), ["n1:pretest", "n2:pretest"])

    def test_followup_not_weaken_and_ddimer_conditions(self):
        eps = [Episode("E0", "PAST_EPISODE", "", 1.0)]
        hy = [(Hypothesis("h0", "Pulmonary embolism", PE, 1.0, DxStatus.CONFIRMED_DIAGNOSIS, "E0", "PAST_EPISODE", 1.0), True)]
        r = G.evaluate(patient([(Doc("r9", "Follow-up CTPA after three months of anticoagulation showed no pulmonary embolism.", "CTPA_REPORT", 90.0, 91.0), "E0")], eps, hy), 95.0)
        self.assertFalse([i for i in items(r, "h0") if i["direction"] in LG.DIRECTIONAL])
        r = G.evaluate(patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("l1", "D-dimer was normal.", "LAB", 1.0, 1.5), None)]), 2.0)
        self.assertEqual(rel_item(r, "PE-DDIMER-NORMAL")["direction"], "INSUFFICIENT_EVIDENCE")

    def test_explanation_traces_only_used_relation(self):
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", POS, "CTPA_REPORT", 2.0, 4.0), None)])
        t = RS.review_tree(G.evaluate(pg, 5.0), pg)[0]
        s = t["supporting"][0]
        self.assertEqual((s["relation_id"], s["graph_path"][-1], s["condition_trace"]["stage"]), ("PE-CTPA-POSITIVE", PE, "DIRECTIONAL_PATH_TRUE"))
        self.assertTrue(s["sources"] and s["sentence"] and s["evidence_id"])
        self.assertTrue(all(x.startswith(("2019 ESC", "Gallo")) for x in t["medical_sources_used"]))

    def test_graph_and_flat_identical(self):
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None),
                      (Doc("x1", "The patient has dyspnea.", "NOTE", 0.5, 1.0), None)])
        a, b = G.evaluate(pg, 5.0), FL.evaluate(pg, 5.0)
        strip = lambda r: [{k: v for k, v in i.items() if k != "path"} for i in items(r)]  # noqa: E731
        self.assertEqual(strip(a), strip(b))

    def test_relation_disable_only_dependents(self):
        g2 = RS.Reasoner(GR.normalized_relations(disabled=["PE-CTPA-NEGATIVE"]), "graph")
        pg = patient([(Doc("n1", SUSP, "NOTE", 0.5, 1.0), None), (Doc("u1", "Compression ultrasound shows femoral deep vein thrombosis.", "NOTE", 1.0, 1.5), None),
                      (Doc("r1", NEG, "CTPA_REPORT", 2.0, 4.0), None)])
        r = g2.evaluate(pg, 5.0)
        self.assertEqual(rel_item(r, "PE-PROXIMAL-DVT")["direction"], "SUPPORT")
        self.assertFalse([i for i in items(r) if i["relation_id"] == "PE-CTPA-NEGATIVE"])


if __name__ == "__main__":
    unittest.main()
