"""엔진 자동 테스트(합성 자료만). 예상 결과는 각 테스트 안에 먼저 적고 엔진 출력과 비교한다.
T1~T10 시나리오 · 단위 · 통합 · 불변성 · 오류 주입."""
import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap_demo.assess import assess, counterfactual, diff, provenance_graph  # noqa: E402
from medmap_demo.events import EventStore, IngestError, make_event  # noqa: E402
from medmap_demo.model_adapter import DModel  # noqa: E402
from medmap_demo.replay import Case, replay  # noqa: E402
from medmap_demo.scenarios import at, demo_case  # noqa: E402

KST = timezone(timedelta(hours=9))
T0 = datetime(2026, 3, 1, 9, 0, tzinfo=KST)
CASE = Case("P1", ("F1",), "H1", "pulmonary embolism")


def m(x):
    return T0 + timedelta(minutes=x)


def E(eid, status, rec, lin="L1", **kw):
    d = dict(patient_id="P1", feed_id="F1", event_id=eid, lineage_id=lin, kind="LAB", item="D-dimer", status=status, recorded_at=at(rec),
             hypothesis_ids=["H1"])
    for k in ("observed_at", "available_at"):
        if k in kw and kw[k] is not None:
            kw[k] = at(kw[k])
    d.update(kw)
    return d


R = dict(source="Lab", content="D-dimer elevated.")


def st(*raws):
    return EventStore().extend(raws)


def item(rp, lin="L1"):
    return rp.by_lineage().get(lin)


class FakeModel:
    pipe = object()
    model_id = "FAKE"
    error = None

    def predict(self, c, e):
        return {"score": 1, "probs": {"-2": 0, "-1": 0, "0": 0, "1": 1, "2": 0}}


