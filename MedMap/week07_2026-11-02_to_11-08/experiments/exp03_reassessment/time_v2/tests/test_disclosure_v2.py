"""공개 집계 역산 공격 합성 테스트(PROTOCOL_TIME_v2.md §9-2) — 직접 만든 가상 집계·관계만 사용(실제 MIMIC 없음).

A. 독립 검증기(disclosure_verifier) 단위 공격: 손으로 만든 관계·공개값으로 역산 가능 → FAILED, 막힌 경우 → VERIFIED.
B. 보호 단계(disclosure_v2.protect): 위험 표가 PUBLIC_WITHHELD 로 전환되는지.
C. 파이프라인 끝단: 실제 공개 파일을 다시 읽어 검증(VERIFIED), 보호를 끈 결함 → 공개 파일 없이 ABORT.
"""
from __future__ import annotations

import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import disclosure_v2 as DS  # noqa: E402
import disclosure_verifier as DV  # noqa: E402

S, C, W = DV.SMALL_TOKEN, DV.COMPLEMENT_TOKEN, DV.WITHHELD_TOKEN


def rel(universe, eqs=(), ineq=(), const=None):
    """eqs: [{셀: 계수}] (합 = 0), ineq: [(a, b)] (a ≤ b)."""
    r = {"universe": list(universe), "equalities": [{"cells": list(e), "coef": [float(w) for w in e.values()]} for e in eqs],
         "inequalities": [list(x) for x in ineq], "constant": dict(const or {})}
    r["_index"] = {c: i for i, c in enumerate(r["universe"])}
    return r


def sumrel(total, parts):
    return {total: 1.0, **{p: -1.0 for p in parts}}


def V(flat, r, ratios=None):
    return DV.verify_flat(flat, ratios or {}, r)


