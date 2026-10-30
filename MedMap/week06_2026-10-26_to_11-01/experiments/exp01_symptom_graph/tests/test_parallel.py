"""병렬 실행(2026-10-28) — 직렬(run_exp01.evaluate)과 작업자 1·2·4 의 결과 동일성, 병합 검증, 메모리 구조. 가상 세계만."""
import json
import math
import os
import sys
import tempfile
import unittest
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

import artifacts  # noqa: E402
import confirm  # noqa: E402
import metrics as mt  # noqa: E402
import parallel  # noqa: E402
import par_world  # noqa: E402
import run_exp01  # noqa: E402
from core import Exp01Invalid  # noqa: E402

META_KEYS = ("ms",)                    # 본질적으로 달라지는 값(실행시간) — 따로 비교


def serial(cases, kw, counters=None):
    k = dict(kw)
    return run_exp01.evaluate(cases, k.pop("sem"), k.pop("lik"), k.pop("classes"), k.pop("budgets"), k.pop("taus"),
                              k.pop("seeds"), counters=counters, **k)


def par(cases, kw, workers, chunk=3):
    return parallel.evaluate_parallel(cases, workers, chunk, **kw)


def strip(r):
    d = dict(r) if isinstance(r, dict) else r.to_dict()
    return {k: v for k, v in d.items() if k not in META_KEYS}


