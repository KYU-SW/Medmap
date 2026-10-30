"""FINAL 재시도 보호(독립 검증 M-1, 2026-10-28) — run_exp01.main() 전체 흐름을 가상 사례로 재현.
run_real(실데이터 적재)만 가상 사례 반환으로 바꾸고, 출력 루트(OUTPUTS)는 임시 폴더. 실제 outputs/·FINAL_USED 는 건드리지 않는다."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

import artifacts  # noqa: E402
import confirm  # noqa: E402
import lockhash  # noqa: E402
import par_world  # noqa: E402
import run_exp01  # noqa: E402
import split_rules  # noqa: E402

REAL_OUTPUTS = HERE / "outputs"
TAU = 0.001
_STATE = {}


def _toy():
    if "recs" not in _STATE:
        cases, kw, severe, prior = par_world.toy_world(n=24, with_tree=False)
        kw = dict(kw, taus=[TAU])
        k = dict(kw)
        recs = run_exp01.evaluate(cases, k.pop("sem"), k.pop("lik"), k.pop("classes"), k.pop("budgets"), k.pop("taus"),
                                  k.pop("seeds"), **k)
        _STATE.update(recs=recs, severe=severe, prior=prior, kw=kw)
    return _STATE


def fake_run_real(cfg):
    s = _toy()
    return (s["recs"], s["severe"], s["prior"], s["kw"]["classes"], s["kw"]["lik"],
            {"evaluated_split": cfg["split"], "evaluated_rows": 24}, {}, None)


def env_fail(cfg):
    import errno
    raise OSError(errno.ENOSPC, "simulated environment failure (No space left on device) before any metric")


class FinalGuardScenarios(unittest.TestCase):
    def setUp(self):
        self.real_marker_before = (REAL_OUTPUTS / "FINAL_USED").exists()
        self.real_ledger_before = (REAL_OUTPUTS / run_exp01.FINAL_LEDGER).exists()
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.out_root = d / "outputs"
        self.out_root.mkdir()
        sel = self.out_root / "select_x"                     # G: SELECT 결과(지표 파일 포함)만 있는 상태
        sel.mkdir()
        smoke = self.out_root / "smoke_x"
        smoke.mkdir()
        (smoke / "run_meta.json").write_text(json.dumps({"split": "SELECT_SMOKE"}))
        (smoke / "per_case.parquet").write_bytes(b"x")
        self.fcfg = d / "final.json"
        self.fcfg.write_text(json.dumps(dict(run_exp01.DEFAULT_CONFIG, split="FINAL", tau_selected=TAU,
                                             tau_selection_run=str(sel))))
        h = lockhash.run_lock_hash(self.fcfg, run_exp01.CODE_SCOPE)
        self.sha = h["lock_sha256"]
        (sel / "tau_selection.json").write_text(json.dumps({"tau": TAU, "source_split": "SELECT"}))
        (sel / "run_meta.json").write_text(json.dumps({"split": "SELECT", "run_lock": {"parts": h["parts"]}}))
        (sel / "per_case.parquet").write_bytes(b"x")
        (sel / "summary.json").write_text(json.dumps({"meta": {"split": "SELECT"}}))
        self.lock = d / "lock.json"
        self.lock.write_text(json.dumps({"config_sha256": self.sha, "config_path": str(self.fcfg),
                                         "outputs_root": str(self.out_root.resolve())}))
        self.marker = self.out_root / "FINAL_USED"
        self.patches = [mock.patch.object(run_exp01, "OUTPUTS", self.out_root),
                        mock.patch.object(run_exp01, "rg_status_ok", lambda: True),
                        mock.patch.object(run_exp01, "run_real", fake_run_real)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()
        self.assertEqual((REAL_OUTPUTS / "FINAL_USED").exists(), self.real_marker_before)          # 실제 사용 기록 불변
        self.assertEqual((REAL_OUTPUTS / run_exp01.FINAL_LEDGER).exists(), self.real_ledger_before)

    def run_main(self, name, retry=False, out=None, reason="test: simulated environment failure before metrics"):
        argv = ["run_exp01.py", "--config", str(self.fcfg), "--out", str(out or (self.out_root / name)), "--approved",
                "--final-lock", str(self.lock)] + (["--retry-environmental"] if retry else [])
        if retry and reason is not None:
            argv += ["--retry-reason", reason]
        with mock.patch.object(sys, "argv", argv):
            run_exp01.main()

    def refused(self, name, retry=False, out=None, code=None, reason="test: simulated environment failure before metrics"):
        before = self.marker.read_text() if self.marker.exists() else None
        target = Path(out or (self.out_root / name))
        with self.assertRaises((SystemExit, split_rules.SplitInvalid)) as cm:
            self.run_main(name, retry, out, reason)
        self.assertFalse(target.exists(), "거부된 FINAL 이 출력 폴더를 만들면 안 됨")
        self.assertEqual(self.marker.read_text() if self.marker.exists() else None, before, "사용 기록 변경 금지")
        if code:
            self.assertIn(code, str(cm.exception))
        return str(cm.exception)

    def ledger(self):
        p = self.out_root / run_exp01.FINAL_LEDGER
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    # A + G
    def test_A_first_run_allowed_with_select_outputs_present(self):
        ev = run_exp01.final_evidence(self.out_root)
        self.assertEqual(ev["attempts"], [])                 # G: SELECT·SMOKE 결과를 FINAL 사용으로 보지 않음
        self.assertFalse(ev["metrics_written"])
        self.run_main("f1")
        f1 = self.out_root / "f1"
        for f in ("final_attempt.json", "per_case.parquet", "final_judgement.json", "comparisons.csv", "summary.json",
                  "run_meta.json"):
            self.assertTrue((f1 / f).exists(), f)
        self.assertEqual(self.marker.read_text().split(), ["used", self.sha])
        self.assertEqual([x["out"] for x in self.ledger()], [str(f1.resolve())])

    # B
    def test_B_per_case_saved_then_analysis_fails_blocks_retry(self):
        with mock.patch.object(confirm, "final_analysis", side_effect=RuntimeError("injected after per_case")):
            with self.assertRaises(RuntimeError):
                self.run_main("f1")
        f1 = self.out_root / "f1"
        self.assertTrue((f1 / "per_case.parquet").exists())
        self.assertFalse((f1 / "summary.json").exists())
        self.assertTrue(run_exp01.final_evidence(self.out_root)["metrics_written"])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")
        self.refused("f2", retry=False, code="EXP01_FINAL_ALREADY_USED")
        self.assertTrue((f1 / "per_case.parquet").exists())  # 결과 보존

    # C (실제 흐름 주입 + 통계 파일만 있는 폴더)
    def test_C_partial_stat_files_block_retry(self):
        orig = artifacts.write_all

        def partial(out, *a, **k):
            artifacts.write_csv(Path(out) / "metrics.csv", [{"status": "partial"}])
            raise RuntimeError("injected after metrics.csv")
        with mock.patch.object(artifacts, "write_all", partial):
            with self.assertRaises(RuntimeError):
                self.run_main("f1")
        self.assertIs(artifacts.write_all, orig)
        self.assertFalse((self.out_root / "f1" / "summary.json").exists())
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    def test_C2_only_stats_file_in_attempt_dir(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        (self.out_root / "f1" / "comparisons.csv").write_text("x\n")   # 통계 파일 하나만 남은 상태
        ev = run_exp01.final_evidence(self.out_root)
        self.assertTrue(ev["metrics_written"])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    # D
    def test_D_completed_final_blocks_rerun(self):
        self.run_main("f1")
        self.refused("f2", retry=False, code="EXP01_FINAL_ALREADY_USED")
        self.refused("f3", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    # E
    def test_E_final_results_in_other_folder_without_attempt_file(self):
        self.marker.write_text(f"used {self.sha}\n")
        other = self.out_root / "legacy_final"                 # 표지·장부 없이 run_meta 만 FINAL 인 결과 폴더
        other.mkdir()
        (other / "run_meta.json").write_text(json.dumps({"split": "FINAL"}))
        (other / "per_case.parquet").write_bytes(b"x")
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    def test_E2_evidence_without_marker_blocks(self):
        other = self.out_root / "legacy_final"
        other.mkdir()
        (other / "summary.json").write_text(json.dumps({"meta": {"split": "FINAL"}}))
        self.refused("f2", code="EXP01_FINAL_EVIDENCE_WITHOUT_USED_MARKER")

    def test_E3_out_outside_outputs_blocked(self):
        outside = Path(self.tmp.name) / "elsewhere" / "f1"
        self.refused("x", out=outside, code="EXP01_FINAL_OUT_OUTSIDE_OUTPUTS")
        self.assertFalse(self.marker.exists())

    def test_E3b_nested_out_blocked(self):
        self.refused("x", out=self.out_root / "sub" / "f1", code="EXP01_FINAL_OUT_OUTSIDE_OUTPUTS")
        self.assertFalse(self.marker.exists())

    def test_E4_ledger_listed_dir_missing_blocks(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        moved = Path(self.tmp.name) / "moved_f1"
        (self.out_root / "f1").rename(moved)                    # 시도 폴더를 다른 곳으로 옮긴 우회
        ev = run_exp01.final_evidence(self.out_root)
        self.assertTrue(ev["metrics_written"])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    def test_E6_attempt_file_detected_without_ledger(self):
        with mock.patch.object(confirm, "final_analysis", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                self.run_main("f1")
        (self.out_root / run_exp01.FINAL_LEDGER).unlink()       # 장부가 없어져도 시도 표지로 감지(임시 폴더에서만)
        ev = run_exp01.final_evidence(self.out_root)
        self.assertEqual(ev["attempts"], [str((self.out_root / "f1").resolve())])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")

    def test_E5_unreadable_meta_blocks(self):
        bad = self.out_root / "weird"
        bad.mkdir()
        (bad / "run_meta.json").write_text("{not json")
        self.assertTrue(run_exp01.final_evidence(self.out_root)["metrics_written"])

    # F
    def test_F_config_or_code_mismatch_refused(self):
        cfg = json.loads(self.fcfg.read_text())
        cfg["note"] = "changed after lock"
        self.fcfg.write_text(json.dumps(cfg))
        self.refused("f1", code="EXP01_FINAL_CONFIG_MISMATCH")
        self.fcfg.write_text(json.dumps({k: v for k, v in cfg.items() if k != "note"}))
        sel = self.out_root / "select_x"
        meta = json.loads((sel / "run_meta.json").read_text())
        meta["run_lock"]["parts"]["code"] = meta["run_lock"]["parts"]["code"][:-1]
        (sel / "run_meta.json").write_text(json.dumps(meta))
        self.refused("f1", code="EXP01_FINAL_CODE_DIFFERS_FROM_SELECT")
        self.assertFalse(self.marker.exists())

    # H
    def test_H_environmental_retry_only_when_allowed(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        f1 = self.out_root / "f1"
        self.assertEqual(sorted(p.name for p in f1.iterdir()), ["final_attempt.json", "final_status.jsonl"])
        self.assertFalse(run_exp01.final_evidence(self.out_root)["metrics_written"])
        self.refused("f2", retry=False, code="EXP01_FINAL_ALREADY_USED")       # 플래그 없으면 거부
        self.run_main("f2", retry=True)                                         # 조건 충족 → 1회 허용
        self.assertEqual(self.marker.read_text().split(), ["used", self.sha, "retry_environmental"])
        self.assertTrue((self.out_root / "f2" / "summary.json").exists())
        self.refused("f3", retry=True, code="EXP01_FINAL_RETRY_METRICS_EXIST")         # 두 번째 재시도 거부

    def test_H2_second_environmental_failure_cannot_retry_again(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
            with self.assertRaises(OSError):
                self.run_main("f2", retry=True)
        self.refused("f3", retry=True, code="EXP01_FINAL_ALREADY_USED")



def nonenv_fail(cfg):
    raise AssertionError("simulated non-environmental failure (e.g. leak check) before metrics")


def slow_run_real(cfg):
    import time as _t
    _t.sleep(2.5)
    return fake_run_real(cfg)


class FinalRetryRulesN1(FinalGuardScenarios):
    """N1 수정(2026-10-28): 파일 잠금·상태 기록·재시도 근거. 상속한 A~H 도 다시 돈다."""

    def _attempt_dir(self, name, pid, proc_start, events):
        d = self.out_root / name
        d.mkdir()
        (d / run_exp01.FINAL_ATTEMPT_FILE).write_text(json.dumps({"out": str(d.resolve()), "pid": pid, "proc_start": proc_start}))
        with open(d / run_exp01.FINAL_STATUS_FILE, "w") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        self.marker.write_text(f"used {self.sha}\n")
        return d

    def test_R1_retry_needs_reason(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        self.refused("f2", retry=True, reason=None, code="EXP01_FINAL_RETRY_NEEDS_REASON")
        self.refused("f2", retry=True, reason="   ", code="EXP01_FINAL_RETRY_NEEDS_REASON")

    def test_R2_non_environmental_failure_cannot_retry(self):
        with mock.patch.object(run_exp01, "run_real", nonenv_fail):
            with self.assertRaises(AssertionError):
                self.run_main("f1")
        st = run_exp01.final_status_read(self.out_root / "f1")
        self.assertEqual([e["event"] for e in st], ["STARTED", "FAILED"])
        self.assertIs(st[-1]["environmental"], False)
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_NOT_ENVIRONMENTAL:AssertionError")

    def test_R3_killed_attempt_state_unclear(self):
        import subprocess
        p = subprocess.Popen(["true"])
        p.wait()
        self._attempt_dir("f1", p.pid, "1", [{"event": "STARTED"}])              # 강제 종료: FAILED 기록 없음
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR:STARTED")
        d = self.out_root / "f9"
        self._attempt_dir("f9", p.pid, "1", [{"event": "STARTED"}, {"event": "EVALUATED"}])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR")
        self.assertTrue(d.exists())

    def test_R4_attempt_in_progress_refused(self):
        import subprocess
        p = subprocess.Popen(["sleep", "30"])
        try:
            self._attempt_dir("f1", p.pid, run_exp01._proc_start(p.pid), [{"event": "STARTED"}])
            self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_PREVIOUS_IN_PROGRESS")
        finally:
            p.kill()
            p.wait()

    def test_R5_unreadable_status_or_attempt_refused(self):
        d = self._attempt_dir("f1", 1, "1", [])
        (d / run_exp01.FINAL_STATUS_FILE).write_text("{broken")
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR:STATUS_UNREADABLE")
        (d / run_exp01.FINAL_STATUS_FILE).write_text(json.dumps({"event": "FAILED", "environmental": True}) + "\n")
        (d / run_exp01.FINAL_ATTEMPT_FILE).write_text(json.dumps({"out": str(d.resolve())}))       # pid 없음
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR:NO_PID")

    def test_R6_lock_held_by_other_process(self):
        import subprocess
        code = ("import fcntl,os,sys,time;fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT);"
                "fcntl.flock(fd,fcntl.LOCK_EX);print('L',flush=True);time.sleep(30)")
        p = subprocess.Popen([sys.executable, "-c", code, str(self.out_root / run_exp01.FINAL_LOCK_FILE)],
                             stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(), "L")
            self.refused("f1", code="EXP01_FINAL_LOCKED_BY_ANOTHER_PROCESS")          # 최초 실행도 잠금 중이면 거부
            self.assertFalse(self.marker.exists())
        finally:
            p.kill()
            p.wait()
        self.run_main("f1")                                                           # 잠금 해제 후 정상 허가

    def test_R7_lock_outputs_root_mismatch(self):
        body = json.loads(self.lock.read_text())
        body.pop("outputs_root")
        self.lock.write_text(json.dumps(body))
        self.refused("f1", code="EXP01_FINAL_LOCK_OUTPUTS_ROOT_MISMATCH")
        body["outputs_root"] = str(Path(self.tmp.name) / "other_outputs")
        self.lock.write_text(json.dumps(body))
        self.refused("f1", code="EXP01_FINAL_LOCK_OUTPUTS_ROOT_MISMATCH")
        self.assertFalse(self.marker.exists())

    def test_R8_marker_written_empty_blocks(self):
        self.marker.write_text("")                                                    # 표지 생성 중 강제 종료
        self.refused("f1", code="EXP01_FINAL_ALREADY_USED")
        self.refused("f1", retry=True, code="EXP01_FINAL_RETRY_NO_ATTEMPT_RECORD")

    def test_R9_status_and_retry_evidence_recorded(self):
        self.run_main("ok1")
        st = run_exp01.final_status_read(self.out_root / "ok1")
        self.assertEqual([e["event"] for e in st], ["STARTED", "EVALUATED", "COMPLETED"])

    def test_R10_retry_records_reason_and_evidence(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        st = run_exp01.final_status_read(self.out_root / "f1")
        self.assertEqual(st[-1]["error_type"], "OSError")
        self.assertIs(st[-1]["environmental"], True)
        self.run_main("f2", retry=True, reason="disk full at 03:10, see logs/x.log")
        att = json.loads((self.out_root / "f2" / run_exp01.FINAL_ATTEMPT_FILE).read_text())
        self.assertEqual(att["retry_reason"], "disk full at 03:10, see logs/x.log")
        self.assertEqual(att["retry_evidence"][0]["failed"]["error_type"], "OSError")
        led = self.ledger()
        self.assertEqual(led[-1]["retry_reason"], "disk full at 03:10, see logs/x.log")

    def test_R11_lock_released_after_main(self):
        with mock.patch.object(run_exp01, "run_real", env_fail):
            with self.assertRaises(OSError):
                self.run_main("f1")
        self.assertEqual(run_exp01._FINAL_LOCK, {})
        self.assertEqual(run_exp01._FINAL_RUN, {})


# ---------------- 실제 별도 프로세스 동시성(fork, 동시 시작 barrier) ----------------
def _proc_call(case, name, retry, barrier, q, run_real_fn):
    import io
    sys.stdout = io.StringIO()
    argv = ["run_exp01.py", "--config", str(case.fcfg), "--out", str(case.out_root / name), "--approved",
            "--final-lock", str(case.lock)]
    if retry:
        argv += ["--retry-environmental", "--retry-reason", "concurrency test"]
    try:
        with mock.patch.object(run_exp01, "run_real", run_real_fn), mock.patch.object(sys, "argv", argv):
            if barrier is not None:
                barrier.wait()
            run_exp01.main()
        q.put("OK")
    except BaseException as e:  # noqa: BLE001
        q.put(type(e).__name__ + ":" + str(e)[:60])


class ConcurrencyRealProcesses(FinalGuardScenarios):
    REPS = 6

    def _run(self, specs, barrier=True):
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        b = ctx.Barrier(len(specs)) if barrier else None
        ps = [ctx.Process(target=_proc_call, args=(self, n, r, b, q, fn)) for n, r, fn in specs]
        for p in ps:
            p.start()
        for p in ps:
            p.join(120)
        return [q.get() for _ in ps]

    def _completed(self):
        return sorted(p.name for p in self.out_root.iterdir()
                      if p.is_dir() and (p / "summary.json").exists() and (p / run_exp01.FINAL_ATTEMPT_FILE).exists())

    def _reset(self):
        import shutil
        for p in list(self.out_root.iterdir()):
            if p.name in ("select_x", "smoke_x"):
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()                         # 임시 폴더 안에서만

    def test_C1_concurrent_first_runs(self):
        _toy()
        for _ in range(self.REPS):
            self._reset()
            res = self._run([(f"f{i}", False, fake_run_real) for i in range(3)])
            self.assertLessEqual(sum(r == "OK" for r in res), 1, res)
            self.assertLessEqual(len(self._completed()), 1)

    def test_C2_concurrent_retries_after_env_failure(self):
        _toy()
        for _ in range(self.REPS):
            self._reset()
            self._run([("f0", False, env_fail)], barrier=False)
            res = self._run([(f"r{i}", True, fake_run_real) for i in range(3)])
            self.assertEqual(sum(r == "OK" for r in res), 1, res)                  # 정확히 1회 재시도
            self.assertEqual(len(self._completed()), 1)
            self.assertEqual(self.marker.read_text().split().count("retry_environmental"), 1)

    def test_C3_retry_while_first_running(self):
        _toy()
        import multiprocessing as mp
        import time as _t
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        pa = ctx.Process(target=_proc_call, args=(self, "f0", False, None, q, slow_run_real))
        pa.start()
        _t.sleep(1.0)
        pb = ctx.Process(target=_proc_call, args=(self, "r1", True, None, q, fake_run_real))
        pb.start()
        pa.join(120)
        pb.join(120)
        res = sorted([q.get(), q.get()])
        self.assertEqual(sum(r == "OK" for r in res), 1, res)
        self.assertTrue(any("EXP01_FINAL_LOCKED_BY_ANOTHER_PROCESS" in r for r in res), res)
        self.assertEqual(self._completed(), ["f0"])


def pool_broken(cfg):
    from concurrent.futures.process import BrokenProcessPool
    raise BrokenProcessPool("simulated worker OOM kill")


def fnf_fail(cfg):
    raise FileNotFoundError("simulated missing data path (configuration error)")


def kbd_fail(cfg):
    raise KeyboardInterrupt()


def einval_fail(cfg):
    import errno
    raise OSError(errno.EINVAL, "simulated invalid argument (non-resource OSError)")


class FinalRetryRulesReview(FinalGuardScenarios):
    """독립 리뷰(N1 수정) MINOR 대응: 환경 오류 분류표·찢어진 줄·실제 강제 종료·잠금 파일 바꿔치기·outputs 없음."""

    def _fail_then(self, fn, exc):
        with mock.patch.object(run_exp01, "run_real", fn):
            with self.assertRaises(exc):
                self.run_main("f1")
        return run_exp01.final_status_read(self.out_root / "f1")[-1]

    def test_V1_broken_pool_is_environmental(self):
        from concurrent.futures.process import BrokenProcessPool
        last = self._fail_then(pool_broken, BrokenProcessPool)
        self.assertIs(last["environmental"], True)
        self.run_main("f2", retry=True)

    def test_V2_file_not_found_is_not_environmental(self):
        last = self._fail_then(fnf_fail, FileNotFoundError)
        self.assertIs(last["environmental"], False)
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_NOT_ENVIRONMENTAL:FileNotFoundError")

    def test_V3_keyboard_interrupt_not_environmental(self):
        last = self._fail_then(kbd_fail, KeyboardInterrupt)
        self.assertIs(last["environmental"], False)
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_NOT_ENVIRONMENTAL:KeyboardInterrupt")

    def test_V2b_non_resource_oserror_not_environmental(self):
        last = self._fail_then(einval_fail, OSError)
        self.assertIs(last["environmental"], False)
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_NOT_ENVIRONMENTAL:OSError")

    def test_V4_torn_last_status_line(self):
        self._fail_then(env_fail, OSError)
        with open(self.out_root / "f1" / run_exp01.FINAL_STATUS_FILE, "a") as fh:
            fh.write('{"event": "FAIL')                                        # 기록 중 강제 종료(찢어진 줄)
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR:STATUS_UNREADABLE")

    def test_V5_real_sigkill_leaves_unclear_and_releases_lock(self):
        import multiprocessing as mp
        import signal
        import time as _t
        _toy()
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        p = ctx.Process(target=_proc_call, args=(self, "f1", False, None, q, slow_run_real))
        p.start()
        _t.sleep(1.2)
        os.kill(p.pid, signal.SIGKILL)
        p.join(30)
        st = run_exp01.final_status_read(self.out_root / "f1")
        self.assertEqual([e["event"] for e in st], ["STARTED"])
        self.refused("f2", retry=True, code="EXP01_FINAL_RETRY_STATE_UNCLEAR:STARTED")   # 잠금은 커널이 해제(LOCKED 아님)
        self.refused("f2", code="EXP01_FINAL_ALREADY_USED")

    def test_V6_lock_file_replaced_detected(self):
        import fcntl
        lock = self.out_root / run_exp01.FINAL_LOCK_FILE
        fd = os.open(lock, os.O_RDWR | os.O_CREAT)
        real_flock = fcntl.flock

        def flock_then_replace(f, op):
            real_flock(f, op)
            lock.unlink()
            lock.write_text("")                                                 # 잠금 직후 다른 파일로 바뀜
        try:
            with mock.patch.object(fcntl, "flock", flock_then_replace):
                self.refused("f1", code="EXP01_FINAL_LOCK_FILE_REPLACED")
        finally:
            os.close(fd)

    def test_V7_outputs_root_missing(self):
        import shutil
        body = json.loads(self.lock.read_text())
        missing = Path(self.tmp.name) / "no_outputs"
        body["outputs_root"] = str(missing)
        self.lock.write_text(json.dumps(body))
        with mock.patch.object(run_exp01, "OUTPUTS", missing):
            with self.assertRaises(SystemExit) as cm:
                self.run_main("f1", out=missing / "f1")
        self.assertIn("EXP01_FINAL_OUTPUTS_ROOT_MISSING", str(cm.exception))
        self.assertFalse(missing.exists())
        shutil.rmtree(missing, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
