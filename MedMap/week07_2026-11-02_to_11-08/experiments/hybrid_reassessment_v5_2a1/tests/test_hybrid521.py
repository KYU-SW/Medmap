"""v5-2A.1 테스트. 기대값은 사례 실행 전에 고정(2026-11-08). 출력에 맞춰 바꾸지 않는다."""
import sys
import unittest
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_v5_2a1 as R  # noqa: E402
from hybrid521 import grouping as GP  # noqa: E402

D, CR = GP.DIRECTIONAL, GP.CRITERION


@lru_cache(maxsize=None)
def case(name):
    return R.run_case(name)


def eg(name, i=0):
    return case(name)[1][i]["graph"]["evidence_grouping"]


def v52(name, i=0):
    return case(name)[1][i]["graph"]["v5_2a"]


def grp(e, kind=D, hyp=None, sup=False):
    return [g for g in e["groups"] if g["group_kind"] == kind and (hyp is None or g["hypothesis_id"] == hyp)
            and ((g["dependency_status"] == GP.SUPERSEDED) == sup)]


def raws(e, kind=D, hyp=None):
    return [r for r in e["raw_judgments"] if r["raw_kind"] == kind and (hyp is None or r["hypothesis_id"] == hyp)]


class Cases(unittest.TestCase):
    def test_c01_same_event_three_docs(self):
        e = eg("C01_same_event_three_docs")
        r = raws(e)
        self.assertEqual((len(r), {x["directional_result"] for x in r}, sorted(x["source_record_id"] for x in r)), (3, {"WEAKEN"}, ["d1", "r1", "s1"]))
        g = grp(e)
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["dependency_status"], g[0]["source_event_id"], g[0]["source_record_ids"], g[0]["directional_result"]),
                         ("DERIVED_FROM_SAME_EVENT", "CT001", ["d1", "r1", "s1"], "WEAKEN"))
        c = e["counts_by_hypothesis"]["h_pe"]["directional"]
        self.assertEqual((c["raw_count"], c["group_count"], c["raw_in_multi_member_groups"], c["dependency_unknown_raw"]), (3, 1, 3, 0))
        self.assertTrue(any("근거 그룹 1개" in s["text"] and "CT001" in s["text"] for s in e["statements"]))

    def test_c02_same_text_no_event(self):
        e = eg("C02_same_text_no_event")
        self.assertEqual(len(raws(e)), 2)
        self.assertEqual([g["dependency_status"] for g in grp(e)], ["DEPENDENCY_UNKNOWN"] * 2)
        self.assertFalse(any("근거 그룹 1개" in s["text"] for s in e["statements"]))
        self.assertTrue(all("독립 근거라는 뜻이 아닙니다" in s["text"] for s in e["statements"]))

    def test_c03_different_text_same_event(self):
        e = eg("C03_different_text_same_event")
        g = grp(e)
        self.assertEqual((len(g), len(g[0]["raw_judgment_ids"]), g[0]["dependency_status"], g[0]["source_event_id"]), (1, 2, "DERIVED_FROM_SAME_EVENT", "CT001"))
        s1 = next(x for x in raws(e) if x["source_record_id"] == "s1")
        self.assertEqual(s1["lineage_basis"], "SOURCE_EVENT")

    def test_c04_different_time(self):
        g = grp(eg("C04_different_time_ctpa"))
        self.assertEqual(sorted((x["source_event_id"], x["dependency_status"]) for x in g), [("CT001", "DISTINCT_OBSERVATION"), ("CT002", "DISTINCT_OBSERVATION")])

    def test_c05_same_event_different_findings(self):
        e = eg("C05_same_event_different_findings")
        g = [x for x in grp(e, CR, "h_peri") if x["relation_id"] == "PERI_ECG"]
        self.assertEqual(len(g), 2)
        self.assertEqual({x["source_event_id"] for x in g}, {"ECG-1"})
        self.assertEqual({x["dependency_status"] for x in g}, {"DERIVED_FROM_SAME_EVENT"})
        self.assertEqual(sorted(len(x["raw_judgment_ids"]) for x in g), [1, 1])

    def test_c06_conflict(self):
        e = eg("C06_same_event_conflict")
        pe = [x for x in raws(e) if x["finding_key"][1] == "PE_DIAGNOSIS"]
        self.assertEqual(sorted(x["source_record_id"] for x in pe), ["r1", "r2"])
        self.assertEqual(len(e["conflicts"]), 1)
        cg = [g for g in grp(e) if g["conflict_status"] == "CONFLICTING_EVENT_EVIDENCE"]
        self.assertEqual(sorted(r for g in cg for r in g["source_record_ids"]), ["r1", "r2"])
        self.assertTrue(e["conflicts"][0]["resolution"].startswith("NOT_RESOLVED"))

    def test_c07_correction_provenance(self):
        p6 = {x["record_key"]: x["status_at_as_of"] for x in v52("C07_explicit_correction", 0)["source_provenance"]}
        p8 = {x["record_key"]: x["status_at_as_of"] for x in v52("C07_explicit_correction", 1)["source_provenance"]}
        self.assertEqual((p6["r1"], p6["r1c"], p8["r1"], p8["r1c"]), ("VISIBLE", "NOT_YET_AVAILABLE", "SUPERSEDED", "VISIBLE"))

    def test_c08_before_correction(self):
        e = eg("C08_before_correction")
        self.assertEqual({x["source_record_id"] for x in raws(e) if x["source_record_id"].startswith("r1")}, {"r1"})
        self.assertEqual(grp(e, sup=True), [])

    def test_c09_after_correction(self):
        e = eg("C09_after_correction")
        self.assertEqual({x["source_record_id"] for x in raws(e) if x["source_record_id"].startswith("r1")}, {"r1c"})
        cur = [g for g in grp(e) if "r1c" in g["source_record_ids"]]
        self.assertTrue(cur and all(g["correction_status"].startswith("CORRECTED_VERSION") for g in cur))
        sup = grp(e, sup=True)
        self.assertEqual(len(sup), 1)
        self.assertEqual((sup[0]["source_record_ids"], sup[0]["relation_id"]), (["r1"], "PE-CTPA-POSITIVE"))
        self.assertEqual(e["conflicts"], [])

    def test_c10_episodes_not_merged(self):
        e = eg("C10_different_episodes")
        self.assertTrue(any(x["source_record_id"] == "r0" and x["episode_id"] == "E0" for x in raws(e)))
        self.assertTrue(any(x["source_record_id"] == "s2" and x["episode_id"] == "E2" for x in raws(e)))
        by = {x["raw_id"]: x for x in e["raw_judgments"]}
        for g in e["groups"]:
            self.assertEqual(len({(by[r]["hypothesis_id"], by[r]["episode_id"]) for r in g["raw_judgment_ids"] if r in by}), 1)
            self.assertFalse({"r0", "s2"} <= set(g["source_record_ids"]))

    def test_c11_unresolved_episode(self):
        e = eg("C11_unresolved_episode")
        u = [x for x in e["unresolved_episode_records"] if x["record_key"] == "r1"]
        self.assertEqual((len(u), u[0]["lineage"]["event_id"]), (1, "CT001"))
        self.assertFalse(any(x["source_record_id"] == "r1" for x in e["raw_judgments"]))

    def test_c12_same_event_different_relation(self):
        e = eg("C12_same_event_different_relation")
        g = [x for x in grp(e) if x["source_event_id"] == "CT001"]
        self.assertEqual(sorted(x["relation_id"] for x in g), ["PE-CTPA-POSITIVE", "PE-FILLING-DEFECT"])
        self.assertEqual(e["conflicts"], [])

    def test_c13_same_event_different_target(self):
        e = eg("C13_same_event_different_target")
        pe = [x for x in grp(e, D, "h_pe") if "r1" in x["source_record_ids"]]
        pc = [x for x in grp(e, CR, "h_peri") if x["relation_id"] == "PERI_EFFUSION"]
        self.assertEqual((len(pe), len(pc), pe[0]["source_event_id"], pc[0]["source_event_id"]), (1, 1, "CT001", "CT001"))
        self.assertNotEqual(pe[0]["group_id"], pc[0]["group_id"])

    def test_c14_troponin_repeats(self):
        g = [x for x in grp(eg("C14_repeated_troponin"), CR, "h_acs") if x["relation_id"] == "INJ_ABOVE_SEX_SPECIFIC_URL"]
        self.assertEqual(sorted((x["source_event_id"], x["dependency_status"]) for x in g),
                         [("LAB-T0", "DISTINCT_OBSERVATION"), ("LAB-T1", "DISTINCT_OBSERVATION"), ("LAB-T2", "DISTINCT_OBSERVATION")])

    def test_c15_repeated_mention_no_event(self):
        e = eg("C15_repeated_mention_no_event")
        self.assertEqual([g["dependency_status"] for g in grp(e)], ["DEPENDENCY_UNKNOWN"] * 3)
        self.assertEqual(e["counts_by_hypothesis"]["h_pe"]["directional"]["dependency_unknown_raw"], 3)

    def test_c16_raw_preserved_unchanged(self):
        e, items = eg("C16_weaken_grouped_sources_kept"), v52("C16_weaken_grouped_sources_kept")
        legacy = next(h for h in items["hypotheses"] if h["hypothesis_id"] == "h_pe")["legacy_v4"]["items"]
        self.assertEqual(sorted((i["evidence_id"], i["relation_id"], i["direction"], i["hold_reason"]) for i in legacy),
                         sorted((x["evidence_id"], x["relation_id"], x["directional_result"], x["hold_reason"]) for x in raws(e)))
        self.assertEqual(sorted({r for g in grp(e) for r in g["source_record_ids"]}), sorted({x["source_record_id"] for x in raws(e)}))

    def test_c17_no_acs_support(self):
        e, r = eg("C17_no_acs_support_after_grouping"), v52("C17_no_acs_support_after_grouping")
        self.assertEqual(raws(e, D, "h_acs"), [])
        self.assertFalse(any(g["hypothesis_id"] == "h_acs" and g["directional_result"] == "SUPPORT" for g in e["groups"]))
        self.assertEqual(next(h for h in r["hypotheses"] if h["hypothesis_id"] == "h_acs")["supporting_evidence_ids"], [])

    def test_c18_c19_graph_flat(self):
        n = 0
        for name in R.CASES:
            _, out, decl = case(name)
            self.assertTrue(decl["declarations_equal"], name)
            for o in out:
                n += 1
                self.assertTrue(o["flat_equal"] and o["grouping_equal"], (name, o["as_of"], o["diff_paths"][:5]))
        self.assertEqual(n, 24)       # 정정(2026-11-08): 처음 27 은 작성 시 계산 오류. 사례 정의상 23개 × 시점 1 + C07 추가 시점 1 = 24

    def test_c20_registry(self):
        reg = R.R52.registry_check()
        self.assertEqual((reg["n"], reg["groups"], reg["engine_active_true"]), (37, {"A": 6, "B": 22, "C": 9}, 0))


