"""v5-2B-Research 테스트. 사례 기대값은 hybrid5b/experiment_matrix.py·run_v5_2b_research.py 에 실행 전 고정(2026-11-09).
여기서는 결과 파일을 읽지 않고 함수를 직접 다시 실행해 확인한다."""
import json
import sys
import unittest
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_v5_2b_research as RUN  # noqa: E402
from hybrid5b import comparison as CMP, experiment_matrix as EM, graph_flat as GF, multidisease as MD  # noqa: E402
from hybrid5b import shadow_catalog as SC, shadow_reasoner as SR, temporal as TP  # noqa: E402
from hybrid4 import graphs as GR  # noqa: E402


@lru_cache(maxsize=None)
def pe(cid):
    c = next(x for x in EM.CASES if x["case_id"] == cid)
    return RUN.run_pe_case(c)


@lru_cache(maxsize=None)
def temporal():
    return TP.run_temporal("graph")


class ShadowCases(unittest.TestCase):
    def test_all_pe_expectations(self):
        bad = [(c["case_id"], r, x) for c in EM.CASES for r, x in pe(c["case_id"])[4].items() if not x["pass"]]
        self.assertEqual(bad, [])
        self.assertGreaterEqual(len(EM.CASES), 40)

    def test_comparison_expectations(self):
        bad = [(c["case_id"], pe(c["case_id"])[5]) for c in EM.CASES if pe(c["case_id"])[5] and not pe(c["case_id"])[5]["pass"]]
        self.assertEqual(bad, [])

    def test_key_differences(self):
        cats = {c: {r["category"] for r in pe(c)[3] if r["shadow_relation"] in next(x for x in EM.CASES if x["case_id"] == c)["expect"]}
                for c in ("F01", "D01", "J01", "U02", "U01", "U07")}
        self.assertEqual(cats, {"F01": {"SHADOW_MORE_CONSERVATIVE"}, "D01": {"LEGACY_MORE_CONSERVATIVE"}, "J01": {"LEGACY_MORE_CONSERVATIVE"},
                                "U02": {"SEMANTIC_REVIEW_REQUIRED"}, "U01": {"SOURCE_INCOMPLETE"}, "U07": {"SHADOW_MORE_CONSERVATIVE"}})

    def test_p0_matrix_all_rows_covered_and_agree(self):
        import csv
        rows = list(csv.DictReader(open(RUN.P0 / "knowledge/v5_2b_p0_condition_matrix.csv", encoding="utf-8")))
        self.assertEqual(len(rows), 33)
        relmap = {"PE-CTPA-NEGATIVE": "SH-CTPA-NEG", "PE-CTPA-POSITIVE": "SH-CTPA-POS", "PE-DDIMER-NORMAL(ELISA·연령보정)": "SH-DD-NORMAL"}
        for row in rows:
            rel = relmap[row["relation"]]
            c = next(x for x in EM.CASES if x["p0_scenario"] == row["scenario"] and rel in x["expect"] and not x["policy"])
            act = sorted({EM.token(j["direction"]) for j in pe(c["case_id"])[2]["judgments"] if j["relation_id"] == rel}) or ["NONE"]
            self.assertEqual(act, [RUN.p0_token(row["candidate_outcome"])], (row["scenario"], rel))


class Isolation(unittest.TestCase):
    def test_labels_and_inactive(self):
        for c in EM.CASES:
            for j in pe(c["case_id"])[2]["judgments"]:
                self.assertEqual(j["labels"], ["RESEARCH_ONLY", "NOT_CLINICALLY_VALIDATED", "ENGINE_ACTIVE_FALSE"])
                if j["direction"] in ("SUPPORT", "WEAKEN"):
                    self.assertTrue(j["applied_sources"])
                    self.assertEqual(j["shadow_status"], "RESEARCH_DIRECTIONAL")
        self.assertTrue(all(r["engine_active"] is False for r in SC.catalog_rows()))

    def test_legacy_catalog_unchanged(self):
        before = json.dumps([r["structured"].to_dict() for r in GR.normalized_relations()], sort_keys=True, default=str)
        SC.build({"haemo": "B_REQUIRE_DOCUMENTED_STABILITY"})
        SR.evaluate(EM.build_pg(EM.CASES[0]), 10.0)
        after = json.dumps([r["structured"].to_dict() for r in GR.normalized_relations()], sort_keys=True, default=str)
        self.assertEqual(before, after)
        self.assertEqual(sorted(r["relation_id"] for r in GR.normalized_relations()),
                         sorted(SC.LEGACY_MAP))

    def test_non_directional_never_directional(self):
        for c in EM.CASES:
            for j in pe(c["case_id"])[2]["judgments"]:
                if j["relation_id"] in ("SH-DD-ELEVATED", "SH-PERF-NORMAL", "SH-PROX-DVT", "SH-FILLING-DEFECT", "SH-HISTORY-VTE"):
                    self.assertTrue(j["direction"].startswith("NO_DIRECTION"))


