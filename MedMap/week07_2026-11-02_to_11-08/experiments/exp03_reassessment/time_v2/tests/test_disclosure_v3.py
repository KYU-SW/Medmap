"""공개 보호 개정(2026-11-03, PROTOCOL_TIME_v2 §5-1·§9-3) 회귀 테스트 — 지어낸 값·합성 자료만(실제 MIMIC 없음).

마지막 심사의 재현 사례를 그대로 고정한다. 기대값은 코드 실행 전에 손으로 계산한 값이다.
A 관계 선언·거짓 관계 처리 / B 범위·직접 노출 / C 외부 공개값 결합 / D 공개 범위 / E addendum 시간 순서 / F 실행 경로 / G 합성 끝단 공격.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import disclosure_schema as DSC  # noqa: E402
import disclosure_v2 as DS  # noqa: E402
import disclosure_verifier as DV  # noqa: E402
import fixture_v2 as FX  # noqa: E402
import run_time_policy_audit_v2 as R  # noqa: E402
import synth_random_v2 as SR  # noqa: E402

S, C, W = DV.SMALL_TOKEN, DV.COMPLEMENT_TOKEN, DV.WITHHELD_TOKEN


def rel(universe, eqs=(), ineq=(), const=None, gen_const=None, external=None, general=()):
    r = {"universe": list(universe), "equalities": [{"cells": list(e), "coef": [float(w) for w in e.values()]} for e in eqs],
         "inequalities": [list(x) for x in ineq], "constant": dict(const or {}), "generator_constant": dict(gen_const or {}),
         "external_known": dict(external or {}),
         "inequalities_general": [{"cells": list(e), "coef": [float(w) for w in e.values()]} for e in general]}
    r["_index"] = {c: i for i, c in enumerate(r["universe"])}
    return r


def sumrel(total, parts):
    return {total: 1.0, **{p: -1.0 for p in parts}}


def st(flat, r):
    return DV.verify_flat(flat, {}, r)["status"]


def real_relations():
    return DV.load_relations(R.RELATIONS_DEFAULT)


class FalseRelations(unittest.TestCase):
    """이번 자료에서 거짓인 관계를 지우고 통과시키던 결함(심사 MAJOR 1)."""
    U = ["stays/a", "stays/b", "stays/c", "stays/d"]

    def test_accidental_relation_is_not_a_rule(self):                  # 구조 관계 a=c+d 만 선언. 합성 전용 d=b 는 선언 안 함 → a=c+d 로 d=5 복원 → FAILED
        r = rel(self.U, [sumrel("stays/a", ["stays/c", "stays/d"])])
        truth = {"stays/a": 100, "stays/b": 50, "stays/c": 95, "stays/d": 5}
        rr, _ = DV.restrict_to_truth(r, truth)
        self.assertEqual(st({"stays/a": 100, "stays/b": 50, "stays/c": 95, "stays/d": S}, rr), DV.FAILED)

    def test_false_equality_makes_cells_not_verifiable(self):          # 선언 a=c+d 가 이번 자료에서 거짓 → 그 칸 전부 NOT_VERIFIABLE
        r = rel(self.U, [sumrel("stays/a", ["stays/c", "stays/d"])])
        rr, n = DV.restrict_to_truth(r, {"stays/a": 100, "stays/b": 50, "stays/c": 80, "stays/d": 5})
        self.assertEqual(n["equalities_false_on_data"], 1)
        self.assertEqual(set(rr["_untrusted"]), {"stays/a", "stays/c", "stays/d"})
        self.assertEqual(st({"stays/a": 100, "stays/b": 50, "stays/c": 80, "stays/d": S}, rr), DV.NOT_VERIFIABLE)
        self.assertEqual(st({"stays/a": W, "stays/b": 50, "stays/c": W, "stays/d": W}, rr), DV.VERIFIED)   # 표 비공개 후에만 통과

    def test_false_inequality_blocks_instead_of_losing_edges(self):    # a≤b 거짓(축약으로 a≤c 를 잃던 경로) → a,b 비공개 전 통과 금지
        r = rel(self.U, ineq=[("stays/a", "stays/b"), ("stays/b", "stays/c")])
        rr, n = DV.restrict_to_truth(r, {"stays/a": 8, "stays/b": 3, "stays/c": 4, "stays/d": 0})
        self.assertEqual(n["inequalities_false_on_data"], 1)
        self.assertEqual(st({"stays/a": S, "stays/b": S, "stays/c": S, "stays/d": 0}, rr), DV.NOT_VERIFIABLE)

    def test_constant_mismatch_on_masked_cell(self):                   # 상수 0 인데 실제 3 — 공개 '<10'·비공개·공개 모두 처리
        r = rel(["stays/t", "stays/z"], const={"stays/z": 0})
        self.assertEqual(st({"stays/t": 50, "stays/z": S}, r), DV.NOT_VERIFIABLE)   # 공개 파일만으로도 판정
        rr, n = DV.restrict_to_truth(r, {"stays/t": 50, "stays/z": 3})
        self.assertEqual(n["constants_false_on_data"], 1)
        self.assertIn("stays/z", rr["_untrusted"])
        self.assertEqual(st({"stays/t": 50, "stays/z": S}, rr), DV.NOT_VERIFIABLE)

    def test_generator_constant_is_not_attacker_knowledge(self):       # 생성기 미도달 칸은 0 으로 고정하지 않음 — 값이 다르면 비공개
        r = rel(["stays/t", "stays/a", "stays/g"], [sumrel("stays/t", ["stays/a", "stays/g"])], gen_const={"stays/g": 0})
        self.assertEqual(st({"stays/t": 50, "stays/a": C, "stays/g": W}, r), DV.VERIFIED)
        self.assertEqual(st({"stays/t": 50, "stays/a": C, "stays/g": S}, r), DV.NOT_VERIFIABLE)
        rr, n = DV.restrict_to_truth(r, {"stays/t": 50, "stays/a": 47, "stays/g": 3})
        self.assertEqual(n["generator_constants_false_on_data"], 1)
        self.assertIn("stays/g", rr["_untrusted"])

    def test_missing_cell_cannot_confirm_relation(self):               # 자료에 없는 칸이 낀 관계 = 대조 불가 → untrusted
        r = rel(["stays/t", "stays/a", "stays/q"], [sumrel("stays/t", ["stays/a", "stays/q"])])
        rr, _ = DV.restrict_to_truth(r, {"stays/t": 50, "stays/a": 50})
        self.assertIn("stays/t", rr["_untrusted"])

    def test_declared_untrusted_cells_never_published(self):
        r = rel(["stays/t"])
        r["untrusted_cells"] = ["stays/t"]
        self.assertEqual(st({"stays/t": 50}, r), DV.NOT_VERIFIABLE)

    def test_protect_withholds_tables_of_false_relation(self):
        X = {("stays", "a"): 100, ("stays", "c"): 80, ("stays", "d"): 5, ("denominator", "lab"): 40}
        r = rel(["stays/a", "stays/c", "stays/d", "denominator/lab"], [sumrel("stays/a", ["stays/c", "stays/d"])])
        pub, rep = DS.protect(X, [], [], r)
        self.assertEqual(rep["verifier_status"], DV.VERIFIED)
        self.assertEqual(pub[("stays", "a")], W)
        self.assertEqual(pub[("denominator", "lab")], 40)
        self.assertEqual(rep["_internal_only"]["relations_dropped_false_on_data"]["equalities_false_on_data"], 1)
        self.assertEqual(rep["verifier_scope"]["n_equalities"], 1)     # 공개 건수 = 선언 수(참·거짓 수를 드러내지 않음)


class Ranges(unittest.TestCase):
    """0 포함 범위·1–9 직접 공개(심사 MAJOR 2)."""
    U = ["stays/T", "stays/x", "stays/y", "stays/z"]

    def test_zero_lower_bound_narrow(self):                            # T=22, y·z ≥ 10, x 비공개 → x ∈ [0,2]
        r = rel(self.U, [sumrel("stays/T", ["stays/x", "stays/y", "stays/z"])])
        self.assertEqual(st({"stays/T": 22, "stays/x": W, "stays/y": C, "stays/z": C}, r), DV.FAILED)

    def test_small_sum_after_withholding(self):                        # x+y = 1000−997 = 3, 둘 다 비공개 → x ∈ [0,3]
        r = rel(self.U, [sumrel("stays/T", ["stays/x", "stays/y", "stays/z"])])
        self.assertEqual(st({"stays/T": 1000, "stays/x": W, "stays/y": W, "stays/z": 997}, r), DV.FAILED)
        self.assertEqual(st({"stays/T": 1000, "stays/x": S, "stays/y": S, "stays/z": 997}, r), DV.FAILED)

    def test_candidate_boundary(self):                                 # 1 이상 후보 수 경계: [0,4]=4개 FAILED, [0,5]=5개 통과
        r = rel(self.U[:3], [sumrel("stays/T", ["stays/x", "stays/y"])])
        self.assertEqual(st({"stays/T": 14, "stays/x": W, "stays/y": C}, r), DV.FAILED)
        self.assertEqual(st({"stays/T": 15, "stays/x": W, "stays/y": C}, r), DV.VERIFIED)

    def test_range_straddling_nine(self):                              # a − b ≤ x (a=18, b=10) → x ≥ 8, x + p = 21 (p ≥ 10) → x ≤ 11 → [8,11] 후보 4개
        u = ["stays/x", "stays/a", "stays/b", "stays/p", "stays/t"]
        r = rel(u, [sumrel("stays/t", ["stays/x", "stays/p"])], general=[{"stays/a": 1, "stays/x": -1, "stays/b": -1}])
        self.assertEqual(st({"stays/x": W, "stays/a": 18, "stays/b": 10, "stays/p": C, "stays/t": 21}, r), DV.FAILED)
        self.assertEqual(st({"stays/x": W, "stays/a": 18, "stays/b": 10, "stays/p": C, "stays/t": 40}, r), DV.VERIFIED)   # [8,30] 넓음

    def test_exact_zero_is_not_failure(self):                          # 복원값이 정확히 0 → 작은 값 노출 아님
        r = rel(self.U[:3], [sumrel("stays/T", ["stays/x", "stays/y"])])
        self.assertEqual(st({"stays/T": 40, "stays/x": W, "stays/y": 40}, r), DV.VERIFIED)

    def test_direct_small_integer(self):                               # 공개 정수 1–9 는 관계와 무관하게 FAILED
        for v in (1, 3, 9):
            self.assertEqual(st({"stays/x": v}, rel(["stays/x"])), DV.FAILED, v)
        self.assertEqual(st({"stays/x": 0}, rel(["stays/x"])), DV.VERIFIED)
        self.assertEqual(st({"stays/x": 10}, rel(["stays/x"])), DV.VERIFIED)
        self.assertEqual(st({"records/lab/q": 4}, rel(["records/lab/q"])), DV.FAILED)

    def test_pairwise_inequality_alone_narrows(self):                  # T=16, w<10 → y ∈ [7,15], y ≤ x, x<10 → x ∈ [7,9]. 부등식이 없으면 잡히지 않음(결함 D3 탐지)
        u = ["stays/T", "stays/y", "stays/w", "stays/x"]
        r = rel(u, [sumrel("stays/T", ["stays/y", "stays/w"])], ineq=[("stays/y", "stays/x")])
        flat = {"stays/T": 16, "stays/w": S, "stays/y": W, "stays/x": S}
        self.assertEqual(st(flat, r), DV.FAILED)
        self.assertEqual(st(flat, rel(u, [sumrel("stays/T", ["stays/y", "stays/w"])])), DV.VERIFIED)

    def test_out_of_universe_token(self):                              # 관계 범위 밖 '<10' 도 숫자 칸과 같이 검증 불가
        self.assertEqual(st({"stays/nope": S}, rel(["stays/x"])), DV.NOT_VERIFIABLE)

    def test_general_inequality_bounds_used(self):                     # 다항 부등식 2m + p + v ≤ both(심사 재현: both 44, v 40 → p ≤ 4)
        r = rel(["records/radiology/m", "records/radiology/p", "records/radiology/v", "records/radiology/both"],
                general=[{"records/radiology/m": 2, "records/radiology/p": 1, "records/radiology/v": 1, "records/radiology/both": -1}])
        self.assertEqual(st({"records/radiology/m": 0, "records/radiology/p": S, "records/radiology/v": 40, "records/radiology/both": 44}, r), DV.FAILED)


class External(unittest.TestCase):
    """기존 EXP-02 공개값 결합(심사 M-pat-link)."""
    U = ["stays/cohort_patients", "stays/evaluated_patients", "stays/patients_without_evaluable_stay"]
    EQ = [sumrel("stays/cohort_patients", ["stays/evaluated_patients", "stays/patients_without_evaluable_stay"])]

    def test_public_count_minus_exp02_value(self):                     # 10,277 − 10,272 = 5
        r = rel(self.U, self.EQ, external={"stays/cohort_patients": 10277})
        self.assertEqual(st({"stays/evaluated_patients": 10272, "stays/patients_without_evaluable_stay": W}, r), DV.FAILED)
        self.assertEqual(st({"stays/evaluated_patients": W, "stays/patients_without_evaluable_stay": W}, r), DV.VERIFIED)
        self.assertEqual(st({"stays/evaluated_patients": 10277, "stays/patients_without_evaluable_stay": W}, r), DV.VERIFIED)   # 복원값 0

    def test_external_value_used_even_if_absent_from_file(self):       # 이번 공개본에 cohort 칸이 없어도 공격자는 앎
        r = rel(self.U, self.EQ, external={"stays/cohort_patients": 10277})
        self.assertEqual(st({"stays/evaluated_patients": 10270}, r), DV.FAILED)

    def test_external_mismatch_is_not_verifiable(self):
        r = rel(self.U, self.EQ, external={"stays/cohort_patients": 10277})
        self.assertEqual(st({"stays/cohort_patients": 10000, "stays/evaluated_patients": W}, r), DV.NOT_VERIFIABLE)

    def test_protect_withholds_only_patient_table(self):
        X = {("stays", "cohort_patients"): 10277, ("stays", "evaluated_patients"): 10272, ("stays", "patients_without_evaluable_stay"): 5,
             ("stays", "cohort_stays"): 12358}
        r = rel(self.U + ["stays/cohort_stays"], self.EQ, external={"stays/cohort_patients": 10277})
        pub, rep = DS.protect(X, [], [], r)
        self.assertEqual(rep["verifier_status"], DV.VERIFIED)
        self.assertEqual(pub[("stays", "evaluated_patients")], W)
        self.assertEqual(pub[("stays", "patients_without_evaluable_stay")], W)
        self.assertEqual(pub[("stays", "cohort_stays")], 12358)        # 체류 표는 유지

    def test_evaluated_patients_masked_with_evaluated_stays(self):     # 평가 체류가 보완 마스킹되면 평가 환자도 공개 안 함(결함 X5 탐지)
        ev, pt = ("stays", "evaluated_stays"), ("stays", "evaluated_patients")
        X = {("stays", "a"): 3, ("stays", "b"): 900, ev: 500, pt: 400}
        pub, _ = DS.protect(X, [[("stays", "a"), ("stays", "b"), ev]], [(ev, pt)], rel(["/".join(k) for k in X]))
        self.assertEqual(pub[ev], C)
        self.assertEqual(pub[pt], C)

    def test_exp02_values_read_from_public_file(self):                 # 값은 손으로 적지 않고 EXP-02 공개 파일에서
        ext = R.external_public_values()
        self.assertEqual(set(ext), set(DSC.EXTERNAL_CELLS))
        pub = json.loads(R.EXP02_PUBLIC.read_text(encoding="utf-8"))
        self.assertEqual(ext["stays/cohort_patients"], pub["union_subjects"])
        self.assertEqual(ext["records/radiology/input_rows"], pub["radiology_rows"])


class Scope(unittest.TestCase):
    def test_detail_tiers_excluded_from_publication(self):
        X = {("flags_by_policy", "P", "lab:OK"): 500, ("categories", "P", "T0", "A", "stays"): 300, ("denominator", "lab"): 500,
             ("paired_crosstab_vs_STRICT", "P", "T0", "STRICT=A|P=A", "stays"): 200, ("records", "radiology", "type:CTA"): 700,
             ("flags_merged", "P", "lab:USABLE"): 500}
        pub, rep = DS.protect(X, [], [], rel(["/".join(k) for k in X]))
        self.assertEqual(rep["verifier_status"], DV.VERIFIED)
        for k in X:
            if k[0] in ("flags_by_policy", "categories", "paired_crosstab_vs_STRICT") or k[-1] == "type:CTA":
                self.assertEqual(pub[k], W, k)
        self.assertEqual(pub[("denominator", "lab")], 500)
        self.assertEqual(pub[("flags_merged", "P", "lab:USABLE")], 500)
        self.assertEqual(X[("flags_by_policy", "P", "lab:OK")], 500)   # 내부 정확값은 그대로


class Schema(unittest.TestCase):
    def test_schema_independent_of_protection_code(self):
        for f in ("disclosure_schema.py", "disclosure_verifier.py"):
            tree = ast.parse((HERE / f).read_text(encoding="utf-8"))
            mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
                {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            self.assertFalse(mods & {"public_v2", "disclosure_v2", "run_time_policy_audit_v2", "records_v2"}, (f, mods))

    def test_no_data_derived_coefficient(self):                        # 합성에서만 2 이던 '부모 수' 를 등식으로 두지 않음 — 부등식
        s = DSC.build_schema()
        for e in s["equalities"]:
            self.assertFalse("records/radiology/child_multiple_parents" in e["cells"], e["cells"])

    def test_relations_file_built_from_schema(self):
        r = real_relations()
        s = DSC.build_schema()
        self.assertEqual(len(r["equalities"]), len(s["equalities"]))
        self.assertEqual(r["constant"], s["constant"])
        self.assertTrue(set(r["generator_constant"]).isdisjoint(s["constant"]))
        self.assertIn("coverage_report", r)

    def test_all_declared_true_on_fixture_and_cells_exist(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            src = FX.write(tmp / "src")
            flat = R.run(src, tmp / "o", src / "radiology_detail.parquet", publish=False)["flat"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        s = DSC.build_schema()
        missing = [c for c in s["schema_cells"] if c not in flat]
        self.assertEqual(missing, [])
        for e in s["equalities"]:
            self.assertEqual(sum(w * flat[c] for c, w in zip(e["cells"], e["coef"])), 0, e["why"])
        self.assertEqual(flat["stays/cohort_patients"], 9)
        self.assertEqual(flat["stays/patients_without_evaluable_stay"], 1)   # p4


def add_case(frames, parent_store, child_chart, child_store, parent_chart=1.0, out_h=6.0):
    """환자 20·체류 201(0–out_h): 원 판독(급성) + 연결 addendum(음성). 다른 행은 fixture 그대로."""
    co, labs, rd, ecg, det = frames
    co = pd.concat([co, pd.DataFrame([FX.stay(20, 201, 0, out_h)])], ignore_index=True)
    FX.NIDS.setdefault("px", "90000020-RR-1")
    FX.NIDS.setdefault("ax", "90000020-AR-2")
    rows = [FX.rad("px", 20, "RR", parent_chart, parent_store, FX.CTA, FX.POS)]
    if child_store is not None or child_chart is not None:
        rows.append(FX.rad("ax", 20, "AR", child_chart, child_store, FX.CTA, FX.NEG))
        det = pd.concat([det, pd.DataFrame([(FX.NIDS["ax"], "parent_note_id", FX.NIDS["px"]), (FX.NIDS["px"], "addendum_note_id", FX.NIDS["ax"])],
                                           columns=det.columns)], ignore_index=True)
    rd = pd.concat([rd, pd.DataFrame(rows)], ignore_index=True)
    return co, labs, rd, ecg, det


def write_frames(d: Path, frames) -> Path:
    co, labs, rd, ecg, det = frames
    d.mkdir(parents=True)
    co.to_parquet(d / "cohort.parquet")
    labs.to_parquet(d / "labs.parquet")
    rd.to_parquet(d / "radiology.parquet")
    ecg.to_parquet(d / "ecg.parquet")
    det.to_parquet(d / "radiology_detail.parquet")
    return d


class AddendumOrder(unittest.TestCase):
    """addendum 이 원 판독보다 이른 시각으로 기록된 경우(PROTOCOL §5-1)."""
    KEYS = ("addendum_stored_before_parent_excluded", "addendum_charted_before_parent_excluded", "addendum_order_undeterminable_excluded")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def flat(self, name, *a, **kw):
        src = write_frames(self.tmp / name, add_case(FX.frames(), *a, **kw))
        res = R.run(src, self.tmp / (name + "_o"), src / "radiology_detail.parquet", publish=False)
        self.assertEqual(res["status"], "INTERNAL_ONLY", res.get("violations"))
        return res["flat"]

    def baseline(self, parent_store, parent_chart=1.0, out_h=6.0):
        return self.flat("base", parent_store, None, None, parent_chart=parent_chart, out_h=out_h)

    def test_stored_before_parent_no_abort_excluded_counted(self):     # 원 판독 저장 8h, addendum 저장 5h, T2=6h → 예전: StopIteration
        f = self.flat("a", 8, 2, 5)
        self.assertEqual(f["records/radiology/addendum_stored_before_parent_excluded"], 1)
        self.assertEqual(f["records/radiology/addendum_linked_replacing"], 3)   # fixture 3건 그대로, 새 대체 없음

    def test_future_information_not_reflected(self):                   # addendum 제외 = addendum 없는 자료와 상태·알림·사용이 같음
        with_child, base = self.flat("a", 8, 2, 5), self.baseline(8)
        for k in base:
            if k.split("/")[0] in ("states", "usage", "categories", "paired_crosstab_vs_STRICT", "flags_by_policy", "denominator"):
                self.assertEqual(with_child[k], base[k], k)

    def test_past_state_not_retroactively_changed(self):               # 원 판독 2h 저장·addendum 시각 역전: 원 판독은 T2 까지 유효 그대로
        with_child, base = self.flat("a", 4, 0.5, 3, parent_chart=1.0), self.baseline(4)
        self.assertEqual(with_child["records/radiology/addendum_stored_before_parent_excluded"], 1)
        for k in base:
            if k.startswith("states/"):
                self.assertEqual(with_child[k], base[k], k)

    def test_charted_before_parent_excluded(self):                     # 저장 순서는 맞고 기록 시각만 앞섬 → 순서 불명확 → 제외
        f = self.flat("a", 2, 0.5, 5, parent_chart=1.0)
        self.assertEqual(f["records/radiology/addendum_charted_before_parent_excluded"], 1)

    def test_parent_availability_unknown_excluded(self):               # 원 판독 storetime 없음 → 순서 판단 불가 → 제외
        f = self.flat("a", None, 2, 5)
        self.assertEqual(f["records/radiology/addendum_order_undeterminable_excluded"], 1)

    def test_parent_time_inverted_excluded(self):
        f = self.flat("a", 0.5, 2, 5, parent_chart=1.0)
        self.assertEqual(f["records/radiology/addendum_order_undeterminable_excluded"], 1)

    def test_normal_order_still_replaces(self):                        # 정상 순서 대조 — 규칙이 정상 대체를 막지 않음
        f = self.flat("a", 2, 3, 4)
        self.assertEqual(sum(f[f"records/radiology/{k}"] for k in self.KEYS), 0)
        self.assertEqual(f["records/radiology/addendum_linked_replacing"], 4)

    def test_equal_store_time_not_excluded(self):                      # 같은 시각은 '이른 시각' 아님
        f = self.flat("a", 2, 1, 2)
        self.assertEqual(sum(f[f"records/radiology/{k}"] for k in self.KEYS), 0)

    def test_counts_reconcile_with_identity(self):
        f = self.flat("a", 8, 2, 5)
        r = "records/radiology/"
        self.assertEqual(f[r + "attributed:CTA"], f[r + "cta_input"] + f[r + "addendum_linked_no_decisive_not_input"] + sum(f[r + k] for k in self.KEYS))

    def test_independent_audit_applies_same_rule(self):                # 계층 B 가 같은 제외를 독립 계산 — 어긋나면 ABORT
        src = write_frames(self.tmp / "ia", add_case(FX.frames(), 8, 2, 5))
        res = R.run(src, self.tmp / "ia_o", src / "radiology_detail.parquet", publish=False)
        self.assertEqual(res["status"], "INTERNAL_ONLY", res.get("violations"))
        self.assertNotIn("violations", res)


class RunPath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = FX.write(self.tmp / "src")
        self.det = self.src / "radiology_detail.parquet"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_internal_aggregates_never_overwritten(self):
        R.run(self.src, self.tmp / "o1", self.det, internal_dir=self.tmp / "int", withhold_all=True)
        p = self.tmp / "int" / "INTERNAL_AGGREGATES.json"
        before = p.read_bytes()
        with self.assertRaises(FileExistsError):
            R.run(self.src, self.tmp / "o2", self.det, internal_dir=self.tmp / "int", withhold_all=True)
        self.assertEqual(p.read_bytes(), before)

    def test_external_mismatch_withholds_all_tables(self):
        wrong = dict.fromkeys(DSC.EXTERNAL_CELLS, 123456)
        res = R.run(self.src, self.tmp / "o", self.det, external_public=wrong)
        self.assertEqual(res["status"], "DONE", res.get("violations"))
        self.assertEqual(res["disclosure_check"]["published_tables"], [])
        self.assertIn("external_public_mismatch", res["disclosure_check"])

    def test_end_to_end_scope_permissions_and_temp_file(self):         # 끝단 실행 1회로 공개 범위·권한·임시 파일을 함께 확인
        res = R.run(self.src, self.tmp / "o", self.det, internal_dir=self.tmp / "int")
        self.assertEqual(res["status"], "DONE", res.get("violations"))
        self.assertEqual(sorted(p.name for p in (self.tmp / "o").iterdir()), ["time_policy_audit_v2_public.json"])
        self.assertEqual(os.stat(self.tmp / "int" / "INTERNAL_AGGREGATES.json").st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.tmp / "int" / "DISCLOSURE_INTERNAL.json").st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.tmp / "int").st_mode & 0o777, 0o700)
        pub = json.loads((self.tmp / "o" / "time_policy_audit_v2_public.json").read_text(encoding="utf-8"))
        flat = DV.flatten({k: v for k, v in pub.items() if k in DV.DATA_ROOTS})
        for k, v in flat.items():
            if k.split("/")[0] in ("flags_by_policy", "grades_by_policy", "categories") or "STRICT=" in k:
                self.assertEqual(v, W, k)
        self.assertFalse(any(t.startswith(("crosstab_", "flags_by_policy", "grades_by_policy", "categories_")) for t in res["disclosure_check"]["published_tables"]))

    def test_unknown_top_level_block_not_verifiable(self):
        p = self.tmp / "x.json"
        p.write_text(json.dumps({"stays": {"a": 50}, "new_block": {"b": 3}}), encoding="utf-8")
        self.assertEqual(DV.verify_file(p, rel(["stays/a"]))["status"], DV.NOT_VERIFIABLE)

    def test_internal_out_prefix_enforced(self):
        with self.assertRaises(SystemExit):
            R.main(["--src", str(self.src), "--out", str(self.tmp / "ox"), "--i-have-user-approval", "--code-sha-manifest", "x",
                    "--internal-out", R.SEALED_ROOT + "/extract_v2_20261030_1139"])


class SyntheticAttack(unittest.TestCase):
    """합성 자료 끝단 공격: 공개 파일 + 선언 관계로 공격자처럼 단순 계산(LP 와 별도 경로)."""

    def test_random_synth_public_files(self):
        checked = 0
        for seed in (7001, 7002, 7003, 7004):
            tmp = Path(tempfile.mkdtemp())
            try:
                src = SR.make(seed, tmp / "src")
                res = R.run(src, tmp / "o", src / "radiology_detail.parquet", internal_dir=tmp / "int")
                if res.get("status") == "ABORT" and set(res.get("violations", {})) <= {"B_zero_match_guard_ecg", "B_zero_match_guard_lab", "B_zero_match_guard_radiology"}:
                    continue
                self.assertEqual(res["status"], "DONE", res.get("violations"))
                self.assertEqual(res["disclosure_check"]["verifier_status"], DV.VERIFIED)
                pub = json.loads((tmp / "o" / "time_policy_audit_v2_public.json").read_text(encoding="utf-8"))
                flat = DV.flatten({k: v for k, v in pub.items() if k in DV.DATA_ROOTS})
                truth = json.loads((tmp / "int" / "INTERNAL_AGGREGATES.json").read_text(encoding="utf-8"))["flat"]
                self.assertFalse([k for k, v in flat.items() if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 9])
                ext = {c: truth[c] for c in DSC.EXTERNAL_CELLS if truth[c] >= 10}
                for e in DSC.build_schema()["equalities"]:             # 공격: 등식에 숨은 칸이 1개면 나머지로 직접 계산
                    hidden = [c for c in e["cells"] if not (isinstance(flat.get(c), int) or c in ext)]
                    if len(hidden) == 1:
                        v = truth[hidden[0]]
                        if flat.get(hidden[0]) in (S, W, C) and 1 <= v <= 9:
                            self.fail(f"역산 가능 seed={seed} {hidden[0]}")
                checked += 1
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        self.assertGreaterEqual(checked, 3)


if __name__ == "__main__":
    unittest.main()