class Attacks(unittest.TestCase):
    def test_total_minus_subset(self):                                 # 전체 100, 정상 96, 오류 <10 → 4
        r = rel(["stays/total", "stays/ok", "stays/err"], [sumrel("stays/total", ["stays/ok", "stays/err"])])
        self.assertEqual(V({"stays/total": 100, "stays/ok": 96, "stays/err": S}, r)["status"], DV.FAILED)
        self.assertEqual(V({"stays/total": 100, "stays/ok": C, "stays/err": S}, r)["status"], DV.VERIFIED)

    def test_row_sum(self):
        u = ["records/r", "records/a", "records/b", "records/c"]
        r = rel(u, [sumrel("records/r", u[1:])])
        self.assertEqual(V({"records/r": 60, "records/a": 30, "records/b": 25, "records/c": S}, r)["status"], DV.FAILED)

    def test_column_sum_and_crosstab(self):                           # 2×2 + 행·열 합: 행만 보완하면 열로 복원
        c = lambda i, j: f"categories/x{i}{j}"
        u = [c(i, j) for i in range(2) for j in range(2)] + ["categories/r0", "categories/r1", "categories/c0", "categories/c1"]
        eqs = [sumrel("categories/r0", [c(0, 0), c(0, 1)]), sumrel("categories/r1", [c(1, 0), c(1, 1)]),
               sumrel("categories/c0", [c(0, 0), c(1, 0)]), sumrel("categories/c1", [c(0, 1), c(1, 1)])]
        r = rel(u, eqs)
        leak = {c(0, 0): S, c(0, 1): C, c(1, 0): 40, c(1, 1): 50, "categories/r0": 35, "categories/r1": 90,
                "categories/c0": 45, "categories/c1": 80}
        self.assertEqual(V(leak, r)["status"], DV.FAILED)             # 열 c0 − x10 = x00
        safe = {c(0, 0): S, c(0, 1): C, c(1, 0): C, c(1, 1): C, "categories/r0": 35, "categories/r1": 90,
                "categories/c0": 45, "categories/c1": 80}
        self.assertEqual(V(safe, r)["status"], DV.VERIFIED)

    def test_two_policy_difference(self):                             # pooled_S1 − pooled_STRICT = triage_S1
        u = ["usage/S1/pooled", "usage/ST/pooled", "usage/S1/triage"]
        r = rel(u, [sumrel("usage/S1/pooled", ["usage/ST/pooled", "usage/S1/triage"])])
        self.assertEqual(V({"usage/S1/pooled": 505, "usage/ST/pooled": 500, "usage/S1/triage": S}, r)["status"], DV.FAILED)

    def test_exact_percentage_and_rounded_ratio(self):               # 분모 공개 + 정확·반올림 비율 → 분자 복원 → 비율 공개 금지
        r = rel(["usage/P/T0/used/lab", "denominator/lab"])
        ratios = {"usage/P/T0/rate/lab": ["usage/P/T0/used/lab", "denominator/lab"]}
        for rate in (0.04, 0.0412):
            flat = {"usage/P/T0/used/lab": S, "denominator/lab": 100, "usage/P/T0/rate/lab": rate}
            self.assertEqual(V(flat, r, ratios)["status"], DV.FAILED)
        flat = {"usage/P/T0/used/lab": S, "denominator/lab": 100, "usage/P/T0/rate/lab": DV.NA_TOKEN}
        self.assertEqual(V(flat, r, ratios)["status"], DV.VERIFIED)

    def test_rate_diff_needs_public_rates(self):
        r = rel(["usage/a", "usage/b"])
        ratios = {"rate_diff_vs_STRICT/S1/T0/lab": ["usage/S1/T0/rate/lab", "usage/ST/T0/rate/lab"],
                  "usage/S1/T0/rate/lab": ["usage/a", "usage/b"], "usage/ST/T0/rate/lab": ["usage/a", "usage/b"]}
        flat = {"usage/a": 5, "usage/b": 10, "usage/S1/T0/rate/lab": DV.NA_TOKEN, "usage/ST/T0/rate/lab": 0.5,
                "rate_diff_vs_STRICT/S1/T0/lab": 0.1}
        self.assertEqual(V(flat, r, ratios)["status"], DV.FAILED)

    def test_multiple_tables_chain(self):                             # 표 A: T = a + b, 표 B: b = c + d (c, d 공개) → a 복원
        u = ["stays/T", "records/a", "records/b", "flags_merged/c", "flags_merged/d"]
        r = rel(u, [sumrel("stays/T", ["records/a", "records/b"]), sumrel("records/b", ["flags_merged/c", "flags_merged/d"])])
        self.assertEqual(V({"stays/T": 80, "records/a": S, "records/b": C, "flags_merged/c": 30, "flags_merged/d": 45}, r)["status"],
                         DV.FAILED)
        self.assertEqual(V({"stays/T": 80, "records/a": S, "records/b": C, "flags_merged/c": C, "flags_merged/d": C}, r)["status"],
                         DV.VERIFIED)

    def test_overlapping_population_inequality(self):                # 부분집합 관계 a ≥ b(공개 7) → a ∈ [7,9] 후보 3개
        r = rel(["states/a", "states/b"], ineq=[("states/b", "states/a")])
        self.assertEqual(V({"states/a": S, "states/b": 7}, r)["status"], DV.FAILED)
        # 원래 사례(b=2): 범위 a ∈ [2,9] 는 넓지만 공개 정수 2 자체가 1–9 직접 노출 → 기대값이 FAILED 로 바뀐 사유를 고정(사례 삭제 안 함).
        out = V({"states/a": S, "states/b": 2}, r)
        self.assertEqual(out["status"], DV.FAILED)
        self.assertEqual(out["failed"], ["states/b"])                  # a 범위 때문이 아니라 b 직접 노출 때문
        self.assertEqual(V({"states/a": S, "states/b": 0}, r)["status"], DV.VERIFIED)
        # 원래 의도('하한이 2 라도 후보가 충분하면 범위 검사는 통과')는 공개 정수 없이 독립 검사: T=12, w ≥ 10 → y ∈ [0,2] 는 실패하므로 비교 칸은 제약 없는 하한으로
        g = {"cells": ["stays/k", "states/a", "stays/m"], "coef": [1.0, -1.0, -1.0]}   # k − m ≤ a, k=12, m=10 → a ≥ 2
        r2 = rel(["states/a", "stays/k", "stays/m"])
        r2["inequalities_general"] = [g]
        self.assertEqual(V({"states/a": S, "stays/k": 12, "stays/m": 10}, r2)["status"], DV.VERIFIED)   # a ∈ [2,9] 후보 8개

    def test_several_small_cells(self):
        u = ["stays/T", "stays/a", "stays/b"]
        r = rel(u, [sumrel("stays/T", ["stays/a", "stays/b"])])
        self.assertEqual(V({"stays/T": 10, "stays/a": S, "stays/b": S}, r)["status"], DV.VERIFIED)   # a ∈ [1,9]
        self.assertEqual(V({"stays/T": 4, "stays/a": S, "stays/b": S}, r)["status"], DV.FAILED)     # a ∈ [1,3]

    def test_withheld_cell_recovered_from_other_tables(self):         # 비공개 표의 칸도 다른 공개 칸으로 정확히 복원되면 FAILED
        u = ["stays/T", "records/a", "flags_merged/b"]
        r = rel(u, [sumrel("stays/T", ["records/a", "flags_merged/b"])])
        self.assertEqual(V({"stays/T": 100, "records/a": W, "flags_merged/b": 96}, r)["status"], DV.FAILED)
        self.assertEqual(V({"stays/T": 100, "records/a": W, "flags_merged/b": 60}, r)["status"], DV.VERIFIED)   # 복원값 40 ≥ 10

    def test_multi_timepoint(self):                                    # T0 ≤ T1 ≤ T2, T1 공개 3 → T0 ∈ [1,3]
        r = rel(["usage/T0", "usage/T1", "usage/T2"], ineq=[("usage/T0", "usage/T1"), ("usage/T1", "usage/T2")])
        self.assertEqual(V({"usage/T0": S, "usage/T1": 3, "usage/T2": 50}, r)["status"], DV.FAILED)

    def test_denominator_reuse(self):                                  # 같은 분모가 두 표에: den = n1 + n2, n2 는 다른 표에서 공개
        u = ["denominator/x", "usage/n1", "records/n2"]
        r = rel(u, [sumrel("denominator/x", ["usage/n1", "records/n2"])])
        self.assertEqual(V({"denominator/x": 70, "usage/n1": S, "records/n2": 65}, r)["status"], DV.FAILED)

    def test_output_vs_summary(self):                                  # 요약(stays) 과 세부(states) 의 관계
        u = ["stays/evaluated_stays", "states/P/T0/A/stays", "states/P/T0/B/stays"]
        r = rel(u, [sumrel("stays/evaluated_stays", u[1:])])
        self.assertEqual(V({"stays/evaluated_stays": 500, "states/P/T0/A/stays": 495, "states/P/T0/B/stays": S}, r)["status"],
                         DV.FAILED)

    def test_gate6_grade_equals_flag_sum(self):                       # 6차 심사 지적 경로(합성 값): A+B = OK+POST+EXCL, C = UNK+TC
        F = lambda f: f"flags_by_policy/P/lab:{f}"
        Gd = lambda g: f"grades_by_policy/P/lab:{g}"
        u = [F("OK"), F("POST_ED"), F("EXCL"), F("UNK"), F("TC"), Gd("A"), Gd("B"), Gd("C"), "denominator/lab"]
        eqs = [sumrel("denominator/lab", [F("OK"), F("POST_ED"), F("EXCL"), F("UNK"), F("TC")]),
               sumrel("denominator/lab", [Gd("A"), Gd("B"), Gd("C")]),
               {Gd("A"): 1.0, Gd("B"): 1.0, F("OK"): -1.0, F("POST_ED"): -1.0, F("EXCL"): -1.0},
               sumrel(Gd("C"), [F("UNK"), F("TC")])]
        r = rel(u, eqs)
        heuristic = {F("OK"): 900, F("POST_ED"): S, F("EXCL"): 0, F("UNK"): C, F("TC"): 20, Gd("A"): 905, Gd("B"): 0, Gd("C"): 35,
                     "denominator/lab": 940}                           # flag 묶음 안 보완만 한 상태
        self.assertEqual(V(heuristic, r)["status"], DV.FAILED)        # POST_ED = 905 − 900
        X = {tuple(k.split("/")): v for k, v in {F("OK"): 900, F("POST_ED"): 5, F("EXCL"): 0, F("UNK"): 15, F("TC"): 20,
                                                 Gd("A"): 905, Gd("B"): 0, Gd("C"): 35, "denominator/lab": 940}.items()}
        G = [[tuple(c.split("/")) for c in ["denominator/lab", F("OK"), F("POST_ED"), F("EXCL"), F("UNK"), F("TC")]]]
        pub, rep = DS.protect(X, G, [], r)
        flat = {"/".join(k): v for k, v in pub.items()}
        self.assertEqual(DV.verify_flat(flat, {}, r)["status"], DV.VERIFIED)
        self.assertFalse(isinstance(flat[Gd("A")], int) and isinstance(flat[F("OK")], int))   # 뺄셈 경로가 남지 않음

    def test_not_verifiable_is_not_pass(self):
        r = rel(["stays/a"])
        out = V({"stays/a": 50, "stays/unknown_cell": 7}, r)          # 관계 범위 밖 숫자 칸
        self.assertEqual(out["status"], DV.NOT_VERIFIABLE)
        out = V({"stays/a": 50, "usage/x/patients": 30}, r)           # 허용 목록 밖 환자 수
        self.assertEqual(out["status"], DV.NOT_VERIFIABLE)
        r2 = rel(["stays/a", "stays/z"], const={"stays/z": 0})
        self.assertEqual(V({"stays/a": 50, "stays/z": 3}, r2)["status"], DV.NOT_VERIFIABLE)   # 상수 칸 불일치
        self.assertEqual(V({"stays/a": 50, "stays/f": 0.5}, rel(["stays/a"]))["status"], DV.NOT_VERIFIABLE)  # 출처 없는 소수

    def test_normal_control(self):
        u = ["stays/T", "stays/a", "stays/b"]
        r = rel(u, [sumrel("stays/T", ["stays/a", "stays/b"])])
        self.assertEqual(V({"stays/T": 100, "stays/a": 40, "stays/b": 60}, r)["status"], DV.VERIFIED)

    def test_verifier_does_not_import_protection_code(self):
        tree = ast.parse((HERE / "disclosure_verifier.py").read_text(encoding="utf-8"))
        mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
            {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(mods & {"public_v2", "disclosure_v2", "run_time_policy_audit_v2", "records_v2"}, mods)


class Protect(unittest.TestCase):
    def test_protect_withholds_leaking_table(self):
        X = {("stays", "total"): 100, ("stays", "ok"): 96, ("records", "lab", "err"): 4}
        r = rel(["stays/total", "stays/ok", "records/lab/err"], [sumrel("stays/total", ["stays/ok", "records/lab/err"])])
        pub, rep = DS.protect(X, [], [], r)                            # heuristic 묶음 없음 → 검증기가 잡아야 함
        flat = {"/".join(k): v for k, v in pub.items()}
        self.assertEqual(rep["verifier_status"], DV.VERIFIED)
        self.assertEqual(DV.verify_flat(flat, {}, r)["status"], DV.VERIFIED)
        self.assertTrue(flat["records/lab/err"] in (S, W) and (flat["stays/ok"] in (S, C, W) or flat["stays/total"] in (S, C, W)))

    def test_protect_without_relations_withholds_everything(self):
        X = {("stays", "total"): 100, ("stays", "ok"): 96}
        pub, rep = DS.protect(X, [], [], None)
        self.assertTrue(all(v == W for v in pub.values()))
        self.assertEqual(rep["verifier_status"], DV.NOT_VERIFIABLE)

    def test_patient_policy_keeps_stay_table_publishable(self):       # 환자 칸만 비공개 → 같은 표의 체류 칸은 공개 유지
        X = {("states", "P", "T0", "A", "stays"): 50, ("states", "P", "T0", "A", "patients"): 40,
             ("states", "P", "T0", "B", "stays"): 70, ("states", "P", "T0", "B", "patients"): 60}
        r = rel(["/".join(k) for k in X])
        pub, rep = DS.protect(X, [], [], r)
        self.assertEqual(pub[("states", "P", "T0", "A", "stays")], 50)
        self.assertEqual(pub[("states", "P", "T0", "A", "patients")], W)
        self.assertIn("states_P_T0", rep["published_tables"])

    def test_patient_counts_policy(self):
        X = {("stays", "evaluated_patients"): 50, ("stays", "evaluated_stays"): 60, ("usage", "P", "T0", "x", "patients"): 40,
             ("usage", "P", "T0", "x", "stays"): 45}
        pub, _ = DS.protect(X, [], [], None, withhold_all=False)
        self.assertEqual(pub[("usage", "P", "T0", "x", "patients")], W)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        import fixture_v2 as FX
        self.tmp = Path(tempfile.mkdtemp())
        self.src = FX.write(self.tmp / "src")
        self.det = self.src / "radiology_detail.parquet"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_published_file_reverified_and_internal_exact_kept(self):
        import run_time_policy_audit_v2 as R
        if not R.RELATIONS_DEFAULT.exists():
            self.skipTest("관계 파일 없음")
        res = R.run(self.src, self.tmp / "o", self.det, internal_dir=self.tmp / "int")
        self.assertEqual(res["status"], "DONE", res.get("violations"))
        self.assertEqual(res["disclosure_check"]["verifier_status"], DV.VERIFIED)
        self.assertTrue(res["disclosure_check"]["published_tables"])                   # 안전한 표는 공개(전부 비공개로 도피하지 않음)
        pf = self.tmp / "o" / "time_policy_audit_v2_public.json"
        internal = json.loads((self.tmp / "int" / "INTERNAL_AGGREGATES.json").read_text(encoding="utf-8"))
        rel_ = DV.restrict_to_truth(DV.load_relations(R.RELATIONS_DEFAULT), internal["flat"])[0]   # 재검증 = 내부 정확값에서 참인 관계로
        self.assertEqual(DV.verify_file(pf, rel_)["status"], DV.VERIFIED)
        self.assertEqual(internal["tree"]["records"]["lab"]["attributed"], 6)      # 내부 정확값 보존(공개 가림과 무관)
        pub = json.loads(pf.read_text(encoding="utf-8"))
        flat = DV.flatten({k: v for k, v in pub.items() if k in DV.DATA_ROOTS})
        self.assertFalse(any(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 9 for v in flat.values()))   # 1–9 그대로 공개 0

    def test_protection_disabled_is_caught(self):
        import run_time_policy_audit_v2 as R
        if not R.RELATIONS_DEFAULT.exists():
            self.skipTest("관계 파일 없음")
        with mock.patch.object(R.DS, "protect", lambda X, G, PAT, relations, **kw: ({k: v for k, v in X.items()}, {"verifier_status": "BYPASS"})):
            res = R.run(self.src, self.tmp / "o2", self.det)
        self.assertEqual(res["status"], "ABORT")
        self.assertFalse((self.tmp / "o2" / "time_policy_audit_v2_public.json").exists())

    def test_heuristic_only_is_caught(self):                           # 1단계(묶음 보완)만 하고 검증 단계 생략 → 재검사 실패
        import run_time_policy_audit_v2 as R
        if not R.RELATIONS_DEFAULT.exists():
            self.skipTest("관계 파일 없음")
        import public_v2 as PB

        def heuristic_only(X, G, PAT, relations, **kw):
            pub = PB.suppress(X, G)
            for sp, pp in PAT:
                if PB.is_masked(pub[sp]):
                    pub[pp] = PB.COMPLEMENT
            for k in list(pub):
                if k[-1] == "patients" and k not in DS.PATIENT_WHITELIST:
                    pub[k] = W
            return pub, {"verifier_status": "SKIPPED"}
        with mock.patch.object(R.DS, "protect", heuristic_only):
            res = R.run(self.src, self.tmp / "o3", self.det)
        self.assertEqual(res["status"], "ABORT")


if __name__ == "__main__":
    unittest.main()
