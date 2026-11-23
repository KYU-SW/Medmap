"""실제 실행 관문·1회 실행·사후 검증 테스트(합성 자료만, 실제 MIMIC 없음). PROTOCOL_TIME_v2.md §12."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import disclosure_verifier as DV  # noqa: E402
import fixture_v2 as FX  # noqa: E402
import records_v2 as RV  # noqa: E402
import run_time_policy_audit_v2 as R  # noqa: E402
import verify_counted_run as VC  # noqa: E402

RG = R.RG_TOOL


def make_project(root: Path, status: str, last_gate: str, deviations: list, code_manifest: Path, lock: bool = True, reviewed_code=True):
    exp = root / ".research-guardian" / "experiments" / R.EXP_ID
    exp.mkdir(parents=True)
    (root / ".research-guardian" / "enabled").write_text("", encoding="utf-8")
    rep = root / ".research-guardian" / "audits" / "gate.md"
    rep.parent.mkdir(parents=True)
    rep.write_text("x", encoding="utf-8")
    m = {"experiment_id": R.EXP_ID, "review_status": status, "audit_trail": [{"at": "t", "kind": "gate", "verdict": last_gate, "report": str(rep.relative_to(root))}],
         "code_sha_manifest_sha256": R.sha(code_manifest) if reviewed_code else "0" * 64}
    (exp / "manifest.yaml").write_text(yaml.safe_dump(m, allow_unicode=True), encoding="utf-8")
    (exp / "deviations.yaml").write_text(yaml.safe_dump({"deviations": deviations}, allow_unicode=True), encoding="utf-8")
    if lock:
        subprocess.run([sys.executable, str(RG), "freeze", "--root", str(root), "--exp", R.EXP_ID], check=True, capture_output=True)
    return exp


APPROVED = [{"at": "t", "field": "proposed_method", "status": "APPROVED", "reason": "변경 기록", "approved_by": "user"}]


class GateGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.code = self.tmp / "CODE.json"
        self.code.write_text("{}", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_authorized_only_with_run_lock_and_reviewed_code(self):
        make_project(self.tmp / "p", "RUN", "RUN", [], self.code)
        self.assertEqual(R.gate_authorization(self.tmp / "p", self.code), [])

    def test_approved_deviation_does_not_authorize(self):              # deviation APPROVED ≠ 실행 권한
        make_project(self.tmp / "p", "NEEDS_FIX", "NEEDS_FIX", APPROVED * 50, self.code, lock=False)
        why = R.gate_authorization(self.tmp / "p", self.code)
        self.assertIn("REVIEW_STATUS_NOT_RUN", why)
        self.assertIn("LAST_GATE_NOT_RUN", why)
        self.assertIn("PROTOCOL_NOT_LOCKED", why)

    def test_rg_tool_hook_ignores_approved_deviation(self):            # 공식 hook 판단도 동일
        make_project(self.tmp / "p", "NEEDS_FIX", "NEEDS_FIX", APPROVED, self.code, lock=False)
        q = subprocess.run([sys.executable, str(RG), "gate-check", "--cwd", str(self.tmp / "p"), "--command", f"RG_EXP={R.EXP_ID} python evaluate_train.py"], capture_output=True, text=True)
        self.assertIn("NEEDS_FIX", q.stdout)

    def test_status_edited_to_run_without_gate_record_refused(self):   # review_status 만 RUN 으로 바꾼 경우
        make_project(self.tmp / "p", "RUN", "NEEDS_FIX", [], self.code)
        self.assertIn("LAST_GATE_NOT_RUN", R.gate_authorization(self.tmp / "p", self.code))

    def test_protocol_change_after_lock_refused(self):
        exp = make_project(self.tmp / "p", "RUN", "RUN", [], self.code)
        m = yaml.safe_load((exp / "manifest.yaml").read_text(encoding="utf-8"))
        m["primary_metric"] = "changed"
        (exp / "manifest.yaml").write_text(yaml.safe_dump(m, allow_unicode=True), encoding="utf-8")
        self.assertIn("PROTOCOL_LOCK_MISMATCH", R.gate_authorization(self.tmp / "p", self.code))

    def test_unreviewed_code_manifest_refused(self):
        make_project(self.tmp / "p", "RUN", "RUN", [], self.code, reviewed_code=False)
        self.assertIn("CODE_MANIFEST_NOT_THE_REVIEWED_ONE", R.gate_authorization(self.tmp / "p", self.code))

    def test_real_project_is_not_authorized_by_tests(self):            # 관문 함수는 사유 목록을 돌려줄 뿐 — 없는 manifest 는 거부
        self.assertEqual(R.gate_authorization(self.tmp / "nope", self.code), ["MANIFEST_MISSING"])

    def test_cli_refuses_before_reading_data(self):
        src = self.tmp / "no_such_src"
        with mock.patch.object(R, "RG_ROOT", self.tmp / "nope"), mock.patch.object(R, "SEALED_ROOT", str(self.tmp)), \
                mock.patch.object(R, "COUNTED_MARKER", self.tmp / "marker"), self.assertRaises(SystemExit) as cm:
            R.main(["--src", str(src), "--out", str(self.tmp / "o"), "--rad-detail", "x", "--i-have-user-approval", "--code-sha-manifest", str(self.code),
                    "--internal-out", str(self.tmp / "int")])
        self.assertIn("GATE_NOT_AUTHORIZED", str(cm.exception))
        self.assertFalse((self.tmp / "marker").exists())               # 거부되면 표지도 안 생김
        self.assertFalse((self.tmp / "o").exists())

    def test_cli_requires_rad_detail(self):
        with mock.patch.object(R, "SEALED_ROOT", str(self.tmp)), self.assertRaises(SystemExit) as cm:
            R.main(["--src", "s", "--out", str(self.tmp / "o"), "--i-have-user-approval", "--code-sha-manifest", str(self.code), "--internal-out", str(self.tmp / "int")])
        self.assertIn("--rad-detail", str(cm.exception))


class OneShot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.code = self.tmp / "CODE.json"
        self.code.write_text("{}", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_claim_refused(self):
        R.claim_counted_run(self.tmp / "m", {"a": 1})
        with self.assertRaises(FileExistsError):
            R.claim_counted_run(self.tmp / "m", {"a": 2})
        self.assertEqual(json.loads((self.tmp / "m").read_text(encoding="utf-8")), {"a": 1})

    def test_failed_run_keeps_marker_and_second_cli_refused(self):     # 실패한 실행을 새 실행으로 반복 불가
        a = mock.Mock(code_sha_manifest=str(self.code), out=str(self.tmp / "o"), internal_out=str(self.tmp / "i"))
        with mock.patch.object(R, "gate_authorization", return_value=[]), mock.patch.object(R, "COUNTED_MARKER", self.tmp / "m"):
            R.authorize_counted_run(a)
            self.assertTrue((self.tmp / "m").exists())
            with self.assertRaises(SystemExit) as cm:
                R.authorize_counted_run(a)
        self.assertIn("COUNTED_RUN_ALREADY_USED", str(cm.exception))


class RecordUnits(unittest.TestCase):
    def test_unique_records_stays_patients_separate(self):             # 환자 1: 체류 11·12, lab 고유 5건 + 체류 12 1건
        co, labs, rd, ecg, det = FX.frames()
        p = RV.prepare(co, labs, rd, ecg, det, lambda n: dict(zip(rd["note_id"], rd["text"]))[n])
        a = p.audit
        self.assertEqual((a["lab"]["attributed"], a["lab"]["stays_with_records"], a["lab"]["patients_with_records"]), (6, 2, 1))
        self.assertEqual((a["radiology"]["cta_input"], a["radiology"]["stays_with_records"], a["radiology"]["patients_with_records"]), (12, 7, 7))
        self.assertEqual((a["ecg"]["matched"], a["ecg"]["stays_with_records"], a["ecg"]["patients_with_records"]), (1, 1, 1))
        self.assertEqual((a["triage"]["stays_with_records"], a["triage"]["patients_with_records"]), (1, 1))

    def test_record_not_counted_per_stay(self):                        # 겹친 체류에 걸친 기록은 AMBIGUOUS 1건 — 체류마다 다시 세지 않음
        co, labs, rd, ecg, det = FX.frames()
        p = RV.prepare(co, labs, rd, ecg, det, lambda n: dict(zip(rd["note_id"], rd["text"]))[n])
        ids = [x.record_id for recs in p.per_stay.values() for x in recs if x.source == "lab"]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(p.audit["lab"]["ambiguous"], 1)

    def test_cross_patient_addendum_regression(self):                  # 다른 환자 addendum 은 저장 순서와 무관하게 연결 안 함
        co, labs, rd, ecg, det = FX.frames()
        rd = rd.copy()
        rd.loc[rd["note_id"] == FX.NIDS["a7"], "storetime"] = FX.ts(0.5)    # 부모보다 먼저 저장
        p = RV.prepare(co, labs, rd, ecg, det, lambda n: dict(zip(rd["note_id"], rd["text"]))[n])
        self.assertNotIn(FX.NIDS["a7"], p.links)
        self.assertEqual(p.audit["radiology"]["link_subject_mismatch"], 1)


class RealInputDtypes(unittest.TestCase):
    """실제 추출본의 열 형식(시각 = 문자열, ed_stay_id = 실수)과 같은 입력에서 정확값이 같아야 함 — 실제 실행 1회가 형식 때문에 무효가 되는 것 방지."""

    def test_string_time_columns_same_exact_counts(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            base = FX.write(tmp / "a")
            flat_a = R.run(base, tmp / "oa", base / "radiology_detail.parquet", publish=False)["flat"]
            co, labs, rd, ecg, det = FX.frames()
            fmt = lambda col: col.map(lambda x: None if pd.isna(x) else str(x))
            for df, cols in ((labs, ("charttime", "storetime")), (rd, ("charttime", "storetime")), (ecg, ("ecg_time_ext",))):
                for c in cols:
                    df[c] = fmt(df[c])
            labs.loc[labs.index[0], "charttime"] = str(labs.loc[labs.index[0], "charttime"]) + ".000000"   # 형식 혼합
            b = tmp / "b"
            b.mkdir()
            co.to_parquet(b / "cohort.parquet"); labs.to_parquet(b / "labs.parquet"); rd.to_parquet(b / "radiology.parquet")
            ecg.to_parquet(b / "ecg.parquet"); det.to_parquet(b / "radiology_detail.parquet")
            res = R.run(b, tmp / "ob", b / "radiology_detail.parquet", publish=False)
            self.assertEqual(res["status"], "INTERNAL_ONLY", res.get("violations"))
            self.assertEqual(res["flat"], flat_a)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class PostRunVerify(unittest.TestCase):
    """합성 실행 1회를 만들어 검증기가 통과·변조 탐지하는지."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.src = FX.write(cls.tmp / "src")
        cls.det = cls.src / "radiology_detail.parquet"
        cls.code = cls.tmp / "CODE.json"
        cls.code.write_text(json.dumps(R.code_sha()), encoding="utf-8")
        cls.run_root = cls.tmp / "runs"
        cls.run_dir = cls.run_root / "real_run_x"
        cls.run_root.mkdir()
        cls.int = cls.tmp / "int"
        res = R.run(cls.src, cls.run_dir, cls.det, internal_dir=cls.int, expected_code_sha=json.loads(cls.code.read_text(encoding="utf-8")))
        assert res["status"] == "DONE"
        R.write_run_record(cls.run_dir, cls.int, cls.code)
        cls.proj = cls.tmp / "proj"
        make_project(cls.proj, "RUN", "RUN", [], cls.code)
        cls.marker = cls.tmp / "marker"
        cls.marker.write_text(json.dumps({"out_dir": cls.run_dir.name, "internal_dir": cls.int.name, "code_sha_manifest_sha256": R.sha(cls.code)}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, run=None, internal=None, src=None, code=None, marker=None, proj=None):
        return VC.verify(run or self.run_dir, internal or self.int, src or self.src, self.det, code or self.code, root=proj or self.proj, marker=marker or self.marker, skip_frozen=True)

    def clone(self, name):
        d = self.tmp / name
        d.mkdir()
        run = d / "real_run_x"
        shutil.copytree(self.run_dir, run)
        i = d / "int"
        shutil.copytree(self.int, i)
        return run, i

    def test_clean_run_passes(self):
        out = self.verify()
        self.assertEqual(out["status"], "PASS", out["failed_names"])

    def test_output_has_no_values(self):
        txt = json.dumps(self.verify(), ensure_ascii=False)
        for bad in list(FX.NIDS.values()) + ["2150-"]:
            self.assertNotIn(bad, txt)

    def test_tampered_public_file_detected(self):
        run, i = self.clone("a")
        p = run / VC.PUBLIC_NAME
        d = json.loads(p.read_text(encoding="utf-8"))
        d["stays"]["cohort_stays"] = 999
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        out = self.verify(run=run, internal=i)
        self.assertEqual(out["checks"]["output_integrity"], "FAIL")
        self.assertEqual(out["checks"]["public_equals_internal"], "FAIL")

    def test_tampered_internal_detected(self):
        run, i = self.clone("b")
        p = i / "INTERNAL_AGGREGATES.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["flat"]["records/lab/attributed"] += 1
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        out = self.verify(run=run, internal=i)
        self.assertEqual(out["status"], "FAIL")
        self.assertEqual(out["checks"]["output_integrity"], "FAIL")
        self.assertEqual(out["checks"]["raw_denominators_match"], "FAIL")
        self.assertEqual(out["checks"]["policy_identities_hold"], "FAIL")

    def test_small_public_integer_detected(self):
        run, i = self.clone("c")
        p = run / VC.PUBLIC_NAME
        d = json.loads(p.read_text(encoding="utf-8"))
        d["stays"]["t1_equals_t2"] = 1
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        out = self.verify(run=run, internal=i)
        self.assertEqual(out["checks"]["no_public_small_integer"], "FAIL")

    def test_detail_table_public_detected(self):
        run, i = self.clone("d")
        p = run / VC.PUBLIC_NAME
        d = json.loads(p.read_text(encoding="utf-8"))
        k = next(iter(d["flags_by_policy"][R.STRICT]))
        d["flags_by_policy"][R.STRICT][k] = 0
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.verify(run=run, internal=i)["checks"]["detail_tables_withheld"], "FAIL")

    def test_identifier_in_public_detected(self):
        run, i = self.clone("e")
        p = run / VC.PUBLIC_NAME
        d = json.loads(p.read_text(encoding="utf-8"))
        d["interpretation"] += " 90000001-RR-1"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.verify(run=run, internal=i)["checks"]["no_identifier_pattern_in_public"], "FAIL")

    def test_changed_input_detected(self):
        src2 = self.tmp / "src2"
        shutil.copytree(self.src, src2)
        co = pd.read_parquet(src2 / "cohort.parquet")
        co.iloc[:-1].to_parquet(src2 / "cohort.parquet")
        out = self.verify(src=src2)
        self.assertEqual(out["checks"]["input_sha_matches"], "FAIL")
        self.assertEqual(out["checks"]["raw_denominators_match"], "FAIL")

    def test_code_change_detected(self):
        c2 = self.tmp / "CODE2.json"
        d = json.loads(self.code.read_text(encoding="utf-8"))
        d["reassess.py"] = "0" * 64
        c2.write_text(json.dumps(d), encoding="utf-8")
        out = self.verify(code=c2)
        self.assertEqual(out["checks"]["code_sha_matches_freeze"], "FAIL")

    def test_second_run_folder_detected(self):
        (self.tmp / "runs2").mkdir()
        run = self.tmp / "runs2" / "real_run_x"
        shutil.copytree(self.run_dir, run)
        (self.tmp / "runs2" / "real_run_y").mkdir()
        self.assertEqual(self.verify(run=run)["checks"]["counted_run_once"], "FAIL")

    def test_missing_marker_detected(self):
        self.assertEqual(self.verify(marker=self.tmp / "none")["checks"]["counted_run_once"], "FAIL")

    def test_gate_not_run_detected(self):
        p2 = self.tmp / "proj2"
        make_project(p2, "NEEDS_FIX", "NEEDS_FIX", APPROVED, self.code, lock=False)
        self.assertEqual(self.verify(proj=p2)["checks"]["gate_authorization"], "FAIL")

    def test_frozen_artifact_check_on_real_tree(self):                 # 실제 EXP-01 FINAL·표지·EXP-02 동결 확인(내부 권한 칸은 합성 폴더)
        import os
        os.chmod(self.int, 0o700)
        with mock.patch.object(R, "SEALED_ROOT", str(self.int)):
            out = VC.check_frozen_artifacts(self.int)
        self.assertEqual(out["frozen_artifacts_preserved"], [])
        self.assertEqual(out["sealed_permissions"], [])


class IntegerGap(unittest.TestCase):
    def test_lp_passes_integer_fails(self):                            # 3x + 5y = 66, y ≥ 10: LP x ∈ [0,5](1 이상 5개 통과), 정수 해는 (x,y)=(2,12) 뿐 → FAILED
        r = {"universe": ["stays/x", "stays/y", "stays/t"], "equalities": [{"cells": ["stays/t", "stays/x", "stays/y"], "coef": [1.0, -3.0, -5.0]}],
             "inequalities": [], "constant": {}, "generator_constant": {}}
        r["_index"] = {c: i for i, c in enumerate(r["universe"])}
        flat = {"stays/t": 66, "stays/x": DV.WITHHELD_TOKEN, "stays/y": DV.COMPLEMENT_TOKEN}
        self.assertEqual(DV.verify_flat(flat, {}, r)["status"], DV.VERIFIED)
        self.assertEqual(DV.verify_flat(flat, {}, r, integer_check=True)["status"], DV.FAILED)

    def test_public_file_check_uses_integer_by_default(self):
        import inspect
        self.assertTrue(inspect.signature(DV.verify_file).parameters["integer_check"].default)


if __name__ == "__main__":
    unittest.main()
