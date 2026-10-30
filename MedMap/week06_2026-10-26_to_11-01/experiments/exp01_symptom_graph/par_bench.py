"""병렬화 동일성·성능 점검(2026-10-28). 가상 환자만 사용(tests/par_world.ddx_world) — DDXPlus 환자 행 미접근.

  equiv : 직렬(run_exp01.evaluate, 기본 BLAS 스레드) vs 병렬 작업자 1·2·4 — 기록·추적·산출물·τ 선택·확인적 분석 비교
  perf  : 추적 없이 직렬·작업자 1·2·4·6 실행시간·처리량·메모리(부모 RSS, 작업자 PSS 합, 시스템 사용량 증가)
  scale : 기록 수를 SELECT 전체 규모로 복제한 열 단위 표로 집계·산출물 쓰기 메모리·시간

사용: ~/ai_env/bin/python par_bench.py {equiv,perf,scale} --n N --out <새 폴더>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import resource
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

import artifacts  # noqa: E402
import confirm  # noqa: E402
import metrics as mt  # noqa: E402
import parallel  # noqa: E402
import par_world  # noqa: E402
import run_exp01  # noqa: E402

FLOAT_KEYS = ("p_top1", "brier", "truth_gap", "diff_recall")
META_KEYS = ("ms",)


# ------------------------------------------------------------------ 메모리 표본기
def _kb(path, key):
    try:
        for line in open(path):
            if line.startswith(key):
                return int(line.split()[1])
    except OSError:
        return None
    return None


def _children(pid):
    out = []
    try:
        for t in os.listdir(f"/proc/{pid}/task"):
            txt = open(f"/proc/{pid}/task/{t}/children").read().split()
            out += [int(x) for x in txt]
    except OSError:
        pass
    return out


class MemSampler:
    def __init__(self, every=0.5):
        self.every, self.stop_ev = every, threading.Event()
        self.peak = {"parent_rss_mb": 0.0, "children_pss_mb": 0.0, "children_rss_mb": 0.0, "total_pss_mb": 0.0,
                     "system_used_delta_mb": 0.0}
        tot = _kb("/proc/meminfo", "MemTotal:")
        self.base_used = tot - _kb("/proc/meminfo", "MemAvailable:")
        self.th = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        me = os.getpid()
        while not self.stop_ev.is_set():
            prss = (_kb(f"/proc/{me}/status", "VmRSS:") or 0) / 1024
            ppss = (_kb(f"/proc/{me}/smaps_rollup", "Pss:") or 0) / 1024
            cp = cr = 0.0
            for c in _children(me):
                cp += (_kb(f"/proc/{c}/smaps_rollup", "Pss:") or 0) / 1024
                cr += (_kb(f"/proc/{c}/status", "VmRSS:") or 0) / 1024
            tot = _kb("/proc/meminfo", "MemTotal:")
            used = (tot - _kb("/proc/meminfo", "MemAvailable:") - self.base_used) / 1024
            for k, v in (("parent_rss_mb", prss), ("children_pss_mb", cp), ("children_rss_mb", cr),
                         ("total_pss_mb", ppss + cp), ("system_used_delta_mb", used)):
                self.peak[k] = max(self.peak[k], v)
            time.sleep(self.every)

    def __enter__(self):
        self.th.start()
        return self

    def __exit__(self, *a):
        self.stop_ev.set()
        self.th.join()
        self.peak = {k: round(v, 1) for k, v in self.peak.items()}


# ------------------------------------------------------------------ 실행
def run_serial(cases, kw):
    k = dict(kw)
    cnt = {"aref_steps": 0, "reference_steps": 0}
    if k.get("aref") is not None:
        k["aref"].max_abs_diff = 0.0
    recs = run_exp01.evaluate(cases, k.pop("sem"), k.pop("lik"), k.pop("classes"), k.pop("budgets"), k.pop("taus"),
                              k.pop("seeds"), counters=cnt, **k)
    return recs, cnt, (kw["aref"].max_abs_diff if kw.get("aref") is not None else None)


def run_par(cases, kw, w, chunk):
    tab, cnt, amax, info = parallel.evaluate_parallel(cases, w, chunk, **kw)
    return tab, cnt, amax, info


def rowdict(r):
    return r if isinstance(r, dict) else r.to_dict()


def compare_records(ser, tab):
    """비트 동일 비교 + 실수 열 최대 |차|(보고용). 반환: 불일치 목록(최대 20), 실수 최대 |차|, 메타 열 비교."""
    bad, maxdiff, meta_diff = [], {k: 0.0 for k in FLOAT_KEYS}, 0
    if len(ser) != len(tab):
        return [f"LEN {len(ser)}!={len(tab)}"], maxdiff, None
    for a, b in zip(ser, tab):
        b = rowdict(b)
        if list(a.keys()) != list(b.keys()):
            bad.append("KEYS")
            continue
        for k in a:
            x, y = a[k], b[k]
            if k in META_KEYS:
                meta_diff += int(x != y)
                continue
            if k in FLOAT_KEYS and isinstance(x, float) and isinstance(y, float):
                if not (math.isnan(x) and math.isnan(y)):
                    maxdiff[k] = max(maxdiff[k], abs(x - y))
            same = (type(x) is type(y)) and (x == y or (isinstance(x, float) and math.isnan(x) and math.isnan(y)))
            if not same and len(bad) < 20:
                bad.append(f"{a['row_index']}|{a['model']}|{a['budget']}|{a['wd_mode']}|{a['seed']}|{a['tau']}|"
                           f"{a['noise']}|{k}:{x!r}!={y!r}")
    return bad, maxdiff, meta_diff


def write_outputs(recs, severe, kw, prior, d):
    tau_sel = mt.select_tau(artifacts.tau_stats(recs, severe, kw["taus"]), kw["taus"])
    artifacts.write_all(Path(d), recs, severe, kw["taus"], prior, kw["classes"], kw["lik"], {"split": "PARCHECK"},
                        {"split": "PARCHECK"}, tau_selection=tau_sel)
    return tau_sel


def compare_outputs(d0, d1):
    import pandas as pd
    res = {}
    a = pd.read_parquet(Path(d0, "per_case.parquet"))
    b = pd.read_parquet(Path(d1, "per_case.parquet"))
    res["per_case_rows"] = [len(a), len(b)]
    res["per_case_identical_except_ms"] = bool(a.drop(columns=["ms"]).equals(b.drop(columns=["ms"]))
                                               and list(a.dtypes) == list(b.dtypes))
    for f in ("subgroups.csv", "graph_stats.json", "tau_selection.json", "split_manifest.json"):
        res[f] = Path(d0, f).read_bytes() == Path(d1, f).read_bytes()
    ma = pd.read_csv(Path(d0, "metrics.csv"))
    mb = pd.read_csv(Path(d1, "metrics.csv"))
    res["metrics_identical_except_ms"] = bool(ma.drop(columns=["ms_p50", "ms_p95"]).equals(
        mb.drop(columns=["ms_p50", "ms_p95"])))
    res["metrics_ms_cols_differ_rows"] = int(((ma["ms_p50"] != mb["ms_p50"]) | (ma["ms_p95"] != mb["ms_p95"])).sum())
    return res


def equiv(a):
    cases, kw, severe, prior = par_world.ddx_world(n=a.n)
    out = {"mode": "equiv", "n_cases": len(cases), "world": "ddx_world(가상 환자, DDXPlus 근거 정의·STEP16B 우도표·A 모델)",
           "blas_serial": "기본(프로세스 시작 시 스레드 수)", "blas_workers": 1, "runs": {}}
    parallel.install_trace()
    t0 = time.time()
    ser, scnt, samax = run_serial(cases, kw)
    out["serial_s"] = round(time.time() - t0, 1)
    strace = list(parallel.TRACE_BUFFER)
    out["n_records"] = len(ser)
    out["serial_counters"] = scnt
    out["serial_aref_max_abs_diff"] = samax
    with tempfile.TemporaryDirectory() as d0:
        tsel0 = write_outputs(ser, severe, kw, prior, d0)
        fin0 = {str(t): confirm.final_analysis(ser, severe, t, par_world.SEEDS, B=a.boot) for t in (0.001,)}
        out["serial_tau_selection"] = tsel0
        for w in (1, 2, 4):
            parallel.TRACE_BUFFER.clear()
            t0 = time.time()
            tab, cnt, amax, info = run_par(cases, kw, w, a.chunk)
            r = {"wall_s": round(time.time() - t0, 1), "counters": cnt, "aref_max_abs_diff": amax,
                 "records": len(tab)}
            bad, maxdiff, meta_diff = compare_records(ser, tab)
            r["record_mismatches"] = bad
            r["float_max_abs_diff"] = maxdiff
            r["ms_values_differ"] = meta_diff
            tr = info.pop("traces")
            r["traces_n"] = [len(strace), len(tr)]
            r["traces_identical"] = json.dumps(tr) == json.dumps(strace)
            r["counters_identical"] = cnt == scnt
            r["case_ids_identical"] = tab.column("row_index")[::info["records_per_case"]] == [c["row_index"] for c in cases]
            with tempfile.TemporaryDirectory() as d1:
                tsel1 = write_outputs(tab, severe, kw, prior, d1)
                r["tau_selection_identical"] = tsel1 == tsel0
                r["outputs"] = compare_outputs(d0, d1)
            fin1 = {str(t): confirm.final_analysis(tab, severe, t, par_world.SEEDS, B=a.boot) for t in (0.001,)}
            r["confirmatory_identical"] = json.dumps(fin1, sort_keys=True, default=str) == json.dumps(
                fin0, sort_keys=True, default=str)
            r["parallel_info"] = {k: v for k, v in info.items()}
            out["runs"][str(w)] = r
            del tab
    parallel.uninstall_trace()
    ok = all(not r["record_mismatches"] and r["traces_identical"] and r["counters_identical"] and r["case_ids_identical"]
             and r["tau_selection_identical"] and r["confirmatory_identical"]
             and all(v is True for k, v in r["outputs"].items() if k not in ("per_case_rows", "metrics_ms_cols_differ_rows"))
             and all(v == 0.0 for v in r["float_max_abs_diff"].values())
             for r in out["runs"].values())
    stats_sel = sum(1 for t in strace for _, _, act in t["steps"] if act is not None)
    out["coverage"] = {
        "trace_runs": len(strace),
        "steps_with_active_set": stats_sel,
        "neg_answers": sum(1 for t in strace for _, ans in t["answers"] if tuple(ans) == ("NEG",)),
        "value_answers": sum(1 for t in strace for _, ans in t["answers"] if str(ans[0]).startswith("VALUE::")),
        "reactivations_total": sum(t["reactivations"] or 0 for t in strace),
        "prune_steps_total": sum(t["prune_steps"] or 0 for t in strace),
        "leak_pass": sum(1 for r in ser if r["leak"] == "PASS"),
        "severe_miss_records": sum(1 for r in ser if r["truth"] in severe and not r["in8"]),
        "aref_steps": scnt["aref_steps"], "reference_steps": scnt["reference_steps"]}
    out["VERDICT"] = "IDENTICAL" if ok else "MISMATCH"
    return out


def perf(a):
    cases, kw, _, _ = par_world.ddx_world(n=a.n)
    out = {"mode": "perf", "n_cases": len(cases), "runs": {}, "cpu_logical": os.cpu_count()}
    for label in ["serial"] + [f"w{w}" for w in a.workers]:
        t0 = time.time()
        with MemSampler() as ms:
            if label == "serial":
                recs, *_ = run_serial(cases, kw)
                n = len(recs)
            else:
                tab, cnt, amax, info = run_par(cases, kw, int(label[1:]), a.chunk)
                n = len(tab)
        wall = time.time() - t0
        r = {"wall_s": round(wall, 2), "cases_per_s": round(len(cases) / wall, 3), "s_per_case": round(wall / len(cases), 4),
             "records": n, "mem_peak": ms.peak}
        if label != "serial":
            r["worker_peak_rss_mb"] = [round(w["peak_rss_mb"], 1) for w in info["worker_stats"]]
            r["worker_busy_s"] = [round(w["sec"], 1) for w in info["worker_stats"]]
            del tab
        else:
            del recs
        out["runs"][label] = r
        print(label, r, file=sys.stderr, flush=True)
    s = out["runs"]["serial"]["wall_s"]
    for k, r in out["runs"].items():
        r["speedup_vs_serial"] = round(s / r["wall_s"], 3)
        if k != "serial":
            w = int(k[1:])
            r["parallel_efficiency"] = round(s / r["wall_s"] / w, 3)
    return out


def scale(a):
    """작업자 결과(가상 환자)를 행 단위로 복제해 SELECT 전체 기록 수(사례 a.target_cases)의 열 단위 표를 만들고 집계."""
    cases, kw, severe, prior = par_world.ddx_world(n=a.n)
    tab, _, _, info = run_par(cases, kw, 4, a.chunk)
    per = info["records_per_case"]
    base_cols = {k: tab.column(k) for k in tab.keys()}
    big = parallel.RecordTable(tab.keys())
    reps = math.ceil(a.target_cases / len(cases))
    t0 = time.time()
    with MemSampler() as ms_build:
        for rep in range(reps):
            n_take = min(len(cases), a.target_cases - rep * len(cases))
            m = n_take * per
            for k in big.keys():
                src = base_cols[k][:m]
                if k == "row_index":
                    big.column(k).extend(v + rep * 1_000_000 for v in src)
                elif k in FLOAT_KEYS or k == "ms":
                    big.column(k).extend(v * 1.0 if isinstance(v, float) else v for v in src)
                elif k == "counter":
                    big.column(k).extend(v + 0 if isinstance(v, int) else v for v in src)
                else:
                    big.column(k).extend(src)
            big._n += m
    build_s = time.time() - t0
    del tab, base_cols
    out = {"mode": "scale", "target_cases": a.target_cases, "records": len(big), "records_per_case": per,
           "build_s": round(build_s, 1), "build_mem_peak": ms_build.peak}
    with tempfile.TemporaryDirectory(dir=a.tmp) as d:
        t0 = time.time()
        with MemSampler() as ms:
            write_outputs(big, severe, kw, prior, d)
        out["write_all_s"] = round(time.time() - t0, 1)
        out["write_all_mem_peak"] = ms.peak
        out["per_case_parquet_mb"] = round(Path(d, "per_case.parquet").stat().st_size / 2**20, 1)
    t0 = time.time()
    with MemSampler() as ms:
        confirm.final_analysis(big, severe, 0.001, par_world.SEEDS, B=a.boot)
    out["confirm_B"] = a.boot
    out["confirm_s"] = round(time.time() - t0, 1)
    out["confirm_mem_peak"] = ms.peak
    out["process_peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("equiv", "perf", "scale"))
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--chunk", type=int, default=10)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--workers", type=int, nargs="*", default=[1, 2, 4, 6])
    ap.add_argument("--target-cases", type=int, default=102_460)
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    res = {"equiv": equiv, "perf": perf, "scale": scale}[a.mode](a)
    res["args"] = vars(a)
    res["elapsed_s"] = round(time.time() - t0, 1)
    res["env_threads"] = {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}
    (out / f"{a.mode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"END {a.mode} {res.get('VERDICT', '')} {out}", flush=True)


if __name__ == "__main__":
    main()
