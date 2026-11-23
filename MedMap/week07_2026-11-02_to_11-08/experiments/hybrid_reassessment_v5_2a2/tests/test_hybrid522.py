"""v5-2A.2 테스트. 기대값은 사례 실행 전에 고정(2026-11-08). CASE 02·06 핵심 회귀. 출력에 맞춰 바꾸지 않는다.
CASE 02 의 'v5-2A.1 재계산 값(INSUFFICIENT_EVIDENCE)'은 PHASE 1 재현에서 관찰한 기존 동작을 회귀 기록으로 고정한 것."""
import sys
import unittest
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_v5_2a2 as R  # noqa: E402
from hybrid522 import COUNTERFACTUAL as CFK, EVENT_HISTORY as EHK, PATIENT_HISTORY as PHK  # noqa: E402
from hybrid522 import attribution as AT  # noqa: E402

D = "RAW_DIRECTIONAL_JUDGMENT"


@lru_cache(maxsize=None)
def case(name):
    return R.run_case(name)


def res(name):
    return case(name)[1]


def event(r, key):
    return next(e for e in r[EHK]["events"] if e["event_key"] == key)


def version(e, rec):
    return next(v for v in e["versions"] if v["source_record_id"] == rec)


def snap(r, t):
    return next(s for s in r[PHK]["snapshots"] if s["as_of"] == t)


def summ(v, rel):
    return next(j for j in v["direct_judgment_summary"] if j["relation_id"] == rel)


def status_at(v, t):
    return next(x["version_status"] for x in v["status_timeline"] if x["as_of"] == t)


def cfs(r, key):
    return [c for c in r[CFK]["comparisons"] if c.get("changed_event_key") == key]