class Edges(unittest.TestCase):
    def test_e01_partial(self):
        p, out, _ = case("E01_partial_provenance")
        s1 = next(x for x in raws(out[0]["graph"]["evidence_grouping"]) if x["source_record_id"] == "s1")
        self.assertTrue(any(i.startswith("PARTIAL_PROVENANCE") for i in s1["lineage_issues"]))
        self.assertEqual(next(g for g in out[0]["graph"]["evidence_grouping"]["groups"] if g["group_id"] == s1["group_id"])["dependency_status"], "DEPENDENCY_UNKNOWN")
        self.assertEqual(p.g.nodes["r_missing"]["kind"], "MISSING_SOURCE_RECORD")

    def test_e02_cycle(self):
        e = eg("E02_derivation_cycle")
        a = [x for x in raws(e) if x["source_record_id"] in ("a1", "a2")]
        self.assertEqual(len(a), 2)
        self.assertTrue(all("DERIVATION_CYCLE" in x["lineage_issues"] and x["source_event_id"] is None for x in a))

    def test_e03_event_conflict(self):
        e = eg("E03_event_id_conflict")
        by = {x["source_record_id"]: x for x in raws(e)}
        for k in ("r1", "s2"):
            self.assertTrue(any(i.startswith("EVENT_ID_CONFLICT") for i in by[k]["lineage_issues"]), k)
            self.assertIsNone(by[k]["source_event_id"])
        self.assertEqual(by["r2"]["source_event_id"], "CT003")

    def test_e04_multi_step(self):
        e = eg("E04_multi_step_correction")
        self.assertEqual({x["source_record_id"] for x in raws(e) if x["source_record_id"] in ("r1", "r2", "r3")}, {"r3"})
        self.assertEqual(sorted(g["source_record_ids"][0] for g in grp(e, sup=True)), ["r1", "r2"])

    def test_e05_duplicate_record_id(self):
        p, _, _ = case("E05_duplicate_record_id")
        self.assertTrue(p.case_notes[0].startswith("RAISED:DUPLICATE_RECORD_ID"))
        self.assertEqual(p.docs["r1"].text, R.NEG)

    def test_e06_exact_duplicate(self):
        g = [x for x in grp(eg("E06_exact_duplicate")) if set(x["source_record_ids"]) == {"r1", "r1copy"}]
        self.assertEqual((len(g), g[0]["dependency_status"]), (1, "EXACT_DUPLICATE"))

    def test_e07_fabricated(self):
        self.assertTrue(R.fabricated_judgment_check().startswith("RAISED:SOURCE_NOT_FOUND"))


class Global(unittest.TestCase):
    def test_invariants(self):
        for name in R.CASES:
            for o in case(name)[1]:
                e, v = o["graph"]["evidence_grouping"], o["graph"]["v5_2a"]
                self.assertEqual((e["active_direction_relations_v5_2a1"], v["active_direction_relations_v5_2a"]), (0, 0))
                leg = {(h["hypothesis_id"], i["relation_id"], i["evidence_id"]): i["direction"] for h in v["hypotheses"] if h.get("legacy_v4") for i in h["legacy_v4"]["items"]}
                for r in raws(e):
                    self.assertEqual(r["directional_result"], leg[(r["hypothesis_id"], r["relation_id"], r["evidence_id"])])
                cur = [g for g in e["groups"] if g["dependency_status"] != GP.SUPERSEDED]
                ids = [rid for g in cur for rid in g["raw_judgment_ids"]]
                self.assertEqual(sorted(ids), sorted(r["raw_id"] for r in e["raw_judgments"]), name)
                self.assertFalse(any(g["representative_is_new_judgment"] for g in e["groups"]))
                for h in v["hypotheses"]:
                    self.assertEqual(h.get("supporting_evidence_ids", []), [])


if __name__ == "__main__":
    unittest.main()
