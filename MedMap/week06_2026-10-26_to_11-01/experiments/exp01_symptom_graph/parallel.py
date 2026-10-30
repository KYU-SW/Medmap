"""EXP-01 사례 단위 병렬 실행(2026-10-28). 계산은 run_exp01.evaluate 그대로 — 이 모듈은 나누기·모으기·검증만.

- 작업자 = fork 로 만든 프로세스. 부모가 적재한 우도표·엔진·트리·사례 목록을 복사 없이(copy-on-write) 공유하고,
  작업자에게는 사례 구간 (lo, hi) 만 보낸다(전체 데이터프레임은 fork 전에 부모에서 지운다 — run_real).
- 탐색기·엔진은 사례·계획마다 새로 만들어지므로(evaluate 의 make()) 작업자 간 모델 상태 공유가 없다.
- 작업자별 카운터·aref 최대 |차| 는 구간마다 0 에서 시작해 부모가 합(카운터)·최대(|차|)로 모은다.
- 병합: 사례 ID(row_index) 오름차순 입력만 받고, 구간 순서대로 이어 붙여 직렬과 같은 기록 순서를 만든다.
  중복·누락·순서 뒤바뀜·사례당 기록 수 불일치는 모두 거부(Exp01Invalid).
- 결과는 열 단위 RecordTable(사례당 dict 를 남기지 않음 — SELECT 전체 약 880만 기록의 메모리 대책).
"""
from __future__ import annotations

import gc
import os
import resource
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

from core import Exp01Invalid

_CTX: dict = {}
TRACE_BUFFER: list | None = None          # 동일성 검증 전용(install_trace). 실행 기본값은 None


# ------------------------------------------------------------------ 열 단위 기록
class Row:
    """기록 한 행의 읽기 전용 보기. dict 처럼 r[key]·r.get(key) 지원."""
    __slots__ = ("_c", "_i")

    def __init__(self, cols, i):
        self._c, self._i = cols, i

    def __getitem__(self, k):
        return self._c[k][self._i]

    def get(self, k, default=None):
        col = self._c.get(k)
        return default if col is None else col[self._i]

    def keys(self):
        return self._c.keys()

    def to_dict(self):
        return {k: v[self._i] for k, v in self._c.items()}


class RecordTable(Sequence):
    """evaluate 기록(dict 목록)과 같은 값을 열(list)로 보관. 값은 파이썬 객체 그대로(None·int·bool·float 형 보존)."""

    def __init__(self, keys):
        self._keys = tuple(keys)
        self._c = {k: [] for k in self._keys}
        self._n = 0

    def extend_records(self, recs):
        for r in recs:
            if tuple(r.keys()) != self._keys:
                raise Exp01Invalid("EXP01_PAR_RECORD_KEYS_MISMATCH")
            for k in self._keys:
                self._c[k].append(r[k])
        self._n += len(recs)

    def column(self, k):
        return self._c[k]

    def keys(self):
        return self._keys

    def __len__(self):
        return self._n

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [Row(self._c, j) for j in range(*i.indices(self._n))]
        if i < 0:
            i += self._n
        if not 0 <= i < self._n:
            raise IndexError(i)
        return Row(self._c, i)

    def __iter__(self):
        c = self._c
        for i in range(self._n):
            yield Row(c, i)


# ------------------------------------------------------------------ 계획 수(사례당 기록 수)
def expected_plans(budgets, taus, seeds, has_wd, has_tree, has_a, noise) -> int:
    """run_exp01.evaluate 의 계획 목록 길이(사례당 기록 수)를 닫힌 식으로 계산 — 병합 검증용."""
    n = 0
    for q in budgets:
        n += 3 + len(taus)
        if has_wd:
            n += len(taus) * (3 + len(seeds))          # WD_CORRECT·WD_MODEL·WD_MODEL_WRONG(seed 1개) + RANDOM(seed 별)
        n += int(has_tree) + int(has_a)
        if noise and q == noise["budget"]:
            n += len(noise["models"]) * len(noise["modes"])
    return n