class Cases(unittest.TestCase):
    def test_c01_correction(self):
        e = event(res("C01_neg_to_pos_correction"), "CT001@E1")
        v1, v2 = version(e, "r1"), version(e, "r1c")
        self.assertEqual((v1["version_index"], v2["version_index"], v1["chain_index"], v2["chain_index"], v1["correction_time"]), (1, 2, 1, 1, 12.0))
        j = summ(v1, "PE-CTPA-NEGATIVE")
        self.assertEqual((j["first_observed_as_of"], j["first_observed_result"][0], j["stable_within_validity"]), (10.0, "WEAKEN", True))
        self.assertTrue(any(x["relation_id"] == "PE-CTPA-POSITIVE" for x in v2["direct_judgment_summary"]))
        c = cfs(res("C01_neg_to_pos_correction"), "CT001@E1")
        self.assertEqual((len(c), c[0]["performed"], c[0]["fixed_context_identical"]), (1, True, True))

    def test_c02_other_result_not_in_event_history(self):
        r = res("C02_other_result_between")
        e = event(r, "CT001@E1")
        v1 = version(e, "r1")
        recs = {o["raw_id"].split(":")[-2] for v in e["versions"] for o in v["direct_judgment_observations"]}
        self.assertEqual(recs, {"r1", "r1c"})                                     # 트로포닌·노트 판단 유입 없음
        self.assertFalse(any("OBS:t11" in o["raw_id"] or o["hypothesis_id"] == "h_acs" for v in e["versions"] for o in v["direct_judgment_observations"]))
        j = summ(v1, "PE-CTPA-NEGATIVE")
        self.assertEqual((j["first_observed_as_of"], j["first_observed_result"][0], j["stable_within_validity"]), (10.0, "WEAKEN", False))
        self.assertIn("n2", j["context_record_ids"])
        s11 = snap(r, 11.0)
        self.assertTrue({"n2", "OBS:t11"} <= set(s11["visible_record_ids"]))   # 환자 전체 이력에는 포함(정상)
        ch = next(c for c in s11["diff_from_previous"]["judgment_changes"] if c["raw_id"] == "RAW:h_pe:PE-CTPA-NEGATIVE:EV:r1:0")
        self.assertEqual([(c["cause"], c["records"]) for c in ch["causes"]], [("PATIENT_CONTEXT_CHANGED", ["n2"])])
        sup = [g for g in r["v5_2a1_compat"]["groups"] if g["dependency_status"] == "SUPERSEDED_EVIDENCE" and g["source_record_ids"] == ["r1"]]
        self.assertEqual((len(sup), sup[0]["directional_result"]), (1, "INSUFFICIENT_EVIDENCE"))   # v5-2A.1 재계산 값(재현된 혼동)

    def test_c03_no_other_results_stable(self):
        r = res("C03_correction_without_other_results")
        j = summ(version(event(r, "CT001@E1"), "r1"), "PE-CTPA-NEGATIVE")
        self.assertTrue(j["stable_within_validity"])
        c = cfs(r, "CT001@E1")[0]
        b = [x for x in c["before_result"]["raw_judgments"] if x["source_record_id"] == "r1" and x["relation_id"] == "PE-CTPA-NEGATIVE"]
        self.assertEqual(b[0]["directional_result"], j["first_observed_result"][0])

    def test_c04_patient_vs_event(self):
        r = res("C04_patient_vs_event_differ")
        j = summ(version(event(r, "CT001@E1"), "r1"), "PE-CTPA-NEGATIVE")
        p = next(x for x in snap(r, 11.5)["raw_judgments"] if x["raw_id"] == "RAW:h_pe:PE-CTPA-NEGATIVE:EV:r1:0")
        self.assertNotEqual(p["directional_result"], j["first_observed_result"][0])

    def test_c05_other_test_kept(self):
        r = res("C05_other_test_kept")
        rid = "USE:h_acs:INJ_ABOVE_SEX_SPECIFIC_URL:OBS:t11"
        a, b = (next(x for x in snap(r, t)["raw_judgments"] if x["raw_id"] == rid) for t in (11.5, 12.5))
        self.assertEqual((a["directional_result"], a["hold_reason"]), (b["directional_result"], b["hold_reason"]))
        lab = event(r, "LAB-T11@E1")
        self.assertEqual(len(lab["versions"]), 1)
        self.assertTrue(all(j["stable_within_validity"] for j in lab["versions"][0]["direct_judgment_summary"]))

    def test_c06_counterfactual_only_ct_changed(self):
        p, r, _ = case("C06_counterfactual_ct_only")
        c = cfs(r, "CT001@E1")
        self.assertEqual(len(c), 1)
        c = c[0]
        self.assertEqual((c["performed"], c["fixed_context_identical"], c["valid"]), (True, True, True))
        orig_vis = sorted(set(p.visible_records(12.5)) - {"r1", "r1c"})
        self.assertEqual(c["fixed_context_record_ids"], orig_vis)
        self.assertTrue({"n1", "n2"} <= set(c["fixed_context_record_ids"]) and not {"r1", "r1c"} & set(c["fixed_context_record_ids"]))
        self.assertIn("OBS:t11", [o[0] for o in c["fixed_context"]["structured_observations"]])
        self.assertTrue(c["difference"])
        self.assertEqual((c["comparison_type"], c["historical_status"], c["causal_status"], c["replay_type"]),
                         ("CORRECTION_ONLY_COUNTERFACTUAL", "NOT_HISTORICAL_OBSERVATION", "NOT_CAUSAL_PROOF", "COUNTERFACTUAL_REPLAY"))

    def test_c07_counterfactual_separate_and_injected(self):
        r = res("C07_counterfactual_vs_history")
        c = cfs(r, "CT001@E1")[0]
        self.assertEqual([x["record_key"] for x in c["injected_versions"]], ["r1c"])
        self.assertEqual(status_at(version(event(r, "CT001@E1"), "r1c"), 10.5), "NOT_YET_AVAILABLE")
        for s in r[PHK]["snapshots"]:
            self.assertNotIn("historical_status", s)
            self.assertFalse(any(x["source_record_id"] == "r1c" for x in s["raw_judgments"]))

    def test_c08_before(self):
        r = res("C08_before_correction")
        e = event(r, "CT001@E1")
        self.assertEqual((status_at(version(e, "r1"), 11.0), status_at(version(e, "r1c"), 11.0)), ("ACTIVE", "NOT_YET_AVAILABLE"))
        self.assertEqual({x["source_record_id"] for x in snap(r, 11.0)["raw_judgments"]} & {"r1", "r1c"}, {"r1"})

    def test_c09_after(self):
        r = res("C09_after_correction")
        e = event(r, "CT001@E1")
        self.assertEqual((status_at(version(e, "r1"), 12.5), status_at(version(e, "r1c"), 12.5)), ("SUPERSEDED", "ACTIVE"))
        self.assertEqual({x["source_record_id"] for x in snap(r, 12.5)["raw_judgments"]} & {"r1", "r1c"}, {"r1c"})
        self.assertEqual(next(p for p in snap(r, 12.5)["provenance"] if p["record_key"] == "r1")["status_at_as_of"], "SUPERSEDED")

    def test_c10_three_step(self):
        r = res("C10_three_step_correction")
        e = event(r, "CT001@E1")
        self.assertEqual([(v["source_record_id"], v["version_index"], status_at(v, 9.0)) for v in e["versions"]],
                         [("r1", 1, "SUPERSEDED"), ("r2", 2, "SUPERSEDED"), ("r3", 3, "ACTIVE")])
        self.assertEqual([(c["before_record_id"], c["after_record_id"]) for c in cfs(r, "CT001@E1")], [("r1", "r2"), ("r2", "r3")])
        self.assertEqual([summ(version(e, k), rel)["first_observed_as_of"] for k, rel in (("r1", "PE-CTPA-POSITIVE"), ("r2", "PE-CTPA-NEGATIVE"), ("r3", "PE-CTPA-POSITIVE"))],
                         [4.0, 6.0, 8.0])

    def test_c11_conflict(self):
        r = res("C11_conflict_no_correction")
        e = event(r, "CT001@E1")
        st = next(x for x in e["state_timeline"] if x["as_of"] == 5.0)
        self.assertEqual((st["event_state"], sorted(st["active_version_ids"])), ("CONFLICTING_EVENT_EVIDENCE_HOLD", sorted(v["version_id"] for v in e["versions"])))
        self.assertEqual({v["chain_index"] for v in e["versions"]}, {1, 2})
        self.assertEqual(cfs(r, "CT001@E1"), [])

    def test_c12_findings_separate(self):
        r = res("C12_same_event_different_findings")
        e = event(r, "CT001@E1")
        v1, v2 = version(e, "r1"), version(e, "r1c")
        for v in (v1, v2):
            kinds = {(j["raw_kind"], j["relation_id"]) for j in v["direct_judgment_summary"]}
            self.assertIn(("RAW_CRITERION_INPUT", "PERI_EFFUSION"), kinds)
        self.assertIn((D, "PE-CTPA-POSITIVE"), {(j["raw_kind"], j["relation_id"]) for j in v1["direct_judgment_summary"]})
        c = cfs(r, "CT001@E1")[0]
        self.assertNotIn("h_peri", c["evaluation_difference"])
        self.assertFalse(any(d["hypothesis_id"] == "h_peri" and d["record_role"] == "CHANGED_EVENT_VERSION" and d["before"] and d["after"] for d in c["difference"]))

    def test_c13_no_event(self):
        r = res("C13_no_event_id")
        self.assertEqual(r[EHK]["events"], [])
        u = {x["record_key"]: x for x in r[EHK]["unresolved_event_links"]}
        self.assertEqual(u["r1c"]["status"], "UNRESOLVED_EVENT_LINK")
        self.assertTrue(u["r1c"]["judgment_observations"])
        self.assertTrue(all(o["attribution"]["status"] == "ATTRIBUTION_UNRESOLVED" for o in u["r1c"]["judgment_observations"]))
        self.assertEqual(r[CFK]["comparisons"], [])

    def test_c14_unresolved_episode(self):
        r = res("C14_unresolved_episode")
        e = event(r, "CT001@UNRESOLVED_EPISODE_LINK")
        self.assertEqual([o for v in e["versions"] for o in v["direct_judgment_observations"]], [])

    def test_c15_episodes(self):
        r = res("C15_different_episodes")
        keys = {e["event_key"] for e in r[EHK]["events"]}
        self.assertTrue({"CT001@E0", "CT001@E2"} <= keys)
        self.assertEqual([v["source_record_id"] for v in event(r, "CT001@E0")["versions"]], ["r0"])
        self.assertEqual([v["source_record_id"] for v in event(r, "CT001@E2")["versions"]], ["s2"])

    def test_c16_not_attributed(self):
        r = res("C16_judgment_not_attributed")
        u = {x["record_key"]: x for x in r[EHK]["unresolved_event_links"]}
        obs = u["l1"]["judgment_observations"]
        self.assertTrue(obs)
        self.assertTrue(all(o["attribution"]["status"] == "ATTRIBUTION_UNRESOLVED" and o["attribution"]["reason"] == "UNRESOLVED_EVENT_LINK" for o in obs))

    def test_c17_context_dependency(self):
        r = res("C17_multi_context_dependency")
        o = [x for x in version(event(r, "CT001@E1"), "r1")["direct_judgment_observations"] if x["as_of"] == 11.5]
        self.assertEqual(o[0]["attribution"]["status"], "DIRECT_WITH_CONTEXT_DEPENDENCY")
        self.assertTrue({"n1", "n2"} <= set(o[0]["context_record_ids"]))

    def test_c18_fabricated(self):
        a = AT.judgment_attribution({"source_record_id": "zzz", "context_record_ids": []}, {})
        self.assertEqual((a["status"], a["event_key"]), ("ATTRIBUTION_UNRESOLVED", None))
        self.assertTrue(R.R1.fabricated_judgment_check().startswith("RAISED:SOURCE_NOT_FOUND"))

    def test_c19_cycle(self):
        u = R.correction_cycle_unit()
        self.assertEqual((u["held_records"], u["events"]), (["a", "b"], []))
        self.assertTrue(all("CORRECTION_CYCLE" in i for _, i in u["unresolved"]))

    def test_c20_missing_parent(self):
        p, r, _ = case("C20_missing_parent")
        self.assertTrue(p.case_notes[0].startswith("RAISED_KEYERROR"))
        u = {x["record_key"]: x for x in r[EHK]["unresolved_event_links"]}
        self.assertTrue(any(i.startswith("PARTIAL_PROVENANCE") for i in u["s1"]["issues"]))

    def test_c20b_no_partial_state(self):
        # 실행 중 발견한 결함의 회귀 테스트(2026-11-08 추가, 사전 고정 기대값 아님): 없는 정정 대상 → 상태 변경 없이 거부
        p, _, cmpr = case("C20_missing_parent")
        self.assertEqual(p.case_notes[1], "PARTIAL_STATE_AFTER_ERROR:docs_has_r1c=False")
        self.assertNotIn("REC:r1c", p.g.nodes)
        self.assertTrue(cmpr["identical"])

    def test_c21_conflicting_ids(self):
        r = res("C21_conflicting_event_ids")
        u = {x["record_key"]: x for x in r[EHK]["unresolved_event_links"]}
        self.assertEqual(u["r1"]["status"], "INVALID_EVENT_METADATA")
        self.assertTrue(any(i.startswith("EVENT_ID_CONFLICT") for i in u["r1"]["issues"]))
        self.assertTrue(all(o["attribution"]["status"] == "ATTRIBUTION_UNRESOLVED" for o in u["r1"]["judgment_observations"]))

    def test_c22_partial_multi_step(self):
        r = res("C22_partial_multi_step")
        e = event(r, "CT001@E1")
        self.assertEqual([status_at(v, 7.0) for v in e["versions"]], ["SUPERSEDED", "ACTIVE", "NOT_YET_AVAILABLE"])
        self.assertEqual({x["source_record_id"] for x in snap(r, 7.0)["raw_judgments"]} & {"r1", "r2", "r3"}, {"r2"})

    def test_c23_c24_c25_graph_flat(self):
        for name in R.CASES:
            self.assertTrue(case(name)[2]["identical"], (name, case(name)[2]["diff_paths"][:5]))

    def test_c26_v521_compat(self):
        for name in R.CASES:
            r = res(name)
            hz = snap(r, r["reference_time"])
            self.assertEqual(sorted((x["raw_id"], x["directional_result"]) for x in hz["raw_judgments"]),
                             sorted((x["raw_id"], x["directional_result"]) for x in r["v5_2a1_compat"]["raw_judgments"]), name)

    def test_c27_registry(self):
        reg = R.R1.R52.registry_check()
        self.assertEqual((reg["n"], reg["groups"], reg["engine_active_true"]), (37, {"A": 6, "B": 22, "C": 9}, 0))

    def test_c28_no_new_direction(self):
        from hybrid522 import comparator as CM
        for name in R.CASES:
            p, r, _ = case(name)
            self.assertEqual(r["active_direction_relations_v5_2a2"], 0)
            for s in r[PHK]["snapshots"]:
                leg = CM.legacy_items(p, s["as_of"], "graph")
                for x in s["raw_judgments"]:
                    if x["raw_kind"] == D:
                        self.assertEqual(x["directional_result"], leg[(x["hypothesis_id"], x["relation_id"], x["evidence_id"])]["direction"])
                    else:
                        self.assertTrue(x["directional_result"].startswith("NONE"))
                self.assertFalse(any(x["raw_kind"] == D and x["hypothesis_id"] in ("h_acs", "h_peri") for x in s["raw_judgments"]))
            snap_ids = {x["raw_id"] for s in r[PHK]["snapshots"] for x in s["raw_judgments"]}
            ev_ids = {o["raw_id"] for e in r[EHK]["events"] for v in e["versions"] for o in v["direct_judgment_observations"]}
            self.assertTrue(ev_ids <= snap_ids, name)


class Invariants(unittest.TestCase):
    def test_event_history_only_own_record(self):
        for name in R.CASES:
            r = res(name)
            for e in r[EHK]["events"]:
                for v in e["versions"]:
                    for o in v["direct_judgment_observations"]:
                        s = snap(r, o["as_of"])
                        x = next(y for y in s["raw_judgments"] if y["raw_id"] == o["raw_id"])
                        self.assertEqual(x["source_record_id"], v["source_record_id"])

    def test_no_future_in_history(self):
        for name in R.CASES:
            r = res(name)
            for s in r[PHK]["snapshots"]:
                for p in s["provenance"]:
                    if p["status_at_as_of"] == "VISIBLE":
                        self.assertLessEqual(p["available_time"], s["as_of"])

    def test_counterfactual_labels_and_context(self):
        for name in R.CASES:
            for c in res(name)[CFK]["comparisons"]:
                self.assertEqual((c["historical_status"], c["causal_status"]), ("NOT_HISTORICAL_OBSERVATION", "NOT_CAUSAL_PROOF"))
                if c["performed"]:
                    self.assertTrue(c["fixed_context_identical"], name)


if __name__ == "__main__":
    unittest.main()
