"""v5-2A 테스트. 기대값은 사례 실행 전에 고정(2026-11-08). 출력에 맞춰 바꾸지 않는다."""
import json
import sys
import unittest
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_v5_2a as R  # noqa: E402

T, F, U, C = "TRUE", "FALSE", "UNKNOWN", "CONFLICT"
NOR = "NOT_EVALUATED_NO_VERIFIED_RULE"


@lru_cache(maxsize=None)
def case(name):
    return R.run_case(name)


def res(name, i=0):
    return case(name)[1][i]["graph"]


def hyp(r, hid):
    return next(h for h in r["hypotheses"] if h["hypothesis_id"] == hid)


def crit(h, cid):
    return next(x for x in h["condition_evaluations"] if x["criterion_id"] == cid)


def ucls(r, item_id):
    return {u["class"] for u in r["unmapped_and_unevaluated_findings"] if u["item_id"] == item_id}


def items_where(r, pred):
    return sorted(i for i, d in r["dependency_items"].items() if pred(d))


class Cases(unittest.TestCase):
    def test_c01_three_hypotheses(self):
        r = res("C01_three_hypotheses")
        self.assertEqual({h["hypothesis_id"] for h in r["hypotheses"]}, {"h_pe", "h_acs", "h_peri"})
        self.assertEqual(r["working_diagnosis"], ["h_pe"])
        p, a, pe = hyp(r, "h_peri"), hyp(r, "h_acs"), hyp(r, "h_pe")
        self.assertEqual([crit(p, k)["evaluation_result"] for k in ("CLINICAL_PRESENTATION", "PERI_RUB", "PERI_ECG")], [T, T, T])
        self.assertEqual((crit(a, "INJ_ABOVE_SEX_SPECIFIC_URL")["evaluation_result"], crit(a, "INJ_RISE_OR_FALL_REPORTED")["evaluation_result"]), (T, U))
        self.assertEqual(crit(a, "ACS_DIAGNOSTIC_CRITERIA")["evaluation_result"], NOR)
        self.assertEqual(crit(pe, "PE_V5_CRITERIA")["evaluation_result"], NOR)
        self.assertEqual((a["directional_relation_status"], p["directional_relation_status"], pe["directional_relation_status"]),
                         ("NO_VERIFIED_DIRECTIONAL_RELATION", "NO_VERIFIED_DIRECTIONAL_RELATION", "LEGACY_V4_UNVALIDATED"))
        for h in r["hypotheses"]:
            self.assertEqual((h["supporting_evidence_ids"], h["weakening_evidence_ids"]), ([], []))
        self.assertIn("NOT_ASSUMED", r["mutual_exclusivity"])

    def test_c02_working_dx_vs_ai(self):
        p, out = case("C02_working_dx_vs_ai_candidate")
        self.assertTrue(all(n.startswith("RAISED") for n in p.case_notes) and len(p.case_notes) == 2)
        r = out[0]["graph"]
        self.assertEqual(len(r["hypotheses"]), 2)
        ai = hyp(r, "h_mi_ai")
        self.assertEqual((ai["hypothesis_source"], ai["physician_confirmation_status"], ai["is_working_diagnosis"]), ("AI_CANDIDATE_UNCONFIRMED", "UNCONFIRMED", False))
        self.assertEqual(r["working_diagnosis"], ["h_peri"])
        self.assertTrue(any(c["concept_id"] == "V5:DX:MI" and c["surface"] == "NSTEMI" for c in r["ai_candidates_unconfirmed"]))

    def test_c03_shared_not_support(self):
        r = res("C03_shared_evidence")
        sh = [s for s in r["shared_findings"] if s["item_id"] == "OBS:t0"]
        self.assertEqual(len(sh), 1)
        self.assertEqual(sh[0]["hypotheses"], ["h_acs", "h_mi"])
        self.assertTrue(sh[0]["interpretation"].startswith("USED_IN_MULTIPLE_EVALUATIONS_NOT_SUPPORT"))
        self.assertEqual(r["dependency_items"]["OBS:t0"]["shared_evidence_hypotheses"], ["h_acs", "h_mi"])
        for h in r["hypotheses"]:
            self.assertEqual(h["supporting_evidence_ids"], [])

    def test_c04_unverified_relation_not_unmapped(self):
        r = res("C04_unverified_relation")
        self.assertNotIn("ECG:e1:0", hyp(r, "h_acs")["evidence_ids"])
        self.assertEqual(ucls(r, "ECG:e1:0"), {"LINKED_CONCEPT_NO_VERIFIED_RULE"})

    def test_c05_same_text_no_metadata(self):
        r = res("C05_similar_finding_no_metadata")
        rub = items_where(r, lambda d: d["item_kind"] == "EVIDENCE" and d["evidence_id"] in hyp(r, "h_peri")["evidence_links"]
                          and "PERI_RUB" in hyp(r, "h_peri")["evidence_links"][d["evidence_id"]]["criteria"])
        self.assertEqual(len(rub), 2)
        d1, d2 = (r["dependency_items"][i] for i in rub)
        self.assertNotEqual(d1["dependency_group_id"], d2["dependency_group_id"])
        self.assertEqual(r["duplicate_evidence_groups"], [])
        n2 = next(d for d in (d1, d2) if d["source_record_id"] == "n2")
        self.assertEqual(n2["dependency_status"], "DEPENDENCY_UNKNOWN")
        k = crit(hyp(r, "h_peri"), "PERI_ADDITIONAL_AT_LEAST_2")["kofn"]
        self.assertEqual(k["confirmed_true_count"], 1)                          # 같은 기준 두 기록 → 1개로 셈

    def test_c06_repeated_statement_same_event(self):
        r = res("C06_same_result_repeated")
        g = [d for d in r["duplicate_evidence_groups"] if set(d["records"]) == {"r1", "s1", "d1"}]
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["dependency_group_id"], g[0]["relation"], g[0]["independent_source_events"]), ("EVT:CTPA-1", "DERIVED_FROM_SAME_SOURCE", 1))

    def test_c07_repeated_tests_distinct(self):
        r = res("C07_repeated_tests")
        for i in ("OBS:t0", "OBS:t1", "OBS:t2"):
            self.assertEqual(r["dependency_items"][i]["dependency_status"], "DISTINCT_OBSERVATION")
        self.assertEqual(r["duplicate_evidence_groups"], [])
        self.assertEqual(len(hyp(r, "h_acs")["series"][0]["points"]), 3)

    def test_c08_same_event_different_values(self):
        r = res("C08_same_event_different_values")
        self.assertEqual(len(r["value_discrepancies"]), 1)
        its = r["value_discrepancies"][0]["items"]
        self.assertIn("OBS:t1", its)
        self.assertTrue(any(i.startswith("OBS:n1:") for i in its))
        self.assertTrue(set(its) <= set(hyp(r, "h_acs")["evidence_ids"]))
        self.assertTrue(r["value_discrepancies"][0]["resolution"].startswith("NOT_RESOLVED"))

    def test_c09_duplicate_vs_repeat(self):
        r = res("C09_duplicate_vs_repeat")
        self.assertEqual(len(r["duplicate_evidence_groups"]), 1)
        m = r["duplicate_evidence_groups"][0]["members"]
        self.assertIn("OBS:t0", m)
        self.assertTrue(any(i.startswith("OBS:n1:") for i in m))
        self.assertEqual(r["dependency_items"]["OBS:t2"]["dependency_status"], "DISTINCT_OBSERVATION")
        self.assertIsNone(r["dependency_items"]["OBS:t2"]["duplicate_group_id"])
        self.assertEqual(len(hyp(r, "h_acs")["series"][0]["points"]), 3)        # 중복 표시만, 삭제 없음

    def test_c10_derived_findings_kept_separate(self):
        r = res("C10_derived_findings_same_event")
        a, b = r["dependency_items"]["ECG:e1:0"], r["dependency_items"]["ECG:e1:1"]
        self.assertEqual((a["dependency_group_id"], b["dependency_group_id"]), ("EVT:ECG-1", "EVT:ECG-1"))
        self.assertEqual((a["dependency_status"], a["duplicate_group_id"], b["duplicate_group_id"]), ("DERIVED_FROM_SAME_SOURCE", None, None))
        h = hyp(r, "h_peri")
        self.assertEqual(crit(h, "PERI_ECG")["evaluation_result"], T)
        self.assertEqual(crit(h, "PERI_ADDITIONAL_AT_LEAST_2")["kofn"]["confirmed_true_count"], 1)

    def test_c11_true(self):
        h = hyp(res("C11_condition_true"), "h_peri")
        self.assertEqual([crit(h, k)["evaluation_result"] for k in ("PERI_RUB", "PERI_ECG", "PERI_CRP", "PERI_EFFUSION", "PERI_ADDITIONAL_AT_LEAST_2")], [T, T, T, F, T])
        self.assertEqual(h["research_classifications"][0]["guideline_classification"], "DEFINITE")

    def test_c12_false(self):
        h = hyp(res("C12_condition_false"), "h_peri")
        for k in ("PERI_RUB", "PERI_ECG", "PERI_CRP", "PERI_EFFUSION", "PERI_CMR", "PERI_ADDITIONAL_AT_LEAST_2"):
            self.assertEqual(crit(h, k)["evaluation_result"], F, k)
            self.assertIsNone(crit(h, k)["gap"])

    def test_c13_unknown_not_false(self):
        h = hyp(res("C13_condition_unknown"), "h_peri")
        for k in ("PERI_RUB", "PERI_ECG", "PERI_CRP", "PERI_EFFUSION", "PERI_CMR"):
            self.assertEqual(crit(h, k)["evaluation_result"], U)
            self.assertEqual(crit(h, k)["gap"]["category"], "MISSING_INFORMATION")

    def test_c14_conflict(self):
        r = res("C14_conflict")
        c = crit(hyp(r, "h_peri"), "PERI_RUB")
        self.assertEqual((c["evaluation_result"], c["gap"]["category"]), (C, "CONFLICTING_INFORMATION"))
        self.assertTrue(any(g["criterion_id"] == "PERI_RUB" for g in r["conflicting_information"]))

    def test_c15_order_only_pending(self):
        r = res("C15_order_only")
        c = crit(hyp(r, "h_acs"), "INJ_ABOVE_SEX_SPECIFIC_URL")
        self.assertEqual((c["evaluation_result"], c["gap"]["category"], c["gap"]["test_status"]), (U, "PENDING_RESULT", {"trop1": "PENDING"}))
        self.assertTrue(c["gap"]["action"].startswith("NONE"))
        self.assertEqual(ucls(r, "n1:TROPONIN_MENTION"), {"TEST_NAME_MENTION_ONLY"})

    def test_c16_result_availability(self):
        r4, r5 = res("C16_result_availability", 0), res("C16_result_availability", 1)
        c4 = crit(hyp(r4, "h_acs"), "INJ_ABOVE_SEX_SPECIFIC_URL")
        self.assertEqual((c4["evaluation_result"], c4["gap"]["category"]), (U, "PENDING_RESULT"))
        self.assertNotIn("OBS:late", hyp(r4, "h_acs")["evidence_ids"])
        self.assertEqual(ucls(r4, "OBS:late"), {"RESULT_NOT_YET_AVAILABLE"})
        self.assertEqual(crit(hyp(r5, "h_acs"), "INJ_ABOVE_SEX_SPECIFIC_URL")["evaluation_result"], T)
        self.assertIn("OBS:late", hyp(r5, "h_acs")["evidence_ids"])

    def test_c17_correction(self):
        p, out = case("C17_report_correction")
        c3, c5 = (crit(hyp(o["graph"], "h_peri"), "PERI_EFFUSION") for o in out)
        self.assertEqual(c3["evaluation_result"], F)
        self.assertTrue(all(s.startswith("EV:m1:") for s in c3["source_evidence_ids"]) and c3["source_evidence_ids"])
        self.assertEqual(c5["evaluation_result"], T)
        self.assertTrue(all(s.startswith("EV:m1c:") for s in c5["source_evidence_ids"]) and c5["source_evidence_ids"])
        m1 = next(x for x in out[1]["graph"]["source_provenance"] if x["record_key"] == "m1")
        self.assertEqual((m1["status_at_as_of"], m1["corrected_by"]), ("SUPERSEDED", ["m1c"]))
        self.assertIn("REC:m1", p.g.nodes)

    def test_c18_episode_separation(self):
        r = res("C18_past_vs_current_episode")
        a, pe = hyp(r, "h_acs"), hyp(r, "h_pe")
        self.assertEqual(crit(a, "INJ_ABOVE_SEX_SPECIFIC_URL")["evaluation_result"], U)
        self.assertNotIn("OBS:old", a["evidence_ids"])
        self.assertIn("OBS:old", a["excluded_other_episode_items"])
        self.assertFalse(any(i.startswith("EV:r0:") for i in pe["evidence_ids"]))

    def test_c19_unresolved_episode(self):
        r = res("C19_unresolved_episode")
        c = crit(hyp(r, "h_peri"), "PERI_CRP")
        self.assertEqual((c["evaluation_result"], c["gap"]["category"]), (U, "UNRESOLVED_EPISODE"))
        self.assertTrue(c["gap"]["unresolved_episode_items"])
        for i in c["gap"]["unresolved_episode_items"]:
            self.assertEqual(ucls(r, i), {"UNRESOLVED_EPISODE"})

    def test_c20_grade_vs_direction(self):
        r = res("C20_pericarditis_grade_vs_direction")
        h = hyp(r, "h_peri")
        cl = h["research_classifications"][0]
        self.assertEqual(cl["guideline_classification"], "DEFINITE")
        self.assertTrue(cl["evidence_direction"].startswith("NOT_DERIVED"))
        self.assertEqual((h["directional_relation_status"], h["physician_confirmation_status"], h["supporting_evidence_ids"], r["working_diagnosis"]),
                         ("NO_VERIFIED_DIRECTIONAL_RELATION", "UNCONFIRMED", [], []))

    def test_c21_troponin_not_mi(self):
        h = hyp(res("C21_troponin_change_not_mi"), "h_mi")
        self.assertEqual(crit(h, "ACUTE_INJURY_RESEARCH")["evaluation_result"], T)
        self.assertEqual(crit(h, "MI_ISCHEMIA_EVIDENCE")["evaluation_result"], NOR)
        self.assertTrue(h["research_classifications"][0]["mi_assessment"].startswith("NOT_ASSESSED"))
        self.assertEqual(h["supporting_evidence_ids"], [])

    def test_c22_pr_depression(self):
        p, out = case("C22_pr_depression_mislink")
        r = out[0]["graph"]
        ecg_dep = [i for i, n in p.g.nodes.items() if n["kind"] == "EVIDENCE" and n["source_record_id"] == "e1" and n.get("base_concept") == "HP:0000716"]
        note_dep = [i for i, n in p.g.nodes.items() if n["kind"] == "EVIDENCE" and n["source_record_id"] == "n1" and n.get("base_concept") == "HP:0000716"]
        self.assertEqual((len(ecg_dep), len(note_dep)), (1, 1))
        self.assertEqual(ucls(r, ecg_dep[0]), {"EXCLUDED_KNOWN_MISLINK"})
        self.assertEqual(ucls(r, note_dep[0]), {"LINKED_CONCEPT_NO_VERIFIED_RULE"})
        self.assertIn("PERI_ECG", hyp(r, "h_peri")["evidence_links"]["ECG:e1:0"]["criteria"])

    def test_c23_test_name_mention(self):
        p, out = case("C23_test_name_mention")
        r = out[0]["graph"]
        ctpa = [i for i, n in p.g.nodes.items() if n["kind"] == "EVIDENCE" and n.get("base_concept") == "CTPA_STUDY"]
        self.assertEqual(len(ctpa), 1)
        self.assertEqual(ucls(r, ctpa[0]), {"TEST_NAME_MENTION_ONLY"})
        self.assertEqual(ucls(r, "n1:TROPONIN_MENTION"), {"TEST_NAME_MENTION_ONLY"})
        a = hyp(r, "h_acs")
        self.assertFalse(any(x["evaluation_result"] == T for x in a["condition_evaluations"]))
        self.assertEqual(crit(a, "INJ_ABOVE_SEX_SPECIFIC_URL")["gap"]["category"], "MISSING_INFORMATION")

    def test_c24_pe_weaken_not_acs_support(self):
        r = res("C24_pe_weaken_not_acs_support")
        pe, a = hyp(r, "h_pe"), hyp(r, "h_acs")
        self.assertIn("WEAKEN", {i["direction"] for i in pe["legacy_v4"]["items"]})
        self.assertEqual((a["supporting_evidence_ids"], a["weakening_evidence_ids"], a["directional_relation_status"]), ([], [], "NO_VERIFIED_DIRECTIONAL_RELATION"))
        self.assertFalse(any(i.startswith("EV:r1:") for i in a["evidence_ids"]))
        self.assertNotIn('"SUPPORT"', json.dumps(a))

    def test_c25_concurrent(self):
        r = res("C25_concurrent_diseases")
        self.assertEqual(hyp(r, "h_peri")["research_classifications"][0]["guideline_classification"], "DEFINITE")
        self.assertEqual(crit(hyp(r, "h_inj"), "ACUTE_INJURY_RESEARCH")["evaluation_result"], T)
        self.assertTrue(all(h["hypothesis_status_at_as_of"] == "EVALUATED" for h in r["hypotheses"]))
        self.assertFalse({"rank", "ranking", "probability", "score"} & set(json.dumps(r).replace('"', " ").split()))
        self.assertIn("NOT_ASSUMED", r["mutual_exclusivity"])

    def test_c26_graph_flat_all_cases(self):
        n = 0
        for name in R.CASES:
            for o in case(name)[1]:
                n += 1
                self.assertTrue(o["flat_equal"], (name, o["as_of"], o["diff_paths"][:5]))
                self.assertTrue(set(o["comparison_subgraph"]["edge_types"]) <= {"EVALUATES_CRITERION", "USES_INPUT"})
        self.assertGreaterEqual(n, 30)
        r3, r10 = res("C26_graph_flat_full", 0), res("C26_graph_flat_full", 3)
        self.assertEqual(hyp(r3, "h_late")["hypothesis_status_at_as_of"], "NOT_APPLICABLE_AT_AS_OF")
        self.assertEqual(hyp(r10, "h_late")["hypothesis_status_at_as_of"], "EVALUATED")

    def test_c27_registry(self):
        reg = R.registry_check()
        self.assertEqual((reg["n"], reg["groups"], reg["engine_active_true"]), (37, {"A": 6, "B": 22, "C": 9}, 0))
        self.assertFalse(any(c["used_in_v5_2a_comparison"] for c in reg["candidates"]))

    def test_c28_unsupported(self):
        p, out = case("C28_unsupported_concept")
        r = out[0]["graph"]
        self.assertTrue(p.case_notes[0].startswith("RAISED"))
        amb = [i for i, n in p.g.nodes.items() if n["kind"] == "EVIDENCE" and n["source_record_id"] == "n2"]
        self.assertEqual([ucls(r, i) for i in amb], [{"UNMAPPED_FINDING"}])
        self.assertEqual(ucls(r, "n1:ECG_STATEMENT"), {"UNSUPPORTED_EXTRACTION"})
        self.assertEqual(crit(hyp(r, "h_acs"), "ACS_DIAGNOSTIC_CRITERIA")["gap"]["category"], "NO_VERIFIED_RULE")


class Global(unittest.TestCase):
    def test_no_direction_and_v51_consistent(self):
        for name in R.CASES:
            p, out = case(name)
            self.assertFalse([e for v in p.g.out.values() for e in v if e["rel"] in ("SUPPORTS_HYPOTHESIS", "WEAKENS_HYPOTHESIS")], name)
            for o in out:
                g = o["graph"]
                self.assertEqual((g["active_direction_relations_v5_2a"], g["clinical_validation_status"]), (0, "NOT_EVALUATED"))
                for h in g["hypotheses"]:
                    self.assertEqual(h.get("v51_consistency_mismatches", []), [], (name, h["hypothesis_id"]))
                    self.assertEqual(h.get("supporting_evidence_ids", []), [])

    def test_unknown_never_false_without_negative_record(self):
        h = hyp(res("C13_condition_unknown"), "h_peri")
        self.assertFalse(any(x["evaluation_result"] == F for x in h["condition_evaluations"]))


if __name__ == "__main__":
    unittest.main()
