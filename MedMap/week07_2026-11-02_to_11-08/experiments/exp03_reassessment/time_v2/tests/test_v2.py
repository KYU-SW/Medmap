"""EXP-03-TIME v2 합성 테스트(실제 MIMIC 없음). 기대값은 fixture_v2 설계에서 손으로 도출해 실행 전 고정(docstring 표 참조).

마스킹 없는 정확값 확인은 PB.SMALL=1 로 패치(0<n<1 칸 없음). 마스킹 규칙은 별도 테스트.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_v2 as FX  # noqa: E402
import independent_audit as IA  # noqa: E402
import public_v2 as PB  # noqa: E402
import records_v2 as RV  # noqa: E402
import run_time_policy_audit_v2 as R  # noqa: E402

ST, S1, S2 = "STRICT_AVAILABLE_TIME", "S1_TRIAGE_AT_INTIME_APPROX", "S2_STRICT_A_ONLY"
I, SU, CO = "INSUFFICIENT", "SUPPORTED", "CONFLICT"

# 기대 상태 분포(체류 수) — fixture 설계에서 도출
EXP_STATES = {
    ST: {"T0": {I: 10}, "T1": {SU: 3, CO: 2, I: 5}, "T2": {SU: 3, CO: 2, I: 5}},
    S1: {"T0": {SU: 1, I: 9}, "T1": {SU: 3, CO: 2, I: 5}, "T2": {SU: 3, CO: 2, I: 5}},
    S2: {"T0": {I: 10}, "T1": {I: 10}, "T2": {I: 10}},
}
EXP_USED = {  # (lab, rad, triage 행, ecg)
    ST: {"T0": (0, 0, 0, 0), "T1": (3, 6, 0, 0), "T2": (3, 8, 0, 0)},
    S1: {"T0": (0, 0, 1, 0), "T1": (3, 6, 1, 0), "T2": (3, 8, 1, 0)},
    S2: {"T0": (0, 0, 0, 0), "T1": (3, 0, 0, 0), "T2": (3, 0, 0, 0)},
}
EXP_PROXY = {ST: (0, 6, 8), S1: (0, 6, 8), S2: (0, 0, 0)}
EXP_APPROX = {ST: (0, 0, 0), S1: (2, 2, 2), S2: (0, 0, 0)}
EXP_DEN = {"lab": 6, "rad": 12, "triage": 1, "ecg": 1}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = FX.write(self.tmp / "src")
        self.det = self.src / "radiology_detail.parquet"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_exact(self, name="out", **kw):
        """정확값 = INTERNAL_AGGREGATES(내부 보안 영역 파일)에서 읽음. 공개는 전부 비공개 모드(검증 시간 절약) — 공개 보호는 test_disclosure_v2."""
        res = R.run(self.src, self.tmp / name, self.det, withhold_all=True, internal_dir=self.tmp / f"{name}_int", **kw)
        internal = json.loads((self.tmp / f"{name}_int" / "INTERNAL_AGGREGATES.json").read_text(encoding="utf-8"))
        res = dict(res)
        res.update(internal["tree"])
        return res


def heuristic_public(src: Path, out: Path, small: int):
    """1단계(heuristic 묶음 보완 + 환자 짝) 공개값만 재구성 — 2단계(독립 검증·표 비공개) 이전 상태를 시험."""
    seen = {}
    real = R.DS.protect

    def spy(X, G, PAT, relations, **kw):
        seen.update(X=dict(X), G=[list(g) for g in G], PAT=list(PAT))
        return real(X, G, PAT, relations, **kw)
    with mock.patch.object(PB, "SMALL", small), mock.patch.object(R.DS, "protect", spy):
        R.run(src, out, src / "radiology_detail.parquet", withhold_all=True)
        pub = PB.suppress(seen["X"], seen["G"])
        for sp, pp in seen["PAT"]:
            if PB.is_masked(pub[sp]) and not PB.is_masked(pub[pp]):
                pub[pp] = PB.COMPLEMENT
        return R.render(pub, seen["X"], seen["X"][("stays", "evaluated_stays")])


class Records(Base):
    def test_record_units_and_reconciliation(self):
        r = self.run_exact()
        self.assertEqual(r["status"], "DONE", r.get("violations"))
        lab = r["records"]["lab"]
        self.assertEqual((lab["input_rows"], lab["unique_keys"], lab["dup_extra_rows"], lab["kept_unique"]), (11, 9, 2, 8))
        self.assertEqual((lab["dup_key_groups_identical"], lab["dup_key_groups_time_conflict"]), (1, 1))
        self.assertEqual((lab["attributed"], lab["ambiguous"], lab["unattributed"]), (6, 1, 1))
        rd = r["records"]["radiology"]
        self.assertEqual((rd["input_rows"], rd["unique_keys"], rd["dup_extra_rows"], rd["kept_unique"]), (18, 17, 1, 17))
        self.assertEqual((rd["attributed"], rd["ambiguous"], rd["unattributed"]), (15, 2, 0))       # a5 → 11(가족), a6 → AMBIGUOUS(가족)
        self.assertEqual((rd["type:CTA"], rd["type:OTHER"], rd["type:UNKNOWN_TYPE"]), (15, 1, 1))
        self.assertEqual(rd["attributed:CTA"], 13)
        self.assertEqual(rd["class:CHRONIC_OR_PERSISTENT"], 1)
        self.assertEqual((rd["class:ACUTE_POS"], rd["class:NEGATIVE"], rd["class:NO_MENTION"]), (6, 4, 2))
        self.assertEqual((rd["verified_links"], rd["link_pairs_both_fields"], rd["link_pairs_parent_field_only"]), (5, 6, 1))
        self.assertEqual(rd["link_subject_mismatch"], 1)                                # a7: 다른 환자 연결
        self.assertEqual((rd["cta_input"], rd["addendum_linked_replacing"], rd["addendum_linked_no_decisive_not_input"],
                          rd["addendum_unlinked_AR_input"], rd["addendum_type_from_parent"]), (12, 3, 1, 2, 1))
        self.assertEqual((rd["linked_addendum_stay_ne_parent_stay"], rd["linked_addendum_parent_ambiguous_or_unattributed"]), (1, 1))
        self.assertEqual((rd["replace_pair:NEGATIVE->ACUTE_POS"], rd["replace_pair:ACUTE_POS->NEGATIVE"]), (1, 2))
        self.assertEqual(rd["nomention_addendum_parent_class:ACUTE_POS"], 1)
        ecg = r["records"]["ecg"]
        self.assertEqual((ecg["matched"], ecg["stay_key_not_in_cohort"], ecg["no_stay_key"]), (1, 1, 1))
        tri = r["records"]["triage"]
        self.assertEqual((tri["rows"], tri["rows_with_derived_evidence"], tri["derived_evidence"], tri["rows_on_time_undefined_stay"]),
                         (11, 1, 2, 1))
        s = r["stays"]
        self.assertEqual((s["cohort_stays"], s["time_defined"], s["time_undefined"], s["t1_equals_t2"]), (11, 10, 1, 1))
        self.assertEqual((s["evaluated_stays"], s["evaluated_patients"]), (10, 8))   # p4 는 시각 불명 체류만

    def test_flags_and_C_candidates(self):
        r = self.run_exact()
        f = r["flags_by_policy"][ST]
        self.assertEqual((f["lab:OK"], f["lab:UNKNOWN_AVAILABILITY"], f["lab:TIME_CONFLICT"], f["lab:POST_ED"]), (3, 1, 1, 1))
        self.assertEqual((f["rad:OK"], f["rad:POST_ED"], f["rad:TIME_CONFLICT"]), (8, 3, 1))          # n2·a5·a7 POST_ED
        self.assertEqual((f["triage:UNKNOWN_AVAILABILITY"], f["ecg:NOT_IDENTIFIABLE"]), (2, 1))
        self.assertEqual(r["flags_by_policy"][S2]["rad:EXCLUDED_BY_POLICY"], 11)
        self.assertEqual(r["flags_by_policy"][S1]["triage:APPROX_INTIME"], 2)
        c = r["C_candidates_vs_used"]
        self.assertEqual(c[ST]["C_input_by_source"], {"lab": 2, "rad": 1, "triage": 2, "ecg": 1})
        self.assertEqual(c[ST]["C_used"], {"T0": 0, "T1": 0, "T2": 0})
        self.assertEqual(c[S2]["C_used"], {"T0": 0, "T1": 0, "T2": 0})
        self.assertEqual(c[S1]["C_used"], {"T0": 2, "T1": 2, "T2": 2})

    def test_pseudonymous_internal_keys(self):
        co, labs, rd, ecg, det = FX.frames()
        prep = RV.prepare(co, labs, rd, ecg, det, lambda n: dict(zip(rd["note_id"], rd["text"]))[n])
        natives = list(FX.NIDS.values()) + ["90000"]
        for recs in prep.per_stay.values():
            for x in recs:
                for nat in natives:
                    self.assertNotIn(nat, x.record_id)
                    self.assertNotIn(nat, x.source_reference)
                    self.assertNotIn(nat, x.supersedes or "")


class Usage(Base):
    def test_usage_inclusion_proxy_approx(self):
        r = self.run_exact()
        u = r["usage"]
        self.assertEqual({k: r["denominator"][k] for k in EXP_DEN}, EXP_DEN)
        self.assertEqual(r["denominator"]["pooled"], 20)
        for p in (ST, S1, S2):
            for i, k in enumerate(("T0", "T1", "T2")):
                row = u[p][k]
                got = tuple(row["used"][s] for s in ("lab", "rad", "triage", "ecg"))
                self.assertEqual(got, EXP_USED[p][k], (p, k))
                self.assertEqual(row["PROXY_used(evidence)"], EXP_PROXY[p][i], (p, k))
                self.assertEqual(row["APPROX_used(evidence)"], EXP_APPROX[p][i], (p, k))
        t2 = u[ST]["T2"]
        self.assertEqual((t2["rate"]["lab"], t2["rate"]["rad"], t2["rate"]["pooled"]), (0.5, round(8 / 12, 4), round(11 / 20, 4)))
        d = r["rate_diff_vs_STRICT"]
        self.assertEqual(d[S1]["T0"]["triage"], 1.0)
        self.assertEqual(d[S2]["T2"]["rad"], round(0 - 8 / 12, 4))
        self.assertEqual(d[S2]["T2"]["pooled"], round(3 / 20 - 11 / 20, 4))
        self.assertEqual(d[S1]["T2"]["lab"], 0.0)
        self.assertEqual(t2["stays_with_any_used"], {"stays": 7, "patients": 6, "stay_rate": round(7 / 10, 4)})
        self.assertEqual([u[p][k]["stays_with_unlinked_AR_effective"]["stays"] for p in (ST, S2) for k in ("T0", "T1", "T2")],
                         [0, 1, 1, 0, 0, 0])                                            # a3(71) 만, a7 은 POST_ED
        self.assertEqual((u[ST]["T1"]["observed_le_T_lt_available(records)"], u[ST]["T2"]["observed_le_T_lt_available(records)"]), (2, 3))      # + a7(1→5)
        self.assertEqual(u[ST]["T2"]["stays_cta_performed_not_yet_available"], 1)
        self.assertEqual(u[ST]["rejected_no_source"], 0)


class States(Base):
    def test_state_distribution(self):
        r = self.run_exact()
        for p, d in EXP_STATES.items():
            for k, want in d.items():
                got = {s: v["stays"] for s, v in r["states"][p][k].items() if s != "alerts" and v["stays"]}
                self.assertEqual(got, want, (p, k))

    def test_alerts_addendum_and_changes(self):
        r = self.run_exact()
        a = r["states"][ST]
        self.assertEqual(a["T1"]["alerts"]["AL1_NEW_CONFLICT"]["stays"], 2)            # 51(p1 음성), 71(a3)
        self.assertEqual(a["T2"]["alerts"]["AL1_NEW_CONFLICT"]["stays"], 2)            # 71, 81(a4)
        self.assertEqual(a["T2"]["alerts"]["AL2_SUPPORT_RETRACTED"]["stays"], 1)       # 81: 급성 p4 → 음성 a4 대체
        self.assertEqual(a["T1"]["alerts"]["AL2_SUPPORT_RETRACTED"]["stays"], 0)       # 대체 전 시점 불변
        ch = a["changes"]
        self.assertEqual((ch["summary_T0_vs_T2"]["stays"], ch["summary_any_checkpoint"]["stays"]), (5, 5))
        self.assertEqual((ch["alerts_T0_vs_T2"]["stays"], ch["alerts_any_checkpoint"]["stays"]), (2, 3))

    def test_paired_crosstab(self):
        r = self.run_exact()
        IN, R1, R7, R2 = "INSUFFICIENT_NO_DECISIVE", "SUPPORTED_R1", "SUPPORTED_R7", "CONFLICT_R2"
        x1 = r["paired_crosstab_vs_STRICT"][S1]["T0"]
        self.assertEqual(x1[f"STRICT={IN}|{S1}={R7}"]["stays"], 1)                      # triage 만 지지 = 비결정
        self.assertEqual(x1[f"STRICT={R7}|{S1}={IN}"]["stays"], 0)
        self.assertEqual(x1[f"STRICT={IN}|{S1}={IN}"]["stays"], 9)
        self.assertEqual(x1["differs"]["summary"]["stays"], 1)
        self.assertEqual((x1["decisive_lost(STRICT 결정 → 비결정)"]["stays"], x1["decisive_gained(STRICT 비결정 → 결정)"]["stays"]), (0, 0))
        x2 = r["paired_crosstab_vs_STRICT"][S2]["T2"]
        self.assertEqual((x2[f"STRICT={R1}|{S2}={IN}"]["stays"], x2[f"STRICT={R2}|{S2}={IN}"]["stays"],
                          x2[f"STRICT={IN}|{S2}={IN}"]["stays"]), (3, 2, 4))
        self.assertEqual(x2[f"STRICT=INSUFFICIENT_R3|{S2}={IN}"]["stays"], 1)              # 같은 요약 상태·다른 범주
        off = sum(v["stays"] for kk, v in x2.items() if kk.startswith("STRICT=") and kk.split("|")[0][7:] != kk.split("=")[2])
        self.assertEqual(off, 6)                                                       # 비대각 합 ≠ 상이 체류(5)
        self.assertEqual(x2[f"STRICT={IN}|{S2}={R1}"]["stays"], 0)
        self.assertEqual((x2["differs"]["summary"]["stays"], x2["differs"]["alerts"]["stays"]), (5, 2))
        self.assertEqual((x2["decisive_lost(STRICT 결정 → 비결정)"]["stays"], x2["decisive_gained(STRICT 비결정 → 결정)"]["stays"]), (5, 0))
        c = r["categories"]
        self.assertEqual({k: v["stays"] for k, v in c[ST]["T2"].items() if v["stays"]}, {R1: 3, R2: 2, IN: 4, "INSUFFICIENT_R3": 1})
        self.assertEqual({k: v["stays"] for k, v in c[S1]["T0"].items() if v["stays"]}, {R7: 1, IN: 9})


class Safety(Base):
    def test_layer_B_catches_charttime_as_available(self):
        real = R.TP.time_info

        def bad(r, stay, policy):
            ti = real(r, stay, policy)
            if r.source == "lab" and ti.available_at is not None:
                return R.TP.TimeInfo(r.observed_at, ti.grade, ti.flag, ti.approx, ti.proxy)
            return ti
        with mock.patch.object(R.TP, "time_info", bad):
            res = R.run(self.src, self.tmp / "o2", self.det)
        self.assertEqual(res["status"], "ABORT")
        self.assertTrue(any(k.startswith("B_") for k in res["violations"]), res["violations"])
        self.assertTrue((self.tmp / "o2" / "ABORT_time_policy_audit_v2.json").exists())

    def test_layer_B_catches_window_mixing(self):
        real = R.TP.attribute

        def bad(r, stays):
            mine = [s for s in stays if s.subject_id == r.subject_id]
            return mine[0].stay_id if (r.stay_id is None and mine) else real(r, stays)
        with mock.patch.object(R.TP, "attribute", bad):
            res = R.run(self.src, self.tmp / "o3", self.det)
        self.assertEqual(res["status"], "ABORT")

    def test_layer_B_direct_sets(self):
        co, labs, rd, ecg, det = FX.frames()
        ia = IA.IndependentAudit(co, labs, rd, ecg, det, {})
        v = ia.check_stay("11", ST, 10_000_000_000.0, [("ecg", "7", None), ("triage", "11", 0.0)])
        self.assertGreater(v["B_ecg_used"], 0)
        self.assertGreater(v["B_triage_outside_S1"], 0)
        self.assertGreater(v["B_allowed_not_used"], 0)

    def test_code_and_input_sha(self):
        r = self.run_exact()
        self.assertEqual(set(r["code_sha256"]), set(R.code_files()))
        for k in ("time_v2/records_v2.py", "time_v2/independent_audit.py", "time_v2/run_time_policy_audit_v2.py",
                  "time_v1/time_policy.py", "reassess.py", "ct_bridge.py", "exp02/mimic_adapter.py", "exp02/ext_pe_eval_v3.py",
                  "time_v2/PROTOCOL_TIME_v2.md"):
            self.assertEqual(r["code_sha256"][k], R.sha(R.code_files()[k]), k)
        for n in R.INPUTS:
            self.assertEqual(r["input_sha256"][n], R.sha(self.src / n), n)
        self.assertEqual(r["input_sha256"]["radiology_detail.parquet"], R.sha(self.det))
        ok = R.run(self.src, self.tmp / "o4ok", self.det, expected_code_sha=R.code_sha(), withhold_all=True)     # 일치하면 정상 진행
        self.assertEqual(ok["status"], "DONE", ok.get("violations"))
        bad = dict(r["code_sha256"], **{"reassess.py": "0" * 64})
        res = R.run(self.src, self.tmp / "o4", self.det, expected_code_sha=bad)
        self.assertEqual(res["status"], "ABORT")
        self.assertIn("code_sha_mismatch", res["violations"])

    def test_public_privacy(self):
        R.run(self.src, self.tmp / "o5", self.det, internal_dir=self.tmp / "o5_int")
        txt = (self.tmp / "o5" / "time_policy_audit_v2_public.json").read_text(encoding="utf-8")
        itxt = (self.tmp / "o5_int" / "INTERNAL_AGGREGATES.json").read_text(encoding="utf-8")
        for bad in ["Filling defects", "2150-", "pulmonary arteries"] + list(FX.NIDS.values()):
            self.assertNotIn(bad, txt)
            self.assertNotIn(bad, itxt)                                                   # 내부 집계도 건수만(원문·시각·ID 없음)

    def test_exception_path_no_identifiers(self):
        nid = FX.NIDS["n1"]
        man = self.tmp / "CODE_SHA256.json"
        R.main(["--write-code-sha", str(man)])
        with mock.patch.object(R.RV, "prepare", side_effect=ValueError(f"다른 체류 증거 거부: rad{nid}")), \
                mock.patch.object(R, "frozen_ok", return_value=True), mock.patch.object(R, "SEALED_ROOT", str(self.tmp)), \
                mock.patch.object(R, "authorize_counted_run"):         # gate 관문은 test_counted_run 에서 시험 — 여기는 예외 로그만
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), self.assertRaises(SystemExit) as cm:
                R.main(["--src", str(self.src), "--out", str(self.tmp / "o6"), "--rad-detail", str(self.det), "--i-have-user-approval",
                        "--code-sha-manifest", str(man), "--internal-out", str(self.tmp / "o6_int")])
        self.assertEqual(cm.exception.code, 4)
        out = buf.getvalue()
        self.assertIn("ABORT stage=prepare type=ValueError", out)
        self.assertNotIn(nid, out)
        self.assertNotIn("90000001", out)

    def test_cli_refuses_without_approval(self):
        with self.assertRaises(SystemExit):
            R.main(["--src", str(self.src), "--out", str(self.tmp / "o7")])
        self.assertFalse((self.tmp / "o7").exists())
        with self.assertRaises(SystemExit):                                            # 승인 있어도 코드 SHA 동결 목록 없으면 거부
            R.main(["--src", str(self.src), "--out", str(self.tmp / "o7"), "--i-have-user-approval"])
        self.assertFalse((self.tmp / "o7").exists())

    def test_layer_B_catches_under_use(self):
        real = R.TP.time_info

        def bad(r, stay, policy):
            ti = real(r, stay, policy)
            if r.source == "lab" and ti.available_at is not None:
                return R.TP.TimeInfo(None, ti.grade, "UNKNOWN_AVAILABILITY")             # 허용 기록을 안 씀
            return ti
        with mock.patch.object(R.TP, "time_info", bad):
            res = R.run(self.src, self.tmp / "o9", self.det)
        self.assertEqual(res["status"], "ABORT")
        self.assertIn("B_allowed_not_used", res["violations"])

    def test_zero_match_guard(self):
        with mock.patch.object(R.TP, "attribute", lambda r, stays: None if r.stay_id is None else r.stay_id):
            res = R.run(self.src, self.tmp / "o10", self.det)
        self.assertEqual(res["status"], "ABORT")

    def test_out_dir_conflict_at_start(self):
        (self.tmp / "o8").mkdir()
        with self.assertRaises(FileExistsError):
            R.run(self.src, self.tmp / "o8", self.det)


class MaskingGroups(Base):
    def test_exact_identity_groups_present(self):
        """suppress 에 넘긴 묶음 중, 공개 합계 칸마다 '합이 정확히 맞는' 묶음이 있어야 함(과잉 포함 묶음만으로는 부족)."""
        seen = {}
        real = PB.suppress

        def spy(cells, groups):
            seen["cells"], seen["groups"] = dict(cells), [list(g) for g in groups]
            return real(cells, groups)
        with mock.patch.object(PB, "SMALL", 1), mock.patch.object(PB, "suppress", spy):
            R.run(self.src, self.tmp / "og", self.det, withhold_all=True)
        X, G = seen["cells"], seen["groups"]

        def exact(total):
            return any(g[0] == total and X[total] == sum(X[c] for c in g[1:]) for g in G)
        for px in (S1, S2):
            for k in ("T0", "T1", "T2"):
                self.assertTrue(exact(("paired_crosstab_vs_STRICT", px, k, "differs", "summary", "stays")), (px, k))
                for a in R.CATS:
                    self.assertTrue(exact(("categories", ST, k, a, "stays")), (px, k, a))
        for p in (ST, S1, S2):
            for k in ("T0", "T1", "T2"):
                self.assertTrue(exact(("usage", p, k, "used", "pooled")) or
                                any(set(g) == {("usage", p, k, "used", x) for x in ("lab", "rad", "triage", "ecg", "pooled")} for g in G))
        self.assertTrue(exact(("stays", "cohort_stays")))
        self.assertTrue(exact(("denominator", "pooled")))
        for k in ("T0", "T1", "T2"):                                                   # 같은 양 = 2칸 사슬, 실제로 같은 값
            labs = [("usage", q, k, "used", "lab") for q in (ST, S1, S2)]
            for a_, b_ in zip(labs, labs[1:]):
                self.assertIn([a_, b_], G)
                self.assertEqual(X[a_], X[b_])
            self.assertFalse(any(len(g) > 2 and set(g) <= set(labs) for g in G))      # 3칸 같은 양 묶음 금지

    def test_equal_quantity_scenario_T0_rad_small(self):
        """reviewer 재현 시나리오(합성 값): T0 STRICT·S1 rad 사용 4, lab 세 정책 300, S1 triage 12000 → lab 세 칸 전부 가려야 함."""
        seen = {}
        real = PB.suppress

        def spy(cells, groups):
            seen["cells"], seen["groups"] = dict(cells), [list(g) for g in groups]
            return real(cells, groups)
        with mock.patch.object(PB, "SMALL", 1), mock.patch.object(PB, "suppress", spy):
            R.run(self.src, self.tmp / "osc", self.det, withhold_all=True)
        X = {k: 1000 for k in seen["cells"]}                                           # 다른 칸은 크게(가림 유발 없음)
        U = lambda q, s: ("usage", q, "T0", "used", s)
        for q in (ST, S1, S2):
            X[U(q, "lab")] = 300
            X[U(q, "ecg")] = 0
        X[U(ST, "rad")] = X[U(S1, "rad")] = 4
        X[U(S2, "rad")] = 0
        X[U(ST, "triage")] = X[U(S2, "triage")] = 0
        X[U(S1, "triage")] = 12000
        X[U(ST, "pooled")], X[U(S1, "pooled")], X[U(S2, "pooled")] = 304, 12304, 300
        pub = real(X, seen["groups"])
        labs = [pub[U(q, "lab")] for q in (ST, S1, S2)]
        self.assertTrue(all(PB.is_masked(v) for v in labs), labs)                     # S2 lab 공개 → STRICT rad = 304 − 300 역산
        self.assertTrue(PB.is_masked(pub[U(S2, "pooled")]) or PB.is_masked(pub[U(ST, "pooled")]))


class MaskingRadFlags(Base):
    def test_rad_flag_equal_across_policies_scenario(self):
        """5차 gate 재현(합성 값): rad OK 900·POST_ED 12·UNKNOWN 15·TIME_CONFLICT 5, S2 EXCLUDED 912, 분모 932.
        S2 TIME_CONFLICT 가 가려지면 STRICT·S1 의 UNKNOWN 공개로 932−912−15 역산 → 세 정책 같은 flag 는 전부 가림/전부 공개."""
        seen = {}
        real = PB.suppress

        def spy(cells, groups):
            seen["cells"], seen["groups"] = dict(cells), [list(g) for g in groups]
            return real(cells, groups)
        with mock.patch.object(PB, "SMALL", 1), mock.patch.object(PB, "suppress", spy):
            R.run(self.src, self.tmp / "orf", self.det, withhold_all=True)
        X = {k: 1000 for k in seen["cells"]}
        F = lambda p, f: ("flags_by_policy", p, f"rad:{f}")
        for p in (ST, S1, S2):
            for f in R.FLAGS:
                X[F(p, f)] = 0
            X[F(p, "UNKNOWN_AVAILABILITY")], X[F(p, "TIME_CONFLICT")] = 15, 5
        for p in (ST, S1):
            X[F(p, "OK")], X[F(p, "POST_ED")] = 900, 12
        X[F(S2, "EXCLUDED_BY_POLICY")] = 912
        X[("denominator", "rad")] = 932
        pub = real(X, seen["groups"])
        for f in ("UNKNOWN_AVAILABILITY", "TIME_CONFLICT"):
            st = [PB.is_masked(pub[F(p, f)]) for p in (ST, S1, S2)]
            self.assertIn(sum(st), (0, 3), (f, st))
        self.assertTrue(PB.is_masked(pub[F(S2, "TIME_CONFLICT")]))
        self.assertTrue(PB.is_masked(pub[F(ST, "UNKNOWN_AVAILABILITY")]))           # 역산 차단

    def test_no_three_cell_equal_groups(self):
        """같은 양 사슬은 2칸만 — 길이 3 이상인 묶음은 모두 합 항등식이어야 함(첫 칸 = 나머지 합 또는 합 묶음 목록)."""
        seen = {}
        real = PB.suppress

        def spy(cells, groups):
            seen["groups"] = [list(g) for g in groups]
            return real(cells, groups)
        with mock.patch.object(PB, "SMALL", 1), mock.patch.object(PB, "suppress", spy):
            R.run(self.src, self.tmp / "o3c", self.det, withhold_all=True)
        for g in seen["groups"]:
            if len(g) >= 3:
                kinds = {c[0] for c in g}
                pols = {c[1] for c in g if len(c) > 1}
                same_field_cross_policy = len(kinds) == 1 and kinds <= {"flags_by_policy", "grades_by_policy"} and \
                    len({c[2] for c in g}) == 1 and len(pols) == 3
                self.assertFalse(same_field_cross_policy, g)


class Masking(unittest.TestCase):
    def test_small_and_complement(self):
        pub = PB.suppress({"a": 5, "b": 40, "c": 30}, [["a", "b", "c"]])
        self.assertEqual(pub, {"a": "<10", "b": 40, "c": PB.COMPLEMENT})
        self.assertEqual(PB.suppress({"a": 5, "b": 3, "c": 30}, [["a", "b", "c"]]), {"a": "<10", "b": "<10", "c": 30})
        self.assertEqual(PB.suppress({"a": 0, "b": 30}, [["a", "b"]]), {"a": 0, "b": 30})

    def test_ratio_masked_is_na(self):
        self.assertEqual(PB.ratio("<10", 100, 5, 100), PB.NA)
        self.assertEqual(PB.ratio(50, PB.COMPLEMENT, 50, 70), PB.NA)
        self.assertEqual(PB.ratio(0, 0, 0, 0), PB.NA)
        self.assertEqual(PB.ratio(50, 100, 50, 100), 0.5)

    def test_public_run_masks_fixture(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            src = FX.write(tmp / "src")
            r = heuristic_public(src, tmp / "o", 10)                                         # 1단계 결과
            self.assertEqual(r["records"]["lab"]["attributed"], "<10")
            self.assertEqual(r["usage"][ST]["T2"]["rate"]["lab"], PB.NA)
            self.assertEqual(r["rate_diff_vs_STRICT"][S2]["T2"]["lab"], PB.NA)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cross_table_identities_not_single_masked(self):
        """SMALL=3: 공개 항등식마다 마스킹 칸이 정확히 1개인 경우가 없어야 함(묶음 간 같은 양 포함), 체류 가림 → 환자 가림."""
        tmp = Path(tempfile.mkdtemp())
        try:
            src = FX.write(tmp / "src")
            r = heuristic_public(src, tmp / "o", 3)                                          # 1단계 결과(2단계 검증은 test_disclosure_v2)
            m = PB.is_masked
            st, rec, den = r["stays"], r["records"], r["denominator"]
            ids = [[st["cohort_stays"], st["time_defined"], st["time_undefined"]],
                   [den["lab"], rec["lab"]["attributed"]], [den["rad"], rec["radiology"]["cta_input"]],
                   [rec["lab"]["kept_unique"], rec["lab"]["attributed"], rec["lab"]["ambiguous"], rec["lab"]["unattributed"]],
                   [rec["ecg"]["kept_unique"], rec["ecg"]["no_stay_key"], rec["ecg"]["stay_key_not_in_cohort"],
                    rec["ecg"]["on_time_undefined_stay"], rec["ecg"]["matched"]],
                   [den["lab"]] + [r["flags_by_policy"][ST][f"lab:{f}"] for f in R.FLAGS]]
            for p in (ST, S1, S2):
                for k in ("T0", "T1", "T2"):
                    ids.append([r["usage"][p][k]["used"][s] for s in ("lab", "rad", "triage", "ecg", "pooled")])
                    ids.append([st["evaluated_stays"]] + [r["states"][p][k][s]["stays"] for s in R.STATES])
            eq = [[r["usage"][q][k]["used"]["lab"] for q in (ST, S1, S2)] for k in ("T0", "T1", "T2")]
            eq.append([r["usage"][S1][k]["used"]["triage"] for k in ("T0", "T1", "T2")])
            for e in eq:                                                               # 같은 양 = 전부 가림 또는 전부 공개
                self.assertIn(sum(m(x) for x in e), (0, len(e)), e)
            for px in (S1, S2):
                for k in ("T0", "T1", "T2"):
                    x = r["paired_crosstab_vs_STRICT"][px][k]
                    cells = {kk: v["stays"] for kk, v in x.items() if kk.startswith("STRICT=")}
                    summ = R.SUMMARY_OF
                    ids.append([x["differs"]["summary"]["stays"]] +
                               [v for kk, v in cells.items() if summ[kk.split("|")[0][7:]] != summ[kk.split("=")[2]]])
                    for a in R.CATS:
                        ids.append([r["categories"][ST][k][a]["stays"]] + [cells[f"STRICT={a}|{px}={b}"] for b in R.CATS])
            for g in ids:
                self.assertNotEqual(sum(m(x) for x in g), 1, g)
            for p in (ST, S1, S2):
                for k in ("T0", "T1", "T2"):
                    for s in R.STATES:
                        cell = r["states"][p][k][s]
                        if m(cell["stays"]):
                            self.assertTrue(m(cell["patients"]), (p, k, s))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