# ------------------------------------------------------------------ 동일성 검증용 추적(실행 기본값 꺼짐)
def install_trace():
    """run_exp01.run_case 를 추적 래퍼로 바꾼다(검증 전용). 단계별 점수·질문·답·활성 집합·최종 통계를 TRACE_BUFFER 에."""
    global TRACE_BUFFER
    import numpy as np

    import run_exp01
    from searchers import GraphSearcher
    TRACE_BUFFER = []
    orig = run_exp01.__dict__.setdefault("_orig_run_case", run_exp01.run_case)

    def traced(searcher, sem, initial, age, sex, tokens, budget, wd=None, on_step=None, sim=None):
        steps = []

        def hook(s, k):
            if on_step:
                on_step(s, k)
            act = sorted(s.active()) if isinstance(s, GraphSearcher) else None
            steps.append((k, np.asarray(s.scores(), dtype=np.float64).tolist(), act))
        tr, s = orig(searcher, sem, initial, age, sex, tokens, budget, wd, on_step=hook, sim=sim)
        st = s.stats()
        TRACE_BUFFER.append({
            "asked": list(tr.asked), "answers": [(q, tuple(a)) for q, a in tr.answers.items()],
            "stop": tr.stop_reason, "steps": steps, "posterior": np.asarray(s.posterior()).tolist(),
            "used": sorted(map(repr, st["used"])), "reactivations": st.get("reactivations"),
            "prune_steps": st.get("prune_steps"), "counter": st.get("counter")})
        return tr, s
    run_exp01.run_case = traced


def uninstall_trace():
    global TRACE_BUFFER
    import run_exp01
    if "_orig_run_case" in run_exp01.__dict__:
        run_exp01.run_case = run_exp01.__dict__.pop("_orig_run_case")
    TRACE_BUFFER = None


# ------------------------------------------------------------------ 작업자
def _init_worker(threads):
    try:
        from threadpoolctl import threadpool_limits
        _CTX["_tp"] = threadpool_limits(threads)        # 작업자당 BLAS 스레드 제한(과다 구독 방지)
    except ImportError:
        _CTX["_tp"] = None                              # 없으면 info 에 기록(실행 환경 변수로 제한해야 함)


def _has_threadpoolctl():
    try:
        import threadpoolctl  # noqa: F401
        return True
    except ImportError:
        return False