class TestScenariosT1toT10(unittest.TestCase):
    def test_T1_order_only(self):
        rp = replay(st(E("o", "ORDERED", 0)), CASE, m(5))
        self.assertEqual((item(rp).state, item(rp).reasons), ("HELD", ["EVIDENCE_ORDERED_ONLY"]))

    def test_T2_completed_not_available(self):
        rp = replay(st(E("o", "ORDERED", 0), E("r", "AVAILABLE", 10, observed_at=5, available_at=30, **R)), CASE, m(20))
        self.assertEqual((item(rp).state, item(rp).reasons, item(rp).used), ("HELD", ["EVIDENCE_NOT_YET_AVAILABLE"], None))

    def test_T3_available(self):
        rp = replay(st(E("o", "ORDERED", 0), E("r", "AVAILABLE", 30, observed_at=5, available_at=30, **R)), CASE, m(30))
        self.assertEqual((item(rp).state, item(rp).used.event_id), ("USABLE", "r"))

    def test_T4_correction(self):
        s = st(E("r1", "AVAILABLE", 30, observed_at=5, available_at=30, **R),
               E("r2", "CORRECTED", 90, observed_at=5, available_at=90, source="Lab", content="Corrected: D-dimer normal.", prev_version_id="r1"))
        self.assertEqual(item(replay(s, CASE, m(60))).used.event_id, "r1")            # 정정 전 시점: 원본
        it = item(replay(s, CASE, m(95)))
        self.assertEqual(it.used.event_id, "r2")                                        # 정정 후: 정정본
        self.assertEqual(dict((e.event_id, r) for e, r in it.versions)["r1"], "SUPERSEDED")

    def test_T5_duplicate_same_and_cross_lineage(self):
        s = st(E("r1", "AVAILABLE", 30, observed_at=5, available_at=30, **R), E("r1b", "AVAILABLE", 40, observed_at=5, available_at=30, **R),
               E("x1", "AVAILABLE", 50, lin="L2", observed_at=5, available_at=30, **R))
        rp = replay(s, CASE, m(60))
        self.assertEqual(item(rp).used.event_id, "r1")
        self.assertEqual(dict((e.event_id, r) for e, r in item(rp).versions)["r1b"], "DUPLICATE")
        self.assertEqual((item(rp, "L2").state, item(rp, "L2").reasons, item(rp, "L2").duplicate_of), ("EXCLUDED", ["DUPLICATE_EVIDENCE"], "L1"))
        self.assertEqual(len(rp.usable()), 1)

    def test_T6_late_registration_uses_available_time(self):
        s = st(E("r", "AVAILABLE", 10, observed_at=5, available_at=120, **R))           # 관찰 5분, 결과 등록 120분
        self.assertEqual(item(replay(s, CASE, m(60))).reasons, ["EVIDENCE_NOT_YET_AVAILABLE"])
        self.assertEqual(item(replay(s, CASE, m(120))).state, "USABLE")

    def test_T7_late_arrival_of_older_event(self):
        s = st(E("r", "AVAILABLE", 200, observed_at=5, available_at=10, **R))           # 10분에 가용했지만 200분에 도착
        self.assertIsNone(item(replay(s, CASE, m(100))))                                # 100분 시점 시스템은 이 기록을 모름
        self.assertEqual(replay(s, CASE, m(100)).n_unknown_future_records, 1)
        self.assertEqual(item(replay(s, CASE, m(200))).state, "USABLE")

    def test_T8_future_result_excluded(self):
        s = st(E("o", "ORDERED", 0), E("r", "AVAILABLE", 300, observed_at=5, available_at=300, **R))
        rp = replay(s, CASE, m(100))
        self.assertEqual(item(rp).reasons, ["EVIDENCE_ORDERED_ONLY"])
        self.assertEqual(rp.usable(), [])

    def test_T9_missing_time(self):
        s = st(E("r", "AVAILABLE", 10, observed_at=5, available_at=None, **R), E("q", "AVAILABLE", 10, lin="L2", observed_at=None, available_at=10, **R))
        rp = replay(s, CASE, m(20))
        self.assertEqual((item(rp).state, item(rp).reasons), ("HELD", ["TIME_UNKNOWN"]))
        self.assertEqual(item(rp, "L2").state, "USABLE")                                # 관찰 시각만 모름 → 가용 시각으로 사용

    def test_T10_mixed_patients(self):
        s = st(E("r", "AVAILABLE", 10, observed_at=5, available_at=10, **R),
               {**E("o", "AVAILABLE", 10, lin="L9", observed_at=5, available_at=10, **R), "patient_id": "P2"},          # 같은 묶음에 다른 환자
               {**E("z", "AVAILABLE", 10, lin="L8", observed_at=5, available_at=10, **R), "patient_id": "P3", "feed_id": "F3"})  # 무관 환자
        rp = replay(s, CASE, m(20))
        self.assertEqual((item(rp, "L9").state, item(rp, "L9").reasons), ("EXCLUDED", ["PATIENT_MISMATCH"]))
        self.assertIsNone(item(rp, "L8"))
        self.assertEqual([i.used.event_id for i in rp.usable()], ["r"])