def same_value(a, b):
    """비트 동일(형 포함). NaN 은 NaN 끼리 같다고 본다."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float) and math.isnan(a):
        return math.isnan(b)
    return a == b


# 실패를 주입하는 구간 함수(fork 로 작업자에 전달)
def _drop_last_record(task):
    res = _ORIG_RUN_CHUNK(task)
    res["recs"] = res["recs"][:-1]
    return res


def _wrong_ids(task):
    res = _ORIG_RUN_CHUNK(task)
    res["row_ids"] = list(reversed(res["row_ids"]))
    return res


def _swap_records(task):
    res = _ORIG_RUN_CHUNK(task)
    n = len(res["recs"])
    if n >= 2 and res["row_ids"][0] != res["row_ids"][-1]:
        res["recs"] = res["recs"][n // 2:] + res["recs"][:n // 2]
    return res


def _swap_within_cases(task):
    """두 사례의 둘째 기록을 맞바꿈 — 사례 첫 기록 간격(최종 ID 대조)과 건수는 그대로, 사례 블록 검사만 걸림."""
    res = _ORIG_RUN_CHUNK(task)
    per = len(res["recs"]) // len(res["row_ids"])
    if len(res["row_ids"]) >= 2:
        r = res["recs"]
        r[1], r[per + 1] = r[per + 1], r[1]
    return res


def _compensate_counts(task):
    """구간 0 은 마지막 기록 하나 빠짐, 구간 1 은 마지막 기록 중복 — 전체 건수·첫 기록 간격은 맞음, 구간 건수 검사만 걸림."""
    res = _ORIG_RUN_CHUNK(task)
    if task[0] == 0:
        res["recs"] = res["recs"][:-1]
    elif task[0] == 1:
        res["recs"] = res["recs"] + [dict(res["recs"][-1])]
    return res


def _aref_by_chunk(task):
    res = _ORIG_RUN_CHUNK(task)
    res["aref_max"] = [0.0, 3e-12, 1e-12, 0.0][task[0] % 4]
    return res


def _die(task):
    if task[0] == 1:
        os._exit(3)
    return _ORIG_RUN_CHUNK(task)


_ORIG_RUN_CHUNK = parallel._run_chunk


class TestParallelIdentityToy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.kw, cls.severe, cls.prior = par_world.toy_world(n=40)
        parallel.install_trace()
        cls.cnt = {"aref_steps": 0, "reference_steps": 0}
        cls.ser = serial(cls.cases, cls.kw, cls.cnt)
        cls.ser_trace = list(parallel.TRACE_BUFFER)
        cls.par = {}
        for w in (1, 2, 4):
            parallel.TRACE_BUFFER.clear()
            cls.par[w] = par(cls.cases, cls.kw, w)
        parallel.uninstall_trace()

    def test_records_identical_all_workers(self):
        for w, (tab, cnt, _, info) in self.par.items():
            self.assertEqual(len(tab), len(self.ser))
            self.assertEqual(tab.keys(), tuple(self.ser[0].keys()))
            for a, b in zip(self.ser, tab):
                sa, sb = strip(a), strip(b)
                bad = [k for k in sa if not same_value(sa[k], sb[k])]
                self.assertEqual(bad, [], f"workers={w} row={a['row_index']} model={a['model']}")
            self.assertEqual(cnt, self.cnt)
            self.assertEqual(info["workers"], w)

    def test_traces_identical(self):
        """질문 순서·답·단계별 질환 점수·활성 집합(우선순위 하향·재활성)·최종 사후확률·사용 근거 집합."""
        for w, (_, _, _, info) in self.par.items():
            self.assertEqual(len(info["traces"]), len(self.ser_trace))
            self.assertEqual(json.dumps(info["traces"]), json.dumps(self.ser_trace), f"workers={w}")
        self.assertTrue(any(t["reactivations"] for t in self.ser_trace))     # 재활성 경로가 실제로 지나감
        self.assertTrue(any(t["prune_steps"] for t in self.ser_trace))
        self.assertTrue(any(a == ("NEG",) for t in self.ser_trace for _, a in t["answers"]))

    def test_case_ids_and_counts(self):
        ids = [c["row_index"] for c in self.cases]
        for w, (tab, _, _, info) in self.par.items():
            per = info["records_per_case"]
            self.assertEqual(per * len(ids), len(tab))
            self.assertEqual(tab.column("row_index")[::per], ids)

    def _write(self, recs, d):
        tau_sel = mt.select_tau(artifacts.tau_stats(recs, self.severe, self.kw["taus"]), self.kw["taus"])
        artifacts.write_all(Path(d), recs, self.severe, self.kw["taus"], self.prior, self.kw["classes"],
                            self.kw["lik"], {"x": 1}, {"m": 1}, tau_selection=tau_sel)
        return tau_sel

    def test_artifacts_identical(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as d0:
            t0 = self._write(self.ser, d0)
            for w, (tab, _, _, _) in self.par.items():
                with tempfile.TemporaryDirectory() as d1:
                    t1 = self._write(tab, d1)
                    self.assertEqual(t0, t1)
                    a = pd.read_parquet(Path(d0, "per_case.parquet")).drop(columns=["ms"])
                    b = pd.read_parquet(Path(d1, "per_case.parquet")).drop(columns=["ms"])
                    pd.testing.assert_frame_equal(a, b, check_exact=True)
                    self.assertEqual(list(a.dtypes), list(b.dtypes))
                    for f in ("subgroups.csv", "graph_stats.json", "tau_selection.json", "split_manifest.json"):
                        self.assertEqual(Path(d0, f).read_bytes(), Path(d1, f).read_bytes(), f)
                    ma = pd.read_csv(Path(d0, "metrics.csv")).drop(columns=["ms_p50", "ms_p95"])
                    mb = pd.read_csv(Path(d1, "metrics.csv")).drop(columns=["ms_p50", "ms_p95"])
                    pd.testing.assert_frame_equal(ma, mb, check_exact=True)

    def test_confirmatory_analysis_identical(self):
        for tau in (0.01, 0.001):
            ref = confirm.final_analysis(self.ser, self.severe, tau, par_world.SEEDS, B=300)
            for w, (tab, _, _, _) in self.par.items():
                got = confirm.final_analysis(tab, self.severe, tau, par_world.SEEDS, B=300)
                self.assertEqual(json.dumps(ref, sort_keys=True, default=str),
                                 json.dumps(got, sort_keys=True, default=str), f"workers={w} tau={tau}")

    def test_severe_miss_counts_identical(self):
        def miss(recs):
            out = {}
            for r in recs:
                if r["truth"] in self.severe and not r["in8"]:
                    k = (r["model"], r["budget"], r["wd_mode"], r["seed"], r["tau"], r["noise"])
                    out[k] = out.get(k, 0) + 1
            return out
        ref = miss(self.ser)
        self.assertGreater(sum(ref.values()), 0)
        for w, (tab, _, _, _) in self.par.items():
            self.assertEqual(miss(tab), ref)


@unittest.skipUnless(Path(par_world.S16B, "model_k3.pkl").exists(), "STEP16B 모델 없음")
class TestParallelIdentityDDX(unittest.TestCase):
    """Baseline A(제품 엔진)·aref 매 단계 대조·B·WD·누출·잡음이 모두 지나가는 가상 환자 세계(작게)."""
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.kw, cls.severe, _ = par_world.ddx_world(n=4, n_tree=600)
        cls.cnt = {"aref_steps": 0, "reference_steps": 0}
        cls.kw["aref"].max_abs_diff = 0.0
        cls.ser = serial(cls.cases, cls.kw, cls.cnt)
        cls.ser_amax = cls.kw["aref"].max_abs_diff
        cls.par = par(cls.cases, cls.kw, 2, chunk=1)

    def test_identical_with_baseline_a_path(self):
        tab, cnt, amax, _ = self.par
        self.assertEqual(len(tab), len(self.ser))
        for a, b in zip(self.ser, tab):
            sa, sb = strip(a), strip(b)
            self.assertEqual([k for k in sa if not same_value(sa[k], sb[k])], [])
        self.assertEqual(cnt, self.cnt)
        self.assertGreater(cnt["aref_steps"], 0)
        self.assertEqual(amax, self.ser_amax)
        self.assertEqual({r["model"] for r in tab}, {"A", "B", "C", "PA", "PB_REL", "PB", "PC"})
        self.assertTrue(any(r["leak"] == "PASS" and r["model"] == "A" for r in tab))


class TestMergeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.kw, _, _ = par_world.toy_world(n=8, with_tree=False)

    def tearDown(self):
        parallel._run_chunk = _ORIG_RUN_CHUNK

    def test_duplicate_case_rejected(self):
        with self.assertRaises(Exp01Invalid):
            par(self.cases + [self.cases[-1]], self.kw, 2)

    def test_unsorted_cases_rejected(self):
        with self.assertRaises(Exp01Invalid):
            par(list(reversed(self.cases)), self.kw, 2)

    def test_missing_record_rejected(self):
        parallel._run_chunk = _drop_last_record
        with self.assertRaises(Exp01Invalid):
            par(self.cases, self.kw, 2)

    def test_wrong_chunk_ids_rejected(self):
        parallel._run_chunk = _wrong_ids
        with self.assertRaises(Exp01Invalid):
            par(self.cases, self.kw, 2)

    def test_record_order_rejected(self):
        parallel._run_chunk = _swap_records
        with self.assertRaises(Exp01Invalid):
            par(self.cases, self.kw, 2)

    def test_within_case_order_rejected(self):
        parallel._run_chunk = _swap_within_cases
        with self.assertRaises(Exp01Invalid):
            par(self.cases, self.kw, 2)

    def test_compensating_counts_rejected(self):
        parallel._run_chunk = _compensate_counts
        with self.assertRaises(Exp01Invalid):
            par(self.cases, self.kw, 1)

    def test_aref_max_is_max_over_chunks(self):
        parallel._run_chunk = _aref_by_chunk
        _, _, amax, _ = parallel.evaluate_parallel(self.cases, 2, 2, **self.kw)
        self.assertEqual(amax, 3e-12)

    def test_killed_worker_raises(self):
        parallel._run_chunk = _die
        with self.assertRaises(BrokenProcessPool):
            par(self.cases, self.kw, 2)

    def test_worker_exception_propagates(self):
        bad = [dict(c) for c in self.cases]
        bad[5]["initial"] = "E_999999"                 # 존재하지 않는 근거 → 작업자 예외
        with self.assertRaises(Exception):
            par(bad, self.kw, 2)

    def test_expected_plans_matches_evaluate(self):
        for tree, noise, wd in ((None, None, None), (None, par_world.NOISE, self.kw["wd_rank"])):
            kw = dict(self.kw, tree=tree, noise=noise, wd_rank=wd)
            n = len(serial(self.cases[:2], kw))
            self.assertEqual(n, 2 * parallel.expected_plans(kw["budgets"], kw["taus"], kw["seeds"], wd is not None,
                                                            False, False, noise))

    def test_trace_uninstall_restores(self):
        orig = run_exp01.run_case
        parallel.install_trace()
        self.assertIsNot(run_exp01.run_case, orig)
        parallel.uninstall_trace()
        self.assertIs(run_exp01.run_case, orig)
        self.assertIsNone(parallel.TRACE_BUFFER)


class TestRecordTableAndConfig(unittest.TestCase):
    def test_record_table_view(self):
        recs = [{"a": 1, "b": None, "c": 0.5}, {"a": 2, "b": "x", "c": float("nan")}]
        t = parallel.RecordTable(recs[0].keys())
        t.extend_records(recs)
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0]["a"], 1)
        self.assertIsNone(t[0]["b"])
        self.assertIsNone(t[0].get("zz"))
        self.assertEqual(t[0].get("zz", 7), 7)
        self.assertEqual(t[-1].get("b"), "x")
        self.assertEqual([r["a"] for r in t[0:2]], [1, 2])
        self.assertEqual(t[1].to_dict()["a"], 2)
        with self.assertRaises(IndexError):
            t[2]
        with self.assertRaises(Exp01Invalid):
            t.extend_records([{"a": 1, "c": 0.1, "b": None}])          # 키 순서 다름

    def test_parallel_config_validation(self):
        ok = {"workers": 4, "chunk_cases": 50}
        run_exp01.check_parallel(None)
        run_exp01.check_parallel(ok)
        for bad in ({"workers": 0, "chunk_cases": 5}, {"workers": 13, "chunk_cases": 5}, {"workers": 2},
                    {"workers": 2, "chunk_cases": 0}, {"workers": 2.0, "chunk_cases": 5},
                    {"workers": 2, "chunk_cases": 5, "seed": 1}, [2, 5]):
            with self.assertRaises(SystemExit):
                run_exp01.check_parallel(bad)

    def test_load_config_parallel_and_final_carry(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = dict(run_exp01.DEFAULT_CONFIG, split="SELECT", parallel={"workers": 4, "chunk_cases": 50})
            p = Path(d, "c.json")
            p.write_text(json.dumps(cfg))
            self.assertEqual(run_exp01.load_config(p)["parallel"]["workers"], 4)
            run = Path(d, "sel")
            run.mkdir()
            (run / "tau_selection.json").write_text(json.dumps({"tau": 0.001, "source_split": "SELECT"}))
            (run / "run_meta.json").write_text(json.dumps({"config": cfg}))
            fc = run_exp01.make_final_config(run, Path(d, "f.json"))
            self.assertEqual(fc["parallel"], cfg["parallel"])
            self.assertEqual(fc["tau_selected"], 0.001)
            run_exp01.load_config(Path(d, "f.json"))
            cfg["parallel"] = {"workers": 4}
            p.write_text(json.dumps(cfg))
            with self.assertRaises(SystemExit):
                run_exp01.load_config(p)

    def test_per_case_frame_same_as_dict_path(self):
        import pandas as pd
        cases, kw, _, _ = par_world.toy_world(n=6, with_tree=False)
        recs = serial(cases, kw)
        t = parallel.RecordTable(recs[0].keys())
        t.extend_records(recs)
        a, b = artifacts.per_case_frame(recs), artifacts.per_case_frame(t)
        pd.testing.assert_frame_equal(a, b, check_exact=True)
        self.assertTrue(np.all(a.columns == list(artifacts.PER_CASE_COLS)))
        with tempfile.TemporaryDirectory() as d:                   # 행 묶음 쓰기 = 한 번에 쓰기(읽은 값·형)
            artifacts.write_per_case(recs, Path(d, "one.parquet"))
            artifacts.write_per_case(t, Path(d, "grp.parquet"), rows_per_group=37)
            x, y = pd.read_parquet(Path(d, "one.parquet")), pd.read_parquet(Path(d, "grp.parquet"))
            pd.testing.assert_frame_equal(x, y, check_exact=True)
            self.assertEqual(list(x.dtypes), list(y.dtypes))
            import pyarrow.parquet as pq
            self.assertGreater(pq.ParquetFile(Path(d, "grp.parquet")).num_row_groups, 1)


if __name__ == "__main__":
    unittest.main()