class TemporalGraphFlat(unittest.TestCase):
    def test_temporal_checks(self):
        by_id = {c["case_id"]: (c, pe(c["case_id"])[1], pe(c["case_id"])[2], pe(c["case_id"])[3]) for c in EM.CASES}
        res = RUN.temporal_checks(temporal(), by_id)
        self.assertEqual({k: v["pass"] for k, v in res.items()}, {k: True for k in res})

    def test_fabricated_rejected(self):
        self.assertTrue(TP.fabricated_check().startswith("RAISED:SOURCE_NOT_FOUND"))

    def test_graph_flat_sample(self):
        for cid in ("A01", "D01", "F01", "J01", "M01", "U05", "Z05"):
            c = next(x for x in EM.CASES if x["case_id"] == cid)
            r = GF.compare_case(EM.build_pg(c), c["as_of"], c["policy"])
            self.assertTrue(all(v["identical"] for v in r.values()), (cid, r))


class MultiDisease(unittest.TestCase):
    def test_mi_checks(self):
        for cid, (fn, t, exp) in RUN.MI_CASES.items():
            r = MD.mi_research(fn(), t)
            self.assertEqual(len(r), 1, cid)
            self.assertIsNone(r[0]["directional_output"])
            rc, sym = r[0]["research_classification"], r[0]["ischaemia_evidence"]["symptoms"]
            for k, v in exp.items():
                a = sym if k == "ischaemia_symptoms" else rc[k]
                self.assertTrue((a in v) if isinstance(v, set) else str(a).startswith(v), (cid, k, a))

    def test_pc_checks(self):
        for cid, (fn, t, exp) in RUN.PC_CASES.items():
            r = MD.pericarditis_research(fn(), t)[0]
            self.assertIsNone(r["directional_output"])
            for (pp, ip), allowed in exp.items():
                self.assertIn(r["policies"][RUN.POLKEY[pp]][RUN.POLKEY[ip]], allowed, (cid, pp, ip))

    def test_multidisease_no_score(self):
        fn, t = RUN.MD_CASES["MD01_pe_neg_pericarditis_injury"]
        pg = fn()
        r = MD.comparison(pg, t, SR.evaluate(pg, t, "graph"))
        self.assertEqual((r["combined_score"], r["ranking"]), (None, None))
        self.assertTrue(r["PE"]["judgments"] and r["ACS_MI"]["results"] and r["PERICARDITIS"]["results"])
        self.assertIsNone(r["ACS_MI"]["results"][0]["directional_output"])


class Counterexamples(unittest.TestCase):
    def test_new_counterexamples_shadow(self):
        by_id = {c["case_id"]: (c, pe(c["case_id"])[1], pe(c["case_id"])[2], pe(c["case_id"])[3]) for c in EM.CASES}
        mi = {cid: {"result": MD.mi_research(fn(), t)} for cid, (fn, t, _e) in RUN.MI_CASES.items()}
        pc = {cid: {"result": MD.pericarditis_research(fn(), t)} for cid, (fn, t, _e) in RUN.PC_CASES.items()}
        rows = RUN.new_counterexamples(by_id, temporal(), mi, pc)
        self.assertEqual(len(rows), 18)
        self.assertEqual([r["case_id"] for r in rows if r["discrepancy"]], [])


if __name__ == "__main__":
    unittest.main()
