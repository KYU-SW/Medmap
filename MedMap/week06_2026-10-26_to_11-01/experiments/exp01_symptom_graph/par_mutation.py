"""병렬화 코드 변이 검사(2026-10-28). 작업 폴더를 임시 폴더로 복사한 뒤 변이 1개씩 넣고 tests.test_parallel 을 돌린다.
기대: 모든 변이에서 테스트 실패(검출). 원본 폴더는 건드리지 않는다.

사용: ~/ai_env/bin/python par_mutation.py --out <새 json>
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

MUTANTS = [
    ("M01_no_dup_check", "parallel.py", "if len(set(ids)) != len(ids):", "if False:"),
    ("M02_no_sort_check", "parallel.py", "if ids != sorted(ids):", "if False:"),
    ("M03_no_chunk_check", "parallel.py", "                _check_chunk(res, cases, lo, hi, per_case)\n", ""),
    ("M04_counter_overwrite", "parallel.py", 'counters[k] += res["counters"][k]', 'counters[k] = res["counters"][k]'),
    ("M05_aref_last_not_max", "parallel.py", 'aref_max = max(aref_max, res["aref_max"])', 'aref_max = res["aref_max"]'),
    ("M06_chunk_overlap", "parallel.py", 'chunk = ctx["cases"][lo:hi]', 'chunk = ctx["cases"][lo:hi + 1]'),
    ("M07_trace_not_cleared", "parallel.py", "        TRACE_BUFFER.clear()\n", "        pass\n"),
    ("M08_plans_formula", "parallel.py", "n += len(taus) * (3 + len(seeds))", "n += len(taus) * (2 + len(seeds))"),
    ("M09_drop_noise_kw", "parallel.py", "leak_check=leak_check, aref=aref, noise=noise)",
     "leak_check=leak_check, aref=aref, noise=None)"),
    ("M10_record_key_check", "parallel.py", "if tuple(r.keys()) != self._keys:", "if False:"),
    ("M11_row_get_default", "parallel.py", "return default if col is None else col[self._i]", "return None if col is None else col[self._i]"),
    ("M12_record_order_check", "parallel.py", "if any(r[\"row_index\"] != rid for r in blk):", "if False:"),
    ("M13_count_check", "parallel.py", "if len(recs) != per_case * len(ids):", "if False:"),
    ("M14_chunk_ids_check", "parallel.py", 'if res["row_ids"] != ids:', "if False:"),
    ("M15_frame_col_order", "artifacts.py", "return pd.DataFrame({c: recs.column(c) for c in PER_CASE_COLS})",
     "return pd.DataFrame({c: recs.column(c) for c in reversed(PER_CASE_COLS)})"),
    ("M16_cfg_workers_bound", "run_exp01.py", 'not 1 <= par["workers"] <= 12', 'not 1 <= par["workers"] <= 13'),
    ("M17_cfg_check_not_called", "run_exp01.py", '    check_parallel(cfg.get("parallel"))\n', ""),
    ("M18_final_no_carry", "run_exp01.py", '            cfg["parallel"] = par\n', "            pass\n"),
    ("M19_cfg_int_type", "run_exp01.py", "all(type(par[k]) is int for k in par)", "True"),
    ("M20_aref_reset_shared", "parallel.py", '        aref.max_abs_diff = 0.0                       # 구간마다',
     '        pass                       # 구간마다'),
    ("M21_slice_index", "parallel.py", "return [Row(self._c, j) for j in range(*i.indices(self._n))]",
     "return [Row(self._c, j + 1) for j in range(*i.indices(self._n))]"),
    ("M23_group_write_slice", "artifacts.py", "frame(lo, lo + rows_per_group), schema=schema", "frame(lo, lo + rows_per_group - 1), schema=schema"),
    ("M22_index_bounds", "parallel.py", "if not 0 <= i < self._n:", "if False:"),
]
FINAL_MUTANTS = [
    ("F01_out_outside_allowed", "run_exp01.py", "if Path(out).resolve().parent != root:", "if False:"),
    ("F02_no_marker_check", "run_exp01.py", 'if ev["attempts"] and not marker.exists():', "if False:"),
    ("F03_metrics_written_false", "run_exp01.py", 'metrics_written=ev["metrics_written"])', "metrics_written=False)"),
    ("F04_per_case_not_metric", "run_exp01.py", 'frozenset({FINAL_ATTEMPT_FILE, "run_meta.json", FINAL_STATUS_FILE})',
     'frozenset({FINAL_ATTEMPT_FILE, "run_meta.json", FINAL_STATUS_FILE, "per_case.parquet"})'),
    ("F05_no_ledger_write", "run_exp01.py", 'fh.write(json.dumps(att, ensure_ascii=False, default=str) + "\\n")', "pass"),
    ("F06_no_attempt_file", "run_exp01.py", "        fh.write(json.dumps(att, ensure_ascii=False, indent=1, default=str))",
     "        pass"),
    ("F07_missing_dir_ok", "run_exp01.py", '            written = True\n            why.append(f"ATTEMPT_DIR_MISSING:{d}")',
     '            why.append(f"ATTEMPT_DIR_MISSING:{d}")'),
    ("F08_unreadable_ok", "run_exp01.py", '                why.append(f"UNREADABLE:{d.name}/{f}")', "                written = False"),
    ("F09_summary_split_ignored", "run_exp01.py", 'j.get("meta", {}).get("split")', "None"),
    ("F10_attempt_file_ignored", "run_exp01.py", "        if (d / FINAL_ATTEMPT_FILE).exists():", "        if False:"),
    ("F11_ledger_ignored", "run_exp01.py", "    if ledger.exists():", "    if False:"),
    ("F12_runmeta_split_ignored", "run_exp01.py", 'sp = j.get("split") if f == "run_meta.json" else', 'sp = None if f == "run_meta.json" else'),
    ("F13_extra_files_ignored", "run_exp01.py", "        if extra:\n            written = True", "        if False:\n            written = True"),
    ("N01_no_os_lock", "run_exp01.py", "    final_lock_acquire(root)                                    # 이후", "    pass  # 이후"),
    ("N02_lock_not_exclusive", "run_exp01.py", "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)", "fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)"),
    ("N03_no_retry_check", "run_exp01.py", "    if a.retry_environmental:\n        err, retry_evidence", "    if False:\n        err, retry_evidence"),
    ("N04_no_reason_needed", "run_exp01.py", '        return "EXP01_FINAL_RETRY_NEEDS_REASON", None', "        pass"),
    ("N05_in_progress_ignored", "run_exp01.py",
     '            return f"EXP01_FINAL_RETRY_PREVIOUS_IN_PROGRESS:{Path(d).name}", None', "            pass"),
    ("N06_unclear_allowed", "run_exp01.py", '        if last.get("event") != "FAILED":', '        if last.get("event") not in ("FAILED", "STARTED", "EVALUATED", None):'),
    ("N07_nonenv_allowed", "run_exp01.py", '        if last.get("environmental") is not True:', "        if False:"),
    ("N08_env_flag_always_true", "run_exp01.py", "environmental=_is_env_error(e)", "environmental=True"),
    ("N16_proc_alive_ignored", "run_exp01.py", 'if _proc_start(att["pid"]) == att["proc_start"] and not same_proc_done:', "if False:"),
    ("N17_same_proc_always_done", "run_exp01.py", 'same_proc_done = att["pid"] == os.getpid() and _FINAL_RUN.get("dir") is None',
     "same_proc_done = True"),
    ("N18_no_inode_check", "run_exp01.py", "    if not same:\n        os.close(fd)", "    if False:\n        os.close(fd)"),
    ("N19_all_oserror_env", "run_exp01.py", "    return isinstance(e, OSError) and e.errno in env_errno", "    return isinstance(e, OSError)"),
    ("N20_config_oserror_env", "run_exp01.py",
     "    if isinstance(e, (FileNotFoundError, PermissionError, IsADirectoryError, NotADirectoryError)):\n        return False",
     "    if False:\n        return False"),
    ("N21_root_missing_unchecked", "run_exp01.py", "    if not root.is_dir():\n        raise SystemExit(\"EXP01_FINAL_OUTPUTS_ROOT_MISSING\")",
     "    if False:\n        raise SystemExit(\"EXP01_FINAL_OUTPUTS_ROOT_MISSING\")"),
    ("N09_no_failed_record", "run_exp01.py", "        if d is not None:\n            import traceback", "        if False:\n            import traceback"),
    ("N10_outputs_root_unchecked", "run_exp01.py",
     'if "outputs_root" not in lock or Path(lock["outputs_root"]).resolve() != root:', "if False:"),
    ("N11_status_unreadable_ok", "run_exp01.py",
     '            return f"EXP01_FINAL_RETRY_STATE_UNCLEAR:STATUS_UNREADABLE:{Path(d).name}", None', "            st = []"),
    ("N12_no_attempt_record_ok", "run_exp01.py", '        return "EXP01_FINAL_RETRY_NO_ATTEMPT_RECORD", None', "        return None, []"),
    ("N13_lock_not_released", "run_exp01.py", "        _FINAL_RUN.clear()\n        final_lock_release()", "        _FINAL_RUN.clear()"),
    ("N14_completed_not_recorded", "run_exp01.py",
     '            final_status_append(_FINAL_RUN["dir"], "COMPLETED")', "            pass"),
    ("N15_retry_metrics_ignored", "run_exp01.py", '        return "EXP01_FINAL_RETRY_METRICS_EXIST", None', "        pass"),
]
EQUIVALENT_NOTE = {
    "N20_config_oserror_env": "FileNotFoundError 등은 errno(ENOENT·EACCES)가 환경 errno 집합 밖이라 명시 제외를 지워도 같은 분류(동치)",
    "F03_metrics_written_false": "N1 수정 후 재시도 판정(final_retry_check)이 결과 파일을 먼저 거부 → FinalGuard 의 metrics_written 은 중복 방어(동치 가능)",
    "M05_aref_last_not_max": "실제 실행 |차| 가 모두 0 이면 결과 동일 — 주입 테스트(test_aref_max_is_max_over_chunks)로 검출해야 함",
    "M20_aref_reset_shared": "작업자 내 누적 최대가 구간 최대보다 크거나 같을 뿐 전체 최대는 같음 — 동치 변이 가능(전체 최대 불변)",
    "M22_index_bounds": "list 자체가 IndexError — 음수/초과 인덱스 동치 가능",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--suite", choices=("parallel", "final"), default="parallel")
    a = ap.parse_args()
    res = []
    mutants, test_mod = (MUTANTS, "tests.test_parallel") if a.suite == "parallel" else (FINAL_MUTANTS,
                                                                                         "tests.test_final_guard")
    for name, f, old, new in mutants:
        if a.only and name not in a.only:
            continue
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d, "exp01")
            shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("outputs", "parallel_check", "logs", "__pycache__"))
            p = dst / f
            s = p.read_text(encoding="utf-8")
            if s.count(old) != 1:
                res.append({"mutant": name, "status": "NOT_APPLIED", "count": s.count(old)})
                continue
            p.write_text(s.replace(old, new), encoding="utf-8")
            t0 = time.time()
            r = subprocess.run([sys.executable, "-m", "unittest", test_mod], cwd=dst, capture_output=True,
                               text=True, timeout=1200)
            tail = [ln for ln in r.stderr.splitlines() if ln.startswith(("FAIL:", "ERROR:"))][:5]
            res.append({"mutant": name, "file": f, "status": "KILLED" if r.returncode != 0 else "SURVIVED",
                        "failing_tests": tail, "sec": round(time.time() - t0, 1),
                        "note": EQUIVALENT_NOTE.get(name)})
            print(name, res[-1]["status"], flush=True)
    clean = subprocess.run([sys.executable, "-m", "unittest", test_mod], cwd=HERE, capture_output=True,
                           text=True, timeout=1200)
    out = {"mutants": res, "killed": sum(r["status"] == "KILLED" for r in res), "total": len(res),
           "clean_suite_rc": clean.returncode}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"END killed={out['killed']}/{out['total']} clean_rc={clean.returncode}")


if __name__ == "__main__":
    main()