class TestUnits(unittest.TestCase):
    def test_pending_not_negative_and_held_not_zero(self):
        s = st(E("o", "ORDERED", 0), E("p", "PENDING", 5, observed_at=5))
        a = assess(replay(s, CASE, m(10)), FakeModel())
        r = a["rows"][0]
        self.assertEqual((r["state"], r["assessment"]["status"]), ("HELD", "NOT_ASSESSED"))
        self.assertNotIn("score", r["assessment"])                                      # 보류에 0점 없음
        self.assertEqual(a["n_scored"], 0)

    def test_model_unavailable_no_fake_score(self):
        s = st(E("r", "AVAILABLE", 10, observed_at=5, available_at=10, **R))
        bad = DModel(path=Path("/nonexistent/fold0.joblib")).load()
        a = assess(replay(s, CASE, m(20)), bad)
        self.assertEqual(a["rows"][0]["assessment"]["status"], "MODEL_UNAVAILABLE")
        self.assertNotIn("score", a["rows"][0]["assessment"])
        self.assertEqual(assess(replay(s, CASE, m(20)), None)["rows"][0]["assessment"]["status"], "MODEL_UNAVAILABLE")

    def test_model_hash_mismatch_refused(self):
        p = Path(__file__)
        d = DModel(path=p, expected_sha256="0" * 64).load()
        self.assertEqual(d.status, "MODEL_UNAVAILABLE")
        self.assertIn("sha256", d.error)

    def test_cancelled_invalid_source_unlinked(self):
        s = st(E("o", "ORDERED", 0), E("c", "CANCELLED", 5),
               E("i", "INVALID", 10, lin="L2", observed_at=5, available_at=10, source="Lab", content="Hemolyzed specimen."),
               E("u", "AVAILABLE", 10, lin="L3", observed_at=5, available_at=10, content="x"),
               {**E("n", "AVAILABLE", 10, lin="L4", observed_at=5, available_at=10, **R), "hypothesis_ids": []})
        rp = replay(s, CASE, m(20))
        self.assertEqual(item(rp).reasons, ["EVIDENCE_CANCELLED"])
        self.assertEqual(item(rp, "L2").reasons, ["EVIDENCE_INVALID"])
        self.assertEqual(item(rp, "L3").reasons, ["SOURCE_UNKNOWN"])
        self.assertEqual(item(rp, "L4").reasons, ["NOT_LINKED_TO_HYPOTHESIS"])

    def test_conflicting_versions_held(self):
        s = st(E("a", "AVAILABLE", 10, observed_at=5, available_at=10, **R),
               E("b", "AVAILABLE", 12, observed_at=5, available_at=12, source="Lab", content="D-dimer normal."))
        self.assertEqual(item(replay(s, CASE, m(20))).reasons, ["CONFLICTING_VERSIONS"])

    def test_newer_version_pending_notice(self):
        s = st(E("r1", "AVAILABLE", 10, observed_at=5, available_at=10, **R),
               E("r2", "CORRECTED", 20, observed_at=5, available_at=100, source="Lab", content="Corrected.", prev_version_id="r1"))
        it = item(replay(s, CASE, m(50)))
        self.assertEqual((it.used.event_id, it.reasons), ("r1", ["NEWER_VERSION_NOT_YET_AVAILABLE"]))


class TestFaultInjection(unittest.TestCase):
    def rej(self, raw):
        s = EventStore()
        self.assertIsNone(s.append(raw))
        return s.log[-1]["code"]

    def test_bad_time(self):
        self.assertEqual(self.rej({**E("x", "ORDERED", 0), "recorded_at": "2026-03-01T09:00:00"}), "INVALID_TIME")     # 시간대 없음
        self.assertEqual(self.rej({**E("x", "ORDERED", 0), "recorded_at": "not-a-time"}), "INVALID_TIME")
        self.assertEqual(self.rej(E("x", "AVAILABLE", 0, observed_at=50, available_at=10, **R)), "INVALID_TIME")          # 가용 < 관찰

    def test_missing_source_is_held_not_rejected(self):
        s = st(E("r", "AVAILABLE", 10, observed_at=5, available_at=10, content="x"))
        self.assertEqual(item(replay(s, CASE, m(20))).reasons, ["SOURCE_UNKNOWN"])

    def test_duplicate_event_id(self):
        s = EventStore()
        s.append(E("x", "ORDERED", 0))
        s.append(E("x", "ORDERED", 0))                                                  # 같은 내용 재전송 → 무시(기록)
        self.assertEqual(s.log[-1]["action"], "IGNORED_IDEMPOTENT_RESEND")
        s.append(E("x", "PENDING", 3))                                                  # 같은 ID 다른 내용 → 거부
        self.assertEqual(s.log[-1]["code"], "DUPLICATE_EVENT_ID")
        self.assertEqual(s.events["x"].status, "ORDERED")                               # 원본 유지

    def test_correction_cycle_and_missing_prev(self):
        self.assertEqual(self.rej(E("a", "CORRECTED", 10, observed_at=5, available_at=10, prev_version_id="a", **R)), "CORRECTION_CYCLE")
        s = st(E("a", "CORRECTED", 10, observed_at=5, available_at=10, prev_version_id="b", **R),
               E("b", "CORRECTED", 12, observed_at=5, available_at=12, prev_version_id="a", source="Lab", content="y"))
        it = item(replay(s, CASE, m(20)))
        self.assertEqual(it.reasons[0], "LINEAGE_INVALID")
        self.assertIn("LINEAGE:DERIVATION_CYCLE", it.reasons)
        s2 = st(E("c", "CORRECTED", 10, observed_at=5, available_at=10, prev_version_id="ghost", **R))
        it2 = item(replay(s2, CASE, m(20)))
        self.assertIn("LINEAGE:PREVIOUS_VERSION_MISSING", it2.reasons)

    def test_patient_id_collision(self):
        s = st(E("a", "AVAILABLE", 10, observed_at=5, available_at=10, **R),
               {**E("b", "CORRECTED", 20, observed_at=5, available_at=20, prev_version_id="a", **R), "patient_id": "P2"})
        self.assertEqual(item(replay(s, CASE, m(30))).reasons, ["PATIENT_ID_CONFLICT"])

    def test_invalid_status_empty_evidence_unknown_field(self):
        self.assertEqual(self.rej(E("x", "DONE", 0)), "INVALID_STATUS")
        self.assertEqual(self.rej(E("x", "AVAILABLE", 0, observed_at=0, available_at=0, source="Lab", content="   ")), "EMPTY_EVIDENCE")
        self.assertEqual(self.rej({**E("x", "ORDERED", 0), "bogus": 1}), "UNKNOWN_FIELD")
        self.assertEqual(self.rej({**E("x", "ORDERED", 0), "patient_id": ""}), "MISSING_FIELD")

    def test_model_load_failure(self):
        d = DModel(path=Path("/nonexistent.joblib")).load()
        self.assertEqual(d.status, "MODEL_UNAVAILABLE")