def _run_chunk(task):
    import run_exp01
    cid, lo, hi = task
    ctx = _CTX
    counters = {"aref_steps": 0, "reference_steps": 0}
    aref = ctx["kw"].get("aref")
    if aref is not None:
        aref.max_abs_diff = 0.0                       # 구간마다 0 에서 시작(부모가 최대를 모음)
    if TRACE_BUFFER is not None:
        TRACE_BUFFER.clear()
    chunk = ctx["cases"][lo:hi]
    t0 = time.perf_counter()
    recs = run_exp01.evaluate(chunk, counters=counters, **ctx["kw"])
    return {"cid": cid, "row_ids": [c["row_index"] for c in chunk], "recs": recs, "counters": counters,
            "aref_max": None if aref is None else aref.max_abs_diff, "pid": os.getpid(),
            "sec": time.perf_counter() - t0,
            "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "trace": None if TRACE_BUFFER is None else list(TRACE_BUFFER)}


def _check_chunk(res, cases, lo, hi, per_case):
    ids = [c["row_index"] for c in cases[lo:hi]]
    if res["row_ids"] != ids:
        raise Exp01Invalid(f"EXP01_PAR_CHUNK_CASES_MISMATCH:{res['cid']}")
    recs = res["recs"]
    if len(recs) != per_case * len(ids):
        raise Exp01Invalid(f"EXP01_PAR_RECORD_COUNT:{res['cid']}:{len(recs)}!={per_case}x{len(ids)}")
    for j, rid in enumerate(ids):                      # 사례별 기록이 연속·정확히 per_case 개
        blk = recs[j * per_case:(j + 1) * per_case]
        if any(r["row_index"] != rid for r in blk):
            raise Exp01Invalid(f"EXP01_PAR_RECORD_ORDER:{res['cid']}:{rid}")


def evaluate_parallel(cases, workers: int, chunk_cases: int, *, budgets, taus, seeds, tree=None, a_factory=None,
                      wd_rank=None, leak_check=True, aref=None, noise=None, sem=None, lik=None, classes=None,
                      progress=None, threads=1, chunk_timeout=3600):
    """run_exp01.evaluate 와 같은 인자. 반환: (RecordTable, counters, aref_max_abs_diff, info)."""
    if workers < 1 or chunk_cases < 1:
        raise ValueError("EXP01_PAR_BAD_ARGS")
    ids = [c["row_index"] for c in cases]
    if len(set(ids)) != len(ids):
        raise Exp01Invalid("EXP01_PAR_DUPLICATE_CASE")
    if ids != sorted(ids):
        raise Exp01Invalid("EXP01_PAR_CASES_NOT_SORTED_BY_ID")
    per_case = expected_plans(budgets, taus, seeds, wd_rank is not None, tree is not None, a_factory is not None, noise)
    bounds = [(i, lo, min(lo + chunk_cases, len(cases))) for i, lo in enumerate(range(0, len(cases), chunk_cases))]
    _CTX.clear()
    _CTX["cases"] = cases
    _CTX["kw"] = dict(sem=sem, lik=lik, classes=classes, budgets=budgets, taus=taus, seeds=tuple(seeds), tree=tree,
                      a_factory=a_factory, wd_rank=wd_rank, leak_check=leak_check, aref=aref, noise=noise)
    gc.collect()
    gc.freeze()                                         # fork 뒤 gc 가 공유 페이지를 건드려 복사되는 것 방지
    table, counters, aref_max, traces = None, {"aref_steps": 0, "reference_steps": 0}, 0.0, []
    wstats: dict = {}
    t0 = time.time()
    done_cases = 0
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork"),
                                 initializer=_init_worker, initargs=(threads,)) as ex:
            window = max(2 * workers, 2)                # 진행 중 구간 수 상한(결과 대기열 메모리 제한)
            pending = {}
            nxt = 0
            for cid, lo, hi in bounds:
                while nxt < len(bounds) and len(pending) < window:
                    pending[nxt] = ex.submit(_run_chunk, bounds[nxt])
                    nxt += 1
                try:
                    res = pending.pop(cid).result(timeout=chunk_timeout)   # 작업자 예외·비정상 종료 그대로 전파
                except BaseException:
                    ex.shutdown(wait=False, cancel_futures=True)
                    for p in list((getattr(ex, "_processes", None) or {}).values()):   # 멈춘 작업자 정리(시간 초과 등)
                        p.terminate()
                    raise
                if res["cid"] != cid:
                    raise Exp01Invalid("EXP01_PAR_CHUNK_ID")
                _check_chunk(res, cases, lo, hi, per_case)
                if table is None:
                    table = RecordTable(res["recs"][0].keys() if res["recs"] else ())
                table.extend_records(res["recs"])
                for k in counters:
                    counters[k] += res["counters"][k]
                if res["aref_max"] is not None:
                    aref_max = max(aref_max, res["aref_max"])
                if res["trace"] is not None:
                    traces.extend(res["trace"])
                w = wstats.setdefault(res["pid"], {"chunks": 0, "cases": 0, "sec": 0.0, "peak_rss_mb": 0.0})
                w["chunks"] += 1
                w["cases"] += hi - lo
                w["sec"] += res["sec"]
                w["peak_rss_mb"] = max(w["peak_rss_mb"], res["rss_mb"])
                done_cases += hi - lo
                del res
                if progress is not None:
                    el = time.time() - t0
                    progress(f"PROGRESS chunks={cid + 1}/{len(bounds)} cases={done_cases}/{len(cases)} "
                             f"elapsed_s={el:.0f} eta_s={el / done_cases * (len(cases) - done_cases):.0f}")
    finally:
        gc.unfreeze()
        _CTX.clear()
    if table is None:
        table = RecordTable(())
    merged = table.column("row_index")[::per_case] if len(table) else []
    if list(merged) != ids or len(table) != per_case * len(ids):        # 최종 사례 ID 목록·건수 대조
        raise Exp01Invalid("EXP01_PAR_MERGE_MISMATCH")
    if aref is not None:
        aref.max_abs_diff = max(aref.max_abs_diff, aref_max)
    info = {"workers": workers, "chunk_cases": chunk_cases, "n_chunks": len(bounds), "start_method": "fork",
            "blas_threads_per_worker": threads, "threadpoolctl_available": _has_threadpoolctl(),
            "env_threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            "records_per_case": per_case, "wall_s": round(time.time() - t0, 2),
            "worker_stats": sorted(wstats.values(), key=lambda w: -w["cases"]),
            "children_peak_rss_mb": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024}
    if TRACE_BUFFER is not None:
        info["traces"] = traces
    return table, counters, aref_max, info


def log(msg):
    print(msg, file=sys.stderr, flush=True)