class TestInvariants(unittest.TestCase):
    def setUp(self):
        self.case, self.raws, self.steps = demo_case()

    def out(self, raws, t):
        return assess(replay(EventStore().extend(raws), self.case, datetime.fromisoformat(t)), FakeModel())

    def test_order_independence_and_determinism(self):
        rng = random.Random(1)
        for _, t in self.steps:
            ref = self.out(self.raws, t)
            self.assertEqual(ref, self.out(self.raws, t))
            for _ in range(5):
                sh = self.raws[:]
                rng.shuffle(sh)
                self.assertEqual(ref, self.out(sh, t))

    def test_past_replay_equals_snapshot_and_no_future_info(self):
        s = EventStore().extend(self.raws)
        for _, t in self.steps:
            ts = datetime.fromisoformat(t)
            full = assess(replay(s, self.case, ts), FakeModel())
            snap = assess(replay(s.snapshot(ts), self.case, ts), FakeModel())
            self.assertEqual(full, snap)                                                 # 정정 이후에도 과거 시점 복원 일치
            for it in replay(s, self.case, ts).items:
                for e, _ in it.versions:
                    self.assertLessEqual(e.recorded_at, ts)                              # 미래 기록 미사용
                if it.used:
                    self.assertLessEqual(it.used.available_at, ts)

    def test_append_only(self):
        s = EventStore().extend(self.raws)
        before = dict(s.events)
        replay(s, self.case, datetime.fromisoformat(self.steps[-2][1]))
        s.append({**self.raws[0], "status": "PENDING"})                                 # 덮어쓰기 시도
        self.assertEqual(s.events, before)

    def test_demo_story(self):
        s = EventStore().extend(self.raws)
        a = {n: assess(replay(s, self.case, datetime.fromisoformat(t)), FakeModel()) for n, t in self.steps[:-1]}
        lin = lambda name, l: next(r for r in a[name]["rows"] if r["lineage_id"] == l)  # noqa: E731
        self.assertEqual(lin("검사 요청", "L-DDIMER")["reasons"], ["EVIDENCE_ORDERED_ONLY"])
        self.assertEqual(lin("결과 대기", "L-DDIMER")["reasons"], ["EVIDENCE_PENDING"])
        self.assertEqual(lin("D-dimer 결과 이용 가능", "L-DDIMER")["used_event_id"], "DD-R1")
        self.assertFalse(any(r["lineage_id"] == "L-DDIMER-IF2" for r in a["D-dimer 결과 이용 가능"]["rows"]))   # 재전송은 80분 도착
        self.assertEqual(lin("CT 예비 판독", "L-DDIMER-IF2")["reasons"], ["DUPLICATE_EVIDENCE"])
        self.assertEqual(lin("CT 예비 판독", "L-CTPA")["used_event_id"], "CT-R1")
        self.assertEqual(lin("CT 판독 정정", "L-CTPA")["used_event_id"], "CT-R2")
        self.assertEqual(lin("CT 판독 정정", "L-CXR-SYN002")["reasons"], ["PATIENT_MISMATCH"])
        self.assertEqual(lin("CT 판독 정정", "L-SPO2")["reasons"], ["SOURCE_UNKNOWN"])
        self.assertEqual(lin("CT 판독 정정", "L-DUPLEX")["reasons"], ["TIME_UNKNOWN"])
        self.assertEqual(lin("CT 판독 정정", "L-TROP")["reasons"], ["EVIDENCE_CANCELLED"])
        self.assertFalse(any(r["lineage_id"] == "L-ECG" for r in a["CT 예비 판독"]["rows"]))      # 늦은 도착 전
        self.assertEqual(lin("늦은 기록 도착", "L-ECG")["state"], "USABLE")
        d = diff(a["CT 예비 판독"], a["CT 판독 정정"])
        ct = next(x for x in d if x["lineage_id"] == "L-CTPA")
        self.assertEqual(ct["change"], "VERSION_CHANGED")
        past = assess(replay(s, self.case, datetime.fromisoformat(self.steps[-1][1])), FakeModel())
        self.assertEqual(past, a["CT 예비 판독"])                                          # 정정 후 과거 재생 = 당시 상태

    def test_counterfactual_and_graph(self):
        s = EventStore().extend(self.raws)
        t = datetime.fromisoformat(self.steps[3][1])                                     # 재전송본이 도착한 뒤(155분)
        cf = counterfactual(s, self.case, t, FakeModel(), "DD-R1")
        ch = {x["lineage_id"]: x["change"] for x in cf["changes"]}
        self.assertEqual(ch.get("L-DDIMER-IF2"), "BECAME_USABLE")                         # 원본을 빼면 재전송본이 정본이 됨
        g = provenance_graph(replay(s, self.case, datetime.fromisoformat(self.steps[5][1])))
        self.assertGreater(g["stats"]["edge_kinds"].get("CORRECTS", 0), 0)
        self.assertGreater(g["stats"]["edge_kinds"].get("INPUT_TO_AI_FOR", 0), 0)



class TestGenerator(unittest.TestCase):
    def test_generator_accepted_and_deterministic(self):
        from medmap_demo.scenarios import generate
        a, b = generate(7, 5), generate(7, 5)
        self.assertEqual([r for _, r, _, _ in a], [r for _, r, _, _ in b])
        for case, raws, golds, qs in a:
            s = EventStore().extend(raws)
            self.assertFalse([x for x in s.log if x["action"] == "REJECTED"])
            self.assertTrue(all(g.timeline for g in golds))



class TestReviewFixes(unittest.TestCase):
    """1차 심사(EXP-MAI-009 gate NEEDS_FIX) 지적 회귀 테스트."""

    def test_cross_lineage_tiebreak_keeps_original_even_if_copy_id_sorts_first(self):
        s = st(E("P1-L0-R1", "AVAILABLE", 30, lin="P1-L0", observed_at=5, available_at=30, **R),
               E("P1-L0-IF2-R1", "AVAILABLE", 50, lin="P1-L0-IF2", observed_at=5, available_at=30, **R))   # 'IF2' < 'R1'
        rp = replay(s, CASE, m(60))
        self.assertEqual(item(rp, "P1-L0").used.event_id, "P1-L0-R1")
        self.assertEqual(item(rp, "P1-L0-IF2").reasons, ["DUPLICATE_EVIDENCE"])

    def test_resend_of_superseded_version_excluded(self):
        s = st(E("r1", "AVAILABLE", 30, observed_at=5, available_at=30, source="Lab", content="no PE."),
               E("x1", "AVAILABLE", 40, lin="L2", observed_at=5, available_at=30, source="Lab", content="no PE."),
               E("r2", "CORRECTED", 90, observed_at=5, available_at=90, source="Lab", content="PE present.", prev_version_id="r1"))
        before, after = replay(s, CASE, m(60)), replay(s, CASE, m(95))
        self.assertEqual(item(before, "L2").reasons, ["DUPLICATE_EVIDENCE"])
        self.assertEqual(item(after, "L2").reasons, ["DUPLICATE_OF_SUPERSEDED_VERSION"])
        self.assertEqual([i.used.event_id for i in after.usable()], ["r2"])

    def test_newer_version_time_unknown_is_held(self):
        s = st(E("r1", "AVAILABLE", 10, observed_at=5, available_at=10, **R),
               E("r2", "CORRECTED", 20, observed_at=5, available_at=None, source="Lab", content="Corrected.", prev_version_id="r1"))
        it = item(replay(s, CASE, m(50)))
        self.assertEqual((it.state, it.reasons, it.used), ("HELD", ["NEWER_VERSION_TIME_UNKNOWN"], None))

    def test_no_question_mark_roles_in_demo(self):
        case, raws, steps = demo_case()
        s = EventStore().extend(raws)
        for _, t in steps:
            for it in replay(s, case, datetime.fromisoformat(t)).items:
                self.assertNotIn("?", [r for _, r in it.versions])

    def test_replay_dict_hides_unused_content_and_other_patient(self):
        case, raws, steps = demo_case()
        d = replay(EventStore().extend(raws), case, datetime.fromisoformat(steps[5][1])).to_dict()
        for i in d["items"]:
            for v in i["versions"]:
                if v["role"] != "USED":
                    self.assertIsNone(v["content"])
                self.assertNotIn("patient_id", v)

    def test_server_api_exposure_policy(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import server
        c = server.api("/api/case", {})
        self.assertNotIn("events", c)
        t = server.CASE and server.STEPS[1][1]                                           # '결과 대기' 단계
        r = server.api("/api/replay", {"as_of": [t]})
        blob = __import__("json").dumps(r, ensure_ascii=False, default=str)
        self.assertNotIn("consistent with acute pulmonary embolism", blob)                # 미래 정정 판독 내용 미전송
        self.assertNotIn("SYN-002", blob)
        self.assertTrue(all(datetime.fromisoformat(x["recorded_at"]) <= datetime.fromisoformat(t) for x in r["timeline"]))

    def test_compare_harness_on_dev_seed(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import run_compare as RC
        r = RC.run(7, 12)                                                                  # 개발용 seed(사전 지정 seed 20261116~19 와 다름)
        self.assertTrue(RC.passed(r), r["metrics"]["MEDMAP"])
        self.assertGreater(r["metrics"]["BASE"]["B"]["occurrences"], 0)


    def test_compare_api_structure_matches_ui(self):
        """시연 화면 loadCompare 가 읽는 키가 실제 compare.json 구조에 있는지(2차 심사 MAJOR 2). 개발 seed 로 만든 구조를 임시 폴더에 둠."""
        import json
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import run_compare as RC
        import server
        r = RC.run(11, 6)
        body = {"results": {"primary": r, "confirm": [r]}, "pass_primary": RC.passed(r), "pass_confirm": [RC.passed(r)]}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "outputs" / "compare_DEV").mkdir(parents=True)
            (Path(d) / "outputs" / "compare_DEV" / "compare.json").write_text(json.dumps(body))
            old = (server.ROOT, server.COMPARE_RUN)
            server.ROOT, server.COMPARE_RUN = Path(d), "DEV"
            try:
                c = server.api("/api/compare", {})
            finally:
                server.ROOT, server.COMPARE_RUN = old
        P = c["results"]["primary"]
        for m in ("BASE", "MEDMAP"):
            for k in ("A", "A2", "B", "C", "D", "E", "G", "G2", "I"):
                self.assertTrue({"occurrences", "lineages", "patients"} <= set(P["metrics"][m][k]))
            for k in ("F", "H"):
                self.assertTrue({"queries", "patients"} <= set(P["metrics"][m][k]))
            self.assertRegex(P["metrics"][m]["exact_used_match"], r"^\d+/\d+$")
        self.assertTrue({"seed", "n_patients", "n_queries"} <= set(P))
        self.assertEqual(len(c["pass_confirm"]), len(c["results"]["confirm"]))


if __name__ == "__main__":
    unittest.main()
